"""M2 supplier layer: the generated data has the properties the brief asks for."""
import re
from pathlib import Path

import numpy as np

import polars as pl

from samesame import config, store
from samesame.data import feeds, osm_base, world
from samesame.ranking.score import haversine_m
from samesame.service import promise


def _t(name):
    return pl.read_parquet(config.BUILD / f"{name}.parquet").to_dicts()


def test_base_is_deduplicated_osm():
    hotels = _t("base_hotels")
    assert 280 <= len(hotels) <= 320
    for i, a in enumerate(hotels):
        for b in hotels[i + 1:]:
            if osm_base.norm(a["name"]) == osm_base.norm(b["name"]):
                assert haversine_m(a["lat"], a["lng"], b["lat"], b["lng"]) >= osm_base.OSM_DUP_M


def test_at_least_20_real_hard_negatives():
    hotels = {h["hotel_id"]: h for h in _t("base_hotels")}
    hn = _t("hard_negatives")
    assert len(hn) >= 20
    for p in hn:
        a, b = hotels[p["a"]], hotels[p["b"]]
        assert a["family"] == b["family"] and a["osm_id"] != b["osm_id"]
        assert haversine_m(a["lat"], a["lng"], b["lat"], b["lng"]) < osm_base.HARD_NEG_MAX_M


def test_six_suppliers_with_corruption():
    truth = {t["listing_id"]: t["hotel_id"] for t in _t("hotel_truth")}
    listings = _t("hotel_listings")
    assert {l["supplier_id"] for l in listings} == set(world.SUPPLIERS)
    names = {}
    for l in listings:
        names.setdefault(truth[l["listing_id"]], set()).add(l["name"])
    assert sum(len(v) > 1 for v in names.values()) / len(names) > 0.8      # most hotels are named differently by suppliers


def test_booking_log_size_and_profile():
    log = store.get().log
    assert log.height >= 20_000
    est = promise("kestrel", "hotel", 21)
    pc, so, err, _ = world.BEHAVIOUR[("kestrel", "hotel")]
    assert abs(est.honour_rate - (1 - pc - so - err)) < 0.03               # the log reflects the behaviour model
    assert promise("mynah", "hotel", 21).honour_rate > 0.95


def test_golden_case_inputs_present():
    truth = {t["listing_id"]: t["hotel_id"] for t in _t("hotel_truth")}
    room = {t["supplier_room_id"]: t["room_id"] for t in _t("room_truth")}
    offers = [o for o in _t("offers") if truth[o["listing_id"]] == feeds.GOLDEN_HOTEL and room[o["supplier_room_id"]].endswith(":R1")]
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
    """Only the generator, the pipeline, evaluation, the trainer (labels) and store.py's two world_* helpers may read truth."""
    root = Path(__file__).resolve().parents[1] / "samesame"
    allowed = {"store.py", "pipeline.py", "matching/train.py"}
    for f in root.rglob("*.py"):
        rel = f.relative_to(root)
        if rel.parts[0] in ("data", "eval") or str(rel) in allowed:
            continue
        assert not re.search(r"\b(hotel|room|activity)_truth\b|hard_negatives", f.read_text(encoding="utf-8")), f"{rel} reads generator truth"


def test_listing_ids_unique():
    import polars as pl
    from samesame import config
    for t in ("hotel_listings", "activity_listings"):
        ids = pl.read_parquet(config.BUILD / f"{t}.parquet")["listing_id"]
        assert ids.n_unique() == len(ids)
    _ = store


def test_photos_are_credited_free_and_never_shared_by_neighbours():
    import re as _re
    from samesame.data.images_gen import STOCK_REUSE_MIN_M
    from samesame.ranking.score import haversine_m
    imgs = [i for i in _t("images") if i["derived_from"] is None] if (config.BUILD / "images.parquet").exists() else []
    hotels = {h["hotel_id"]: h for h in _t("base_hotels")}
    users: dict = {}
    for i in imgs:
        if i["photo_kind"] != "generated":
            assert i["credit_url"] and _re.search(r"CC0|CC BY|Public domain|PD", i["credit"], _re.I), i
        if i["photo_kind"] == "stock" and i["owner_kind"] == "hotel":
            users.setdefault(i["credit_url"], []).append(hotels[i["owner_id"]])
    for hs in users.values():
        for a in range(len(hs)):
            for b in range(a + 1, len(hs)):
                assert haversine_m(hs[a]["lat"], hs[a]["lng"], hs[b]["lat"], hs[b]["lng"]) > STOCK_REUSE_MIN_M
