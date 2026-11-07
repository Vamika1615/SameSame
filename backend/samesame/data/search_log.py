"""Agents' sightseeing searches (synthetic, disclosed in DATA.md): what they look for, including what nobody sells.

Each event: an agent searched an attraction, ticked some DNA filters (slot, meal, access) and said how the
client gets there. The generator draws these independently: attraction in proportion to how many listings it
has, one of its sellable cores (a ticket-level product) uniformly, and a pickup wish from PICKUP_WISH. So
demand lands on combinations whether or not a supplier packages them. That is the point: the gap finder
(remix/gaps.py) only sees these events and the catalogue, never this file's parameters.
"""
from datetime import timedelta

import numpy as np

from samesame.data.booking_log import ANCHOR, MARKETS
from samesame.data.components import HOTEL_PICKUPS

N_EVENTS = 5_000
DAYS = 90
PICKUP_WISH = [("No transfer", 0.50), ("Shared hotel pickup", 0.25), ("Private hotel pickup", 0.25)]
# filters agents can tick (the same words Variant DNA reads, so the app can match them)
OPTION_FILTERS = {"Sunset slot", "Daytime slot", "Evening slot", "VIP lounge", "Sandboarding", "Standard seat"}
MEAL_FILTERS = {"BBQ dinner", "Buffet dinner", "Set dinner"}


def generate(variants: list[dict], listings: list[dict], truth: list[dict], rng: np.random.Generator) -> list[dict]:
    n_listings: dict[str, int] = {}
    for t in truth:
        n_listings[t["attraction_id"]] = n_listings.get(t["attraction_id"], 0) + 1
    cores: dict[str, list[dict]] = {}
    for v in variants:
        if v["dna"]["pickup"] not in HOTEL_PICKUPS:
            cores.setdefault(v["attraction_id"], []).append(v)
    atts = sorted(cores)
    w = np.array([n_listings[a] for a in atts], dtype=float)
    markets, mw = [m for m, _ in MARKETS], np.array([x for _, x in MARKETS])
    rows = []
    for i in range(N_EVENTS):
        aid = atts[int(rng.choice(len(atts), p=w / w.sum()))]
        core = cores[aid][int(rng.integers(len(cores[aid])))]
        filters = [x for x in (core["dna"]["option"], core["dna"]["meals"]) if x in OPTION_FILTERS | MEAL_FILTERS]
        pickup = PICKUP_WISH[int(rng.choice(3, p=[p for _, p in PICKUP_WISH]))][0]
        market = markets[int(rng.choice(len(markets), p=mw / mw.sum()))]
        rows.append({"event_id": f"se-{i:05d}", "ts": ANCHOR - timedelta(days=int(rng.integers(0, DAYS))), "source_market": market,
                     "attraction_id": aid, "filters": list(filters), "pickup": pickup})
    return rows
