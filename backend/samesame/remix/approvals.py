"""Remix approvals: the product/supply team approves a Remix before it is published.

Append-only log in config.REMIX_APPROVALS_PATH. Each decision snapshots what the approver saw (recipe,
suppliers, sell price, margin, Promise, cancellation, unverified fields), so a later rebuild can't silently
change what was approved: if the numbers move, the Remix goes back to the queue. Undo appends, never deletes.
"""
import json
import time
import uuid

from samesame import config
from samesame.remix import gaps
from samesame.remix import service as rs
from samesame.remix.engine import Settings


def _log() -> list[dict]:
    p = config.REMIX_APPROVALS_PATH
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def _append(row: dict):
    config.REMIX_APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with config.REMIX_APPROVALS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def snapshot(r: dict) -> dict:
    return {"recipe": [p["component_id"] for p in r["parts"]], "suppliers": r["suppliers"], "sell": r["sell"], "margin": r["margin"],
            "promise": r["promise"], "cancel": r["cancel"], "unverified": r.get("unverified") or []}


def candidates() -> list[dict]:
    """Every Remix that passes its guardrails at default settings: catalogue Remixes and gap Remixes."""
    s = Settings()
    return [r for r in rs.all_results(s) if r["status"] == "ready"] + [r for r in gaps.find(s) if r["status"] == "ready"]


def state() -> dict[str, dict]:
    """Latest live decision per Remix (undone decisions don't count)."""
    rows = _log()
    undone = {r["audit_id"] for r in rows if r["action"] == "undo"}
    out = {}
    for r in rows:
        if r["action"] == "decide" and r["audit_id"] not in undone:
            out[r["variant_id"]] = r
    return out


def queue() -> list[dict]:
    st = state()
    items = []
    for r in candidates():
        d = st.get(r["variant_id"])
        stale = d is not None and d["snapshot"] != snapshot(r)
        items.append({"variant_id": r["variant_id"], "remix": r, "decision": None if (d is None or stale) else d["decision"],
                      "decided": d, "stale": stale})
    return items


def published() -> set[str]:
    return {i["variant_id"] for i in queue() if i["decision"] == "approve"}


def decide(variant_id: str, decision: str, approver: str = "product team", note: str = "") -> dict:
    r = next((x for x in candidates() if x["variant_id"] == variant_id), None)
    if r is None:
        raise KeyError(variant_id)
    row = {"audit_id": uuid.uuid4().hex[:12], "action": "decide", "variant_id": variant_id, "decision": decision, "approver": approver,
           "note": note, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "snapshot": snapshot(r)}
    _append(row)
    return row


def undo(audit_id: str) -> dict:
    row = {"audit_id": audit_id, "action": "undo", "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _append(row)
    return row


def history() -> list[dict]:
    rows = _log()
    undone = {r["audit_id"] for r in rows if r["action"] == "undo"}
    return [{**r, "undone": r["audit_id"] in undone} for r in reversed(rows) if r["action"] == "decide"]
