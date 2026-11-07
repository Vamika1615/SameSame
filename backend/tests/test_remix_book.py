"""Booking a Remix: per-part failover to SAME twins only, compensation when a part can't be secured, seeds reproduce."""
from fastapi.testclient import TestClient

from samesame import store
from samesame.remix import book as rb
from samesame.remix import engine as E
from samesame.remix import service as rs
from samesame.api.app import app

client = TestClient(app)


def _demo():
    return rs.result(rs.demo_variant(), E.Settings())


def test_demo_product_is_chosen_by_rule_not_by_hand():
    ready = [r for r in rs.all_results(E.Settings()) if r["status"] == "ready"]
    assert ready, "no publishable Remix: the demo has nothing to show"
    assert rs.demo_variant() == max(ready, key=lambda r: r["agent_saving_inr"])["variant_id"]


def test_failover_only_to_same_twins_of_the_failed_part():
    r = _demo()
    allowed = {p["leg"]: {p["component_id"], *p["twins"]} for p in r["parts"]}
    for seed in range(1, 201):
        b = rb.book(r, seed)
        for leg in b["legs"]:
            assert {s["offer_id"] for s in leg["steps"]} <= allowed[leg["leg"]], (seed, leg["leg"])


def test_compensation_path_runs_and_is_costed():
    r = _demo()
    seen = None
    for seed in range(1, 1001):
        b = rb.book(r, seed)
        if b["outcome"] in ("compensated", "failed"):
            seen = b
            break
    assert seen, "1,000 draws and no part ever failed past its twins: compensation is untested"
    comp = seen["compensation"]
    assert comp and comp["unwind_cost"] >= 0
    booked_before = [l for l in seen["legs"][:-1] if l["status"] == "confirmed"]
    assert len([s for s in comp["steps"] if s["leg"] == "unwind"]) == len(booked_before)
    if seen["outcome"] == "compensated":
        assert comp["fallback"]["status"] == "confirmed"


def test_riskiest_part_is_booked_first():
    r = _demo()
    b = rb.book(r, 1)
    order = [l["leg"] for l in b["legs"]]
    by_risk = [p["leg"] for p in sorted(r["parts"], key=lambda p: p["p_secure"])]
    assert order == by_risk[:len(order)]


def test_seed_reproduces_and_demo_seed_shows_a_failover():
    r = _demo()
    assert rb.book(r, 22) == rb.book(r, 22)
    assert rb.book(r, rs.demo_seed())["outcome"] == "failover"


def test_remix_api():
    m = client.get("/api/meta").json()["demo"]
    d = client.get("/api/remix/demo").json()
    assert d["variant_id"] == m["remix_variant"] and d["status"] == "ready"
    o = client.get("/api/remix").json()
    assert o["counts"]["ready"] >= 1 and o["counts"]["package_wins"] >= 1
    b = client.post("/api/remix/book", json={"variant_id": m["remix_variant"], "seed": m["remix_seed"]}).json()
    assert b["outcome"] == "failover" and b["status"] == "confirmed"
    tighter = client.get("/api/remix/demo?min_margin=0.5").json()
    assert tighter["status"] == "blocked"


def test_no_remix_number_is_typed_in():
    """Every rupee on the Remix card is a sum of part prices the generator drew, and changes when the settings do."""
    r = _demo()
    st = store.get()
    assert r["sticker"] == sum(p["price"] for p in r["parts"])
    for p in r["parts"]:
        c = st.components[p["component_id"]]
        assert p["price"] == c["price"] * (1 if c["price_unit"] == "per vehicle" else 2)
    worse = E.remix(next(t for t in E.targets() if t["variant_id"] == r["variant_id"]), E.PESSIMISTIC)
    assert worse["tbo_cost"] > r["tbo_cost"]
