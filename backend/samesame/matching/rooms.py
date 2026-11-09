"""Room mapping: parse each supplier's room name into (tier, bed, view) and group within a hotel cluster.

Rules only (the LLM fallback for unparseable names is M6). Confidence reflects how much of the name
had to be inferred: 1.0 every attribute spelt out, lower for abbreviations and for a missing view
that had to be borrowed from the only matching room that states one.
"""
import re
import unicodedata

TIERS = [("junior suite", "Junior Suite"), ("jr ste", "Junior Suite"), ("suite", "Suite"), ("ste", "Suite"),
         ("executive", "Executive"), ("exec", "Executive"), ("premier", "Premier"), ("prem", "Premier"),
         ("deluxe", "Deluxe"), ("dlx", "Deluxe"), ("superior", "Superior"), ("sup", "Superior"),
         ("standard", "Standard"), ("std", "Standard"), ("family", "Family"), ("fam", "Family")]
BEDS = [("2 twin", "Twin"), ("twin", "Twin"), ("twn", "Twin"), ("1 king", "King"), ("king", "King"), ("1kg", "King"),
        ("kg", "King"), ("double", "King"), ("dbl", "King")]
VIEWS = [("city", "City"), ("cv", "City"), ("pool", "Pool"), ("pv", "Pool"), ("river", "River"), ("rv", "River"),
         ("creek", "Creek"), ("ck", "Creek"),
         ("garden", "Garden"), ("gv", "Garden")]
ABBREV = {"jr ste", "ste", "exec", "prem", "dlx", "sup", "std", "fam", "twn", "1kg", "kg", "dbl", "cv", "pv", "rv", "ck", "gv"}


# words that describe a room; a hotel name that ends in one ("Landmark Premier") keeps it in the room name
ROOM_WORDS = {w for table in (TIERS, BEDS, VIEWS) for k, _ in table for w in k.split()} | {"room", "rm", "jr", "view", "bed", "beds"}
ONLY_HOTEL_CONFIDENCE = 0.3


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


def strip_hotel(raw: str, hotel_names: list[str]) -> tuple[str, str | None]:
    """Remove the hotel's own name from the start or end of a room name: "Hyatt Place Superior King", "HP SUP KG".

    hotel_names: every way this hotel is written (all listings in its cluster), so "Hyatt Place" is recognised even
    in a short-code listing's rooms. Returns the room words and what was removed (None if nothing)."""
    names = {t for n in hotel_names for t in _norm(n).split()}
    toks = _norm(raw).split()
    i = 0
    while i < len(toks) - 1 and toks[i] in names:
        i += 1
    while i and toks[i - 1] in ROOM_WORDS:                 # "Premier Inn Standard" strips both; "Premier King" strips nothing
        i -= 1
    j = len(toks)
    while j > i + 1 and toks[j - 1] in names:
        j -= 1
    while j < len(toks) and toks[j] in ROOM_WORDS:
        j += 1
    removed = " ".join(toks[:i] + toks[j:])
    return " ".join(toks[i:j]), (removed or None)


def _find(text, table):
    for k, v in table:
        if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", text):
            return k, v
    return None, None


def parse(raw: str) -> dict:
    t = re.sub(r"[^a-z0-9 ]+", " ", raw.lower())
    t = re.sub(r"\s+", " ", t).strip()
    tk, tier = _find(t, TIERS)
    if tier == "Family":
        return {"tier": "Family", "bed": "King + 2 Single", "view": None, "max_occupancy": 4,
                "confidence": 0.9 if tk in ABBREV or re.search(r"2a|2c|2 2|sgl", t) else 0.95}
    bk, bed = _find(t, BEDS)
    vk, view = _find(t, VIEWS)
    if vk in ("cv", "pv", "rv", "ck", "gv") and not re.search(r"\b(dlx|sup|exec|prem|std|kg|twn)\b", t):
        vk, view = None, None                                 # a bare "pv" outside abbreviation style is too risky
    conf = 1.0
    for k in (tk, bk, vk):
        if k in ABBREV:
            conf -= 0.04
    if tier is None or bed is None:
        conf = 0.4
    return {"tier": tier, "bed": bed, "view": view, "max_occupancy": 2, "confidence": round(conf, 2)}


def parse_in_hotel(raw: str, hotel_names: list[str]) -> dict:
    """parse() after removing the hotel's name. A name that is only the hotel ("Hyatt Place Room") can't be mapped."""
    text, removed = strip_hotel(raw, hotel_names)
    a = parse(text)
    a["hotel_words"] = removed
    if removed and a["tier"] is None and a["bed"] is None:
        a["confidence"] = ONLY_HOTEL_CONFIDENCE
        a["note"] = f"names only the hotel ('{raw}'): a person picks the room"
    return a


def map_rooms(cluster_rooms: dict[str, list[dict]], hotel_names: dict[str, list[str]] | None = None) -> list[dict]:
    """cluster_rooms: cluster_id -> [supplier_room rows]; hotel_names: cluster_id -> every listing name in it.
    Returns supplier_room_id -> canonical room assignment rows."""
    out = []
    for cid, rows in cluster_rooms.items():
        parsed = [(r, parse_in_hotel(r["raw_name"], (hotel_names or {}).get(cid, []))) for r in rows]
        stated = {}
        for _, a in parsed:
            if a["view"]:
                stated.setdefault((a["tier"], a["bed"]), set()).add(a["view"])
        for r, a in parsed:
            view, conf, note = a["view"], a["confidence"], a.get("note")
            if view is None and len(stated.get((a["tier"], a["bed"]), ())) == 1:
                view = next(iter(stated[(a["tier"], a["bed"])]))
                conf, note = round(conf - 0.2, 2), f"view not stated; borrowed '{view}' from the only {a['tier']} {a['bed']} that states one"
            key = f"{a['tier'] or 'Unknown'}-{(a['bed'] or 'unknown').replace(' ', '')}-{view or 'none'}"
            if a["confidence"] == ONLY_HOTEL_CONFIDENCE and a.get("hotel_words"):
                # never pooled with another room: until a person picks, it is its own unmapped room
                key, name = f"unmapped-{r['supplier_room_id'].replace(':', '-')}", f"Room (unmapped: {r['raw_name']})"
            elif a["tier"] == "Family":
                name = "Family Room (2 + 2)"
            else:
                name = f"{a['tier'] or 'Room'} {a['bed'] or ''}".strip() + (f", {view} View" if view else "")
            out.append({"supplier_room_id": r["supplier_room_id"], "room_id": f"{cid}:{key}", "cluster_id": cid, "name": name,
                        "tier": a["tier"] or "Unknown", "bed": a["bed"] or "Unknown", "view": view,
                        "max_occupancy": a["max_occupancy"], "confidence": conf, "note": note})
    return out
