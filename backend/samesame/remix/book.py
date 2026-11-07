"""Booking a Remix in the supplier sandbox.

Parts are booked riskiest first (lowest chance of being secured), so a failure costs as little as
possible. Each part goes through the same router as hotels: on sold-out/error, or a price rise that makes a
SAME twin cheaper, it rebooks a SAME twin of *that part only*. If a part can't be secured at all, TBO
cancels the parts already booked (compensation: free cancellations cost nothing but friction, non-refundable
ones are lost) and buys the best package instead. Outcomes are drawn from the world's behaviour model with
a seeded RNG, never forced.
"""
import random

from samesame import config, store
from samesame.booking import sandbox
from samesame.data import world
from samesame.pricing.true_price import inr
from samesame.remix.engine import PRODUCT, Settings, remix

SUPPLIERS = world.SUPPLIERS
NAME_TO_ID = {v: k for k, v in SUPPLIERS.items()}
LEG = {"ticket": "Ticket", "out": "Transfer out", "back": "Transfer back", "lunch": "Lunch"}


def _profile(product: str, vol: float, lead: int):
    return lambda name: sandbox.Profile(*world.behaviour(NAME_TO_ID[name], product, lead, vol))


def _vol(c: dict) -> float:
    if c["role"] == "transfer":
        return 1.0
    return store.get().attractions[c["attraction_id"]]["volatility"]


def _bookable(cid: str, s: Settings) -> sandbox.BookableOffer:
    c = store.get().components[cid]
    price = c["price"] * (1 if c["price_unit"] == "per vehicle" else s.pax)
    return sandbox.BookableOffer(cid, SUPPLIERS[c["supplier_id"]], price, "same", 0)


def book(r: dict, seed: int, s: Settings = Settings()) -> dict:
    """r: a remix() result with parts. Returns the step-by-step story and how it ended."""
    st = store.get()
    rng = random.Random(seed)
    order = sorted(r["parts"], key=lambda p: p["p_secure"])
    t, legs, booked = 0, [], []
    for p in order:
        c = st.components[p["component_id"]]
        pool = [_bookable(x, s) for x in [p["component_id"], *p["twins"]]]
        res = sandbox.book(pool[0], pool, _profile(PRODUCT[c["role"]], _vol(c), s.lead_days), rng, friction=config.FAILOVER_FRICTION_INR)
        steps = [{**st_.model_dump(), "t_ms": st_.t_ms + t, "leg": p["leg"]} for st_ in res.steps]
        t = max(x["t_ms"] for x in steps) + 300
        repriced = any(x["event"] == "price_changed" for x in steps)
        legs.append({"leg": p["leg"], "label": LEG[p["leg"]], "component_id": p["component_id"], "planned_supplier": SUPPLIERS[p["supplier_id"]],
                     "planned_price": p["price"], "status": res.status, "final_supplier": res.final_supplier, "final_price": res.final_price,
                     "via_failover": res.via_failover, "repriced": repriced, "steps": steps})
        if res.status == "failed":
            return {**_compensate(r, legs, booked, t, rng, s), "seed": seed}
        booked.append(legs[-1])
    paid = sum(l["final_price"] for l in legs)
    outcome = "failover" if any(l["via_failover"] for l in legs) else "paid_rise" if any(l["repriced"] for l in legs) else "clean"
    return {"seed": seed, "variant_id": r["variant_id"], "outcome": outcome, "status": "confirmed", "legs": legs,
            "tbo_paid": round(paid, 2), "planned": r["sticker"], "extra_cost": round(paid - r["sticker"], 2), "compensation": None,
            "summary": _summary(outcome, legs, paid, r)}


def _compensate(r, legs, booked, t, rng, s):
    """A part can't be secured: cancel what's booked, then try the best package (and its SAME twins)."""
    st = store.get()
    lost, steps = 0.0, []
    for l in booked:
        c = st.components[l["component_id"]]
        nrf = c["cancel"] == "Non-refundable"
        loss = l["final_price"] if nrf else 0.0
        lost += loss + config.FAILOVER_FRICTION_INR
        steps.append({"t_ms": t, "event": "failed" if nrf else "confirmed", "supplier": l["final_supplier"], "offer_id": l["component_id"],
                      "price": loss or None, "leg": "unwind",
                      "detail": f"Cancelled {l['label'].lower()} with {l['final_supplier']}: " + (f"non-refundable, {inr(loss)} lost" if nrf else "free cancellation")})
        t += 400
    pkg = r.get("packaged")
    fallback = None
    if pkg and r["variant_id"] in st.act_listings_of:
        members = next(x for x in [v for vs in st.variants_of.values() for v in vs] if x["variant_id"] == r["variant_id"])
        listings = st.act_listings_of[members["variant_id"]]
        pool = [sandbox.BookableOffer(m["listing_id"], SUPPLIERS[m["supplier_id"]], m["price_pp"] * s.pax, "pkg", 0) for m in listings]
        first = next(b for b in pool if b.offer_id == pkg["listing_id"])
        vol = st.attractions[r["attraction_id"]]["volatility"]
        res = sandbox.book(first, pool, _profile("activity", vol, s.lead_days), rng, friction=config.FAILOVER_FRICTION_INR)
        steps += [{**x.model_dump(), "t_ms": x.t_ms + t, "leg": "package"} for x in res.steps]
        fallback = {"status": res.status, "final_supplier": res.final_supplier, "final_price": res.final_price}
    ok = fallback and fallback["status"] == "confirmed"
    paid = (fallback["final_price"] if ok else 0) + lost
    outcome = "compensated" if ok else "failed"
    comp = {"steps": steps, "unwind_cost": round(lost, 2), "fallback": fallback}
    return {"seed": None, "variant_id": r["variant_id"], "outcome": outcome, "status": "confirmed" if ok else "failed", "legs": legs,
            "tbo_paid": round(paid, 2), "planned": r["sticker"], "extra_cost": round(paid - r["sticker"], 2), "compensation": comp,
            "summary": _summary(outcome, legs, paid, r, comp)}


def _summary(outcome, legs, paid, r, comp=None):
    if outcome == "clean":
        return f"Every part confirmed first time. TBO paid {inr(paid)}."
    if outcome == "paid_rise":
        return f"All parts confirmed; one repriced and no cheaper SAME twin existed. TBO paid {inr(paid)} (planned {inr(r['sticker'])})."
    if outcome == "failover":
        f = next(l for l in legs if l["via_failover"])
        return (f"{f['label']} via {f['planned_supplier']} failed → SAME {f['label'].lower()} via {f['final_supplier']}, confirmed. "
                f"Whole trip confirmed; TBO paid {inr(paid)} (planned {inr(r['sticker'])}).")
    bad = legs[-1]
    if outcome == "compensated":
        return (f"{bad['label']} couldn't be secured from any SAME twin. TBO cancelled the booked parts ({inr(comp['unwind_cost'])} incl. friction) "
                f"and bought the package via {comp['fallback']['final_supplier']}. The client still travels; TBO paid {inr(paid)}.")
    if comp and comp["fallback"] is None:
        return (f"{bad['label']} couldn't be secured from any SAME twin, and nobody sells this as a package. TBO cancelled the booked parts "
                f"({inr(comp['unwind_cost'])} incl. friction) and refunds the agent in full.")
    return f"{bad['label']} couldn't be secured and the package fallback failed too: the agent must choose."


def first_seed_with_failover(r: dict, s: Settings = Settings(), limit: int = 200) -> int:
    """The demo shows a part failing over. This finds the first seed that does (disclosed on screen), so the
    outcome still comes from the behaviour model; pressing 'fresh seed' shows how often that happens."""
    for seed in range(1, limit + 1):
        if book(r, seed, s)["outcome"] == "failover":
            return seed
    return 1


def stats(r: dict, runs: int = 1000, s: Settings = Settings()) -> dict:
    """Remix vs its best package over seeds 1..runs (same seeds, same behaviour model)."""
    st = store.get()
    keys = ["clean", "paid_rise", "failover", "compensated", "failed"]
    rem = dict.fromkeys(keys, 0)
    pkg = dict.fromkeys(keys, 0)
    listings = st.act_listings_of[r["variant_id"]]
    vol = st.attractions[r["attraction_id"]]["volatility"]
    pool = [sandbox.BookableOffer(m["listing_id"], SUPPLIERS[m["supplier_id"]], m["price_pp"] * s.pax, "pkg", 0) for m in listings]
    first = next(b for b in pool if b.offer_id == r["packaged"]["listing_id"])
    paid_r, paid_p = 0.0, 0.0
    for seed in range(1, runs + 1):
        b = book(r, seed, s)
        rem[b["outcome"]] += 1
        paid_r += b["tbo_paid"]
        res = sandbox.book(first, pool, _profile("activity", vol, s.lead_days), random.Random(seed), friction=config.FAILOVER_FRICTION_INR)
        k = "failed" if res.status == "failed" else "failover" if res.via_failover else \
            "paid_rise" if any(x.event == "price_changed" for x in res.steps) else "clean"
        pkg[k] += 1
        paid_p += res.final_price or 0
    return {"runs": runs, "remix": rem, "package": pkg, "remix_avg_paid": round(paid_r / runs, 2),
            "package_avg_paid": round(paid_p / runs, 2)}
