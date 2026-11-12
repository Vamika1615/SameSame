"""Import a supplier's rate sheet (CSV / XLSX, any of the layouts in ingest/layouts.py) and resolve it to the catalogue.

  sheet -> hotels, rooms, rates and conditions (layouts.parse)
        -> each hotel: the SAME hotel already in the catalogue, a hotel added by an earlier import, "new", or a person decides
             with coordinates:    Twin Finder's trained LightGBM model, features and thresholds, short codes written out
             without coordinates: names only (real grid sheets rarely give a location). Auto-matched only when the name is
                                  identical to exactly one catalogue hotel; anything else that looks close goes to a person.
        -> each room: the catalogue's room (by code, name, or tier + bed + view with the hotel's own name removed),
                      a new room of the hotel, or a person decides.

Reads only the uploaded sheet and the catalogue. Never the generator's truth: the answer key is used only by
eval/sheet_check.py, and only when the uploaded file is Weaver's sample sheet byte for byte.
"""
import csv
import hashlib
import io
import json
import re
import threading
from functools import lru_cache

import numpy as np
from rapidfuzz import fuzz

from samesame import config, store
from samesame.ingest import layouts
from samesame.ingest.layouts import SheetError  # noqa: F401  (re-exported for callers)
from samesame.matching import hotels as hm
from samesame.matching import rooms as rm
from samesame.ranking.score import haversine_m

MAX_ROWS = 5000
SUPPLIER = "sheet"
NAME_REVIEW = 0.85            # names this alike (once short codes are written out) go to a person when there's no location
NEAR_IMPORTED_M = 150         # an earlier import's hotel this close, with a similar name, is the same hotel
COLUMNS = {   # what we look for -> header spellings seen in supplier sheets (compared lower-case, units in brackets dropped)
    "name": ["hotel", "hotel name", "property", "property name", "name", "hotelname", "accommodation"],
    "address": ["address", "addr", "street address", "location"],
    "lat": ["lat", "latitude"],
    "lng": ["lng", "lon", "long", "longitude"],
    "phone": ["phone", "tel", "telephone", "contact", "phone number"],
    "star": ["star", "stars", "star rating", "rating", "category", "class"],
    "room": ["room", "room type", "room name", "roomtype", "room category", "room description"],
    "meal": ["meal", "meal plan", "board", "board basis", "boarding"],
    "price": ["price", "rate", "net", "net rate", "amount", "cost", "net price", "nightly"],
    "cancel": ["cancellation", "cancel", "cancellation policy", "refundable", "policy"],
    "code": ["room code", "code", "opera code"],
}
REQUIRED = ("name", "room")


# ------------------------------------------------------------------ the flat layout (one row per rate)
def _header_key(h: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\(.*?\)|[_\-./]", " ", str(h or ""))).strip().lower()


def map_columns(headers: list[str]) -> tuple[dict[str, int], list[str]]:
    """field -> column index, and the headers we didn't use."""
    keys = [_header_key(h) for h in headers]
    found: dict[str, int] = {}
    for field, names in COLUMNS.items():
        for i, k in enumerate(keys):
            if i not in found.values() and (k in names or any(k.startswith(n + " ") for n in names)):
                found[field] = i
                break
    unused = [headers[i] for i in range(len(headers)) if i not in found.values() and str(headers[i] or "").strip()]
    return found, unused


def read_table(data: bytes, filename: str) -> list[list[str]]:
    """The first tab, as rows of text (kept for callers of the flat reader)."""
    rows = layouts.read_tables(data, filename)[0][1]
    return [r for r in rows if any(str(c).strip() for c in r)]


_num = layouts.num


def parse_rows(data: bytes, filename: str) -> tuple[list[dict], dict]:
    table = read_table(data, filename)
    hi = next((i for i, r in enumerate(table[:12]) if {"name", "room"} <= set(map_columns(r)[0])), 0)
    headers, body = table[hi], table[hi + 1:hi + 1 + MAX_ROWS]
    cols, unused = map_columns(headers)
    missing = [f for f in REQUIRED if f not in cols]
    if missing:
        raise SheetError(f"Couldn't find a column for {' and '.join(missing)}. Headers seen: {', '.join(map(str, headers))}.")
    get = lambda r, f: (r[cols[f]].strip() if f in cols and cols[f] < len(r) and r[cols[f]] is not None else "")  # noqa: E731
    rows = []
    for i, r in enumerate(body, start=hi + 1):
        name = get(r, "name")
        if not name:
            continue
        lat, lng = _num(get(r, "lat")), _num(get(r, "lng"))
        rows.append({"row": i, "name": name, "address": get(r, "address") or None, "phone": get(r, "phone") or None,
                     "lat": lat if lat is not None and -90 <= lat <= 90 else None, "lng": lng if lng is not None and -180 <= lng <= 180 else None,
                     "star": _num(get(r, "star")), "room": get(r, "room"), "code": get(r, "code") or None, "meal": get(r, "meal") or None,
                     "price": _num(get(r, "price")), "cancel": get(r, "cancel") or None})
    info = {"columns": {f: headers[i] for f, i in cols.items()}, "unused_columns": unused, "rows": len(rows),
            "truncated": len(table) - 1 - hi > MAX_ROWS}
    return rows, info


# ------------------------------------------------------------------ catalogue context (cached)
@lru_cache
def _model():
    import lightgbm as lgb
    info = json.loads((config.BUILD / "matcher.json").read_text(encoding="utf-8"))
    return lgb.Booster(model_file=str(config.BUILD / "hotel_matcher.txt")), info["auto_merge"], info["gray_low"]


@lru_cache
def _encoder():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(config.EMBED_MODEL, cache_folder=str(config.MODELS), device="cpu")
    except Exception as e:                                   # same fallback as the pipeline: the feature is left missing
        print("sheets: embeddings unavailable:", type(e).__name__, e)
        return None


def _embed(texts: list[str]):
    enc = _encoder()
    return None if enc is None else enc.encode(texts, normalize_embeddings=True, batch_size=128, show_progress_bar=False)


@lru_cache
def _catalogue():
    s = store.get()
    P = hm.prep(list(s.listings.values()))
    chain = {p["_phone"] for p in P if p["_chain_phone"]}
    emb = _embed([p["_n"] for p in P])
    lat = np.array([p["lat"] for p in P]); lng = np.array([p["lng"] for p in P])
    return P, chain, emb, lat, lng


def warm():
    """Load the model, encoder and catalogue embeddings in the background so the first upload is quick."""
    if store.ready():
        threading.Thread(target=lambda: (_model(), _catalogue()), daemon=True).start()


def _cluster_name(cid: str) -> str:
    from samesame import service
    return service.golden(cid)["name"]


def name_score(a: str, b: str) -> float:
    """How alike two hotel names are, 0-1. token_set alone calls 'Riviera Hotel' 100% like 'Hard Rock Hotel Riviera Maya'
    (one name's words are a subset of the other's); averaging with token_sort charges for the words that don't match."""
    return (fuzz.token_set_ratio(a, b) + fuzz.token_sort_ratio(a, b)) / 200


def name_key(name: str) -> str:
    """The distinctive words of a hotel name, order-free: 'The AVA Resort, Cancún' -> 'ava cancun resort'."""
    return " ".join(sorted(hm.core(hm.norm(name))))


# ------------------------------------------------------------------ hotels as the sheet writes them
def _flat_listings(rows: list[dict], currency: str | None) -> list[dict]:
    """One listing per hotel as a flat sheet writes it (same name and roughly the same place)."""
    groups: dict = {}
    for r in rows:
        k = (hm.norm(r["name"]), round(r["lat"], 3) if r["lat"] is not None else None, round(r["lng"], 3) if r["lng"] is not None else None)
        groups.setdefault(k, []).append(r)
    out = []
    for i, rs in enumerate(groups.values()):
        first = rs[0]
        stars = [r["star"] for r in rs if r["star"]]
        rooms: dict = {}
        for r in rs:
            room = rooms.setdefault(r["room"], {"name": r["room"], "code": r["code"], "rows": [], "prices": []})
            room["rows"].append(r["row"])
            if r["price"] is not None:
                room["prices"].append({"meal": r["meal"], "price": r["price"], "cancel": r["cancel"]})
        out.append({"listing_id": f"sheet:{i + 1}", "supplier_id": SUPPLIER, "name": first["name"], "address": first["address"],
                    "phone": next((r["phone"] for r in rs if r["phone"]), None), "lat": first["lat"], "lng": first["lng"],
                    "star": stars[0] if stars else None, "amenities": [], "postcode": None, "checkin_time": None,
                    "rows": [r["row"] for r in rs], "rooms": list(rooms.values()), "conditions": [], "tabs": [], "name_from_file": False,
                    "rates": [{"room": r["room"], "code": r["code"], "plan": r["meal"] or "Rate", "season_from": None, "season_to": None,
                               "season": None, "days": None, "occupancy": None, "price": r["price"], "currency": currency,
                               "meal": r["meal"], "cancel": r["cancel"], "row": r["row"]} for r in rs if r["price"] is not None]})
    return out


def _grid_listings(parsed: dict) -> list[dict]:
    return [{"listing_id": f"sheet:{i + 1}", "supplier_id": SUPPLIER, "name": h["name"], "address": h["address"], "phone": h["phone"],
             "lat": h["lat"], "lng": h["lng"], "star": h["star"], "amenities": [], "postcode": None, "checkin_time": None,
             "rows": [], "rooms": [{**r, "prices": []} for r in h["rooms"]], "rates": h["rates"], "conditions": h["conditions"],
             "tabs": h["tabs"], "name_from_file": h["name_from_file"]} for i, h in enumerate(parsed["hotels"])]


# ------------------------------------------------------------------ resolving hotels
def _reasons(f: dict, code: str | None, d: float | None) -> list[str]:
    out = []
    if code:
        c, words = code.split(" = ")
        out.append(f"{c} read as {words}")
    if d is not None:
        out.append(f"{d:,.0f} m apart")
    out.append({1: "same phone", -1: "different phone", 0: "phone not comparable"}[int(f["phone_match"])])
    out.append(f"names {f['name_set']:.0%} alike" + (" once written out" if code else ""))
    if not np.isnan(f["star_delta"]):
        out.append("same stars" if f["star_delta"] == 0 else f"stars differ by {f['star_delta']:g}")
    if f["addr_sort"] >= 0.6:
        out.append(f"address {f['addr_sort']:.0%} alike")
    return out


def _imported_prep(imported: list[dict]) -> list[dict]:
    return hm.prep([{"listing_id": h["id"], "name": h["name"], "phone": h.get("phone"), "address": h.get("address"), "amenities": [],
                     "lat": h.get("lat") or 0.0, "lng": h.get("lng") or 0.0} for h in imported]) if imported else []


def _by_name(u: dict, P: list[dict], s, imported: list[dict], IP: list[dict]) -> dict:
    """No coordinates: compare names only, with short codes written out."""
    best: dict = {}
    key = name_key(u["name"])
    for p in P:
        # without a location, only the sheet's own short code is written out ("WF" -> White Fort). Expanding a catalogue
        # listing's code with the sheet's words would make "SP Hotel" equal any "S... P... Hotel".
        own = hm.short_code(u, p)
        fa, fb, code = hm.expand(u, p) if own else (u["_n"], p["_n"], None)
        sc = name_score(fa, fb)
        cid = s.cluster_of[p["listing_id"]]
        exact = bool(key) and key == name_key(p["name"])
        if cid not in best or (exact, sc) > (best[cid]["_exact"], best[cid]["_sc"]):
            best[cid] = {"cluster_id": cid, "kind": "inventory", "p": None, "_sc": sc, "_exact": exact,
                         "reasons": (["same name"] if exact else [f"names {sc:.0%} alike" + (" once written out" if code else "")]) + ["no location in the sheet"]}
    for h, p in zip(imported, IP):
        sc = name_score(*(hm.expand(u, p)[:2] if hm.short_code(u, p) else (u["_n"], p["_n"])))
        exact = bool(key) and key == name_key(h["name"])
        best[h["id"]] = {"cluster_id": h["id"], "kind": "imported", "p": None, "_sc": sc, "_exact": exact, "name": h["name"],
                         "reasons": (["same name"] if exact else [f"names {sc:.0%} alike"]) + [f"added from {h['source']}"]}
    ranked = sorted(best.values(), key=lambda c: (-c["_exact"], -c["_sc"]))[:3]
    exacts = [c for c in best.values() if c["_exact"]]
    for c in ranked:
        c.setdefault("name", _cluster_name(c["cluster_id"]) if c["kind"] == "inventory" else c.get("name"))
    clean = [{k: v for k, v in c.items() if not k.startswith("_")} for c in ranked]
    if len(exacts) == 1 and ranked and ranked[0]["_exact"]:
        return {"decision": "matched", "why": "Same name as exactly one hotel in the catalogue. The sheet gives no location to double-check.",
                "candidates": clean}
    if ranked and ranked[0]["_sc"] >= NAME_REVIEW:
        why = (f"{len(exacts)} catalogue hotels have this exact name" if len(exacts) > 1
               else f"Name {ranked[0]['_sc']:.0%} alike, and the sheet gives no location to confirm it")
        return {"decision": "review", "why": why, "candidates": clean}
    return {"decision": "new", "why": "No hotel in the catalogue has a name like this" + (f" (closest: {clean[0]['name']}, {ranked[0]['_sc']:.0%})" if clean else ""),
            "candidates": clean}


def _resolve(L: list[dict], imported: list[dict] | None = None) -> list[dict]:
    imported = imported or []
    booster, auto, gray = _model()
    P, chain, emb, lat, lng = _catalogue()
    s = store.get()
    IP = _imported_prep(imported)
    U = hm.prep([{k: v for k, v in l.items() if k not in ("rows", "rooms", "rates", "conditions", "tabs")}
                 | {"lat": l["lat"] or 0.0, "lng": l["lng"] or 0.0} for l in L])
    for u in U:
        u["_chain_phone"] = u["_phone"] in chain
    has_xy = [l["lat"] is not None and l["lng"] is not None for l in L]
    uemb = _embed([u["_n"] for u, ok in zip(U, has_xy) if ok]) if any(has_xy) else None
    k_xy = 0
    out = []
    for l, u, ok in zip(L, U, has_xy):
        if not ok:
            out.append(_by_name(u, P, s, imported, IP))
            continue
        ue = uemb[k_xy] if uemb is not None else None
        k_xy += 1
        d = hm.haversine_vec(l["lat"], l["lng"], lat, lng)
        best: dict = {}
        for j in np.nonzero(d <= hm.BLOCK_RADIUS_M)[0]:
            p = P[int(j)]
            if not ((u["_core"] & p["_core"]) or (u["_fam"] and u["_fam"] == p["_fam"]) or d[j] <= 100
                    or hm.short_code(u, p) or hm.short_code(p, u)):
                continue
            f = hm.pair_features(u, p, float(ue @ emb[j]) if ue is not None and emb is not None else np.nan, (np.nan, 0))
            f["checkin_eq"] = np.nan                       # sheets don't carry a check-in time: unknown, not "different"
            x = np.array([[f[c] for c in hm.FEATURES]], dtype=float)
            prob = float(booster.predict(x)[0])
            cid = s.cluster_of[p["listing_id"]]
            why_not = hm.conflict(u, p)
            if why_not:
                prob = 0.0
            if cid not in best or prob > best[cid]["p"]:
                best[cid] = {"cluster_id": cid, "kind": "inventory", "p": round(prob, 4), "listing": p["name"], "supplier": p["supplier_id"],
                             "reasons": [why_not] if why_not else _reasons(f, hm.expand(u, p)[2], float(d[j]))}
        # hotels added by earlier imports (not in the trained model's world): distance and name
        for h, p in zip(imported, IP):
            if h.get("lat") is None:
                continue
            dist = haversine_m(l["lat"], l["lng"], h["lat"], h["lng"])
            sc = fuzz.token_set_ratio(*hm.expand(u, p)[:2]) / 100
            if dist <= 500 and sc >= 0.7:
                pp = 0.999 if dist <= NEAR_IMPORTED_M and sc >= NAME_REVIEW else 0.5
                best[h["id"]] = {"cluster_id": h["id"], "kind": "imported", "p": pp, "name": h["name"],
                                 "reasons": [f"{dist:,.0f} m apart", f"names {sc:.0%} alike", f"added from {h['source']}"]}
        ranked = sorted(best.values(), key=lambda c: -c["p"])[:3]
        for c in ranked:
            c.setdefault("name", _cluster_name(c["cluster_id"]) if c["kind"] == "inventory" else c.get("name"))
        top = ranked[0] if ranked else None
        second = ranked[1]["p"] if len(ranked) > 1 else 0.0
        if top and top["p"] >= auto and second < gray:
            out.append({"decision": "matched", "why": f"p(SAME) {top['p']:.3f} ≥ the auto-merge bar {auto:.3f}", "candidates": ranked})
        elif top and top["p"] >= gray:
            why = (f"two catalogue hotels look like it (p {top['p']:.2f} and {second:.2f})" if second >= gray
                   else f"p(SAME) {top['p']:.2f} is between the review floor {gray:.2f} and the auto-merge bar {auto:.3f}")
            out.append({"decision": "review", "why": why, "candidates": ranked})
        else:
            out.append({"decision": "new", "why": "no catalogue hotel within 2 km scores above the review floor"
                        + (f" (closest: {top['name']}, p {top['p']:.2f})" if top else ""), "candidates": ranked})
    return out


# ------------------------------------------------------------------ resolving rooms
def canonical_rooms(cid: str) -> list[dict]:
    rooms = store.get().rooms_of.get(cid, {})
    rooms = rooms.values() if isinstance(rooms, dict) else rooms
    return [r for r in rooms if r["tier"] != "Unknown" and ":unmapped-" not in r["room_id"]]


def room_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def map_room(raw: str, code: str | None, target: dict | None, names: list[str], imported: dict[str, dict]) -> dict:
    """Where a sheet's room goes. target: {'kind': 'inventory'|'imported', 'cluster_id'} or None for a new hotel."""
    base = {"raw": raw, "code": code, "hotel_words": None, "parsed": None}
    if target is None:
        a = rm.parse_in_hotel(raw, names)
        base.update(hotel_words=a.get("hotel_words"), parsed=_parsed(a))
        return {**base, "status": "new", "why": "new hotel: this becomes one of its rooms", "room_id": None, "room": None, "confidence": 1.0}
    if target["kind"] == "imported":
        h = imported.get(target["cluster_id"])
        rooms = (h or {}).get("rooms", [])
        if code and (r := next((r for r in rooms if r.get("code") and r["code"].upper() == code.upper()), None)):
            return {**base, "status": "mapped", "why": f"same room code {code}", "room_id": r["id"], "room": r["name"], "confidence": 1.0}
        k = room_key(raw)
        if r := next((r for r in rooms if room_key(r["name"]) == k), None):
            return {**base, "status": "mapped", "why": "same room name", "room_id": r["id"], "room": r["name"], "confidence": 1.0}
        close = max(rooms, key=lambda r: fuzz.token_sort_ratio(room_key(r["name"]), k), default=None)
        if close and fuzz.token_sort_ratio(room_key(close["name"]), k) >= 92:
            return {**base, "status": "mapped", "why": f"name {fuzz.token_sort_ratio(room_key(close['name']), k):.0f}% alike",
                    "room_id": close["id"], "room": close["name"], "confidence": 0.9}
        return {**base, "status": "new", "why": "a room type this hotel didn't have before", "room_id": None, "room": None, "confidence": 1.0}
    a = rm.parse_in_hotel(raw, names)
    base.update(hotel_words=a.get("hotel_words"), parsed=_parsed(a))
    if a.get("note"):
        return {**base, "status": "person", "why": a["note"], "room_id": None, "room": None, "confidence": a["confidence"]}
    if a["tier"] is None or a["bed"] is None:
        return {**base, "status": "person", "why": "couldn't read a room type and bed from this name", "room_id": None, "room": None,
                "confidence": a["confidence"]}
    same = [r for r in canonical_rooms(target["cluster_id"]) if r["tier"] == a["tier"] and r["bed"] == a["bed"]]
    exact = [r for r in same if r["view"] == a["view"]]
    if exact:
        r = exact[0]
        return {**base, "status": "mapped", "why": "same room type, bed and view", "room_id": r["room_id"], "room": r["name"], "confidence": a["confidence"]}
    if a["view"] is None and len(same) == 1:
        r = same[0]
        return {**base, "status": "mapped", "why": f"view not stated; this hotel has one {a['tier']} {a['bed']}", "room_id": r["room_id"],
                "room": r["name"], "confidence": round(a["confidence"] - 0.1, 2)}
    if a["view"] is None and len(same) > 1:
        return {**base, "status": "person", "why": f"view not stated and this hotel has {len(same)} {a['tier']} {a['bed']} rooms", "room_id": None,
                "room": None, "confidence": a["confidence"]}
    return {**base, "status": "person", "why": "no room like this in our record of the hotel (new room type?)", "room_id": None, "room": None,
            "confidence": a["confidence"]}


def _parsed(a: dict) -> str | None:
    return " ".join(x for x in (a["tier"], a["bed"], a["view"] and f"{a['view']} View") if x) or None


def room_options(target: dict | None, imported: dict[str, dict]) -> list[dict]:
    if not target:
        return []
    if target["kind"] == "imported":
        return [{"room_id": r["id"], "name": r["name"]} for r in (imported.get(target["cluster_id"]) or {}).get("rooms", [])]
    return [{"room_id": c["room_id"], "name": c["name"]} for c in canonical_rooms(target["cluster_id"])]


def target_names(target: dict | None, imported: dict[str, dict]) -> list[str]:
    if not target:
        return []
    if target["kind"] == "imported":
        return [(imported.get(target["cluster_id"]) or {}).get("name", "")]
    return [x["name"] for x in store.get().listings_of.get(target["cluster_id"], [])]


# ------------------------------------------------------------------ the import
def ingest(data: bytes, filename: str, imported: list[dict] | None = None) -> dict:
    """Read, resolve and summarise a sheet. imported: hotels earlier imports added to the catalogue
    ([{id, name, lat, lng, phone, address, source, rooms: [{id, name, code}]}])."""
    imported = imported or []
    imp_by_id = {h["id"]: h for h in imported}
    parsed = layouts.parse(data, filename)
    if parsed["layout"] == "flat":
        rows, info = parse_rows(data, filename)
        L = _flat_listings(rows, parsed["currency"])
    else:
        L = _grid_listings(parsed)
        info = {"columns": {}, "unused_columns": [], "rows": sum(len(l["rates"]) for l in L), "truncated": False}
    res = _resolve(L, imported)
    hotels = []
    for l, r in zip(L, res):
        top = r["candidates"][0] if r["candidates"] else None
        target = {"kind": top["kind"], "cluster_id": top["cluster_id"]} if top and r["decision"] != "new" else None
        names = [l["name"]] + target_names(target, imp_by_id)
        by_room: dict = {}
        for x in l["rates"]:
            by_room.setdefault(room_key(x["room"]), []).append(x["price"])
        rooms = []
        for room in l["rooms"]:
            m = map_room(room["name"], room.get("code"), target, names, imp_by_id)
            if r["decision"] == "review" and m["status"] == "mapped":   # a suggestion only, until a person confirms the hotel
                m.update(status="person", why=f"waiting for the hotel decision (would be {m['room']})", room_id=None, room=None)
            prices = by_room.get(room_key(room["name"]), [])
            rooms.append({**m, "rows": room.get("rows", []), "prices": room.get("prices", [])[:4], "extras": room.get("extras", {}),
                          "rate_count": len(prices), "price_from": min(prices) if prices else None})
        if l["name_from_file"] and r["decision"] == "matched":
            r = {**r, "decision": "review", "why": "The sheet doesn't name the hotel (taken from the file name), so a person confirms it."}
        hotels.append({"sheet_id": l["listing_id"], "name": l["name"], "name_from_file": l["name_from_file"], "address": l["address"],
                       "phone": l["phone"], "lat": l["lat"], "lng": l["lng"], "star": l["star"], "rows": l["rows"], "tabs": l["tabs"],
                       **r, "options": room_options(target or ({"kind": top["kind"], "cluster_id": top["cluster_id"]} if top else None), imp_by_id),
                       "rooms": rooms, "rates": l["rates"], "conditions": l["conditions"]})
    # the same hotel twice in one sheet, under two names
    by_cluster: dict = {}
    for h in hotels:
        if h["decision"] == "matched":
            by_cluster.setdefault(h["candidates"][0]["cluster_id"], []).append(h)
    twice = []
    for cid, hs in by_cluster.items():
        if len(hs) > 1:
            twice.append({"cluster_id": cid, "name": hs[0]["candidates"][0]["name"], "as": [h["name"] for h in hs]})
            for h in hs:
                h["also_as"] = [o["name"] for o in hs if o is not h]
    rooms_all = [x for h in hotels for x in h["rooms"]]
    summary = {"rows": info["rows"], "names": len(hotels),
               "hotels": len({h["candidates"][0]["cluster_id"] for h in hotels if h["decision"] == "matched"}) + sum(h["decision"] == "new" for h in hotels)
               + sum(h["decision"] == "review" for h in hotels),
               "matched": sum(h["decision"] == "matched" for h in hotels), "new": sum(h["decision"] == "new" for h in hotels),
               "review": sum(h["decision"] == "review" for h in hotels), "listed_twice": len(twice),
               "room_names": len(rooms_all), "rooms_mapped": sum(x["status"] == "mapped" for x in rooms_all),
               "rooms_person": sum(x["status"] == "person" for x in rooms_all), "rooms_new": sum(x["status"] == "new" for x in rooms_all),
               "short_codes": sum(bool(h["candidates"]) and h["decision"] != "new" and " read as " in h["candidates"][0]["reasons"][0] for h in hotels),
               "rates": sum(len(h["rates"]) for h in hotels)}
    _, auto, gray = _model()
    out = {"file": filename, "layout": parsed["layout"], "currency": parsed["currency"], "tabs": parsed["tabs"], "warnings": parsed["warnings"],
           "sheet": info, "summary": summary, "hotels": hotels, "listed_twice": twice,
           "thresholds": {"auto_merge": auto, "review_floor": gray}, "check": None}
    if hashlib.sha256(data).hexdigest() in sample_hashes():
        from samesame.eval.sheet_check import score         # the answer key lives in eval/, like every truth table
        out["check"] = score(out)
    return out


# ------------------------------------------------------------------ sample sheets (synthetic, built by the pipeline)
SAMPLES = {"weaver": ("weaver_rates", "Weaver", "One row per rate, with coordinates and short codes"),
           "plover": ("plover_group_rates", "Plover", "A price grid: seasons × weekdays, two rate-plan tabs, footnotes")}


def sample_path(fmt: str = "csv", name: str = "weaver"):
    return config.BUILD / "sheets" / f"{SAMPLES[name][0]}.{fmt}"


@lru_cache
def sample_hashes() -> set[str]:
    return {hashlib.sha256(p.read_bytes()).hexdigest() for p in (sample_path("csv"), sample_path("xlsx")) if p.exists()}


@lru_cache
def ingest_sample() -> dict:
    p = sample_path("csv")
    return ingest(p.read_bytes(), p.name)


def to_csv(rows: list[dict], fields: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
