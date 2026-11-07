"""Gap Remixes: products agents search for that no supplier sells as one product, assembled from parts.

A gap is a ticket that is sold on its own (its Variant DNA read from the supplier's text) combined with a
hotel pickup that agents asked for, where no packaged variant at that attraction is that product (by the same
SAME rule the engine uses). Demand is the number of agent searches in the last 90 days that ask for
exactly that: same attraction, same pickup wish, and every ticked filter present in the product's DNA.

There is no package to beat, so the comparison is what the agent does today: buy the ticket (best ticket-only
package on True Price) and book the transfers themselves, carrying their risk and two extra bookings of
friction. Pricing and guardrails are the catalogue Remix's: the agent gets their share of the gap between that
do-it-yourself True Price and TBO's expected cost, and the same saving / margin / Promise floors apply.
"""
from collections import Counter
from dataclasses import asdict
from functools import lru_cache

from samesame import config, store
from samesame.data.components import HOTEL_PICKUPS
from samesame.pricing import true_price as tp
from samesame.remix import engine as E

GAP_MIN_DEMAND = 10          # searches in 90 days before a gap is worth building
DIY_FRICTION = config.FAILOVER_FRICTION_INR   # per extra booking the agent makes and manages


def _short(name: str) -> str:
    return name.split(" (")[0].split(",")[0]


def _events():
    return store.get().search_events


def specs() -> list[dict]:
    st = store.get()
    out = {}
    for c in st.components.values():
        if c["role"] != "ticket":
            continue
        for pickup in HOTEL_PICKUPS:
            spec = {k: v for k, v in c["dna"].items() if k != "duration"}
            spec["pickup"] = pickup
            spec["cancel"] = c["cancel"]
            key = (c["attraction_id"], tuple(sorted(spec.items())))
            out.setdefault(key, {"attraction_id": c["attraction_id"], "dna": spec})
    return list(out.values())


def sold_as_package(aid: str, spec: dict) -> str | None:
    for v in store.get().variants_of.get(aid, []):
        diffs, _ = E.compare(v["dna"], spec)
        if not diffs:
            return v["variant_id"]
    return None


def demand(aid: str, spec: dict) -> int:
    values = set(spec.values())
    return sum(1 for e in _events() if e["attraction_id"] == aid and e["pickup"] == spec["pickup"] and set(e["filters"]) <= values)


@lru_cache(maxsize=16)
def find(s: E.Settings = E.Settings()) -> list[dict]:
    st = store.get()
    out = []
    for g in specs():
        aid, spec = g["attraction_id"], g["dna"]
        if sold_as_package(aid, spec):
            continue
        n = demand(aid, spec)
        if n < GAP_MIN_DEMAND:
            continue
        name = " · ".join([x for x in (spec.get("option"), spec.get("access") if spec.get("access") not in ("Standard", spec.get("option")) else None,
                                       spec.get("meals") if spec.get("meals") != "No meals" else None, spec["pickup"]) if x])
        t = {"variant_id": f"gap:{aid}:{len(out) + 1}", "attraction_id": aid, "attraction": st.attractions[aid]["name"], "name": name,
             "dna": spec, "members": [], "ambiguous": False}
        out.append(build(t, n, s))
    return sorted(out, key=lambda r: (r["status"] != "ready", -r["demand"]))


def _ticket_package(t: dict, s: E.Settings):
    """The best package selling just the ticket at this attraction: what the agent would buy today."""
    st = store.get()
    best = None
    for v in st.variants_of.get(t["attraction_id"], []):
        if v["dna"]["pickup"] in HOTEL_PICKUPS or v.get("ambiguous"):
            continue
        diffs, _ = E.compare(v["dna"], {**t["dna"], "pickup": v["dna"]["pickup"]})
        if diffs:
            continue
        p = E.packaged({**v, "members": st.act_listings_of.get(v["variant_id"], [])}, s)
        if p and (best is None or p["true_price"].total < best["true_price"].total):
            best = {**p, "variant_id": v["variant_id"]}
    return best


def build(t: dict, n: int, s: E.Settings) -> dict:
    base = {"variant_id": t["variant_id"], "attraction_id": t["attraction_id"], "attraction": t["attraction"], "name": t["name"],
            "target_dna": t["dna"], "settings": asdict(s), "demand": n, "gap": True}
    found = E.search(t, s)
    if not found["assemblies"]:
        why = sorted(found["reasons"].items(), key=lambda kv: -kv[1])
        return {**base, "status": "not_remixable", "reasons": [k for k, _ in why[:3]]}
    priced = []
    for a in found["assemblies"]:
        parts = E._parts_of(t, a, s)
        priced.append((E.price_parts(parts, s), a, parts))
    ok = [x for x in priced if x[0]["p_all"] >= s.min_promise]
    pr, a, parts = min(ok or priced, key=lambda x: (x[0]["cost"], x[1]["slot"]))
    assembled = {**a["ticket"]["dna"], "pickup": t["dna"]["pickup"], "cancel": E.strictest([p.cancel for p in parts]),
                 "meals": "Lunch" if a["lunch"] is not None else a["ticket"]["dna"]["meals"]}
    diffs, unverified = E.compare(t["dna"], assembled)
    assert not diffs, diffs
    refund = E._svc()._refund_days(assembled["cancel"])
    zero = tp.Risk("TBO", 0, 0, 0, 0)
    sticker = sum(p.price for p in parts)
    assembly = (1 - pr["p_all"]) * config.FAILOVER_FRICTION_INR * len(parts)
    cost = pr["cost"] + assembly

    # what the agent does today: buy the ticket, book two cars, carry the risk and the friction
    pkg = _ticket_package(t, s)
    ticket_tp = pkg["true_price"].total if pkg else next(x["true_price"].total for x in pr["parts"] if x["leg"] == "ticket")
    transfers = [x for x in pr["parts"] if x["role"] == "transfer"]
    diy = ticket_tp + sum(x["true_price"].total + DIY_FRICTION for x in transfers)

    def agent_tp(sell):
        return tp.compute(sell, set(), [], s.lead_days, refund, None, zero, sell)

    gap = diy - agent_tp(cost).total
    unit = agent_tp(1000.0).total / 1000.0
    sell = (diy - s.agent_share * gap) / unit
    agent = agent_tp(sell)
    saving = (diy - agent.total) / diy
    margin = (sell - cost) / sell
    start, finish = min(p.start for p in parts), max(p.end for p in parts)
    blocks = []
    if gap <= 0:
        blocks.append(f"booking it piece by piece is cheaper on True Price by {tp.inr(-gap)}")
    else:
        if saving < s.min_saving:
            blocks.append(f"agent saves {saving:.1%} vs booking it piece by piece, below the {s.min_saving:.0%} guardrail")
        if margin < s.min_margin:
            blocks.append(f"TBO margin {margin:.1%}, below the {s.min_margin:.0%} guardrail")
    if pr["p_all"] < s.min_promise:
        blocks.append(f"Remix Promise {pr['p_all']:.1%}, below the {s.min_promise:.0%} guardrail")
    return {**base, "status": "blocked" if blocks else "ready",
            "reasons": blocks or [f"nobody sells this; {n} agent searches in 90 days asked for it"],
            "assembled_dna": assembled, "unverified": unverified, "parts": pr["parts"], "sticker": round(sticker, 2),
            "assembly_risk": {"amount": round(assembly, 2), "assumption": f"{1 - pr['p_all']:.1%} chance a part can't be secured; TBO refunds and apologises (friction per part)"},
            "tbo_cost": round(cost, 2), "promise": round(pr["p_all"], 4), "p_clean": round(pr["p_clean"], 4), "cancel": assembled["cancel"],
            "timeline": {"start": E.hhmm(start), "end": E.hhmm(finish), "door_to_door_h": round((finish - start) / 60, 1),
                         "slot": E.hhmm(a["slot"]), "slack_min": min(p.start for p in parts if p.leg == "ticket") - a["out_win"][1]},
            "suppliers": sorted({p.supplier_id for p in parts}), "sell": round(sell, 2), "agent_true_price": agent,
            "margin": round(margin, 4), "margin_inr": round(sell - cost, 2), "gap": round(gap, 2),
            "diy": {"total": round(diy, 2), "ticket": round(ticket_tp, 2), "ticket_from": pkg["title"] if pkg else "the ticket part",
                    "transfers": round(sum(x["true_price"].total for x in transfers), 2), "friction": DIY_FRICTION * len(transfers)},
            "agent_saving": round(saving, 4), "agent_saving_inr": round(diy - agent.total, 2), "packaged": None}


def summary_counts(s: E.Settings = E.Settings()) -> dict:
    rs = find(s)
    return {"gaps": len(rs), **Counter(r["status"] for r in rs)}
