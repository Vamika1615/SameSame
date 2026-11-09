"""Short-code naming (synthetic, disclosed in DATA.md): the naming mess in suppliers' rate spreadsheets.

Added after TBO's CTO described the real pain: suppliers send spreadsheets where one hotel and its rooms are
written as "Radisson Plaza Room", "Radisson Room" or "RP Room". Parameters below were set before measuring.

1. **Short-code listings.** A supplier loads a hotel a second time from another contract under the brand's
   initials: "HGI Dubai Deira" for Hilton Garden Inn Dubai Deira, "HP Dubai Al Rigga" for Hyatt Place.
   These are EXTRA listings: added after the booking log and the images, from their own random stream, with no
   photos. Nothing that existed before changes, so the frozen held-out set and every Remix number stay valid.
2. **Room names that carry the hotel's name.** "Hyatt Place Superior King", "HP SUP KG CV", and sometimes only
   the hotel ("Hyatt Place Room"), which no parser can map: a person has to pick the room.
3. **Weaver's spreadsheet.** A seventh, fictional supplier sends a rate sheet (CSV + XLSX) in that style, used
   by the Supplier Sheets page. It is NOT part of the catalogue; its answer key (weaver_truth) is for scoring only.
"""
import csv
import io
import re
import unicodedata

import numpy as np

from samesame import city, config
from samesame.data import feeds
from samesame.data.world import STYLE
from samesame.ranking.score import haversine_m

SHORT_CODE_SHARE = 0.30              # of hotels whose name has a short code, one supplier re-loads it under that code
ROOM_FULL_PREFIX, ROOM_CODE_PREFIX = 0.40, 0.30   # room names written "<hotel> <room>" / "<CODE> <abbrev room>"
ROOM_ONLY_HOTEL = 0.35               # the entry room written as just "<hotel> Room"
PARTICLES = {"al", "el", "le", "la", "de", "du"}
STOP_RUN = {"dubai", "hotel", "hotels", "by", "the", "and", "&", "-", "at", "of", "a", "an", "uae"}

WEAVER_HOTELS, WEAVER_NEW, WEAVER_TWICE = 26, 4, 3
SHEET_COLUMNS = ["Property", "Address", "Latitude", "Longitude", "Phone", "Star", "Room Type", "Meal", "Net Rate (INR)", "Cancellation"]


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def short_code(name: str) -> tuple[str, str] | None:
    """('HGI Dubai Deira', 'Hilton Garden Inn') for 'Hilton Garden Inn Dubai Deira', or None.

    The code is the initials of the leading run of 2-3 distinctive words (stopping at Dubai / Hotel / by / ...)."""
    toks = re.sub(r"[,()]", " ", name).split()
    if toks and toks[0].lower() == "the":
        toks = toks[1:]
    run = []
    for t in toks:
        w = _fold(t).replace("'", "")
        if len(run) == 3 or not w.isalpha() or w.lower() in STOP_RUN:
            break
        run.append(t)
    while run and _fold(run[-1]).lower() in PARTICLES:     # "Jumeirah Marsa Al Arab" -> "JM Al Arab", not "JMA Arab"
        run.pop()
    if len(run) < 2:
        return None
    rest = toks[len(run):]
    code = "".join(_fold(t)[0].upper() for t in run)
    return (" ".join([code] + rest) if rest else f"{code} Hotel"), " ".join(run)


def _room_words(r: dict) -> str:
    if r["tier"] == "Family":
        return "Family Room"
    return f"{r['tier']} {r['bed']}" + (f" {r['view']} View" if r["view"] else "")


def _room_code(r: dict) -> str:
    A = feeds.ABBR
    if r["tier"] == "Family":
        return "FAM RM"
    return " ".join(x for x in [A.get(r["tier"], r["tier"].upper()), A.get(r["bed"], r["bed"].upper()), A.get(r["view"]) if r["view"] else None] if x)


def room_name(r: dict, brand: str, code: str, entry: bool, plain: str, rng) -> tuple[str, str | None]:
    """A room name in the spreadsheet style, and the corruption it carries."""
    if entry and rng.random() < ROOM_ONLY_HOTEL:
        return (f"{brand} Room" if rng.random() < 0.5 else f"{code} Room"), "room_names_only_hotel"
    x = rng.random()
    if x < ROOM_FULL_PREFIX:
        return f"{brand} {_room_words(r)}", "hotel_in_room_name"
    if x < ROOM_FULL_PREFIX + ROOM_CODE_PREFIX:
        return f"{code} {_room_code(r)}", "hotel_in_room_name"
    return plain, None


def short_code_listings(hotels, listings, truth, rooms_all, sup_rooms, room_truth, offers, rng):
    """Extra listings: a supplier re-loads ~30% of hotels that have a short code under it. Returns new rows."""
    room = {r["room_id"]: r for r in rooms_all}
    hotel_of = {t["listing_id"]: t["hotel_id"] for t in truth}
    corr = {t["listing_id"]: t["corruptions"] for t in truth}
    by_hotel: dict = {}
    for l in listings:
        if "supplier_duplicate" not in corr[l["listing_id"]]:
            by_hotel.setdefault(hotel_of[l["listing_id"]], []).append(l)
    rooms_of: dict = {}
    rt = {r["supplier_room_id"]: r["room_id"] for r in room_truth}
    for sr in sup_rooms:
        rooms_of.setdefault(sr["listing_id"], []).append(sr)
    offers_of: dict = {}
    for o in offers:
        offers_of.setdefault(o["supplier_room_id"], []).append(o)
    out = {k: [] for k in ("listings", "truth", "sup_rooms", "room_truth", "offers")}
    for h in hotels:
        sc = short_code(h["name"])
        srcs = by_hotel.get(h["hotel_id"], [])
        if h["golden"] or not sc or not srcs or rng.random() >= SHORT_CODE_SHARE:
            continue
        name, brand = sc
        code = name.split()[0]
        src = srcs[int(rng.integers(len(srcs)))]
        sup = src["supplier_id"]
        lid = feeds._new_id(f"{sup}:{sup[:2].upper()}", f"{h['hotel_id']}|{sup}|short-code")
        j, ang = abs(rng.normal(0, 25)), rng.random() * 6.283
        out["listings"].append({**src, "listing_id": lid, "name": name.upper() if STYLE[sup]["case"] == "upper" else name,
                                "lat": round(src["lat"] + feeds._m_to_deg(j) * np.sin(ang), 6),
                                "lng": round(src["lng"] + feeds._m_to_deg(j) * np.cos(ang), 6),
                                "phone": src["phone"] if rng.random() < 0.7 else None,
                                "description": src["description"].replace(h["name"], name), "n_images": 0})
        out["truth"].append({"listing_id": lid, "hotel_id": h["hotel_id"], "corruptions": ["short_code_name", "no_images"]})
        srs = sorted(rooms_of.get(src["listing_id"], []), key=lambda s: rt[s["supplier_room_id"]])
        for i, sr in enumerate(srs):
            if i and rng.random() > 0.8:
                continue
            r = room[rt[sr["supplier_room_id"]]]
            raw, corr = room_name(r, brand, code, r["room_id"].endswith(":R1"), sr["raw_name"], rng)
            nid = f"{lid}:{r['room_id'].rsplit(':', 1)[1]}"
            out["sup_rooms"].append({"supplier_room_id": nid, "listing_id": lid, "supplier_id": sup, "raw_name": raw})
            out["room_truth"].append({"supplier_room_id": nid, "room_id": r["room_id"], "corruptions": [corr] if corr else []})
            for o in offers_of.get(sr["supplier_room_id"], []):
                out["offers"].append({**o, "offer_id": f"{nid}:{o['board']}", "listing_id": lid, "supplier_room_id": nid,
                                      "nightly": float(round(o["nightly"] * float(np.exp(rng.normal(0, 0.03))), -1))})
    return out


# ------------------------------------------------------------------ Weaver's spreadsheet
def weaver_sheet(hotels, rooms_all, osm_reference, osm_duplicates, rng) -> tuple[list[dict], list[dict]]:
    """Rows of a seventh supplier's rate sheet (one row per room x meal plan) and the answer key per row."""
    from samesame.data.osm_base import DEMO
    room_by_hotel: dict = {}
    for r in rooms_all:
        room_by_hotel.setdefault(r["hotel_id"], []).append(r)
    near = sorted(hotels, key=lambda h: haversine_m(*DEMO, h["lat"], h["lng"]))
    golden = next(h for h in hotels if h["golden"])
    picked = [golden] + [h for h in near if not h["golden"]][:WEAVER_HOTELS - 1]
    known = {h["osm_id"] for h in hotels} | {d["dropped"] for d in osm_duplicates}
    fresh = [o for o in sorted(osm_reference, key=lambda o: haversine_m(*DEMO, o["lat"], o["lng"]))
             if o["osm_id"] not in known and min(haversine_m(o["lat"], o["lng"], h["lat"], h["lng"]) for h in hotels) > 300][:WEAVER_NEW]
    rows, key = [], []
    twice = {h["hotel_id"] for h in picked[1:] if short_code(h["name"])}
    twice = set(sorted(twice)[:WEAVER_TWICE])

    def emit(name, lat, lng, address, phone, star, rooms, base_rate, answer, code_brand):
        brand, code = code_brand if code_brand else (name, name)
        missing_xy = rng.random() < 0.04 and answer["hotel_id"] != golden["hotel_id"]
        j, ang = abs(rng.normal(0, 40)), rng.random() * 6.283
        for i, r in enumerate(rooms):
            plain = _room_words(r) if rng.random() < 0.5 else _room_code(r)
            raw, corr = room_name(r, brand, code, i == 0, plain, rng) if code_brand else (plain, None)
            for meal in (["Room Only", "Bed & Breakfast"] if rng.random() < 0.6 else ["Room Only"]):
                price = base_rate * r.get("tier_mult", 1.0) * 0.97 * float(np.exp(rng.normal(0, 0.05))) + (900 if meal != "Room Only" else 0)
                rows.append({"Property": name, "Address": address or "",
                             "Latitude": "" if missing_xy else round(lat + feeds._m_to_deg(j) * np.sin(ang), 6),
                             "Longitude": "" if missing_xy else round(lng + feeds._m_to_deg(j) * np.cos(ang), 6),
                             "Phone": phone or "", "Star": star or "", "Room Type": raw, "Meal": meal,
                             "Net Rate (INR)": int(round(price, -1)),
                             "Cancellation": "Non-refundable" if rng.random() < 0.4 else f"Free until {int(rng.integers(1, 8))} days before"})
                key.append({"row": len(rows), **answer, "room_id": r["room_id"], "room_corruption": corr})

    for h in picked:
        sc = short_code(h["name"])
        rooms = [r for r in sorted(room_by_hotel[h["hotel_id"]], key=lambda r: r["room_id"])][:int(rng.integers(2, 5))]
        use_code = bool(sc) and (h["golden"] or rng.random() < 0.55)
        name = sc[0] if use_code else re.sub(r"\s*\bDubai\b\s*", " ", h["name"]).strip() if rng.random() < 0.4 else h["name"]
        cb = (sc[1], sc[0].split()[0]) if sc else None
        phone = h["phone"] if rng.random() < 0.7 else None
        args = (h["lat"], h["lng"], ", ".join(x for x in [h["street"], h["district"], city.NAME] if x), phone, h["star"])
        emit(name, *args, rooms, h["base_rate"], {"hotel_id": h["hotel_id"], "new_hotel": False}, cb)
        if h["hotel_id"] in twice:                      # the same hotel again, under its other name
            other = h["name"] if use_code else sc[0]
            emit(other, *args, rooms[:2], h["base_rate"], {"hotel_id": h["hotel_id"], "new_hotel": False}, cb)
    for o in fresh:
        rooms = [{"room_id": f"new:{o['osm_id']}:R1", "tier": "Standard", "bed": "King", "view": None, "tier_mult": 1.0},
                 {"room_id": f"new:{o['osm_id']}:R2", "tier": "Deluxe", "bed": "Twin", "view": None, "tier_mult": 1.15}]
        emit(o["name"], o["lat"], o["lng"], o.get("address"), o.get("phone"), None, rooms, float(rng.integers(40, 90)) * 100,
             {"hotel_id": None, "new_hotel": True, "osm_id": o["osm_id"]}, None)
    return rows, key


def write_sheet(rows: list[dict]) -> dict:
    """Weaver's sheet as CSV (always) and XLSX (if openpyxl is installed). Returns {format: path}."""
    d = config.BUILD / "sheets"
    d.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=SHEET_COLUMNS)
    w.writeheader()
    w.writerows(rows)
    (d / "weaver_rates.csv").write_text(buf.getvalue(), encoding="utf-8")
    out = {"csv": d / "weaver_rates.csv"}
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Rates"
        ws.append(SHEET_COLUMNS)
        for r in rows:
            ws.append([r[c] for c in SHEET_COLUMNS])
        wb.save(d / "weaver_rates.xlsx")
        out["xlsx"] = d / "weaver_rates.xlsx"
    except ImportError:
        pass
    return out
