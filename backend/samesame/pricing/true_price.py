"""True Price: like-for-like rupee cost of an offer, given the client's needs.

Booking outcomes are mutually exclusive {confirmed, price_changed, sold_out, error}, so the
price-change and failover terms never double count. Cancellation exposure applies to whatever
ends up booked; failover only goes to SAME twins, which carry the same (or better) terms.

    True Price = sticker
               + cost to fill missing needs          (median market price of the inclusion)
               + P(cancel inside non-refundable window) x price
               + P(price change) x min(expected increase, twin delta + friction)
               + P(sold out or error) x (max(twin - price, 0) + friction)
               - value of paying later               (price x daily cost of capital x days deferred)
"""
from dataclasses import dataclass
from typing import Optional

from samesame import config
from samesame.schemas import PriceTerm, TruePrice

NO_TWIN_PREMIUM = 0.10   # if no SAME twin exists, re-buying elsewhere costs ~10% more (assumption)


@dataclass
class Need:
    key: str                 # "breakfast", "transfer"
    label: str               # "Breakfast"
    cost: float              # rupees to fill it outside the offer
    assumption: str          # "2 people x 3 nights x ₹550 (city median)"


@dataclass
class Risk:
    supplier: str
    p_price_change: float
    p_sold_out: float
    p_error: float
    exp_increase_pct: float  # expected size of a price change, as a fraction


def inr(x: float) -> str:
    """Indian digit grouping without the rupee sign's locale dependency."""
    s = f"{abs(round(x)):d}"
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if x < 0 else "") + "₹" + s


def compute(price: float, includes: set[str], needs: list[Need], lead_days: int,
            refundable_until_days: Optional[int], pay_due_days: Optional[int], risk: Risk,
            twin_price: Optional[float], cancel_rate: float = config.DEFAULT_AGENT_CANCEL_RATE,
            friction: float = config.FAILOVER_FRICTION_INR,
            capital_rate: float = config.COST_OF_CAPITAL_ANNUAL) -> TruePrice:
    """refundable_until_days: free cancellation until N days before travel (None = non-refundable).
    pay_due_days: payment due N days before travel (None = pay at booking)."""
    terms = [PriceTerm(key="sticker", label="Sticker", amount=price, assumption="supplier quote")]

    missing = [n for n in needs if n.key not in includes]
    terms.append(PriceTerm(key="fill_needs", label="Fill missing needs",
                           amount=sum(n.cost for n in missing),
                           assumption="; ".join(f"{n.label}: {n.assumption}" for n in missing) or "all needs included"))

    lead = max(lead_days, 1)
    if refundable_until_days is None:
        p_cancel_loss = cancel_rate
        why = f"non-refundable; agency cancel rate {cancel_rate:.0%}"
    else:
        window = min(refundable_until_days, lead)
        p_cancel_loss = cancel_rate * window / lead
        why = (f"free cancel until {refundable_until_days}d before; {cancel_rate:.0%} cancel rate x "
               f"{window}/{lead} days in penalty window (uniform timing)")
    terms.append(PriceTerm(key="cancel_risk", label="Cancellation risk", amount=p_cancel_loss * price, assumption=why))

    if twin_price is not None:
        redo = max(twin_price - price, 0) + friction
        redo_why = f"next SAME twin {inr(twin_price)} + {inr(friction)} friction"
    else:
        redo = price * NO_TWIN_PREMIUM + friction
        redo_why = f"no SAME twin: +{NO_TWIN_PREMIUM:.0%} to rebook + {inr(friction)} friction"

    increase = price * risk.exp_increase_pct
    terms.append(PriceTerm(key="price_change", label="Price-change risk",
                           amount=risk.p_price_change * min(increase, redo),
                           assumption=f"{risk.supplier} changes price {risk.p_price_change:.0%} of the time at {lead_days}d "
                                      f"(avg +{risk.exp_increase_pct:.0%}); agent takes cheaper of paying up or {redo_why}"))

    p_fail = risk.p_sold_out + risk.p_error
    terms.append(PriceTerm(key="failover", label="Booking-failure risk", amount=p_fail * redo,
                           assumption=f"{risk.supplier} fails {p_fail:.0%} (sold out/error) at {lead_days}d; {redo_why}"))

    deferred = 0 if pay_due_days is None else max(lead_days - pay_due_days, 0)
    terms.append(PriceTerm(key="pay_later", label="Pay-later value",
                           amount=-price * capital_rate / 365 * deferred,
                           assumption=f"{deferred} days deferred at {capital_rate:.0%}/yr cost of capital"
                           if deferred else "pay at booking"))

    for t in terms:
        t.amount = round(t.amount, 2)
    return TruePrice(total=round(sum(t.amount for t in terms), 2), terms=terms)
