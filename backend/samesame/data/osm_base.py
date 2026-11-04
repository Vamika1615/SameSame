"""Curate the base hotel catalogue from the OSM snapshot.

Real: name, coordinates, and (where OSM has them) phone, stars, street, postcode, brand.
Synthetic (flagged per field in `*_source`): stars / phone where OSM is silent, pool, family rooms,
nightly base rate, amenities. OSM has its own duplicates (one hotel mapped as a node and a way, or
twice); those are collapsed first and written to osm_duplicates so the disclosure is checkable.
"""
import json
import re
import unicodedata

import numpy as np
from rapidfuzz import fuzz

from samesame import config
from samesame.ranking.score import haversine_m

TARGET = 300
CORE = (13.7400, 100.5450)          # roughly Ratchaprasong; hotels further out are less likely to be kept
ASOK = (13.7370, 100.5603)          # the demo search area: always keep what's within this radius
ASOK_KEEP_M = 900
HARD_NEG_MAX_M = 3000
OSM_DUP_M = 250

# Brand families. Order matters: longer / sub-brands first so "Holiday Inn Express" isn't "Holiday Inn".
FAMILIES = [
    "holiday inn express", "holiday inn", "crowne plaza", "hotel indigo", "intercontinental", "ibis styles", "ibis budget", "ibis",
    "grand mercure", "mercure", "novotel", "pullman", "sofitel", "swissotel", "movenpick", "citadines", "somerset",
    "ascott", "oakwood", "jw marriott", "courtyard", "marriott executive apartments", "marriott", "renaissance", "sheraton", "westin", "le meridien",
    "four points", "aloft", "st. regis", "w bangkok", "doubletree", "hilton garden inn", "hilton", "conrad",
    "hyatt regency", "grand hyatt", "park hyatt", "hyatt place", "centara grand", "centara", "centre point",
    "grande centre point", "amari", "avani", "anantara", "radisson", "park plaza", "best western", "ramada",
    "days inn", "travelodge", "chatrium", "dusit", "shangri-la", "mandarin oriental", "banyan tree", "kempinski",
    "royal orchid", "arnoma", "the berkeley", "eastin", "lub d", "siam@siam", "adelphi", "bandara", "akyra",
    "maitria", "citin", "royal princess", "majestic grande", "s ratchada", "the salil", "hotel j", "glow",
    "lancaster", "admiral", "galleria", "nantra", "residence inn", "fraser", "jasmine", "aspen",
]
BRAND_STARS = {"ibis": 3, "ibis styles": 3, "ibis budget": 2, "holiday inn express": 3, "travelodge": 3, "days inn": 3,
               "novotel": 4, "mercure": 4, "grand mercure": 4, "holiday inn": 4, "citadines": 4, "somerset": 4,
               "courtyard": 4, "four points": 4, "aloft": 4, "centara": 4, "amari": 4, "avani": 4, "eastin": 4,
               "radisson": 4, "park plaza": 4, "best western": 3, "ramada": 3, "hotel indigo": 4, "doubletree": 4,
               "hilton garden inn": 4, "hyatt place": 4, "chatrium": 5, "pullman": 5, "sofitel": 5, "swissotel": 5,
               "movenpick": 5, "jw marriott": 5, "marriott": 5, "renaissance": 5, "sheraton": 5, "westin": 5,
               "le meridien": 5, "st. regis": 5, "conrad": 5, "hilton": 5, "hyatt regency": 5, "grand hyatt": 5,
               "park hyatt": 5, "centara grand": 5, "anantara": 5, "dusit": 5, "shangri-la": 5, "mandarin oriental": 5,
               "banyan tree": 5, "kempinski": 5, "intercontinental": 5, "crowne plaza": 4, "ascott": 5, "oakwood": 4,
               "lub d": 2, "siam@siam": 4, "royal orchid": 5, "fraser": 4, "residence inn": 4}
GENERIC_FIRST = {"the", "hotel", "bangkok", "grand", "royal", "new", "baan", "ban", "house", "home", "residence", "city",
                 "silom", "sukhumvit", "siam", "asoke", "boutique", "golden", "white", "green", "blue", "my", "le", "la"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9@. ]+", " ", s)).strip()


_GENERIC = {"the", "hotel", "hotels", "boutique", "bangkok", "thailand", "by", "and", "resort", "residence", "suites", "inn", "a"}


def _core(n: str) -> frozenset:
    return frozenset(t for t in n.split() if t not in _GENERIC)


def family(name: str, brand: str | None) -> str | None:
    n = norm(name)
    for f in FAMILIES:
        if n.startswith(f + " ") or n == f or n.startswith("the " + f + " ") or (f + " ") in (n + " ")[:len(f) + 12]:
            return f
    if brand:
        b = norm(brand)
        if b and b not in GENERIC_FIRST:
            return b
    return None


def _latin(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and sum(c.isascii() for c in letters) / len(letters) > 0.8


# ------------------------------------------------------------------ geometry from the offline basemap
def _basemap():
    return json.loads((config.RAW_OSM / "basemap.geojson").read_text(encoding="utf-8"))


def _district_rings(bm):
    out = []
    for f in bm["features"]:
        if f["properties"].get("layer") == "district":
            segs = [(a, b) for line in f["geometry"]["coordinates"] for a, b in zip(line, line[1:])]
            out.append((f["properties"]["name"].replace(" District", ""), segs))
    return out


_RINGS = None


def district_at(lat: float, lng: float) -> str | None:
    """Bangkok district containing a point (offline OSM boundaries)."""
    global _RINGS
    if _RINGS is None:
        _RINGS = _district_rings(_basemap())
    return next((n for n, segs in _RINGS if _inside(lat, lng, segs)), None)


def _inside(lat, lng, segs) -> bool:
    """Crossing-number test. Segment order doesn't matter, only that the boundary closes."""
    c = False
    for (x1, y1), (x2, y2) in segs:
        if (y1 > lat) != (y2 > lat) and lng < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            c = not c
    return c


def _seg_dist_m(lat, lng, a, b):
    kx = 111_320 * np.cos(np.radians(lat))
    ky = 110_540
    ax, ay, bx, by = (a[0] - lng) * kx, (a[1] - lat) * ky, (b[0] - lng) * kx, (b[1] - lat) * ky
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    return float(np.hypot(ax + t * dx, ay + t * dy))


def _nearest_road(lat, lng, roads, max_m=400):
    best, name = max_m, None
    for nm, line in roads:
        for a, b in zip(line, line[1:]):
            if abs(a[1] - lat) > 0.01 and abs(b[1] - lat) > 0.01:
                continue
            d = _seg_dist_m(lat, lng, a, b)
            if d < best:
                best, name = d, nm
    return name


def _river_m(lat, lng, river):
    return min((_seg_dist_m(lat, lng, a, b) for line in river for a, b in zip(line, line[1:])), default=1e9)


SOI = re.compile(r"\b(sukhumvit|silom|sathorn|ratchadamri|phetchaburi|charoen krung|ploenchit|rama \w+)\s*(?:soi\s*)?(\d{1,3})\b")


def _street(tags, name, lat, lng, roads):
    s = tags.get("addr:street")
    if s and _latin(s) and "," not in s and len(s) < 40:
        return s, "osm"
    m = SOI.search(norm(name))
    if m:
        return f"{m.group(1).title()} Soi {m.group(2)}", "name"
    if s and _latin(s):
        return s.split(",")[0].strip(), "osm"
    r = _nearest_road(lat, lng, roads)
    return (r, "nearest_road") if r else (None, "none")


# ------------------------------------------------------------------ curation
def curate(rng: np.random.Generator):
    raw = json.loads((config.RAW_OSM / "hotels_raw.json").read_text(encoding="utf-8"))["elements"]
    bm = _basemap()
    districts = _district_rings(bm)
    roads = [(f["properties"]["name"], f["geometry"]["coordinates"]) for f in bm["features"]
             if f["properties"].get("layer") == "road" and f["properties"].get("name") and f["properties"].get("class") != "motorway"
             and "expressway" not in f["properties"]["name"].lower()]
    river = [f["geometry"]["coordinates"] for f in bm["features"] if f["properties"].get("layer") == "river"]

    cands = []
    for el in raw:
        t = el.get("tags", {})
        c = el.get("center") or el
        name = t.get("name:en") or t.get("name")
        if not name or "lat" not in c or not _latin(name) or t.get("tourism") != "hotel":
            continue
        richness = sum(k in t for k in ("phone", "contact:phone", "website", "stars", "brand", "addr:street", "addr:postcode", "rooms"))
        cands.append({"osm_id": f"{el['type']}/{el['id']}", "name": name.strip(), "lat": c["lat"], "lng": c["lon"], "tags": t,
                      "richness": richness, "n": norm(name)})

    # 1. collapse OSM's own duplicates (same name within OSM_DUP_M)
    cands.sort(key=lambda x: (-x["richness"], x["osm_id"]))
    kept, dups = [], []
    for x in cands:
        twin = next((k for k in kept if abs(k["lat"] - x["lat"]) < 0.003 and (
            (fuzz.token_sort_ratio(k["n"], x["n"]) >= 92 and haversine_m(k["lat"], k["lng"], x["lat"], x["lng"]) < OSM_DUP_M)
            # same distinctive words, practically the same spot ("Coach Boutique Hotel" / "The Coach Hotel", 29 m; "Windsor Suites" / "... Hotel", 61 m;
            # found by the M3 matcher, which kept merging them)
            or (_core(k["n"]) and _core(k["n"]) == _core(x["n"]) and haversine_m(k["lat"], k["lng"], x["lat"], x["lng"]) < 120))), None)
        if twin:
            dups.append({"kept": twin["osm_id"], "dropped": x["osm_id"], "name_kept": twin["name"], "name_dropped": x["name"],
                         "distance_m": round(haversine_m(twin["lat"], twin["lng"], x["lat"], x["lng"]))})
        else:
            kept.append(x)

    for x in kept:
        x["family"] = family(x["name"], x["tags"].get("brand"))

    # 2. hard negatives: same brand family, different real hotels, under 3 km apart
    pairs = []
    for i, a in enumerate(kept):
        for b in kept[i + 1:]:
            if a["family"] and a["family"] == b["family"]:
                d = haversine_m(a["lat"], a["lng"], b["lat"], b["lng"])
                if d < HARD_NEG_MAX_M:
                    pairs.append((a["osm_id"], b["osm_id"], d, fuzz.token_set_ratio(a["n"], b["n"])))
    pairs.sort(key=lambda p: (-p[3], p[2]))           # most confusable first

    # 3. pick ~TARGET: everything near the demo area, the most confusable hard-negative pairs, then by score
    by_id = {x["osm_id"]: x for x in kept}
    must = {x["osm_id"] for x in kept if haversine_m(*ASOK, x["lat"], x["lng"]) < ASOK_KEEP_M}
    for a, b, _, _ in pairs[:40]:
        must |= {a, b}
    rest = sorted((x for x in kept if x["osm_id"] not in must),
                  key=lambda x: -(x["richness"] + 2 * bool(x["family"]) - haversine_m(*CORE, x["lat"], x["lng"]) / 2500
                                  + rng.random() * 0.5))
    chosen = [by_id[i] for i in sorted(must)] + rest[:max(0, TARGET - len(must))]
    chosen_ids = {x["osm_id"] for x in chosen}

    hotels = []
    for x in sorted(chosen, key=lambda x: x["osm_id"]):
        t = x["tags"]
        stars_osm = t.get("stars")
        if stars_osm and re.fullmatch(r"\d(\.\d)?", stars_osm):
            star, star_src = int(float(stars_osm)), "osm"
        elif x["family"] in BRAND_STARS:
            star, star_src = BRAND_STARS[x["family"]], "brand"
        else:
            small = re.search(r"\b(inn|guest ?house|hostel|lodge|mansion|place|house|home|room|rooms|bed)\b", x["n"])
            star, star_src = int(rng.choice([2, 2, 3, 3] if small else [3, 3, 3, 4, 4, 4, 5])), "synthetic"
        star = min(max(star, 2), 5)
        phone = t.get("phone") or t.get("contact:phone")
        if phone:
            digits = re.sub(r"\D", "", phone.split(";")[0])
            digits = (digits[2:] if digits.startswith("66") else digits).lstrip("0")
            phone_src = "osm"
        else:
            digits = "2" + "".join(str(d) for d in rng.integers(0, 10, 7))
            phone_src = "synthetic"
        phone = f"+66 {digits[0]} {digits[1:4]} {digits[4:]}" if len(digits) == 8 else f"+66 {digits[:2]} {digits[2:5]} {digits[5:]}"
        street, street_src = _street(t, x["name"], x["lat"], x["lng"], roads)
        district = next((n for n, segs in districts if _inside(x["lat"], x["lng"], segs)), None)
        river_m = _river_m(x["lat"], x["lng"], river)
        pool = bool(rng.random() < {2: 0.1, 3: 0.45, 4: 0.85, 5: 0.97}[star])
        rooms = int(t["rooms"]) if str(t.get("rooms", "")).isdigit() else int(rng.integers(40, 120) * star / 3)
        family_rooms = bool(rng.random() < (0.55 if pool else 0.25) + (0.1 if star >= 4 else 0))
        # nightly base rate (INR, standard room, 2 adults): star level x centrality x lognormal noise. Synthetic.
        centr = np.exp(-haversine_m(*CORE, x["lat"], x["lng"]) / 9000)
        rate = {2: 1500, 3: 2900, 4: 5400, 5: 9800}[star] * (0.8 + 0.4 * centr) * float(np.exp(rng.normal(0, 0.18)))
        hotels.append({
            "hotel_id": "h-" + x["osm_id"].replace("/", "-"), "osm_id": x["osm_id"], "name": x["name"],
            "lat": round(x["lat"], 6), "lng": round(x["lng"], 6), "family": x["family"], "brand": t.get("brand"),
            "star": star, "star_source": star_src, "phone": phone, "phone_source": phone_src,
            "street": street, "street_source": street_src, "house_number": t.get("addr:housenumber") if _latin(t.get("addr:housenumber", "x")) else None,
            "postcode": t.get("addr:postcode"), "district": district, "website": t.get("website"),
            "river_m": round(river_m), "pool": pool, "family_rooms": family_rooms, "room_count": rooms,
            "base_rate": round(rate, -1), "checkin_time": str(rng.choice(["14:00", "14:00", "14:00", "15:00", "13:00"])),
        })
    hard = [{"a": "h-" + a.replace("/", "-"), "b": "h-" + b.replace("/", "-"), "distance_m": round(d), "name_sim": s}
            for a, b, d, s in pairs if a in chosen_ids and b in chosen_ids]
    return hotels, dups, hard


def reference() -> list[dict]:
    """Real OSM fields for every named hotel in the snapshot, unmodified: the public reference data the app may
    look a matched hotel up in (address in whatever script OSM has it, phone, website, stars)."""
    raw = json.loads((config.RAW_OSM / "hotels_raw.json").read_text(encoding="utf-8"))["elements"]
    out = []
    for el in raw:
        t = el.get("tags", {})
        c = el.get("center") or el
        name = t.get("name:en") or t.get("name")
        if not name or "lat" not in c:
            continue
        addr = ", ".join(t[k] for k in ("addr:housenumber", "addr:street", "addr:subdistrict", "addr:district", "addr:postcode") if t.get(k))
        out.append({"osm_id": f"{el['type']}/{el['id']}", "name": name, "lat": c["lat"], "lng": c["lon"], "address": addr or None,
                    "phone": t.get("phone") or t.get("contact:phone"), "website": t.get("website") or t.get("contact:website"),
                    "stars": t.get("stars")})
    return out
