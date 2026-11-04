"""Spot the Twin: the human review queue, built from what the matcher was NOT sure about.

- hotel pairs in the gray zone (p between the review floor and the auto-merge bar), most likely merge
  first; then pairs the model was sure about but a never-merge rule blocked. One item per pair of clusters;
- room names mapped with low confidence (view borrowed from a sibling name);
- sightseeing listings that fit more than one variant.
Labels are appended to config.LABELS_PATH with both listing ids. The next build uses them as training
labels (they override the generator) and as must-link / cannot-link constraints in clustering.
"""
import hashlib
import json
from datetime import datetime
from functools import lru_cache

import polars as pl

from samesame import config, store
from samesame.data.world import SUPPLIERS
from samesame.ranking.score import haversine_m
from samesame.schemas import ImageRef, ReviewItem, ReviewSide

LABEL = {"S": "SAME", "V": "VARIANT", "D": "DIFFERENT"}


def _pid(kind, a, b):
    return "rv-" + hashlib.md5(f"{kind}|{a}|{b}".encode()).hexdigest()[:8]


def _img(owner: str):
    ims = store.get().images_of.get(owner)
    return ImageRef(url=f"/api/images/{ims[0]['path']}", illustrative=True, source="generated") if ims else None


def _hotel_side(lid: str) -> ReviewSide:
    l = store.get().listings[lid]
    return ReviewSide(id=lid, supplier=SUPPLIERS[l["supplier_id"]], title=l["name"], image=_img(lid),
                      fields={"Address": l["address"] or "—", "Phone": l["phone"] or "—", "Stars": f"{l['star']:g}★" if l["star"] else "—",
                              "Lat/Lng": f"{l['lat']:.4f}, {l['lng']:.4f}"})


@lru_cache
def _items() -> tuple[list[ReviewItem], dict]:
    s = store.get()
    auto, gray = s.matcher["auto_merge"], s.matcher["gray_low"]
    items, keys = [], {}
    q = s.pairs.filter(pl.col("decision").is_in(["gray", "blocked"])).with_columns(
        (pl.col("decision") == "blocked").alias("_blocked")).sort(["_blocked", "p"], descending=[False, True])
    seen = set()
    for r in q.iter_rows(named=True):
        a, b = r["a"], r["b"]
        ck = frozenset((s.cluster_of[a], s.cluster_of[b]))
        if len(ck) == 1 or ck in seen:
            continue                                             # joined anyway, or this cluster pair is already queued
        seen.add(ck)
        la, lb = s.listings[a], s.listings[b]
        d = haversine_m(la["lat"], la["lng"], lb["lat"], lb["lng"])
        phone = {1: "Same phone", -1: "Different phones", 0: "Phone missing on one side"}[int(r["phone_match"])]
        reasons = [f"Name similarity {r['name_set']:.0%}", f"{d:,.0f} m apart", phone]
        if r["decision"] == "blocked":
            reasons.append(f"Blocked by a never-merge rule: {r['reason']}")
            routed = "constraint_block"
        else:
            reasons.append(f"Model p(SAME) {r['p']:.3f}: above the {gray:.3f} review floor, below the {auto:.4f} auto-merge bar")
            routed = "gray_zone"
        pid = _pid("hotel", a, b)
        keys[pid] = ("hotel", a, b)
        items.append(ReviewItem(pair_id=pid, entity_type="hotel", left=_hotel_side(a), right=_hotel_side(b), model_p=round(r["p"], 4),
                                model_relation="SAME", routed_by=routed, reasons=reasons))
    # rooms whose view had to be borrowed: pair them with the sibling that states it
    rooms = [r for r in s.supplier_rooms.values() if r["note"]]
    for r in sorted(rooms, key=lambda r: (r["confidence"], r["supplier_room_id"]))[:15]:
        sib = next((x for x in s.supplier_rooms.values() if x["room_id"] == r["room_id"] and not x["note"]
                    and x["listing_id"] != r["listing_id"]), None)
        if not sib:
            continue
        hotel = store.get().listings[r["listing_id"]]["name"]
        pid = _pid("room", r["supplier_room_id"], sib["supplier_room_id"])
        keys[pid] = ("room", r["supplier_room_id"], sib["supplier_room_id"])
        items.append(ReviewItem(pair_id=pid, entity_type="room", model_p=r["confidence"], model_relation="SAME", routed_by="gray_zone",
                                left=ReviewSide(id=r["supplier_room_id"], supplier=SUPPLIERS[r["supplier_id"]], title=r["raw_name"], fields={"Hotel": hotel}),
                                right=ReviewSide(id=sib["supplier_room_id"], supplier=SUPPLIERS[sib["supplier_id"]], title=sib["raw_name"],
                                                 fields={"Hotel": s.listings[sib["listing_id"]]["name"]}),
                                reasons=[r["note"], f"Parser confidence {r['confidence']:.2f}"]))
    # sightseeing listings that fit two variants
    for v in (v for vs in s.variants_of.values() for v in vs if v["ambiguous"]):
        m = s.act_listings_of[v["variant_id"]][0]
        others = [o for x in s.variants_of[v["attraction_id"]] if x["variant_id"] != v["variant_id"] and not x["ambiguous"]
                  for o in s.act_listings_of[x["variant_id"]][:1]]
        for o in others[:2]:
            pid = _pid("activity", m["listing_id"], o["listing_id"])
            keys[pid] = ("activity", m["listing_id"], o["listing_id"])
            items.append(ReviewItem(pair_id=pid, entity_type="activity", model_p=0.5, model_relation="SAME", routed_by="gray_zone",
                                    left=ReviewSide(id=m["listing_id"], supplier=SUPPLIERS[m["supplier_id"]], title=m["title"], fields={"Description": m["description"]}),
                                    right=ReviewSide(id=o["listing_id"], supplier=SUPPLIERS[o["supplier_id"]], title=o["title"], fields={"Description": o["description"]}),
                                    reasons=["Listing doesn't state the option it sells; it fits more than one variant", "Kept apart (precision first) until a human decides"]))
    return items, keys


def _events() -> list[dict]:
    if not config.LABELS_PATH.exists():
        return []
    return [json.loads(l) for l in config.LABELS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]


def _active() -> list[dict]:
    """Label events not undone, oldest first."""
    undone = {e["audit_id"] for e in _events() if e.get("action") == "undo"}
    return [e for e in _events() if e.get("action") == "label" and e["audit_id"] not in undone]


def queue() -> list[ReviewItem]:
    items, _ = _items()
    done = {e["pair_id"] for e in _active()}
    return [it for it in items if it.pair_id not in done]


def label(pair_id: str, lab: str, reviewer: str) -> dict:
    items, keys = _items()
    kind, a, b = keys[pair_id]
    truth = store.world_relation(kind, a, b)
    item = next(it for it in items if it.pair_id == pair_id)
    entry = {"audit_id": f"au-{len(_events()) + 1}", "pair_id": pair_id, "entity_type": kind, "left": a, "right": b, "label": lab,
             "reviewer": reviewer, "truth": truth, "correct": LABEL[lab] == truth}
    _append({**entry, "action": "label"})
    streak = 0
    for x in reversed(_active()):
        if not x["correct"]:
            break
        streak += 1
    return {**entry, "streak": streak, "model_was_right": item.model_relation == truth}


def undo(audit_id: str) -> bool:
    if any(e["audit_id"] == audit_id for e in _active()):
        _append({"audit_id": audit_id, "action": "undo"})
        return True
    return False


def audit_log() -> list[dict]:
    undone = {e["audit_id"] for e in _events() if e.get("action") == "undo"}
    return [{**e, "undone": e["audit_id"] in undone} for e in reversed(_events()) if e.get("action") == "label"]


def _append(row: dict):
    config.LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.LABELS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({**row, "ts": datetime.now().isoformat(timespec="seconds")}) + "\n")
