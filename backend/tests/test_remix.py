"""Remix engine (R2): SAME never VARIANT, only bundleable parts, feasible timing, honest pricing and guardrails."""
from dataclasses import replace

import pytest

from samesame import store
from samesame.data.components import minutes
from samesame.remix import engine as E

DEMO = E.Settings()


@pytest.fixture(scope="module")
def results():
    return {r["variant_id"]: r for r in E.run_all(DEMO)}


def _built(results):
    return [r for r in results.values() if r.get("parts")]


def test_compare_is_exact_on_what_the_package_states():
    pkg = {"pickup": "Private hotel pickup", "meals": "BBQ dinner", "access": "Standard", "stops": "Main site only", "option": "Private"}
    same = {**pkg, "cancel": "Free until 24 h"}
    assert E.compare(pkg, same) == ([], ["cancel"])                       # package silent on cancellation: a human checks
    diffs, _ = E.compare(pkg, {**same, "option": None})
    assert diffs, "a package that promises 'Private' can't be rebuilt from parts that don't state it"
    diffs, _ = E.compare(pkg, {**same, "meals": "No meals"})
    assert diffs
    diffs, _ = E.compare({**pkg, "cancel": "Free until 24 h"}, {**same, "cancel": "Non-refundable"})
    assert diffs


def test_every_remix_has_the_targets_dna(results):
    for r in _built(results):
        diffs, unverified = E.compare(r["target_dna"], r["assembled_dna"])
        assert not diffs, (r["variant_id"], diffs)
        assert unverified == r["unverified"]


def test_never_uses_a_package_only_rate(results):
    comps = store.get().components
    for r in _built(results):
        for p in r["parts"]:
            assert comps[p["component_id"]]["bundleable"], (r["variant_id"], p["title"])
            assert all(comps[t]["bundleable"] for t in p["twins"])


def test_timing_and_meeting_points_are_feasible(results):
    comps = store.get().components
    for r in _built(results):
        parts = {p["leg"]: p for p in r["parts"]}
        ticket = comps[parts["ticket"]["component_id"]]
        for leg in ("out", "back"):
            if leg in parts:
                c = comps[parts[leg]["component_id"]]
                assert c["meeting_point_id"] == ticket["meeting_point_id"] and c["zone_id"] == DEMO.zone
        if "out" in parts:
            assert parts["out"]["end"] <= parts["ticket"]["start"] - DEMO.buffer_min
            assert parts["ticket"]["start"] - parts["out"]["end"] <= DEMO.max_wait_min
        if "back" in parts:
            assert parts["back"]["start"] >= parts["ticket"]["end"]
        if "lunch" in parts:
            assert parts["ticket"]["start"] <= parts["lunch"]["start"] and parts["lunch"]["end"] <= parts["ticket"]["end"]


def test_remix_promise_comes_from_its_parts(results):
    for r in _built(results):
        p = 1.0
        for part in r["parts"]:
            assert 0 < part["p_secure"] <= 1
            assert part["p_secure"] >= 1 - (part["promise"].p_sold_out + part["promise"].p_error) - 1e-9   # twins only help
            p *= part["p_secure"]
        assert r["promise"] == pytest.approx(p, abs=1e-3)


def test_twins_are_same_parts_only(results):
    comps = store.get().components
    for r in _built(results):
        for part in r["parts"]:
            c = comps[part["component_id"]]
            for t in map(comps.get, part["twins"]):
                assert t["role"] == c["role"] and t["meeting_point_id"] == c["meeting_point_id"]
                if c["role"] == "transfer":
                    assert (t["zone_id"], t["direction"], t["mode"]) == (c["zone_id"], c["direction"], c["mode"])
                else:
                    assert t["dna"] == c["dna"]


def test_guardrails_block_what_they_should(results):
    for r in results.values():
        if r["status"] == "ready":
            assert r["agent_saving"] >= DEMO.min_saving and r["margin"] >= DEMO.min_margin and r["promise"] >= DEMO.min_promise
        if r["status"] == "blocked":
            assert r["reasons"]
    strict = replace(DEMO, min_promise=0.9999)
    assert not any(E.remix(t, strict)["status"] == "ready" for t in E.targets() if t["variant_id"] in results)


def test_packaged_can_win_and_we_say_so(results):
    losses = [r for r in results.values() if r.get("gap") is not None and r["gap"] <= 0]
    assert losses, "if Remix never loses, the comparison is rigged"
    assert all("cheaper on True Price" in " ".join(r["reasons"]) for r in losses)


def test_single_part_products_are_not_remixes(results):
    for r in results.values():
        if r["target_dna"]["pickup"] not in E.HOTEL_PICKUPS and r["target_dna"]["meals"] != "Lunch":
            assert r["status"] in ("single_part", "not_remixable")


def test_sell_price_follows_the_settings(results):
    t = next(t for t in E.targets() if results[t["variant_id"]]["status"] == "ready")
    a, b = E.remix(t, replace(DEMO, agent_share=0.25)), E.remix(t, replace(DEMO, agent_share=0.75))
    assert a["sell"] > b["sell"] and a["margin"] > b["margin"] and a["agent_saving"] < b["agent_saving"]


def test_deterministic(results):
    t = next(t for t in E.targets() if results[t["variant_id"]].get("parts"))
    assert E.remix(t, DEMO) == E.remix(t, DEMO)


def test_slot_times_parse():
    assert minutes("17:30") == 1050
