"""Remix component catalogue: the parts suppliers already sell on their own (synthetic, disclosed in DATA.md).

- Entry tickets at an attraction's meeting point, with time slots.
- Transfers between a hotel zone and a meeting point, one way, shared (per seat, fixed timetable) or
  private (per vehicle, on request).
- A buffet-lunch voucher where the catalogue sells "ticket + lunch".

Every part has a supplier, a meeting point, a time window, a price, a cancellation rule and resale terms
(some rates are "package only" and must never be bundled).

How prices are set. These parameters were fixed before any Remix result was computed:
- Ticket: the market's own price for that ticket. That is the median of packaged listings that sell the
  same core (same meals, access, option, stops and cancellation) without a hotel transfer, times a
  per-supplier net-rate factor (mean ~1.0, so no built-in discount). Where every package of a core
  includes a transfer, the ticket is that package's median minus PACKAGE_TRANSFER_SHARE. This applies
  only where a ticket alone is realistic: day trips, where the coach *is* the tour, get no standalone ticket.
- Transfers: Dubai-style tariffs on road distance. Private: ₹1,600 + ₹55/km per sedan. Shared: ₹350 + ₹9/km
  per seat. Times a per-supplier factor and noise.
Any saving a Remix finds comes from these numbers versus the packaged prices written in M2, not from a
discount planted on parts.
"""
import math
import re

import numpy as np

from samesame import city
from samesame.data import activities
from samesame.data.feeds import _new_id
from samesame.ranking.score import haversine_m

HOTEL_PICKUPS = ("Shared hotel pickup", "Private hotel pickup")
PACKAGE_TRANSFER_SHARE = {"Shared hotel pickup": 0.20, "Private hotel pickup": 0.30}   # assumption
TICKET_NET = {"kestrel": 0.95, "mynah": 1.00, "heron": 0.99, "bulbul": 1.02, "hornbill": 1.00, "sunbird": 0.97}
TRANSFER_NET = {"kestrel": 0.92, "mynah": 1.06, "heron": 1.00, "bulbul": 1.02, "hornbill": 1.00, "sunbird": 0.96}
TRANSFER_SHARE = {"kestrel": 1.2, "sunbird": 1.0, "hornbill": 0.9, "mynah": 0.8, "bulbul": 0.6, "heron": 0.5}
PRIVATE_BASE, PRIVATE_KM = 1600, 55          # ₹ per sedan, one way
SHARED_BASE, SHARED_KM = 350, 9              # ₹ per seat, one way
VEHICLES = [("Sedan", 3, 1.0), ("SUV", 6, 1.35)]
SHARED_COLLECTION_MIN = 30                   # a shared vehicle collects/drops at several hotels
LUNCH_PP = 1650                              # buffet lunch voucher at an attraction
NOT_BUNDLEABLE = {"kestrel": 0.35}           # share of a supplier's rates sold "package only"; others 0.10
NRF_TRANSFER = {"kestrel": 0.30}             # share of private transfers sold non-refundable; others 0.05
NO_STANDALONE_TICKET = {"daytrip"}
SHARED_CATS = {"fixed", "park", "show", "observation", "museum"}
# Shared timetables (arrive at / leave from the meeting point). Desert runs its own.
SHARED_TO = {"default": ["09:30", "15:00", "19:15"], "desert-safari": ["07:30", "15:15"]}
SHARED_FROM = {"default": ["13:00", "18:00", "22:30"], "desert-safari": ["11:00", "20:15"]}

# Ticket slots (start times) and hours on site
FIXED_SLOTS = {"bk-day": (["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"], 1.5),
               "bk-sunset": (["17:00", "17:30"], 1.5), "bk-sky": (["10:00", "12:00", "14:00", "16:00", "18:00", "20:00"], 2),
               "ds-evening-shared": (["15:30"], 4.5), "ds-morning": (["08:00"], 2.5), "ds-private": (["15:00"], 5),
               "dc-standard": (["20:00", "20:30"], 2), "dc-transfer": (["20:00", "20:30"], 2), "dc-premium": (["20:00"], 2)}
CAT_SLOTS = {"daytrip": ["08:00"], "park": ["10:00", "11:00", "12:00", "13:00"], "museum": ["10:00", "12:00", "14:00", "16:00"],
             "show": ["15:00", "19:30"], "tour": ["09:00", "16:00"], "observation": ["10:00", "12:00", "14:00", "16:00"]}
OPTION_SLOTS = {"Sunset slot": ["17:00", "17:30"], "Evening slot": ["19:00", "19:30"]}


def hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def road_km(lat1, lng1, lat2, lng2) -> float:
    return haversine_m(lat1, lng1, lat2, lng2) / 1000 * city.ROAD_FACTOR


def drive_min(km: float) -> int:
    city_km = min(km, 15)
    return int(math.ceil(city_km / city.CITY_KMH * 60 + max(km - 15, 0) / city.HIGHWAY_KMH * 60 + 5))


def meeting_point(att: dict) -> dict:
    if att["category"] in NO_STANDALONE_TICKET:            # day trips leave by coach from the mall
        name, lat, lng = city.COACH_BAY
        return {"meeting_point_id": "mp-coach-bay", "name": name, "lat": lat, "lng": lng, "attraction_id": None, "shared": True}
    name, lat, lng = city.MEETING_POINTS.get(att["attraction_id"], (att["name"].split(" (")[0].split(",")[0], att["lat"], att["lng"]))
    return {"meeting_point_id": f"mp-{att['attraction_id']}", "name": name, "lat": lat, "lng": lng,
            "attraction_id": att["attraction_id"], "shared": att["category"] in SHARED_CATS}


def _core(dna: dict) -> tuple:
    return tuple(dna[k] for k in ("meals", "access", "option", "stops", "cancel"))


def _strip_pickup(name: str) -> str:
    s = re.sub(r"(,\s*)?(with |\+ )?(return )?hotel (pickup|transfer)s?", "", name, flags=re.I)
    s = re.sub(r"\s*·\s*,\s*", " · ", s).strip(" ·,")
    return s


def _pick_suppliers(rng, weights: dict, lo: int, hi: int) -> list[str]:
    sups = list(weights)
    w = np.array([weights[s] for s in sups], dtype=float)
    n = int(rng.integers(lo, hi + 1))
    return [str(s) for s in rng.choice(sups, size=min(n, len(sups)), replace=False, p=w / w.sum())]


def _bundleable(rng, sup) -> bool:
    return bool(rng.random() >= NOT_BUNDLEABLE.get(sup, 0.10))


def _ticket_title(att_name: str, suffix: str, sup: str, rng) -> str:
    return activities._title(att_name, suffix, sup, rng) + {"kestrel": " - TKT ONLY", "mynah": " (ticket only)", "heron": " · entry",
                                                            "bulbul": " tkt", "hornbill": " (entry ticket)", "sunbird": " | Ticket"}[sup]


def generate(attractions: list[dict], variants: list[dict], listings: list[dict], truth: list[dict], rng: np.random.Generator):
    att = {a["attraction_id"]: a for a in attractions}
    cat = {a[0]: (a[4], a[6]) for a in activities.ATTRACTIONS}
    price_of: dict[str, list[float]] = {}
    for l, t in zip(listings, truth):
        price_of.setdefault(t["variant_id"], []).append(l["price_pp"])
    mps = {a: meeting_point(att[a]) for a in att}

    cores: dict[tuple, list[dict]] = {}
    for v in variants:
        cores.setdefault((v["attraction_id"], _core(v["dna"])), []).append(v)

    components = []
    for (aid, core), vs in sorted(cores.items(), key=lambda kv: (kv[0][0], [v["variant_id"] for v in kv[1]])):
        category, base_hours = cat[aid]
        alone = [v for v in vs if v["dna"]["pickup"] not in HOTEL_PICKUPS]
        if alone:
            src = min(alone, key=lambda v: v["variant_id"])
            ref = float(np.median(price_of[src["variant_id"]]))
            suffix = src["name"]
        elif category in NO_STANDALONE_TICKET:
            continue
        else:
            src = min(vs, key=lambda v: np.median(price_of[v["variant_id"]]))
            ref = float(np.median(price_of[src["variant_id"]])) * (1 - PACKAGE_TRANSFER_SHARE[src["dna"]["pickup"]])
            suffix = _strip_pickup(src["name"]) + " · meet at the meeting point"
        if src["variant_id"] in FIXED_SLOTS:
            slots, hours = FIXED_SLOTS[src["variant_id"]]
        else:
            slots = OPTION_SLOTS.get(src["dna"]["option"], CAT_SLOTS.get(category, ["10:00"]))
            hours = src["hours"] if src["dna"]["pickup"] not in HOTEL_PICKUPS else base_hours
        dna = {**src["dna"], "pickup": "No transfer", "duration": f"{hours:g} h"}
        tags = [t for t in src["tags"] if t != "pickup"]
        for sup in _pick_suppliers(rng, activities.ACT_SHARE, 2, 4):
            price = round(ref * TICKET_NET[sup] * float(np.exp(rng.normal(0, 0.05))), -1)
            ok = _bundleable(rng, sup)
            components.append({"component_id": _new_id(f"{sup}:T", f"{aid}|{core}|{sup}"), "supplier_id": sup, "role": "ticket",
                               "attraction_id": aid, "meeting_point_id": mps[aid]["meeting_point_id"],
                               "title": _ticket_title(att[aid]["name"], suffix, sup, rng), "description": activities._desc(tags, dna, rng),
                               "price": price, "price_unit": "per person", "max_pax": 99, "mode": None, "vehicle": None, "zone_id": None,
                               "direction": None, "slots": list(slots), "hours": float(hours), "travel_min": None,
                               "cancel": dna["cancel"], "bundleable": ok, "resale_terms": "Bundleable" if ok else "Package only: not for resale in bundles",
                               "source_variant": src["variant_id"]})
        # a lunch voucher where the catalogue sells "ticket + lunch" at this attraction
        sells_lunch = any(v["dna"]["meals"] == "Buffet lunch" for v in variants if v["attraction_id"] == aid)
        if sells_lunch and alone and core[0] == "No meals" and core[2] == activities._BASE["option"]:
            short = att[aid]["name"].split(" (")[0].split(",")[0]
            for sup in _pick_suppliers(rng, activities.ACT_SHARE, 2, 2):
                ok = _bundleable(rng, sup)
                components.append({"component_id": _new_id(f"{sup}:L", f"{aid}|lunch|{sup}"), "supplier_id": sup, "role": "addon",
                                   "attraction_id": aid, "meeting_point_id": mps[aid]["meeting_point_id"],
                                   "title": f"Buffet lunch voucher, {short}", "description": "Buffet lunch included. Free cancellation up to 24h.",
                                   "price": round(LUNCH_PP * TICKET_NET[sup] * float(np.exp(rng.normal(0, 0.06))), -1), "price_unit": "per person",
                                   "max_pax": 99, "mode": None, "vehicle": None, "zone_id": None, "direction": None, "slots": ["12:00", "13:00", "14:00"],
                                   "hours": 1.0, "travel_min": None, "cancel": "Free until 24 h", "bundleable": ok,
                                   "resale_terms": "Bundleable" if ok else "Package only: not for resale in bundles", "source_variant": None})

    used = sorted({c["meeting_point_id"] for c in components})
    by_id = {m["meeting_point_id"]: m for m in mps.values()}           # the coach bay is shared by every day trip
    for mp_id in used:
        mp = by_id[mp_id]
        for zid, zname, zlat, zlng in city.ZONES:
            km = road_km(zlat, zlng, mp["lat"], mp["lng"])
            drive = drive_min(km)
            for direction in ("to", "from"):
                route = f"{zname} hotels → {mp['name']}" if direction == "to" else f"{mp['name']} → {zname} hotels"
                for sup in _pick_suppliers(rng, TRANSFER_SHARE, 2, 3):
                    for vname, seats, vmult in VEHICLES:
                        price = round((PRIVATE_BASE + PRIVATE_KM * km) * vmult * TRANSFER_NET[sup] * float(np.exp(rng.normal(0, 0.06))), -1)
                        ok = _bundleable(rng, sup)
                        cancel = "Non-refundable" if rng.random() < NRF_TRANSFER.get(sup, 0.05) else "Free until 24 h"
                        components.append({"component_id": _new_id(f"{sup}:X", f"{mp_id}|{zid}|{direction}|private|{vname}|{sup}"),
                                           "supplier_id": sup, "role": "transfer", "attraction_id": mp["attraction_id"], "meeting_point_id": mp_id,
                                           "title": f"Private transfer, {route} ({vname}, up to {seats})", "description": "",
                                           "price": price, "price_unit": "per vehicle", "max_pax": seats, "mode": "private", "vehicle": vname,
                                           "zone_id": zid, "direction": direction, "slots": [], "hours": None, "travel_min": drive,
                                           "cancel": cancel, "bundleable": ok, "resale_terms": "Bundleable" if ok else "Package only: not for resale in bundles",
                                           "source_variant": None})
                if mp["shared"]:
                    times = (SHARED_TO if direction == "to" else SHARED_FROM)
                    times = times.get(mp["attraction_id"], times["default"])
                    for sup in _pick_suppliers(rng, TRANSFER_SHARE, 1, 2):
                        price = round((SHARED_BASE + SHARED_KM * km) * TRANSFER_NET[sup] * float(np.exp(rng.normal(0, 0.06))), -1)
                        ok = _bundleable(rng, sup)
                        components.append({"component_id": _new_id(f"{sup}:X", f"{mp_id}|{zid}|{direction}|shared|{sup}"),
                                           "supplier_id": sup, "role": "transfer", "attraction_id": mp["attraction_id"], "meeting_point_id": mp_id,
                                           "title": f"Shared transfer, {route} (seat in coach)", "description": "",
                                           "price": price, "price_unit": "per person", "max_pax": 99, "mode": "shared", "vehicle": "Coach",
                                           "zone_id": zid, "direction": direction, "slots": list(times), "hours": None,
                                           "travel_min": drive + SHARED_COLLECTION_MIN, "cancel": "Free until 24 h", "bundleable": ok,
                                           "resale_terms": "Bundleable" if ok else "Package only: not for resale in bundles", "source_variant": None})
    meeting_points = [by_id[m] for m in used]
    return meeting_points, components


def airport(rng: np.random.Generator) -> tuple[dict, list[dict]]:
    """Airport transfers for Connected Trips: DXB <-> every hotel zone, private (per vehicle) and shared (hourly).
    Generated in their own pipeline stage after the booking log, so adding them doesn't move any earlier draw;
    their reliability comes from each supplier's fitted 'transfer' Promise (per supplier, not per route)."""
    name, lat, lng = city.AIRPORT_POINT
    mp = {"meeting_point_id": "mp-dxb", "name": name, "lat": lat, "lng": lng, "attraction_id": None, "shared": True}
    out = []
    for zid, zname, zlat, zlng in city.ZONES:
        if zid == city.AIRPORT_ZONE:
            continue
        km = road_km(zlat, zlng, lat, lng)
        drive = drive_min(km)
        for direction in ("from", "to"):
            route = f"DXB airport → {zname} hotels" if direction == "from" else f"{zname} hotels → DXB airport"
            for sup in _pick_suppliers(rng, TRANSFER_SHARE, 2, 3):
                for vname, seats, vmult in VEHICLES:
                    ok = _bundleable(rng, sup)
                    out.append({"component_id": _new_id(f"{sup}:X", f"mp-dxb|{zid}|{direction}|private|{vname}|{sup}"), "supplier_id": sup,
                                "role": "transfer", "attraction_id": None, "meeting_point_id": "mp-dxb",
                                "title": f"Private airport transfer, {route} ({vname}, up to {seats})", "description": "",
                                "price": round((PRIVATE_BASE + PRIVATE_KM * km) * vmult * TRANSFER_NET[sup] * float(np.exp(rng.normal(0, 0.06))), -1),
                                "price_unit": "per vehicle", "max_pax": seats, "mode": "private", "vehicle": vname, "zone_id": zid,
                                "direction": direction, "slots": [], "hours": None, "travel_min": drive,
                                "cancel": "Non-refundable" if rng.random() < NRF_TRANSFER.get(sup, 0.05) else "Free until 24 h", "bundleable": ok,
                                "resale_terms": "Bundleable" if ok else "Package only: not for resale in bundles", "source_variant": None})
    return mp, out
