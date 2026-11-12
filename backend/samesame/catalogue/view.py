"""The catalogue: past inventory + every applied supplier-sheet import + people's decisions.

  past inventory   the six suppliers' feeds, consolidated by Twin Finder (store.py clusters, canonical rooms, offers)
  imports          applied in the order they were applied. A sheet's hotel either attaches to an inventory hotel,
                   attaches to a hotel an earlier import created, creates a new hotel, or waits for a person.
                   Its rooms map to that hotel's rooms (by code, name, or tier + bed + view) or become new rooms.
  decisions        a person's choice overrides the engine for that hotel or room; undo restores the engine's.

Rebuilt whenever an import, result or decision file changes (imports.stamp()).
"""
import hashlib
import re
import threading
from functools import lru_cache

from samesame import store
from samesame.catalogue import imports as I
from samesame.ingest import sheet as S

_LOCK = threading.Lock()
_CACHE: dict = {"stamp": None, "state": None}


def _ih(import_id: str, sheet_id: str) -> str:
    return "ih-" + hashlib.md5(f"{import_id}|{sheet_id}".encode()).hexdigest()[:10]


def _rid(hotel_id: str, name: str) -> str:
    return "ihr-" + hashlib.md5(f"{hotel_id}|{S.room_key(name)}".encode()).hexdigest()[:8]


@lru_cache(maxsize=4096)
def inventory_name(cid: str) -> str:
    from samesame import service
    return service.golden(cid)["name"]


def _inventory_rooms(cid: str) -> dict[str, str]:
    return {r["room_id"]: r["name"] for r in S.canonical_rooms(cid)}


def _matching_view(imported: dict) -> dict[str, dict]:
    return {k: {**h, "rooms": [{"id": r["id"], "name": r["name"], "code": r["code"]} for r in h["rooms"]]} for k, h in imported.items()}


def resolve(m: dict, res: dict, dec: dict, imported: dict) -> list[dict]:
    """Every hotel of one import with its final target and room mapping, decisions applied."""
    out = []
    view = _matching_view(imported)
    for h in res["hotels"]:
        top = h["candidates"][0] if h["candidates"] else None
        d = dec.get((m["id"], h["sheet_id"], "hotel", None))
        if d:
            v = d["value"]
            target = (None if v == "new" else {"kind": "imported" if v.startswith("ih-") else "inventory", "cluster_id": v})
            final, by_person = ("new" if v == "new" else "target"), True
        elif h["decision"] == "matched":
            target, final, by_person = {"kind": top["kind"], "cluster_id": top["cluster_id"]}, "target", False
        elif h["decision"] == "new":
            target, final, by_person = None, "new", False
        else:
            target, final, by_person = None, None, False                       # waiting for a person
        if target and target["kind"] == "imported" and target["cluster_id"] not in imported:
            target, final = None, "new"                                          # the earlier import that created it was removed
        names = [h["name"]] + S.target_names(target, view)
        rooms = []
        for r in h["rooms"]:
            rd = dec.get((m["id"], h["sheet_id"], "room", r["raw"]))
            if final is None:
                mapped = {**r, "status": "person" if r["status"] != "new" else "new"}
            else:
                mapped = {**r, **S.map_room(r["raw"], r.get("code"), target, names, view)}
            if rd:
                mapped.update(status="new" if rd["value"] == "new" else "mapped", room_id=None if rd["value"] == "new" else rd["value"],
                              why="decided by a person", decided=True, audit_id=rd["audit_id"])
                if mapped["room_id"]:
                    opts = {o["room_id"]: o["name"] for o in S.room_options(target, view)}
                    mapped["room"] = opts.get(mapped["room_id"], mapped["room_id"])
            rooms.append(mapped)
        out.append({"sheet_id": h["sheet_id"], "name": h["name"], "hotel": h, "final": final, "target": target, "by_person": by_person,
                    "audit_id": d["audit_id"] if d else None, "rooms": rooms, "options": S.room_options(target, view) if target else []})
    return out


def state() -> dict:
    stamp = I.stamp()
    with _LOCK:
        if _CACHE["stamp"] == stamp:
            return _CACHE["state"]
        dec = I.decisions()
        metas = sorted([m for m in I.list_meta() if m["status"] == "applied"], key=lambda m: m["applied_at"] or m["uploaded_at"])
        imported: dict[str, dict] = {}
        attached: dict[str, list] = {}
        resolved: dict[str, list] = {}
        for m in metas:
            res = I.result(m["id"])
            rs = resolve(m, res, dec, imported)
            resolved[m["id"]] = rs
            for rh in rs:
                if rh["final"] is None:
                    continue
                h = rh["hotel"]
                src = {"import_id": m["id"], "supplier": m["supplier"], "file": m["file"], "sheet_id": h["sheet_id"], "as_written": h["name"]}
                if rh["final"] == "new":
                    hid = _ih(m["id"], h["sheet_id"])
                    rec = imported.setdefault(hid, {"id": hid, "kind": "imported", "name": h["name"], "address": h["address"], "phone": h["phone"],
                                                    "lat": h["lat"], "lng": h["lng"], "star": h["star"], "source": m["file"], "sources": [],
                                                    "rooms": [], "rates": [], "conditions": [], "created_by": m["id"]})
                    _attach_imported(rec, rh, src)
                elif rh["target"]["kind"] == "imported":
                    _attach_imported(imported[rh["target"]["cluster_id"]], rh, src)
                else:
                    cid = rh["target"]["cluster_id"]
                    canon = _inventory_rooms(cid)
                    rooms_out, rates = {}, []
                    for r in rh["rooms"]:
                        rid = r["room_id"] if r["status"] == "mapped" else (f"{cid}:sheet-{S.room_key(r['raw']).replace(' ', '-')}" if r["status"] == "new" else None)
                        rooms_out[S.room_key(r["raw"])] = (rid, canon.get(rid, r.get("room") or r["raw"]) if rid else None, r["status"])
                    for x in h["rates"]:
                        rid, rname, st = rooms_out.get(S.room_key(x["room"]), (None, None, "person"))
                        rates.append({**x, "room_id": rid, "room_name": rname or x["room"], "room_status": st, **_src(src)})
                    attached.setdefault(cid, []).append({**src, "rooms": rh["rooms"], "rates": rates, "conditions": h["conditions"]})
        st = {"imported": imported, "attached": attached, "resolved": resolved, "decisions": dec, "applied": metas}
        _CACHE.update(stamp=stamp, state=st)
        return st


def _src(src: dict) -> dict:
    return {"source_supplier": src["supplier"], "source_file": src["file"], "import_id": src["import_id"]}


def _attach_imported(rec: dict, rh: dict, src: dict):
    h = rh["hotel"]
    rec["sources"].append(src)
    for k in ("address", "phone", "lat", "lng", "star"):
        rec[k] = rec[k] if rec[k] is not None else h.get(k)
    ids = {}
    for r in rh["rooms"]:
        if r["status"] == "mapped" and any(x["id"] == r["room_id"] for x in rec["rooms"]):
            rid = r["room_id"]
        elif r["status"] == "person":
            ids[S.room_key(r["raw"])] = (None, r["raw"], "person")
            continue
        else:
            rid = _rid(rec["id"], r["raw"])
            if not any(x["id"] == rid for x in rec["rooms"]):
                rec["rooms"].append({"id": rid, "name": r["raw"], "code": r.get("code"), "extras": r.get("extras", {}), "sources": []})
        room = next(x for x in rec["rooms"] if x["id"] == rid)
        room["code"] = room["code"] or r.get("code")
        room["sources"].append(src["supplier"])
        ids[S.room_key(r["raw"])] = (rid, room["name"], "mapped")
    for x in h["rates"]:
        rid, rname, stt = ids.get(S.room_key(x["room"]), (None, x["room"], "person"))
        rec["rates"].append({**x, "room_id": rid, "room_name": rname, "room_status": stt, **_src(src)})
    seen = {c["text"] for c in rec["conditions"]}
    rec["conditions"] += [{**c, "source_supplier": src["supplier"]} for c in h["conditions"] if c["text"] not in seen]


# ------------------------------------------------------------------ what the API serves
def for_matching(exclude: str | None = None) -> list[dict]:
    """Hotels earlier imports created, in the shape ingest() matches against."""
    return [{"id": h["id"], "name": h["name"], "lat": h["lat"], "lng": h["lng"], "phone": h["phone"], "address": h["address"],
             "source": h["source"], "rooms": [{"id": r["id"], "name": r["name"], "code": r["code"]} for r in h["rooms"]]}
            for h in state()["imported"].values() if h["created_by"] != exclude]


def import_view(import_id: str) -> dict:
    """An import with decisions applied, for the import page (rates summarised, not listed)."""
    m = I.meta(import_id)
    res = I.result(import_id)
    st = state()
    rs = st["resolved"].get(import_id) or resolve(m, res, st["decisions"], st["imported"])
    hotels = []
    for rh in rs:
        h = rh["hotel"]
        if rh["final"] == "new":
            final = {"kind": "new", "id": _ih(import_id, h["sheet_id"]) if m["status"] == "applied" else None, "name": h["name"]}
        elif rh["final"] == "target":
            t = rh["target"]
            final = {"kind": t["kind"], "id": t["cluster_id"],
                     "name": inventory_name(t["cluster_id"]) if t["kind"] == "inventory" else st["imported"].get(t["cluster_id"], {}).get("name")}
        else:
            final = None
        hotels.append({**{k: v for k, v in h.items() if k != "rates"}, "rooms": rh["rooms"], "options": rh["options"] or h.get("options", []),
                       "final": final, "by_person": rh["by_person"], "audit_id": rh["audit_id"],
                       "rate_plans": sorted({x["plan"] for x in h["rates"]}), "seasons": len({(x["season_from"], x["season_to"]) for x in h["rates"]})})
    rooms = [r for h in hotels for r in h["rooms"]]
    waiting = sum(h["final"] is None for h in hotels) + sum(r["status"] == "person" for h in hotels if h["final"] for r in h["rooms"])
    return {"meta": m, **{k: v for k, v in res.items() if k != "hotels"}, "hotels": hotels,
            "progress": {"hotels_resolved": sum(h["final"] is not None for h in hotels), "hotels": len(hotels),
                         "rooms_resolved": sum(r["status"] != "person" for r in rooms), "rooms": len(rooms), "waiting": waiting}}


def pending() -> list[dict]:
    """Everything in draft or applied imports that waits for a person: hotels first, then rooms."""
    st = state()
    items = []
    for m in I.list_meta():
        if m["status"] == "removed":
            continue
        rs = st["resolved"].get(m["id"]) or resolve(m, I.result(m["id"]), st["decisions"], st["imported"])
        for rh in rs:
            h = rh["hotel"]
            base = {"import_id": m["id"], "supplier": m["supplier"], "file": m["file"], "import_status": m["status"], "sheet_id": h["sheet_id"],
                    "hotel_as_written": h["name"]}
            if rh["final"] is None:
                items.append({**base, "kind": "hotel", "why": h["why"], "candidates": h["candidates"], "rooms": len(h["rooms"]),
                              "rates": len(h["rates"]), "address": h["address"], "lat": h["lat"], "lng": h["lng"]})
                continue
            for r in rh["rooms"]:
                if r["status"] == "person" and not r.get("decided"):
                    items.append({**base, "kind": "room", "room": r["raw"], "code": r.get("code"), "why": r["why"], "options": rh["options"],
                                  "hotel": inventory_name(rh["target"]["cluster_id"]) if rh["target"] and rh["target"]["kind"] == "inventory"
                                  else (st["imported"].get(rh["target"]["cluster_id"], {}).get("name") if rh["target"] else h["name"])})
    return items


def hotels(q: str | None = None, source: str | None = None) -> dict:
    s = store.get()
    st = state()
    items = []
    for cid, ls in s.listings_of.items():
        sheets = st["attached"].get(cid, [])
        items.append({"id": cid, "kind": "inventory", "name": inventory_name(cid), "star": next((l["star"] for l in ls if l["star"]), None),
                      "suppliers": sorted({l["supplier_id"].title() for l in ls}), "listings": len(ls),
                      "sheets": sorted({x["supplier"] for x in sheets}), "rooms": len(S.canonical_rooms(cid)),
                      "rates": sum(len(x["rates"]) for x in sheets), "offers": len(s.offers_of.get(cid, [])), "lat": ls[0]["lat"], "lng": ls[0]["lng"]})
    for h in st["imported"].values():
        items.append({"id": h["id"], "kind": "imported", "name": h["name"], "star": h["star"], "suppliers": [], "listings": 0,
                      "sheets": sorted({x["supplier"] for x in h["sources"]}), "rooms": len(h["rooms"]), "rates": len(h["rates"]), "offers": 0,
                      "lat": h["lat"], "lng": h["lng"]})
    total = len(items)
    if q:
        k = re.sub(r"[^a-z0-9]+", " ", q.lower()).strip()
        items = [i for i in items if k in re.sub(r"[^a-z0-9]+", " ", i["name"].lower())]
    if source == "sheets":
        items = [i for i in items if i["sheets"]]
    elif source == "new":
        items = [i for i in items if i["kind"] == "imported"]
    items.sort(key=lambda i: (not i["sheets"], i["kind"] != "imported", i["name"].lower()))
    return {"total": total, "shown": len(items), "items": items,
            "counts": {"inventory": len(s.listings_of), "imported": len(st["imported"]),
                       "with_sheets": sum(1 for c in s.listings_of if st["attached"].get(c)) + len(st["imported"]),
                       "listings": len(s.listings)}}


def hotel(hid: str) -> dict | None:
    st = state()
    if hid in st["imported"]:
        h = st["imported"][hid]
        return {**h, "plans": sorted({x["plan"] for x in h["rates"]})}
    s = store.get()
    if hid not in s.listings_of:
        return None
    sheets = st["attached"].get(hid, [])
    rooms = [{"id": r["room_id"], "name": r["name"], "code": None, "sources": sorted({l["supplier_id"].title() for l in s.listings_of[hid]})}
             for r in S.canonical_rooms(hid)]
    for x in sheets:
        for r in x["rates"]:
            if r["room_id"] and not any(rr["id"] == r["room_id"] for rr in rooms):
                rooms.append({"id": r["room_id"], "name": r["room_name"], "code": r.get("code"), "sources": [x["supplier"]], "from_sheet": True})
    rates = [r for x in sheets for r in x["rates"]]
    return {"id": hid, "kind": "inventory", "name": inventory_name(hid), "sources": [{k: v for k, v in x.items() if k not in ("rates", "rooms", "conditions")}
                                                                                       for x in sheets],
            "suppliers": sorted({l["supplier_id"].title() for l in s.listings_of[hid]}), "rooms": rooms, "rates": rates,
            "conditions": [{**c, "source_supplier": x["supplier"]} for x in sheets for c in x["conditions"]],
            "plans": sorted({r["plan"] for r in rates}), "star": next((l["star"] for l in s.listings_of[hid] if l["star"]), None),
            "address": next((l["address"] for l in s.listings_of[hid] if l["address"]), None)}


def summary() -> dict:
    s = store.get()
    st = state()
    metas = I.list_meta()
    return {"inventory_hotels": len(s.listings_of), "imported_hotels": len(st["imported"]), "listings": len(s.listings),
            "imports": {k: sum(m["status"] == k for m in metas) for k in I.STATUSES},
            "sheet_rates": sum(len(x["rates"]) for v in st["attached"].values() for x in v) + sum(len(h["rates"]) for h in st["imported"].values()),
            "hotels_with_sheets": sum(1 for v in st["attached"].values() if v) + len(st["imported"]), "waiting": len(pending())}
