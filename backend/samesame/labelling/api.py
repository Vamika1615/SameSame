"""Blind-set labelling tool (for C). Shows each frozen pair WITHOUT the model's score or the generator's
label, records S / V / D to data/blind/labels.jsonl. Re-labelling a pair appends; the latest line wins."""
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from samesame.eval import blind

router = APIRouter(prefix="/api/label")
DEFINITIONS = {
    "hotel": {"S": "The same property: you'd book the same building.", "V": "(not used for hotels)",
              "D": "Different properties, even if same brand or name."},
    "room": {"S": "Same room type: a client would get the same room.", "V": "Same tier, different bed or view.",
             "D": "Different tier or room category."},
    "activity": {"S": "Same product: same inclusions, timing and terms.", "V": "Same attraction, different inclusions or option.",
                 "D": "Different attraction."},
}


class Body(BaseModel):
    label: str
    labeller: str = "C"


def _public(p: dict) -> dict:
    return {"pair_id": p["pair_id"], "entity_type": p["entity_type"], "left": p["left"], "right": p["right"],
            "definitions": DEFINITIONS[p["entity_type"]]}


@router.get("/next")
def next_pair():
    pairs, done = blind.ensure(), blind.human_labels()
    todo = [p for p in pairs if p["pair_id"] not in done]
    return {"done": len(pairs) - len(todo), "total": len(pairs), "pair": _public(todo[0]) if todo else None}


@router.post("/{pair_id}")
def save(pair_id: str, body: Body):
    if body.label not in ("S", "V", "D"):
        raise HTTPException(400, "label must be S, V or D")
    if pair_id not in {p["pair_id"] for p in blind.ensure()}:
        raise HTTPException(404, f"no blind pair {pair_id}")
    blind.LABELS.parent.mkdir(parents=True, exist_ok=True)
    with open(blind.LABELS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"pair_id": pair_id, "label": body.label, "labeller": body.labeller,
                            "ts": datetime.now().isoformat(timespec="seconds")}) + "\n")
    return next_pair()
