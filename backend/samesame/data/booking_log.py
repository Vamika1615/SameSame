"""Booking-attempt log: 24,000 hotel/activity attempts plus 6,000 Remix-part attempts over 180 days, sampled from world.BEHAVIOUR.

This is the only thing the Promise model and popularity features see. Each row is what an agency
platform would really record: who tried to book what, how far ahead, the quoted price, and what the
supplier answered at booking time.
"""
from datetime import date, timedelta

import numpy as np

from samesame import city
from samesame.data import world

N_ATTEMPTS = 24_000
N_COMPONENT_ATTEMPTS = 6_000               # Remix parts (tickets, lunch vouchers, transfers), appended after the rest
DAYS = 180
ANCHOR = date(2026, 11, 3)                 # snapshot date; "last 90 days" is relative to this
MARKETS = [("IN", 0.40), ("TH", 0.14), ("MY", 0.10), ("SG", 0.09), ("AE", 0.08), ("GB", 0.07), ("AU", 0.06), ("CN", 0.06)]


def _pick(rng, items, weights):
    w = np.asarray(weights, dtype=float)
    return items[int(rng.choice(len(items), p=w / w.sum()))]


def generate(hotels, listings, truth, offers, attractions, act_listings, act_truth, rng: np.random.Generator, components=()):
    hotel_of = {t["listing_id"]: t["hotel_id"] for t in truth}
    by_hotel = {h["hotel_id"]: h for h in hotels}
    offers_of: dict[str, list] = {}
    for o in offers:
        offers_of.setdefault(o["listing_id"], []).append(o)
    sellable = [l for l in listings if l["listing_id"] in offers_of]
    att_of = {t["listing_id"]: t["attraction_id"] for t in act_truth}
    vol_att = {a["attraction_id"]: a["volatility"] for a in attractions}

    # latent demand: hotels near the centre, higher stars and family facilities get more attempts;
    # Indian agents additionally favour family rooms, pools and Indian breakfast options
    def appeal(h, market):
        cen = np.exp(-((h["lat"] - city.CORE[0]) ** 2 + (h["lng"] - city.CORE[1]) ** 2) ** 0.5 / 0.05)
        a = (0.4 + cen) * (0.6 + 0.2 * h["star"])
        if market == "IN":
            a *= (1 + 0.8 * h["family_rooms"] + 0.4 * h["pool"] + 0.6 * ("Indian breakfast options" in h.get("amenities", [])))
        return a

    hotel_sups = list(world.STYLE)
    hotel_w = [world.STYLE[s]["share"] for s in hotel_sups]
    act_w = {"kestrel": 0.22, "mynah": 0.16, "heron": 0.12, "bulbul": 0.12, "hornbill": 0.14, "sunbird": 0.24}
    by_sup_h = {s: [l for l in sellable if l["supplier_id"] == s] for s in hotel_sups}
    by_sup_a = {s: [l for l in act_listings if l["supplier_id"] == s] for s in hotel_sups}
    appeal_cache = {(l["listing_id"], m): appeal(by_hotel[hotel_of[l["listing_id"]]], m) for l in sellable for m, _ in MARKETS}

    rows = []
    agents = {m: [f"ag-{m.lower()}-{i:03d}" for i in range(60 if m == "IN" else 25)] for m, _ in MARKETS}
    for i in range(N_ATTEMPTS):
        market = _pick(rng, [m for m, _ in MARKETS], [w for _, w in MARKETS])
        ts = ANCHOR - timedelta(days=int(rng.integers(0, DAYS)))
        lead = int(min(180, max(0, rng.lognormal(np.log(21), 0.85))))
        if rng.random() < 0.75:
            product = "hotel"
            sup = _pick(rng, hotel_sups, hotel_w)
            pool = by_sup_h[sup]
            lst = _pick(rng, pool, [appeal_cache[(l["listing_id"], market)] for l in pool])
            offer = offers_of[lst["listing_id"]][int(rng.integers(len(offers_of[lst["listing_id"]])))]
            nights = int(rng.choice([1, 2, 2, 3, 3, 3, 4, 5, 7]))
            quoted = offer["nightly"] * nights
            vol = by_hotel[hotel_of[lst["listing_id"]]]["volatility"]
            item, offer_id = lst["listing_id"], offer["offer_id"]
        else:
            product = "activity"
            sup = _pick(rng, hotel_sups, [act_w[s] for s in hotel_sups])
            pool = by_sup_a[sup]
            lst = pool[int(rng.integers(len(pool)))]
            pax = int(rng.choice([1, 2, 2, 2, 3, 4]))
            quoted = lst["price_pp"] * pax
            vol = vol_att[att_of[lst["listing_id"]]]
            item, offer_id = lst["listing_id"], lst["listing_id"]
        pc, so, err, inc = world.behaviour(sup, product, lead, vol)
        u = rng.random()
        outcome = "price_changed" if u < pc else "sold_out" if u < pc + so else "error" if u < pc + so + err else "confirmed"
        final = quoted
        if outcome == "price_changed":
            final = round(quoted * (1 + inc * float(rng.uniform(0.5, 1.5))), -1)
        elif outcome in ("sold_out", "error"):
            final = None
        rows.append({"attempt_id": f"ba-{i:05d}", "ts": ts, "supplier_id": sup, "product_type": product, "listing_id": item,
                     "offer_id": offer_id, "lead_days": lead, "lead_bucket": world.lead_bucket(lead)[0], "source_market": market,
                     "agent_id": agents[market][int(rng.integers(len(agents[market])))], "quoted": float(quoted),
                     "final_price": None if final is None else float(final), "outcome": outcome})

    # Remix parts: sold on their own today (agents already buy tickets and transfers), so the log has their history too
    vol_att_c = {c["component_id"]: vol_att.get(c["attraction_id"], 1.0) if c["role"] != "transfer" else 1.0 for c in components}
    for i in range(N_COMPONENT_ATTEMPTS if components else 0):
        c = components[int(rng.integers(len(components)))]
        market = _pick(rng, [m for m, _ in MARKETS], [w for _, w in MARKETS])
        ts = ANCHOR - timedelta(days=int(rng.integers(0, DAYS)))
        lead = int(min(180, max(0, rng.lognormal(np.log(21), 0.85))))
        product = "transfer" if c["role"] == "transfer" else "ticket"
        quoted = c["price"] * (1 if c["price_unit"] == "per vehicle" else int(rng.choice([1, 2, 2, 3, 4])))
        pc, so, err, inc = world.behaviour(c["supplier_id"], product, lead, vol_att_c[c["component_id"]])
        u = rng.random()
        outcome = "price_changed" if u < pc else "sold_out" if u < pc + so else "error" if u < pc + so + err else "confirmed"
        final = round(quoted * (1 + inc * float(rng.uniform(0.5, 1.5))), -1) if outcome == "price_changed" else \
            None if outcome in ("sold_out", "error") else quoted
        rows.append({"attempt_id": f"bc-{i:05d}", "ts": ts, "supplier_id": c["supplier_id"], "product_type": product,
                     "listing_id": c["component_id"], "offer_id": c["component_id"], "lead_days": lead,
                     "lead_bucket": world.lead_bucket(lead)[0], "source_market": market,
                     "agent_id": agents[market][int(rng.integers(len(agents[market])))], "quoted": float(quoted),
                     "final_price": None if final is None else float(final), "outcome": outcome})
    return rows
