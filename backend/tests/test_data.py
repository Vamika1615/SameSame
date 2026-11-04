"""M2 supplier layer: the generated data has the properties the brief asks for."""
import re
from pathlib import Path

import numpy as np

from samesame import store
from samesame.data import feeds, osm_base, world
from samesame.ranking.score import haversine_m
from samesame.service import promise


def test_base_is_deduplicated_osm():
    hotels = list(store.get().hotels.values())
    assert 280 <= len(hotels) <= 320
    for i, a in enumerate(hotels):
        for b in hotels[i + 1:]:
            if osm_base.norm(a["name"]) == osm_base.norm(b["name"]):
                assert haversine_m(a["lat"], a["lng"], b["lat"], b["lng"]) >= osm_base.OSM_DUP_M


def test_at_least_20_real_hard_negatives():
    s = store.get()
    hn = s.hard_negatives
    assert len(hn) >= 20
    for p in hn:
        a, b = s.hotels[p["a"]], s.hotels[p["b"]]
        assert a["family"] == b["family"] and a["osm_id"] != b["osm_id"]
        assert haversine_m(a["lat"], a["lng"], b["lat"], b["lng"]) < osm_base.HARD_NEG_MAX_M


def test_six_suppliers_with_corruption():
    s = store.get()
    assert {l["supplier_id"] for l in s.listings.values()} == set(world.SUPPLIERS)
    names = {}
    for l in s.listings.values():
        names.setdefault(s.cluster_of[l["listing_id"]], set()).add(l["name"])
    assert sum(len(v) > 1 for v in names.values()) / len(names) > 0.8      # most hotels are named differently by suppliers


def test_booking_log_size_and_profile():
    log = store.get().log
    assert log.height >= 20_000
    est = promise("kestrel", "hotel", 21)
    pc, so, err, _ = world.BEHAVIOUR[("kestrel", "hotel")]
    assert abs(est.honour_rate - (1 - pc - so - err)) < 0.03               # the log reflects the behaviour model
    assert promise("mynah", "hotel", 21).honour_rate > 0.95


def test_golden_case_inputs_present():
    s = store.get()
    offers = [o for o in s.offers_of[feeds.GOLDEN_HOTEL] if o["room_id"].endswith(":R1")]
    a = [o for o in offers if o["supplier_id"] == "kestrel" and o["board"] == "RO"]
    b = [o for o in offers if o["supplier_id"] == "mynah" and o["board"] == "BB"]
    assert a[0]["nightly"] * 3 == 18600 and a[0]["refundable_days"] is None
    assert b[0]["nightly"] * 3 == 20100 and b[0]["refundable_days"] == 7


def test_generation_is_deterministic():
    def run():
        h, _, _ = osm_base.curate(np.random.default_rng([1, 2]))
        return [l["listing_id"] + l["name"] for l in feeds.generate(h, np.random.default_rng([1, 3]))[0]]
    assert run() == run()


def test_truth_tables_stay_out_of_the_app():
    """Only the generator, the pipeline, the store (until M3) and evaluation may read generator truth."""
    root = Path(__file__).resolve().parents[1] / "samesame"
    allowed = {"store.py", "pipeline.py"}
    for f in root.rglob("*.py"):
        rel = f.relative_to(root)
        if rel.parts[0] in ("data", "eval") or str(rel) in allowed:
            continue
        assert not re.search(r"\b(hotel|room|activity)_truth\b|hard_negatives", f.read_text(encoding="utf-8")), f"{rel} reads generator truth"
