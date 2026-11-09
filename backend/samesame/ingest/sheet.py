"""Supplier Sheets: read a supplier's rate spreadsheet (CSV / XLSX) and resolve every row to TBO's catalogue.

  rows -> one listing per hotel as the sheet writes it -> Twin Finder against the catalogue (the SAME trained
  LightGBM model, features and thresholds as the pipeline; short codes written out) -> one canonical hotel each,
  "new to TBO", or a person decides -> room names parsed with the hotel's own name removed -> canonical room.

Reads only the uploaded sheet and the catalogue the app already serves. Never the generator's truth: the answer
key is used only by eval/sheet_check.py, and only when the uploaded file is Weaver's sample sheet byte for byte.
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
from samesame.matching import hotels as hm
from samesame.matching import rooms as rm

MAX_ROWS = 5000
SUPPLIER = "sheet"
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
}
REQUIRED = ("name", "room")


class SheetError(ValueError):
    pass


# ------------------------------------------------------------------ reading
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
    if filename.lower().endswith((".xlsx", ".xlsm")):
        try:
            import openpyxl
        except ImportError as e:
            raise SheetError("Reading .xlsx needs openpyxl (pip install openpyxl); or save the sheet as CSV.") from e
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as e:
            raise SheetError(f"Couldn't open this Excel file: {type(e).__name__}") from e
        ws = wb.worksheets[0]
        rows = [["" if v is None else str(v) for v in r] for r in ws.iter_rows(values_only=True)]
    else:
        text = data.decode("utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        raise SheetError("The sheet is empty.")
    return rows


def _num(v) -> float | None:
    """'4', '4*', '4 Star', '12,500', '₹ 12500.00', '25,2048' (decimal comma) -> float."""
    t = str(v or "").strip()
    t = t.replace(",", "") if re.search(r"\d,\d{3}(?!\d)", t) else t.replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(m.group()) if m else None


def parse_rows(data: bytes, filename: str) -> tuple[list[dict], dict]:
    table = read_table(data, filename)
    headers, body = table[0], table[1:MAX_ROWS + 1]
    cols, unused = map_columns(headers)
    missing = [f for f in REQUIRED if f not in cols]
    if missing:
        raise SheetError(f"Couldn't find a column for {' and '.join(missing)}. Headers seen: {', '.join(map(str, headers))}.")
    get = lambda r, f: (r[cols[f]].strip() if f in cols and cols[f] < len(r) and r[cols[f]] is not None else "")  # noqa: E731
    rows = []
    for i, r in enumerate(body, start=1):
        name = get(r, "name")
        if not name:
            continue
        lat, lng = _num(get(r, "lat")), _num(get(r, "lng"))
        rows.append({"row": i, "name": name, "address": get(r, "address") or None, "phone": get(r, "phone") or None,
                     "lat": lat if lat is not None and -90 <= lat <= 90 else None, "lng": lng if lng is not None and -180 <= lng <= 180 else None,
                     "star": _num(get(r, "star")), "room": get(r, "room"), "meal": get(r, "meal") or None,
                     "price": _num(get(r, "price")), "cancel": get(r, "cancel") or None})
    info = {"columns": {f: headers[i] for f, i in cols.items()}, "unused_columns": unused, "rows": len(rows),
            "truncated": len(table) - 1 > MAX_ROWS}
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


# ------------------------------------------------------------------ resolving
def _listings(rows: list[dict]) -> list[dict]:
    """One listing per hotel as the sheet writes it (same name and roughly the same place)."""
    groups: dict = {}
    for r in rows:
        k = (hm.norm(r["name"]), round(r["lat"], 3) if r["lat"] is not None else None, round(r["lng"], 3) if r["lng"] is not None else None)
        groups.setdefault(k, []).append(r)
    out = []
    for i, rs in enumerate(groups.values()):
        first = rs[0]
        stars = [r["star"] for r in rs if r["star"]]
        out.append({"listing_id": f"sheet:{i + 1}", "supplier_id": SUPPLIER, "name": first["name"], "address": first["address"],
                    "phone": next((r["phone"] for r in rs if r["phone"]), None), "lat": first["lat"], "lng": first["lng"],
                    "star": stars[0] if stars else None, "amenities": [], "postcode": None, "checkin_time": None, "_rows": rs})
    return out


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


def _resolve(L: list[dict]) -> list[dict]:
    booster, auto, gray = _model()
    P, chain, emb, lat, lng = _catalogue()
    s = store.get()
    U = hm.prep([{k: v for k, v in l.items() if k != "_rows"} | {"lat": l["lat"] or 0.0, "lng": l["lng"] or 0.0} for l in L])
    for u in U:
        u["_chain_phone"] = u["_phone"] in chain
    uemb = _embed([u["_n"] for u in U])
    out = []
    for k, (l, u) in enumerate(zip(L, U)):
        if l["lat"] is None or l["lng"] is None:
            # no coordinates: the model needs distance, so suggest by name only and leave it to a person
            sims = sorted(((fuzz.token_set_ratio(*hm.expand(u, p)[:2]) / 100, p) for p in P), key=lambda x: -x[0])
            seen, cands = set(), []
            for sc, p in sims:
                cid = s.cluster_of[p["listing_id"]]
                if cid not in seen:
                    seen.add(cid); cands.append({"cluster_id": cid, "name": _cluster_name(cid), "p": None, "reasons": [f"name {sc:.0%} alike", "no coordinates in the sheet"]})
                if len(cands) == 3:
                    break
            out.append({"decision": "review", "why": "No coordinates in the sheet, so location can't be checked.", "candidates": cands})
            continue
        d = hm.haversine_vec(l["lat"], l["lng"], lat, lng)
        best: dict = {}
        for j in np.nonzero(d <= hm.BLOCK_RADIUS_M)[0]:
            p = P[int(j)]
            if not ((u["_core"] & p["_core"]) or (u["_fam"] and u["_fam"] == p["_fam"]) or d[j] <= 100
                    or hm.short_code(u, p) or hm.short_code(p, u)):
                continue
            f = hm.pair_features(u, p, float(uemb[k] @ emb[j]) if uemb is not None and emb is not None else np.nan, (np.nan, 0))
            f["checkin_eq"] = np.nan                       # sheets don't carry a check-in time: unknown, not "different"
            x = np.array([[f[c] for c in hm.FEATURES]], dtype=float)
            prob = float(booster.predict(x)[0])
            cid = s.cluster_of[p["listing_id"]]
            why_not = hm.conflict(u, p)
            if why_not:
                prob = 0.0
            if cid not in best or prob > best[cid]["p"]:
                best[cid] = {"cluster_id": cid, "p": round(prob, 4), "listing": p["name"], "supplier": p["supplier_id"],
                             "reasons": [why_not] if why_not else _reasons(f, hm.expand(u, p)[2], float(d[j]))}
        ranked = sorted(best.values(), key=lambda c: -c["p"])[:3]
        for c in ranked:
            c["name"] = _cluster_name(c["cluster_id"])
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


def _canonical(cid: str) -> list[dict]:
    rooms = store.get().rooms_of.get(cid, {})
    rooms = rooms.values() if isinstance(rooms, dict) else rooms
    return [r for r in rooms if r["tier"] != "Unknown" and ":unmapped-" not in r["room_id"]]


def _room(raw: str, cid: str | None, names: list[str]) -> dict:
    a = rm.parse_in_hotel(raw, names)
    base = {"raw": raw, "hotel_words": a.get("hotel_words"), "parsed": " ".join(x for x in (a["tier"], a["bed"], a["view"] and f"{a['view']} View") if x) or None}
    if a.get("note"):
        return {**base, "status": "person", "why": a["note"], "room_id": None, "room": None, "confidence": a["confidence"]}
    if a["tier"] is None or a["bed"] is None:
        return {**base, "status": "person", "why": "couldn't read a room type and bed from this name", "room_id": None, "room": None,
                "confidence": a["confidence"]}
    if cid is None:
        return {**base, "status": "new", "why": "new hotel: this becomes one of its rooms", "room_id": None, "room": None, "confidence": a["confidence"]}
    same = [r for r in _canonical(cid) if r["tier"] == a["tier"] and r["bed"] == a["bed"]]
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


def ingest(data: bytes, filename: str) -> dict:
    rows, info = parse_rows(data, filename)
    L = _listings(rows)
    res = _resolve(L)
    s = store.get()
    hotels = []
    for l, r in zip(L, res):
        top = r["candidates"][0] if r["candidates"] else None
        cid = top["cluster_id"] if r["decision"] == "matched" else None
        names = [l["name"]] + ([x["name"] for x in s.listings_of.get(top["cluster_id"], [])] if top and r["decision"] != "new" else [])
        rooms, seen = [], {}
        for row in l["_rows"]:
            if row["room"] not in seen:
                seen[row["room"]] = len(rooms)
                rooms.append({**_room(row["room"], cid if r["decision"] == "matched" else (top["cluster_id"] if top and r["decision"] == "review" else None),
                                      names), "rows": [], "prices": []})
                x = rooms[-1]
                if r["decision"] == "review" and x["status"] == "mapped":   # a suggestion only, until a person confirms the hotel
                    x.update(status="person", why=f"waiting for the hotel decision (would be {x['room']})", room_id=None, room=None)
            x = rooms[seen[row["room"]]]
            x["rows"].append(row["row"])
            if row["price"] is not None:
                x["prices"].append({"meal": row["meal"], "price": row["price"], "cancel": row["cancel"]})
        hotels.append({"sheet_id": l["listing_id"], "name": l["name"], "address": l["address"], "phone": l["phone"], "lat": l["lat"], "lng": l["lng"],
                       "star": l["star"], "rows": [x["row"] for x in l["_rows"]], **r,
                       "options": [{"room_id": c["room_id"], "name": c["name"]} for c in _canonical(top["cluster_id"])] if top else [],
                       "rooms": rooms})
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
               "short_codes": sum(bool(h["candidates"]) and h["decision"] != "new" and " read as " in h["candidates"][0]["reasons"][0] for h in hotels)}
    _, auto, gray = _model()
    out = {"file": filename, "sheet": info, "summary": summary, "hotels": hotels, "listed_twice": twice,
           "thresholds": {"auto_merge": auto, "review_floor": gray}, "check": None}
    if hashlib.sha256(data).hexdigest() in sample_hashes():
        from samesame.eval.sheet_check import score         # the answer key lives in eval/, like every truth table
        out["check"] = score(out)
    return out


# ------------------------------------------------------------------ Weaver's sample sheet
def sample_path(fmt: str = "csv"):
    return config.BUILD / "sheets" / f"weaver_rates.{fmt}"


@lru_cache
def sample_hashes() -> set[str]:
    return {hashlib.sha256(p.read_bytes()).hexdigest() for p in (sample_path("csv"), sample_path("xlsx")) if p.exists()}


@lru_cache
def ingest_sample() -> dict:
    p = sample_path("csv")
    return ingest(p.read_bytes(), p.name)
