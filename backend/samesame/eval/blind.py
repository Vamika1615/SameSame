"""The blind evaluation set: ~150 pairs sampled ONLY from held-out families / attractions, frozen in
data/blind/pairs.jsonl the first time it is built and never regenerated (delete the file on purpose to
resample). Each pair stores what a human labeller sees plus the generator's label; C's own labels go to
data/blind/labels.jsonl through the labelling tool. Nothing in this module is imported by training.
"""
import itertools
import json
import random

import polars as pl

from samesame import config

PAIRS = config.BLIND / "pairs.jsonl"
LABELS = config.BLIND / "labels.jsonl"
N_HOTEL_SAME, N_HOTEL_DIFF, N_ROOM, N_ACT = 40, 40, 40, 30


def _rows(name):
    return pl.read_parquet(config.BUILD / f"{name}.parquet").to_dicts()


def hotel_side(l: dict) -> dict:
    return {"id": l["listing_id"], "supplier": l["supplier_id"].title(), "title": l["name"],
            "fields": {"Address": l["address"] or "—", "Phone": l["phone"] or "—", "Stars": f"{l['star']:g}★" if l["star"] else "—",
                       "Lat/Lng": f"{l['lat']:.4f}, {l['lng']:.4f}"}}


def room_side(r: dict, hotel_name: str) -> dict:
    return {"id": r["supplier_room_id"], "supplier": r["supplier_id"].title(), "title": r["raw_name"], "fields": {"Hotel listing": hotel_name}}


def act_side(a: dict) -> dict:
    return {"id": a["listing_id"], "supplier": a["supplier_id"].title(), "title": a["title"],
            "fields": {"Description": a["description"], "Price pp": f"₹{a['price_pp']:,.0f}"}}


def sample() -> list[dict]:
    rng = random.Random(config.SEED)
    base = {h["hotel_id"]: h for h in _rows("base_hotels")}
    hold = {h for h, b in base.items() if config.is_holdout(b["family"] or h)}
    truth = {t["listing_id"]: t["hotel_id"] for t in _rows("hotel_truth")}
    L = {l["listing_id"]: l for l in _rows("hotel_listings")}
    held = [lid for lid in L if truth[lid] in hold]
    out = []

    same = [(a, b) for a, b in itertools.combinations(sorted(held), 2) if truth[a] == truth[b]]
    for a, b in rng.sample(same, min(N_HOTEL_SAME, len(same))):
        out.append({"entity_type": "hotel", "left": hotel_side(L[a]), "right": hotel_side(L[b]), "generator_label": "SAME"})
    # hardest DIFFERENT pairs first: real look-alike families, then the most similar names among candidate pairs
    pairs = pl.read_parquet(config.BUILD / "hotel_pairs.parquet").to_dicts()
    diff = [p for p in pairs if truth[p["a"]] in hold and truth[p["b"]] in hold and truth[p["a"]] != truth[p["b"]]]
    hn = {frozenset((h["a"], h["b"])) for h in _rows("hard_negatives")}
    diff.sort(key=lambda p: (frozenset((truth[p["a"]], truth[p["b"]])) not in hn, -p["name_set"]))
    seen = set()
    for p in diff:
        key = frozenset((truth[p["a"]], truth[p["b"]]))
        if key in seen:
            continue
        seen.add(key)
        out.append({"entity_type": "hotel", "left": hotel_side(L[p["a"]]), "right": hotel_side(L[p["b"]]), "generator_label": "DIFFERENT",
                    "hard_negative": key in hn})
        if sum(1 for x in out if x["generator_label"] == "DIFFERENT") >= N_HOTEL_DIFF:
            break

    # rooms inside held-out hotels: SAME = same canonical room, VARIANT = same tier, otherwise DIFFERENT
    rt = {r["supplier_room_id"]: r["room_id"] for r in _rows("room_truth")}
    rooms = {r["room_id"]: r for r in _rows("rooms")}
    sr = [r for r in _rows("supplier_rooms") if truth[r["listing_id"]] in hold]
    by_h: dict = {}
    for r in sr:
        by_h.setdefault(truth[r["listing_id"]], []).append(r)
    cand = [(a, b) for rs in by_h.values() for a, b in itertools.combinations(rs, 2) if a["supplier_id"] != b["supplier_id"]]
    rng.shuffle(cand)
    want = {"SAME": N_ROOM // 2, "VARIANT": N_ROOM // 4, "DIFFERENT": N_ROOM // 4}
    for a, b in cand:
        ra, rb = rooms[rt[a["supplier_room_id"]]], rooms[rt[b["supplier_room_id"]]]
        lab = "SAME" if ra["room_id"] == rb["room_id"] else "VARIANT" if ra["tier"] == rb["tier"] else "DIFFERENT"
        if want[lab] > 0:
            want[lab] -= 1
            out.append({"entity_type": "room", "left": room_side(a, L[a["listing_id"]]["name"]), "right": room_side(b, L[b["listing_id"]]["name"]),
                        "generator_label": lab})

    # activities: held-out attractions first; the rules were not fitted, but see the caveat in the report
    at = {t["listing_id"]: t for t in _rows("activity_truth")}
    acts = _rows("activity_listings")
    held_a = [a for a in acts if config.is_holdout(at[a["listing_id"]]["attraction_id"])]
    pool = held_a if len(held_a) >= 12 else acts
    cand = [(a, b) for a, b in itertools.combinations(pool, 2)
            if at[a["listing_id"]]["attraction_id"] == at[b["listing_id"]]["attraction_id"]]
    rng.shuffle(cand)
    want = {"SAME": N_ACT // 2, "VARIANT": N_ACT - N_ACT // 2}
    for a, b in cand:
        lab = "SAME" if at[a["listing_id"]]["variant_id"] == at[b["listing_id"]]["variant_id"] else "VARIANT"
        if want[lab] > 0:
            want[lab] -= 1
            out.append({"entity_type": "activity", "left": act_side(a), "right": act_side(b), "generator_label": lab,
                        "held_out_attraction": pool is held_a})
    for i, x in enumerate(out, 1):
        x["pair_id"] = f"b{i:03d}"
    return out


def ensure() -> list[dict]:
    """Load the frozen blind set, creating it once if it doesn't exist."""
    if not PAIRS.exists():
        config.BLIND.mkdir(parents=True, exist_ok=True)
        rows = sample()
        PAIRS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return [json.loads(l) for l in PAIRS.read_text(encoding="utf-8").splitlines() if l.strip()]


def human_labels() -> dict[str, str]:
    """Latest label per pair from the labelling tool (later lines win)."""
    out = {}
    if LABELS.exists():
        for line in LABELS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["pair_id"]] = r["label"]
    return out
