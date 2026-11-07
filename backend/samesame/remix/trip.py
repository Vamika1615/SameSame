"""Connected Trip Remix: hotel + DXB airport transfers + a sightseeing Remix, sold as one product.

- Hotel: the offer ranked #1 on True Price for the search (the golden-case hotel), with its own failover twins.
- Airport transfers: arrival and departure between DXB and the hotel's zone, the cheapest bundleable private
  car for the party on TBO's expected cost.
- Activity: the publishable sightseeing Remix with the largest rupee saving from that zone.

Compared with what the agent does today: book the same hotel offer, two airport cars separately (their True
Price + friction per extra booking) and the activity's best package. Same pricing rule and guardrails as
every Remix: the agent keeps their share of the gap, TBO keeps the rest, one Promise and one cancellation rule.
"""
import random
import re
from dataclasses import asdict
from functools import lru_cache

from samesame import city, config, service, store
from samesame.booking import sandbox
from samesame.data import world
from samesame.pricing import true_price as tp
from samesame.ranking.score import haversine_m
from samesame.remix import book as rb
from samesame.remix import engine as E
from samesame.remix import service as rs

DIY_FRICTION = config.FAILOVER_FRICTION_INR


def hotel_zone(hid: str) -> str:
    g = service.golden(hid)
    return min((z for z in city.ZONES if z[0] != city.AIRPORT_ZONE), key=lambda z: haversine_m(g["lat"], g["lng"], z[2], z[3]))[0]


def _airport_part(zone: str, direction: str, start: int, s: E.Settings):
    """Cheapest private car (on TBO's expected cost) that clears the Promise floor, as the activity engine picks parts.
    Twins: every other supplier's smallest car that fits the party, as for activity transfers."""
    st = store.get()
    fits = [c for c in st.components.values() if c["meeting_point_id"] == "mp-dxb" and c["zone_id"] == zone and c["direction"] == direction
            and c["mode"] == "private" and c["max_pax"] >= s.pax and c["bundleable"] and c["cancel"] != "Non-refundable"]
    smallest = {}
    for c in fits:
        if c["supplier_id"] not in smallest or c["max_pax"] < smallest[c["supplier_id"]]["max_pax"]:
            smallest[c["supplier_id"]] = c
    pool = list(smallest.values())
    cands = []
    for c in pool:
        p = E._part(c, "arrival" if direction == "from" else "departure", start, start + int(c["travel_min"]), s, pool)
        cands.append((p, E.price_parts([p], s)))
    if not cands:
        return None
    ok = [x for x in cands if x[1]["p_all"] >= s.min_promise]
    return min(ok, key=lambda x: x[1]["cost"]) if ok else max(cands, key=lambda x: x[1]["p_all"])


@lru_cache(maxsize=8)
def build(s: E.Settings = E.Settings()) -> dict:
    hid = service.demo_hotel()
    zone = hotel_zone(hid)
    sz = E.with_zone(s, zone)
    offers = service.priced_offers(hid)
    hotel = min(offers, key=lambda o: o.true_rank)
    h_terms = {t.key: t.amount for t in hotel.true_price.terms}
    h_cost = hotel.true_price.total - h_terms["cancel_risk"]
    st = store.get()
    pool = [service._bookable(o) for o in st.offers_of[hid]]
    me = next(b for b in pool if b.offer_id == hotel.offer_id)
    chain = [service.risk(hotel.supplier_id, "hotel")] + [service.risk(service.NAME_TO_ID[t.supplier], "hotel") for t in sandbox.same_twins(me, pool)]
    h_secure = E._secure(chain)

    arrival = _airport_part(zone, "from", 14 * 60, sz)            # a typical afternoon landing (assumption, shown)
    departure = _airport_part(zone, "to", 10 * 60, sz)
    ready = [r for r in rs.all_results(sz) if r["status"] == "ready"]
    activity = max(ready, key=lambda r: r["agent_saving_inr"]) if ready else None
    base = {"hotel_id": hid, "zone": zone, "settings": asdict(sz)}
    if not (arrival and departure and activity):
        return {**base, "status": "not_remixable", "reasons": ["no bundleable airport car or no publishable activity Remix from this zone"]}

    parts_cost = arrival[1]["cost"] + departure[1]["cost"] + activity["tbo_cost"]
    cost = h_cost + parts_cost
    promise = h_secure * arrival[1]["p_all"] * departure[1]["p_all"] * activity["promise"]
    rules = [("Hotel", hotel.cancel_text, (hotel.refundable_until and (service.CHECKIN - hotel.refundable_until).days * 24) or float("inf")),
             ("Airport cars", arrival[0].cancel, E._cancel_hours(arrival[0].cancel)),
             (activity["attraction"].split(":")[0], activity["cancel"], E._cancel_hours(activity["cancel"]))]
    strict = max(rules, key=lambda r: r[2])
    refund_days = None if strict[2] == float("inf") else max(1, int(strict[2] // 24))
    zero = tp.Risk("TBO", 0, 0, 0, 0)

    def agent_tp(sell):
        return tp.compute(sell, set(), [], s.lead_days, refund_days, None, zero, sell)

    car_tp = [x[1]["parts"][0]["true_price"].total for x in (arrival, departure)]
    separate = hotel.true_price.total + sum(car_tp) + 2 * DIY_FRICTION + activity["packaged"]["true_price"]
    gap = separate - agent_tp(cost).total
    unit = agent_tp(1000.0).total / 1000.0
    sell = (separate - s.agent_share * gap) / unit
    agent = agent_tp(sell)
    saving = (separate - agent.total) / separate
    margin = (sell - cost) / sell
    blocks = []
    if gap <= 0:
        blocks.append(f"booking the pieces separately is cheaper by {tp.inr(-gap)}")
    else:
        if saving < s.min_saving:
            blocks.append(f"agent saves {saving:.1%}, below the {s.min_saving:.0%} guardrail")
        if margin < s.min_margin:
            blocks.append(f"TBO margin {margin:.1%}, below the {s.min_margin:.0%} guardrail")
    if promise < s.min_promise:
        blocks.append(f"Trip Promise {promise:.1%}, below the {s.min_promise:.0%} guardrail")
    return {**base, "status": "blocked" if blocks else "ready", "reasons": blocks or ["passes every guardrail"],
            "hotel": {"name": service.golden(hid)["name"], "offer": hotel.model_dump(mode="json"), "tbo_cost": round(h_cost, 2), "p_secure": round(h_secure, 4),
                      "nights": service.PARAMS.nights, "checkin": str(service.CHECKIN)},
            "arrival": {**asdict(arrival[0]), "tbo_cost": round(arrival[1]["cost"], 2), "p_secure": round(arrival[1]["p_all"], 4), "true_price": car_tp[0]},
            "departure": {**asdict(departure[0]), "tbo_cost": round(departure[1]["cost"], 2), "p_secure": round(departure[1]["p_all"], 4), "true_price": car_tp[1]},
            "activity": activity,
            "tbo_cost": round(cost, 2), "promise": round(promise, 4), "sell": round(sell, 2), "agent_true_price": agent,
            "separate": {"total": round(separate, 2), "hotel": hotel.true_price.total, "cars": round(sum(car_tp), 2), "friction": 2 * DIY_FRICTION,
                         "activity": activity["packaged"]["true_price"], "activity_from": activity["packaged"]["title"]},
            "gap": round(gap, 2), "agent_saving": round(saving, 4), "agent_saving_inr": round(separate - agent.total, 2),
            "margin": round(margin, 4), "margin_inr": round(sell - cost, 2),
            "cancellation": {"rules": [{"part": a, "rule": b} for a, b, _ in rules], "strictest": strict[0],
                             "summary": f"Free cancellation of the whole trip until {re.sub(r'(?i)^free (cancellation )?until ', '', strict[1])}"
                             f" ({strict[0].lower()} sets it); after that, the trip is non-refundable." if refund_days else "Non-refundable."}}


def book(seed: int) -> dict:
    """Riskiest first: activity parts, airport cars, then the hotel. Any unrecoverable failure unwinds the rest."""
    r = build()
    rng = random.Random(seed)
    legs = []
    act = rb.book(r["activity"], seed)
    legs.append({"leg": "activity", "label": r["activity"]["attraction"].split(":")[0], "outcome": act["outcome"], "status": act["status"],
                 "summary": act["summary"], "steps": [x for l in act["legs"] for x in l["steps"]] + (act["compensation"]["steps"] if act["compensation"] else [])})
    st = store.get()
    for key, label in (("arrival", "Airport arrival"), ("departure", "Airport departure")):
        p = r[key]
        pool = [rb._bookable(x, E.Settings()) for x in [p["component_id"], *p["twins"]]]
        res = sandbox.book(pool[0], pool, rb._profile("transfer", 1.0, E.Settings().lead_days), rng, friction=config.FAILOVER_FRICTION_INR)
        legs.append({"leg": key, "label": label, "status": res.status, "outcome": "failover" if res.via_failover else "clean" if res.status == "confirmed" else "failed",
                     "summary": f"{'SAME car via ' + res.final_supplier if res.via_failover else 'Confirmed'}" if res.status == "confirmed" else "No SAME car left",
                     "steps": [x.model_dump() for x in res.steps]})
    h = service.book([r["hotel"]["offer"]["offer_id"]], seed)[0]
    legs.append({"leg": "hotel", "label": "Hotel", "status": h.status, "outcome": "failover" if h.via_failover else "clean" if h.status == "confirmed" else "failed",
                 "summary": f"{'SAME room via ' + h.final_supplier if h.via_failover else 'Confirmed'}" if h.status == "confirmed" else "No SAME room left",
                 "steps": [x.model_dump() for x in h.steps]})
    failed = [l for l in legs if l["status"] != "confirmed"]
    outcome = "failed" if failed else "failover" if any(l["outcome"] in ("failover", "compensated") for l in legs) else "clean"
    summary = ("Whole trip confirmed" + (": " + "; ".join(f"{l['label']}: {l['summary']}" for l in legs if l["outcome"] in ("failover", "compensated")) if outcome == "failover" else " first time.")
               if not failed else f"{failed[0]['label']} couldn't be secured; TBO unwinds the other parts and the agent is refunded.")
    return {"seed": seed, "outcome": outcome, "legs": legs, "summary": summary}


@lru_cache
def demo_seed() -> int:
    for seed in range(1, 201):
        if book(seed)["outcome"] == "failover":
            return seed
    return 1
