"""Remix business case for the simulator (SIMULATED: the conversion rate is an assumption, everything else is computed).

Agents' sightseeing searches (search_events) are matched to Remixes that pass every guardrail, catalogue and
gap alike, by the same rule the gap finder uses for demand. Each matched search books at the simulator's
bookings-per-search rate, and each booking earns that Remix's computed TBO margin and agent saving.
"""
from samesame import store
from samesame.remix import engine as E
from samesame.remix import gaps
from samesame.remix import service as rs


def _matches(e: dict, r: dict) -> bool:
    dna = r.get("assembled_dna") or r["target_dna"]
    return (r["attraction_id"] == e["attraction_id"] and dna["pickup"] == e["pickup"] and set(e["filters"]) <= set(dna.values()))


def case(bookings_per_search: float, s: E.Settings = E.Settings()) -> dict:
    events = store.get().search_events
    ready = [r for r in rs.all_results(s) if r["status"] == "ready"] + [r for r in gaps.find(s) if r["status"] == "ready"]
    hits, margin, saving = 0, 0.0, 0.0
    for e in events:
        best = max((r for r in ready if _matches(e, r)), key=lambda r: r["agent_saving_inr"], default=None)
        if best:
            hits += 1
            margin += best["margin_inr"]
            saving += best["agent_saving_inr"]
    per = 1000 / len(events)
    return {"searches": len(events), "matched_share": round(hits / len(events), 4), "publishable_remixes": len(ready),
            "bookings_per_1000_searches": round(hits * per * bookings_per_search, 1),
            "tbo_margin_per_1000_searches": round(margin * per * bookings_per_search, 0),
            "agent_saving_per_1000_searches": round(saving * per * bookings_per_search, 0),
            "avg_margin_per_booking": round(margin / hits, 0) if hits else 0, "pessimistic": s.failure_mult > 1,
            "note": "SIMULATED: conversion is the simulator's bookings-per-search; matches, margins and savings are computed from the Remix engine."}
