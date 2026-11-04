"""Room mapping: parse each supplier's room name into (tier, bed, view) and group within a hotel cluster.

Rules only (the LLM fallback for unparseable names is M6). Confidence reflects how much of the name
had to be inferred: 1.0 every attribute spelt out, lower for abbreviations and for a missing view
that had to be borrowed from the only matching room that states one.
"""
import re

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


def map_rooms(cluster_rooms: dict[str, list[dict]]) -> list[dict]:
    """cluster_rooms: cluster_id -> [supplier_room rows]. Returns supplier_room_id -> canonical room assignment rows."""
    out = []
    for cid, rows in cluster_rooms.items():
        parsed = [(r, parse(r["raw_name"])) for r in rows]
        stated = {}
        for _, a in parsed:
            if a["view"]:
                stated.setdefault((a["tier"], a["bed"]), set()).add(a["view"])
        for r, a in parsed:
            view, conf, note = a["view"], a["confidence"], None
            if view is None and len(stated.get((a["tier"], a["bed"]), ())) == 1:
                view = next(iter(stated[(a["tier"], a["bed"])]))
                conf, note = round(conf - 0.2, 2), f"view not stated; borrowed '{view}' from the only {a['tier']} {a['bed']} that states one"
            key = f"{a['tier'] or 'Unknown'}-{(a['bed'] or 'unknown').replace(' ', '')}-{view or 'none'}"
            if a["tier"] == "Family":
                name = "Family Room (2 + 2)"
            else:
                name = f"{a['tier'] or 'Room'} {a['bed'] or ''}".strip() + (f", {view} View" if view else "")
            out.append({"supplier_room_id": r["supplier_room_id"], "room_id": f"{cid}:{key}", "cluster_id": cid, "name": name,
                        "tier": a["tier"] or "Unknown", "bed": a["bed"] or "Unknown", "view": view,
                        "max_occupancy": a["max_occupancy"], "confidence": conf, "note": note})
    return out
