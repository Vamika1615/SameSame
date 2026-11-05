"""The brief's golden case end to end: generated feeds -> matcher -> fitted Promise model -> True Price -> API.

Nothing here is hard-coded except the brief's inputs (which offers exist at the golden hotel). The test asserts the
point that must survive any change to the engines: A is cheaper on sticker and clearly dearer on True Price, and the
router only ever fails over to a SAME twin.
"""
import pytest
from fastapi.testclient import TestClient

from samesame import store
from samesame.api.app import app

client = TestClient(app)


@pytest.fixture(scope="module")
def offers():
    d = client.get("/api/hotels/demo").json()
    a = next(o for o in d["offers"] if o["supplier"] == "Kestrel" and o["board"] == "Room only" and o["refundable_until"] is None)
    b = next(o for o in d["offers"] if o["supplier"] == "Mynah" and o["board"] == "Breakfast" and o["refundable_until"])
    return d["offers"], a, b


def test_golden_case_flips_through_the_api(offers):
    _, a, b = offers
    assert a["price"] < b["price"]
    assert a["sticker_rank"] < b["sticker_rank"]
    assert a["true_price"]["total"] > b["true_price"]["total"] + 2000, (a["true_price"]["total"], b["true_price"]["total"])
    assert b["true_rank"] < a["true_rank"]


def test_true_price_ranks_are_consistent(offers):
    allo, _, _ = offers
    by_true = sorted(allo, key=lambda o: o["true_price"]["total"])
    assert [o["true_rank"] for o in by_true] == list(range(1, len(allo) + 1))
    for o in allo:
        assert o["true_price"]["total"] == pytest.approx(sum(t["amount"] for t in o["true_price"]["terms"]), abs=0.05)


def test_risk_terms_use_the_fitted_promise(offers):
    _, a, _ = offers
    p = a["promise"]
    sup = next(r["hotel"] for r in client.get("/api/suppliers").json() if r["supplier"] == "Kestrel")
    assert sup == p, "offer and supplier report must show the same fitted estimate"
    assert p["ci_low"] <= p["honour_rate"] <= p["ci_high"] and p["n"] > 0 and 0 < p["prior_weight"] < 1
    assert p["honour_rate"] + p["p_price_change"] + p["p_sold_out"] + p["p_error"] == pytest.approx(1, abs=0.002)
    fail = next(t for t in a["true_price"]["terms"] if t["key"] == "failover")
    assert f"{p['p_sold_out'] + p['p_error']:.0%}" in fail["assumption"]


def test_book_both_only_ever_fails_over_to_a_same_twin(offers):
    _, a, b = offers
    s = store.get()
    seen_failover = False
    for seed in range(1, 41):
        r = client.post("/api/book", json={"offer_ids": [a["offer_id"], b["offer_id"]], "seed": seed}).json()
        assert r["seed"] == seed
        for res in r["results"]:
            first = s.offer[res["offer_id"]]
            for st in res["steps"]:
                o = s.offer[st["offer_id"]]
                assert (o["hotel_id"], o["room_id"], o["board"]) == (first["hotel_id"], first["room_id"], first["board"])
                seen_failover |= st["event"] == "failover"
    assert seen_failover, "40 seeds and the riskiest supplier never failed over: the sandbox isn't drawing from its profiles"


def test_same_seed_same_story(offers):
    _, a, b = offers
    body = {"offer_ids": [a["offer_id"], b["offer_id"]], "seed": 7}
    assert client.post("/api/book", json=body).json() == client.post("/api/book", json=body).json()
