"""Promise model: shrinkage behaves, intervals are honest, and it learns only from the booking log."""
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from samesame.pricing import promise as pm

BUCKETS = ["0-7 days", "15-45 days"]


def _log(spec):
    """spec: (supplier, bucket, outcome, count)"""
    rows = []
    for s, b, o, n in spec:
        rows += [{"supplier_id": s, "product_type": "hotel", "lead_bucket": b, "outcome": o, "ts": date(2026, 10, 1),
                  "quoted": 100.0, "final_price": 108.0 if o == "price_changed" else 100.0}] * n
    return pl.DataFrame(rows)


def _row(rows, s, b):
    return pm.summarise(next(r for r in rows if r["supplier_id"] == s and r["lead_bucket"] == b))


MARKET = [(s, b, o, n) for s in ("a", "b", "c") for b in BUCKETS
          for o, n in (("confirmed", 450), ("price_changed", 30), ("sold_out", 15), ("error", 5))]


def test_new_supplier_is_not_condemned_by_a_few_failures():
    rows, _ = pm.fit(_log(MARKET + [("newbie", "15-45 days", "sold_out", 3)]))
    m = _row(rows, "newbie", "15-45 days")
    assert m["honour_rate"] > 0.6, "3 failures must not drive a new supplier to zero"
    assert m["ci_high"] - m["ci_low"] > 0.05, "and we must say we're unsure"


def test_lots_of_evidence_overrides_the_prior():
    bad = [("d", b, o, n) for b in BUCKETS for o, n in (("confirmed", 1400), ("price_changed", 400), ("sold_out", 150), ("error", 50))]
    rows, _ = pm.fit(_log(MARKET + bad))
    assert _row(rows, "d", "15-45 days")["honour_rate"] == pytest.approx(0.70, abs=0.03)


def test_cell_without_bookings_borrows_from_its_supplier():
    rows, _ = pm.fit(_log(MARKET + [("e", "15-45 days", "confirmed", 300), ("e", "15-45 days", "price_changed", 100)]))
    empty = next(r for r in rows if r["supplier_id"] == "e" and r["lead_bucket"] == "0-7 days")
    assert empty["n"] == 0 and empty["prior_weight"] == 1.0
    assert pm.summarise(empty)["p_price_change"] > 0.12, "e reprices a lot at 15-45 days; the empty cell should expect that too"


def test_outcome_shares_sum_to_one():
    rows, _ = pm.fit(_log(MARKET))
    for r in rows:
        m = pm.summarise(r)
        assert m["honour_rate"] + m["p_price_change"] + m["p_sold_out"] + m["p_error"] == pytest.approx(1)


def test_learns_from_the_log_not_the_generator():
    src = (Path(pm.__file__)).read_text(encoding="utf-8")
    assert "BEHAVIOUR" not in src and "samesame.data" not in src
