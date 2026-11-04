"""Twin Finder invariants: never-merge rules hold in every final cluster, chains can't smuggle a merge,
human labels act as must-link / cannot-link, and held-out families never reach training."""
import json

import numpy as np
import polars as pl

from samesame import config, store
from samesame.matching import cluster as clu
from samesame.matching import hotels as hm
from samesame.matching import train


def _l(lid, name, lat=25.12, lng=55.20, phone=None, sup="mynah"):
    return {"listing_id": lid, "supplier_id": sup, "name": name, "lat": lat, "lng": lng, "address": "", "phone": phone, "star": 4.0,
            "checkin_time": "14:00", "amenities": [], "postcode": None}


def test_conflict_rules():
    a, b, c, d = hm.prep([_l("a", "Citadines Al Barsha 1"), _l("b", "Citadines Al Barsha 2"),
                          _l("c", "Holiday Inn Express Al Barsha"), _l("d", "Holiday Inn Al Barsha", lat=25.14)])
    assert "branch number" in hm.conflict(a, b)
    assert "brand family" in hm.conflict(c, d)
    far = hm.prep([_l("e", "Same Name Hotel"), _l("f", "Same Name Hotel", lat=25.14)])
    assert "apart" in hm.conflict(*far)
    assert hm.conflict(*hm.prep([_l("g", "NOVOTEL DXB AL BARSHA2"), _l("h", "Novotel Dubai Al-Barsha 2")])) is None


def test_chain_cannot_smuggle_a_merge():
    """x~y and y~z both look like twins, but x and z are different branches: the cluster must not hold both."""
    P = hm.prep([_l("x", "Citadines Al Barsha 1"), _l("y", "Citadines Al Barsha"), _l("z", "Citadines Al Barsha 2")])
    cl, dec = clu.cluster(P, [(0, 1), (1, 2), (0, 2)], np.array([0.99, 0.98, 0.97]), auto=0.9, gray=0.3)
    assert cl["x"] != cl["z"]
    assert any(d == "blocked" for _, d, _ in dec)


def test_no_final_cluster_breaks_a_never_merge_rule():
    s = store.get()
    for cid, ls in s.listings_of.items():
        P = hm.prep(ls)
        for i in range(len(P)):
            for j in range(i + 1, len(P)):
                assert hm.conflict(P[i], P[j]) is None, (cid, P[i]["name"], P[j]["name"])


def test_human_labels_link_and_split(tmp_path, monkeypatch):
    path = tmp_path / "labels.jsonl"
    monkeypatch.setattr(config, "LABELS_PATH", path)
    path.write_text("\n".join(json.dumps(r) for r in [
        {"action": "label", "audit_id": "au-1", "left": "a", "right": "b", "label": "S"},
        {"action": "label", "audit_id": "au-2", "left": "c", "right": "d", "label": "D"},
        {"action": "label", "audit_id": "au-3", "left": "e", "right": "f", "label": "S"},
        {"action": "undo", "audit_id": "au-3"}]) + "\n")
    P = hm.prep([_l("a", "Alpha Hotel"), _l("b", "Riverside Old Name Hotel"), _l("c", "Gamma Hotel"), _l("d", "Gamma Hotel"),
                 _l("e", "Eps Hotel"), _l("f", "Zeta Inn")])
    cl, _ = clu.cluster(P, [(0, 1), (2, 3), (4, 5)], np.array([0.2, 0.99, 0.2]), auto=0.9, gray=0.3)
    assert cl["a"] == cl["b"]            # human SAME merges a low-scored pair
    assert cl["c"] != cl["d"]            # human DIFFERENT overrides a confident model
    assert cl["e"] != cl["f"]            # an undone label no longer counts


def test_held_out_families_never_train():
    pairs = pl.read_parquet(config.BUILD / "hotel_pairs.parquet")
    _, _, _, ok = train.labels(pairs["a"].to_list(), pairs["b"].to_list())
    truth = dict(pl.read_parquet(config.BUILD / "hotel_truth.parquet").select("listing_id", "hotel_id").iter_rows())
    base = {h["hotel_id"]: h["family"] or h["hotel_id"] for h in pl.read_parquet(config.BUILD / "base_hotels.parquet").to_dicts()}
    for a, b, k in zip(pairs["a"], pairs["b"], ok):
        if config.is_holdout(base[truth[a]]) or config.is_holdout(base[truth[b]]):
            assert not k


def test_precision_first_thresholds():
    m = store.get().matcher
    assert m["auto_merge"] >= train.AUTO_FLOOR and m["gray_low"] <= train.GRAY_CEILING
