"""Every endpoint answers with a payload that validates against schemas.py (FastAPI enforces
response_model; this exercises each route so a contract break fails CI, not the demo)."""
from fastapi.testclient import TestClient

from samesame.api.app import app

c = TestClient(app)


def test_hotel_search_both_views():
    r = c.get("/api/hotels/search").json()
    assert len(r["today"]) == r["counters"]["raw_listings"]
    assert len(r["samesame"]) == r["counters"]["unique_hotels"]
    today_ids = {x["card_id"] for x in r["today"]}
    for card in r["samesame"]:
        assert set(card["member_ids"]) <= today_ids          # every stack member exists in Today (animation anchors)
        assert card["score"] and all(t["detail"] for t in card["score"])
    looks = {x["card_id"]: x["lookalike"]["other_card_id"] for x in r["samesame"] if x["lookalike"]}
    assert len(looks) >= 2                                   # the Citadines trap at least
    shown = {x["card_id"] for x in r["samesame"]}
    assert all(other in shown for other in looks.values())   # both pins are on the map


def test_hotel_detail_golden_flip():
    a_id, b_id = c.get("/api/meta").json()["demo"]["book_offers"]
    d = c.get("/api/hotels/demo").json()
    offers = {o["offer_id"]: o for o in d["offers"]}
    a, b = offers[a_id], offers[b_id]
    assert (a["supplier"], a["price"], b["supplier"], b["price"]) == ("Kestrel", 18600, "Mynah", 20100)
    assert a["price"] < b["price"]
    assert a["true_price"]["total"] > b["true_price"]["total"]
    assert d["enrichment"]["after_amenities"]


def test_unknown_hotel_404():
    assert c.get("/api/hotels/nope").status_code == 404


def test_book_is_reproducible():
    body = {"offer_ids": c.get("/api/meta").json()["demo"]["book_offers"], "seed": 11}
    assert c.post("/api/book", json=body).json() == c.post("/api/book", json=body).json()


def test_activity_groups_and_filters():
    for q, n_raw in [("floating market", 9), ("grand palace", 6), ("skywalk", 6)]:
        r = c.get("/api/activities/search", params={"q": q}).json()
        assert r["raw_count"] == n_raw
        assert len(r["groups"][0]["variants"]) == 3
        assert any(s["differs"] for v in r["groups"][0]["variants"] for s in v["dna"])


def test_review_label_and_undo():
    q = c.get("/api/review/queue").json()
    first = q[0]["pair_id"]
    ack = c.post(f"/api/review/{first}/label", json={"label": "D"}).json()
    assert first not in {x["pair_id"] for x in c.get("/api/review/queue").json()}
    assert c.post(f"/api/review/undo/{ack['audit_id']}").json()["ok"]
    assert first in {x["pair_id"] for x in c.get("/api/review/queue").json()}


def test_sim_and_suppliers():
    assert len(c.post("/api/sim", json={}).json()["arms"]) == 2
    assert len(c.get("/api/suppliers").json()) == 6
