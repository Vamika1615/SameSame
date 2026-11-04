"""Placeholders that stay MOCK until their milestone: the review queue (M3 replaces it with the
matcher's gray-zone pairs) and the simulator (M5 replaces it with the 50,000-session Monte-Carlo).
The UI labels both as mock. Review labels are still appended to config.LABELS_PATH for the M3 retrain.
"""
import json
from datetime import datetime

from samesame import config
from samesame.data.world import SUPPLIERS
from samesame.ranking import score as rk
from samesame.schemas import ImageRef, ReviewItem, ReviewSide, SimArm, SimParams, SimResult


def _img(kind: str, key: str) -> ImageRef:
    return ImageRef(url=f"/api/img/{kind}/{key}.svg", illustrative=True, source="generated")


# ------------------------------------------------------------------ ops review queue (truth = generator label)
def _side(i, sup, title, fields, kind=None):
    return ReviewSide(id=i, supplier=SUPPLIERS[sup], title=title, fields=fields, image=_img(kind, i) if kind else None)


REVIEW = [
    (ReviewItem(pair_id="rv-1", entity_type="hotel", model_p=0.81, model_relation="SAME", routed_by="gray_zone",
                left=_side("kestrel:novotel-suk20", "kestrel", "NOVOTEL BKK SUKHUMVIT20", {"Address": "SUKHUMVIT SOI 20, BKK", "Phone": "+6620094999", "Stars": "3.5★", "Lat/Lng": "13.7315, 100.5643"}, "hotel"),
                right=_side("mynah:novotel-suk4", "mynah", "Novotel Bangkok Sukhumvit 4", {"Address": "Sukhumvit Soi 4, Bangkok", "Phone": "+66 2 659 2888", "Stars": "4★", "Lat/Lng": "13.7394, 100.5534"}, "hotel"),
                reasons=["Name similarity high (same brand + 'Sukhumvit')", "Model says SAME at 0.81, below the 0.90 auto-merge bar",
                         f"{rk.haversine_m(13.73152, 100.56428, 13.73936, 100.55335):,.0f} m apart: under the 1,500 m never-merge rule, so only the threshold saved it"]), "DIFFERENT"),
    (ReviewItem(pair_id="rv-2", entity_type="hotel", model_p=0.64, model_relation="SAME", routed_by="gray_zone",
                left=_side("kestrel:grand-mercure-asoke", "kestrel", "GRAND MERCURE ASOKE RESIDENCE", {"Address": "SUKHUMVIT 19", "Phone": "—", "Stars": "4★", "Lat/Lng": "13.7419, 100.5604"}, "hotel"),
                right=_side("bulbul:grand-mercure-asoke", "bulbul", "Grand Mercure Asoke Residence Bangkok", {"Address": "50/5 Sukhumvit 19, Bangkok", "Phone": "+66 2 204 1222", "Stars": "4★", "Lat/Lng": "13.7416, 100.5607"}, "hotel"),
                reasons=["Phone missing on one side", "38 m apart", "Gray zone 0.55-0.90"]), "SAME"),
    (ReviewItem(pair_id="rv-3", entity_type="hotel", model_p=0.66, model_relation="SAME", routed_by="constraint_block",
                left=_side("heron:holiday-inn-suk22", "heron", "Holiday Inn Sukhumvit 22 Bangkok", {"Address": "Sukhumvit Soi 22", "Brand": "Holiday Inn", "Stars": "4★"}, "hotel"),
                right=_side("sunbird:hix-suk11", "sunbird", "Holiday Inn Express Bangkok Sukhumvit 11", {"Address": "Sukhumvit Soi 11", "Brand": "Holiday Inn Express", "Stars": "3★"}, "hotel"),
                reasons=["Same parent chain", "Blocked: different sub-brand (never-merge rule)"]), "DIFFERENT"),
    (ReviewItem(pair_id="rv-4", entity_type="room", model_p=0.71, model_relation="SAME", routed_by="gray_zone",
                left=_side("bulbul:R2", "bulbul", "DLX TWN PV", {"Hotel": "Novotel Sukhumvit 20", "Bed": "2 twin (parsed)", "View": "PV → pool (parsed)"}),
                right=_side("mynah:R2", "mynah", "Deluxe Twin Pool View", {"Hotel": "Novotel Sukhumvit 20", "Bed": "2 twin", "View": "Pool"}),
                reasons=["Abbreviation expansion confidence 0.74"]), "SAME"),
    (ReviewItem(pair_id="rv-5", entity_type="room", model_p=0.58, model_relation="SAME", routed_by="gray_zone",
                left=_side("sunbird:R1cv", "sunbird", "Superior King City View", {"Hotel": "Novotel Sukhumvit 20", "Bed": "1 king", "View": "City"}),
                right=_side("heron:R1", "heron", "SUPERIOR KING", {"Hotel": "Novotel Sukhumvit 20", "Bed": "1 king", "View": "—"}),
                reasons=["View missing on one side"]), "VARIANT"),
    (ReviewItem(pair_id="rv-6", entity_type="activity", model_p=0.69, model_relation="SAME", routed_by="llm_unsure",
                left=_side("fm-rail-shared:mynah", "mynah", "Railway Market + Floating Market Half Day (Join-in)", {"Pickup": "Shared", "Meals": "—", "Duration": "6 h"}, "activity"),
                right=_side("fm-private-lunch:heron", "heron", "Private Floating & Railway Market Tour with Thai Lunch", {"Pickup": "Private", "Meals": "Lunch", "Duration": "8 h"}, "activity"),
                reasons=["Same stops", "Different pickup + meals + duration"]), "VARIANT"),
]
_labels: list[dict] = []


def review_queue() -> list[ReviewItem]:
    done = {x["pair_id"] for x in _labels if not x.get("undone")}
    return [it for it, _ in REVIEW if it.pair_id not in done]


def review_truth(pair_id: str) -> str:
    return next(t for it, t in REVIEW if it.pair_id == pair_id)


def label(pair_id: str, lab: str, reviewer: str) -> dict:
    truth = review_truth(pair_id)
    right = {"S": "SAME", "V": "VARIANT", "D": "DIFFERENT"}[lab] == truth
    entry = {"audit_id": f"au-{len(_labels) + 1}", "pair_id": pair_id, "label": lab, "reviewer": reviewer, "truth": truth, "correct": right}
    _labels.append(entry)
    _append_label({**entry, "action": "label"})
    streak = 0
    for x in reversed([x for x in _labels if not x.get("undone")]):
        if not x["correct"]:
            break
        streak += 1
    model = next(it for it, _ in REVIEW if it.pair_id == pair_id).model_relation
    return {**entry, "streak": streak, "model_was_right": model == truth}


def undo(audit_id: str) -> bool:
    for x in _labels:
        if x["audit_id"] == audit_id:
            x["undone"] = True
            _append_label({"audit_id": audit_id, "pair_id": x["pair_id"], "action": "undo"})
            return True
    return False


def _append_label(row: dict):
    """Append-only training feedback; the trainer replays label/undo events in order (M3)."""
    config.LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.LABELS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({**row, "ts": datetime.now().isoformat(timespec="seconds")}) + "\n")


def audit_log() -> list[dict]:
    return list(reversed(_labels))


# ------------------------------------------------------------------ simulator (placeholder until M5)
def simulate(p: SimParams) -> SimResult:
    """MOCK: closed-form stand-in with the same knobs as the M5 Monte-Carlo simulator."""
    fail_today = min(0.95, 0.11 * p.failure_scale)
    fail_ss = min(0.95, 0.035 * p.failure_scale)
    base = 0.30
    today_b = base * (1 - p.dup_abandon * 2.2) * (1 - fail_today) * (1 - 0.15 * p.price_sensitivity * 0.3)
    ss_b = base * (1 - p.dup_abandon * 0.3) * (1 - fail_ss)
    arms = [SimArm(arm="today", bookings_per_search=round(today_b, 4), failed_at_booking=round(fail_today, 4), avg_true_cost=22950),
            SimArm(arm="samesame", bookings_per_search=round(ss_b, 4), failed_at_booking=round(fail_ss, 4), avg_true_cost=21310)]
    return SimResult(params=p, arms=arms, lift_bookings_pct=round((ss_b / today_b - 1) * 100, 1),
                     failed_reduction_pct=round((1 - fail_ss / fail_today) * 100, 1),
                     note="MOCK closed-form placeholder; the 50,000-session simulator replaces this in M5.")
