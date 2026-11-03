"""Supplier sandbox + failover router.

Each booking attempt draws its outcome from the supplier's behaviour profile at that lead time
(seeded RNG, so a scenario is reproducible; the seed is always shown to the user).
Router rule: on sold_out / error, or a price change that makes a SAME twin cheaper, rebook the
next SAME twin. Never a VARIANT: a different product is a decision for the agent, not the router.
"""
import random
from dataclasses import dataclass
from typing import Callable, Optional

from samesame.pricing.true_price import inr
from samesame.schemas import BookingResult, BookingStep


@dataclass
class BookableOffer:
    offer_id: str
    supplier: str
    price: float
    relation_key: str          # offers with equal relation_key are SAME (room + board)
    cancel_rank: int           # higher = more flexible; failover never goes to a lower one


@dataclass
class Profile:
    p_price_change: float
    p_sold_out: float
    p_error: float
    exp_increase_pct: float


def same_twins(offer: BookableOffer, pool: list[BookableOffer]) -> list[BookableOffer]:
    """SAME twins of an offer, cheapest first. VARIANTs (other board/room) are excluded by construction."""
    return sorted((o for o in pool if o.offer_id != offer.offer_id and o.relation_key == offer.relation_key
                   and o.cancel_rank >= offer.cancel_rank), key=lambda o: o.price)


def draw(rng: random.Random, p: Profile) -> str:
    u = rng.random()
    if u < p.p_price_change:
        return "price_changed"
    if u < p.p_price_change + p.p_sold_out:
        return "sold_out"
    if u < p.p_price_change + p.p_sold_out + p.p_error:
        return "error"
    return "confirmed"


def book(offer: BookableOffer, pool: list[BookableOffer], profile_of: Callable[[str], Profile],
         rng: random.Random, friction: float = 500, max_hops: int = 3) -> BookingResult:
    steps, t = [], 0
    tried = {offer.offer_id}
    current: Optional[BookableOffer] = offer
    via = False
    for _ in range(max_hops):
        p = profile_of(current.supplier)
        steps.append(BookingStep(t_ms=t, event="request", supplier=current.supplier, offer_id=current.offer_id,
                                 price=current.price, detail=f"Requesting {current.supplier}"))
        t += 900
        outcome = draw(rng, p)
        twins = [o for o in same_twins(current, pool) if o.offer_id not in tried]
        if outcome == "confirmed":
            steps.append(BookingStep(t_ms=t, event="confirmed", supplier=current.supplier, offer_id=current.offer_id,
                                     price=current.price, detail="Confirmed"))
            return BookingResult(offer_id=offer.offer_id, steps=steps, status="confirmed",
                                 final_supplier=current.supplier, final_price=current.price, via_failover=via)
        if outcome == "price_changed":
            new_price = round(current.price * (1 + p.exp_increase_pct * (0.5 + rng.random())), -1)
            steps.append(BookingStep(t_ms=t, event="price_changed", supplier=current.supplier, offer_id=current.offer_id,
                                     price=new_price, detail=f"Price changed at booking: {inr(current.price)} → {inr(new_price)}"))
            if not twins or twins[0].price + friction >= new_price:
                t += 600
                steps.append(BookingStep(t_ms=t, event="confirmed", supplier=current.supplier, offer_id=current.offer_id,
                                         price=new_price, detail="Accepted new price (no cheaper SAME twin)"))
                return BookingResult(offer_id=offer.offer_id, steps=steps, status="confirmed",
                                     final_supplier=current.supplier, final_price=new_price, via_failover=via)
        else:
            steps.append(BookingStep(t_ms=t, event=outcome, supplier=current.supplier, offer_id=current.offer_id,
                                     detail="Sold out" if outcome == "sold_out" else "Supplier error"))
        if not twins:
            break
        nxt = twins[0]
        t += 400
        steps.append(BookingStep(t_ms=t, event="failover", supplier=nxt.supplier, offer_id=nxt.offer_id, price=nxt.price,
                                 detail=f"Failing over to SAME twin via {nxt.supplier}"))
        tried.add(nxt.offer_id)
        current, via = nxt, True
        t += 300
    steps.append(BookingStep(t_ms=t, event="failed", supplier=current.supplier, offer_id=current.offer_id,
                             detail="No SAME twin left; agent must choose"))
    return BookingResult(offer_id=offer.offer_id, steps=steps, status="failed", final_supplier=None,
                         final_price=None, via_failover=via)
