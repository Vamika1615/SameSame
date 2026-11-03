"""Golden case from the brief. Inputs are the brief's; outputs come from the engine.

2 adults, 3 nights, client wants breakfast, travel in 21 days.
A: ₹18,600 room only, non-refundable, pay now, supplier honours ~74% at this lead time.
B: ₹20,100 breakfast, free cancellation until 7 days before, pay now, supplier honours ~97%.
The point that must survive: A is cheaper on sticker, clearly dearer on True Price.
"""
import pytest

from samesame.pricing.true_price import Need, Risk, compute

NEEDS = [Need("breakfast", "Breakfast", 2 * 3 * 550, "2 x 3 x ₹550")]
KESTREL = Risk("Kestrel", p_price_change=0.18, p_sold_out=0.06, p_error=0.02, exp_increase_pct=0.09)   # honours 74%
MYNAH = Risk("Mynah", p_price_change=0.015, p_sold_out=0.01, p_error=0.005, exp_increase_pct=0.05)    # honours 97%


def offer_a():
    return compute(18600, set(), NEEDS, 21, None, None, KESTREL, twin_price=19400)


def offer_b():
    return compute(20100, {"breakfast"}, NEEDS, 21, 7, None, MYNAH, twin_price=21350)


def test_golden_case_flips():
    a, b = offer_a(), offer_b()
    assert 18600 < 20100
    assert a.total > b.total + 2000, (a.total, b.total)


def test_golden_case_ranges():
    assert 23500 <= offer_a().total <= 24500
    assert 20400 <= offer_b().total <= 20900


def test_terms_sum_and_every_term_has_an_assumption():
    for p in (offer_a(), offer_b()):
        assert p.total == pytest.approx(sum(t.amount for t in p.terms), abs=0.05)
        assert all(t.assumption for t in p.terms)
        assert [t.key for t in p.terms] == ["sticker", "fill_needs", "cancel_risk", "price_change", "failover", "pay_later"]


def test_breakfast_filled_only_when_missing():
    assert offer_a().terms[1].amount == 3300
    assert offer_b().terms[1].amount == 0


def test_pay_later_reduces_true_price():
    now = compute(20000, set(), [], 30, None, None, MYNAH, 21000)
    later = compute(20000, set(), [], 30, None, 3, MYNAH, 21000)
    assert later.total < now.total


def test_refundable_beats_nonrefundable_on_cancel_risk():
    nrf = compute(20000, set(), [], 21, None, None, MYNAH, None).terms[2].amount
    ref = compute(20000, set(), [], 21, 7, None, MYNAH, None).terms[2].amount
    assert ref < nrf
