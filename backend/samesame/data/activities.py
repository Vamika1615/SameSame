"""25 real Dubai attractions -> sellable variants (Variant DNA truth) -> six supplier listings each.

Attraction names and approximate coordinates are real; variants, prices, ratings and supplier titles
are synthetic. The three demo products (Desert Safari, Burj Khalifa At the Top, Dubai Creek dhow cruise)
have hand-written variants and titles; every other attraction is generated from its category template.
"""
import numpy as np

from samesame import city
from samesame.data.feeds import _new_id
from samesame.data.world import SUPPLIERS

DNA_KEYS = ["pickup", "meals", "duration", "stops", "access", "option", "cancel"]

# id, name, lat, lng, category, base price per person (INR, synthetic), typical hours
ATTRACTIONS = [
    ("burj-khalifa", "Burj Khalifa: At the Top", 25.1972, 55.2744, "fixed", 3900, 1.5),
    ("desert-safari", "Desert Safari, Lahbab Red Dunes", 24.8300, 55.6200, "fixed", 2000, 6),
    ("dhow-cruise", "Dhow Dinner Cruise, Dubai Creek", 25.2550, 55.3030, "fixed", 2400, 2),
    ("dubai-aquarium", "Dubai Aquarium & Underwater Zoo", 25.1975, 55.2790, "park", 3100, 2),
    ("dubai-frame", "Dubai Frame", 25.2353, 55.3003, "observation", 1150, 1.5),
    ("museum-future", "Museum of the Future", 25.2192, 55.2820, "museum", 3400, 2),
    ("global-village", "Global Village", 25.0717, 55.3089, "park", 600, 4),
    ("miracle-garden", "Dubai Miracle Garden", 25.0599, 55.2440, "park", 2100, 2),
    ("img-worlds", "IMG Worlds of Adventure", 25.0815, 55.3184, "park", 6200, 6),
    ("aquaventure", "Aquaventure Waterpark, Atlantis", 25.1340, 55.1199, "park", 7200, 6),
    ("ski-dubai", "Ski Dubai", 25.1179, 55.1975, "park", 5800, 3),
    ("dubai-fountain", "Dubai Fountain Boat Ride", 25.1959, 55.2758, "tour", 1600, 0.5),
    ("abu-dhabi", "Abu Dhabi City Tour & Sheikh Zayed Grand Mosque", 24.4128, 54.4749, "daytrip", 3800, 9),
    ("hatta", "Hatta Mountain Day Trip", 24.8000, 56.1300, "daytrip", 4200, 8),
    ("old-dubai", "Old Dubai Souks & Abra Walk", 25.2644, 55.2970, "tour", 1900, 3),
    ("al-fahidi", "Al Fahidi Historical Neighbourhood", 25.2637, 55.2997, "museum", 700, 2),
    ("jumeirah-mosque", "Jumeirah Mosque Guided Visit", 25.2338, 55.2655, "museum", 600, 1.5),
    ("view-palm", "The View at The Palm", 25.1124, 55.1388, "observation", 3100, 1.5),
    ("sky-views", "Sky Views Dubai", 25.1945, 55.2690, "observation", 2200, 1.5),
    ("helicopter", "Helicopter Tour over Dubai", 25.2425, 55.3265, "tour", 16000, 0.5),
    ("balloon", "Hot Air Balloon over the Desert", 24.9800, 55.7300, "daytrip", 21000, 4),
    ("la-perle", "La Perle by Dragone", 25.0812, 55.1433, "show", 7400, 1.5),
    ("dubai-opera", "Dubai Opera", 25.1924, 55.2716, "show", 5500, 2.5),
    ("food-tour", "Old Dubai Street Food Tour", 25.2660, 55.3050, "tour", 4300, 3.5),
    ("dolphinarium", "Dubai Dolphinarium", 25.2296, 55.3260, "show", 2400, 1.5),
]

# Hand-written variants for the three demo products: (vid, name, dna, tags, hours, [(supplier, title, price, rating, desc)])
FIXED = {
    "desert-safari": [
        ("ds-evening-shared", "Evening safari · shared 4x4, BBQ dinner",
         {"pickup": "Shared hotel pickup", "meals": "BBQ dinner", "duration": "6 h · evening", "stops": "Lahbab red dunes + camp",
          "access": "Standard", "option": "Shared 4x4", "cancel": "Free until 24 h"}, ["pickup", "free_cancel"], 6, [
            ("kestrel", "DESERT SAFARI WITH BBQ DINNER (SIC)", 2450, 4.5, "SIC basis with pick-up from Dubai hotels. BBQ dinner and live show. Approx. 6 hours."),
            ("mynah", "Evening Desert Safari with BBQ Dinner (Shared)", 2650, 4.6, "Hotel pickup in a shared 4x4, BBQ dinner at camp. Duration 6 h. Free cancellation up to 24h."),
            ("hornbill", "Red Dune Desert Safari & Barbecue Dinner from Dubai", 2590, 4.4, "Collection from your hotel in a shared vehicle; barbecue dinner at the camp.")]),
        ("ds-morning", "Morning dune bashing · sandboarding, no meals",
         {"pickup": "Shared hotel pickup", "meals": "No meals", "duration": "4 h · morning", "stops": "Lahbab red dunes",
          "access": "Standard", "option": "Sandboarding", "cancel": "Non-refundable"}, ["pickup"], 4, [
            ("sunbird", "Morning Desert Safari | Dune Bashing & Sandboarding", 1990, 4.3, "Morning departure, hotel pickup in a shared 4x4. About 4 hours. NRF."),
            ("kestrel", "MORNING DUNE BASHING (SIC)", 1890, 4.1, "SIC pick-up from hotel, sandboarding included. Morning. NRF."),
            ("bulbul", "Morning Desert Safari w/ Sandboarding", 2090, 4.2, "Htl pickup, shared 4x4, morning slot. Non-refundable.")]),
        ("ds-private", "Private 4x4 · hotel pickup, BBQ dinner",
         {"pickup": "Private hotel pickup", "meals": "BBQ dinner", "duration": "7 h · evening", "stops": "Lahbab red dunes + camp",
          "access": "Standard", "option": "Private 4x4", "cancel": "Free until 48 h"}, ["pickup", "free_cancel"], 7, [
            ("heron", "Private Desert Safari with BBQ Dinner", 14200, 4.8, "Private 4x4 and driver, hotel pickup, BBQ dinner. Approx. 7 hours."),
            ("mynah", "Premium Private Desert Safari incl. BBQ Dinner", 13900, 4.7, "Private transfer from hotel. BBQ dinner. Free cancellation 48h."),
            ("bulbul", "PVT Desert Safari w/ BBQ dinner", 14600, 4.6, "PVT 4x4 ex-hotel, BBQ dinner at camp. Duration 7 h.")]),
    ],
    "burj-khalifa": [
        ("bk-day", "At the Top · levels 124-125, daytime slot",
         {"pickup": "No transfer", "meals": "No meals", "duration": "1.5 h", "stops": "Levels 124 + 125",
          "access": "Standard", "option": "Daytime slot", "cancel": "Free until 24 h"}, ["free_cancel"], 1.5, [
            ("sunbird", "Burj Khalifa At the Top (Levels 124 & 125)", 3950, 4.5, "Entry ticket, choose a daytime slot."),
            ("kestrel", "BURJ KHALIFA AT THE TOP TICKET", 3790, 4.4, "Levels 124 and 125. NRF after booking.")]),
        ("bk-sunset", "At the Top · sunset prime time",
         {"pickup": "No transfer", "meals": "No meals", "duration": "1.5 h", "stops": "Levels 124 + 125",
          "access": "Standard", "option": "Sunset slot", "cancel": "Free until 24 h"}, ["free_cancel"], 1.5, [
            ("mynah", "Burj Khalifa At the Top - Prime Time Sunset", 5600, 4.8, "Sunset time-slot, levels 124 & 125."),
            ("hornbill", "Sunset at Burj Khalifa: At the Top", 5750, 4.7, "Golden-hour slot.")]),
        ("bk-sky", "At the Top SKY · level 148 VIP lounge",
         {"pickup": "No transfer", "meals": "Refreshments", "duration": "2 h", "stops": "Levels 148 + 125 + 124",
          "access": "VIP", "option": "VIP lounge", "cancel": "Free until 24 h"}, ["free_cancel"], 2, [
            ("heron", "Burj Khalifa At the Top SKY (Level 148)", 9600, 4.6, "VIP lounge on level 148 with refreshments, then levels 125 and 124."),
            ("bulbul", "Burj Khalifa SKY lvl 148 + VIP lounge", 9350, 4.5, "VIP access, level 148, free cxl 24h.")]),
    ],
    "dhow-cruise": [
        ("dc-standard", "Creek dinner cruise · buffet, pier check-in",
         {"pickup": "Pier check-in", "meals": "Buffet dinner", "duration": "2 h", "stops": "Dubai Creek",
          "access": "Standard", "option": "Standard seat", "cancel": "Free until 24 h"}, ["free_cancel"], 2, [
            ("kestrel", "DHOW CRUISE DUBAI CREEK - BUFFET DINNER", 2350, 4.3, "Check in at Al Seef pier. Buffet dinner. Approx. 2 hours."),
            ("sunbird", "Dubai Creek Dhow Dinner Cruise | Standard Seat", 2450, 4.4, "Buffet dinner on board, standard seat, pier check-in. Free cancellation.")]),
        ("dc-transfer", "Creek dinner cruise · buffet + hotel transfer",
         {"pickup": "Shared hotel pickup", "meals": "Buffet dinner", "duration": "3 h", "stops": "Dubai Creek",
          "access": "Standard", "option": "Standard seat", "cancel": "Free until 24 h"}, ["pickup", "free_cancel"], 3, [
            ("mynah", "Dhow Dinner Cruise Dubai Creek with Hotel Transfer", 3150, 4.6, "Shared hotel pickup, buffet dinner. Duration 3 h. Free cancellation up to 24h."),
            ("hornbill", "Dubai Creek Dhow Cruise incl. Transfers", 3090, 4.5, "Collection from your hotel; buffet dinner on board.")]),
        ("dc-premium", "Upper deck · set menu, VIP",
         {"pickup": "Pier check-in", "meals": "Set dinner", "duration": "2 h", "stops": "Dubai Creek",
          "access": "VIP", "option": "VIP deck", "cancel": "Free until 24 h"}, ["free_cancel"], 2, [
            ("heron", "Premium Dhow Cruise, Upper Deck Set Menu", 4250, 4.7, "VIP upper deck, set dinner menu. Pier check-in."),
            ("bulbul", "Dhow Cruise VIP deck w/ set dinner", 4100, 4.5, "Set menu, VIP deck, check-in at pier.")]),
    ],
}

# Category templates: (suffix, dna overrides, tags, price multiplier, hours multiplier)
_BASE = {"pickup": "No transfer", "meals": "No meals", "access": "Standard", "option": "Self-guided", "cancel": "Free until 24 h"}
TEMPLATES = {
    "temple": [("entry ticket", {}, ["free_cancel"], 1.0, 1.0),
               ("skip-the-line + audio guide", {"access": "Skip-the-line", "option": "Audio guide"}, ["skip_line", "free_cancel"], 1.6, 0.8),
               ("guided walk with hotel pickup", {"pickup": "Shared hotel pickup", "option": "English-speaking guide"}, ["pickup", "free_cancel"], 2.6, 1.6)],
    "daytrip": [("join-in tour, shared transfer", {"pickup": "Shared hotel pickup", "option": "Group (max 15)"}, ["pickup", "free_cancel"], 1.0, 1.0),
                ("private car with lunch", {"pickup": "Private hotel pickup", "meals": "Lunch", "option": "Private guide (English)", "cancel": "Free until 48 h"},
                 ["pickup", "lunch", "free_cancel"], 2.4, 1.1),
                (f"meet at {city.MEETING_POINT}, no refunds", {"pickup": f"Meeting point ({city.MEETING_POINT})", "cancel": "Non-refundable", "option": "Group (max 30)"}, [], 0.7, 1.0)],
    "observation": [("day ticket", {"access": "Time-slot", "option": "Daytime slot"}, ["free_cancel"], 1.0, 1.0),
                    ("sunset slot", {"access": "Time-slot", "option": "Sunset slot"}, ["free_cancel"], 1.3, 1.0),
                    ("ticket + buffet dinner", {"access": "Time-slot", "option": "Evening slot", "meals": "Buffet dinner"}, ["free_cancel"], 2.8, 1.8)],
    "cruise": [("buffet dinner, standard seat", {"meals": "Buffet dinner", "option": "Standard seat", "pickup": "Pier check-in"}, ["free_cancel"], 1.0, 1.0),
               ("buffet dinner, window seat + hotel transfer", {"meals": "Buffet dinner", "option": "Window seat", "pickup": "Shared hotel pickup"}, ["pickup", "free_cancel"], 1.45, 1.4),
               ("set menu, VIP deck", {"meals": "Set dinner", "access": "VIP", "option": "VIP deck", "pickup": "Pier check-in"}, ["free_cancel"], 1.9, 1.0)],
    "park": [("ticket only", {}, ["free_cancel"], 1.0, 1.0),
             ("ticket + lunch", {"meals": "Buffet lunch"}, ["lunch", "free_cancel"], 1.35, 1.0),
             ("ticket + return hotel transfer", {"pickup": "Shared hotel pickup"}, ["pickup", "free_cancel"], 1.6, 1.25)],
    "show": [("standard seat", {"option": "Standard seat"}, ["free_cancel"], 1.0, 1.0),
             ("VIP seat", {"access": "VIP", "option": "VIP seat"}, ["free_cancel"], 1.7, 1.0),
             ("standard seat + hotel transfer", {"option": "Standard seat", "pickup": "Shared hotel pickup"}, ["pickup", "free_cancel"], 1.45, 1.6)],
    "museum": [("entry ticket", {}, ["free_cancel"], 1.0, 1.0),
               ("timed entry with guide", {"access": "Time-slot", "option": "English-speaking guide"}, ["free_cancel"], 1.5, 1.0)],
    "tour": [("small group", {"option": "Group (max 10)", "pickup": "Meeting point"}, ["free_cancel"], 1.0, 1.0),
             ("private with hotel pickup", {"option": "Private guide (English)", "pickup": "Private hotel pickup"}, ["pickup", "free_cancel"], 2.2, 1.1)],
}
# How suppliers phrase the facts that DNA filters search for (keyword search only knows a few of these)
PHRASES = {"pickup": ["hotel pickup", "pick-up from your hotel", "collection from your hotel", "ex-hotel transfer", "transfer included",
                      "SIC from hotel"],
           "skip_line": ["skip-the-line", "fast-track entry", "priority entrance", "no queuing"],
           "free_cancel": ["free cancellation", "cancel free up to 24h", "refundable to 24h", "FC 24H"],
           "lunch": ["lunch included", "local lunch", "incl. buffet lunch", "meal included"]}
# Which suppliers sell activities, weighted (Sunbird is strongest on activities; Heron sells them but fails often)
ACT_SHARE = {"kestrel": 1.0, "mynah": 0.9, "heron": 0.8, "bulbul": 0.6, "hornbill": 0.8, "sunbird": 1.3}


def _title(base: str, suffix: str, sup: str, rng) -> str:
    short = base.split(" (")[0].split(",")[0]
    forms = {
        "kestrel": f"{short} - {suffix}".upper().replace("PRIVATE", "PVT").replace("WITH", "W/").replace("SHARED TRANSFER", "SIC"),
        "mynah": f"{short}: {suffix[0].upper() + suffix[1:]}",
        "heron": f"{short} ({suffix})",
        "bulbul": f"{short} {suffix}".replace("with", "w/").replace("hotel", "htl"),
        "hornbill": f"{suffix[0].upper() + suffix[1:]} at {short}",
        "sunbird": f"{short} | {suffix.title()}",
    }
    return forms[sup]


def _desc(tags: list[str], dna: dict, rng) -> str:
    bits = []
    if rng.random() < 0.6:
        h = dna["duration"].split(" ")[0]
        bits.append(str(rng.choice([f"duration {h} h", f"approx. {h} hours", f"about {h} hrs"])))
    for t in tags:
        if rng.random() < 0.85:                      # suppliers don't always mention what's included
            bits.append(str(rng.choice(PHRASES[t])))
    if dna["cancel"] == "Non-refundable":
        bits.append(str(rng.choice(["NRF", "non-refundable", "no refunds"])))
    if dna["meals"] not in ("No meals",) and "lunch" not in tags:
        bits.append(dna["meals"].lower())
    rng.shuffle(bits)
    return (". ".join(b[0].upper() + b[1:] for b in bits) + ".") if bits else "See itinerary."


def generate(rng: np.random.Generator):
    attractions, variants, listings, truth = [], [], [], []
    sups = list(SUPPLIERS)
    for aid, name, lat, lng, cat, price, hours in ATTRACTIONS:
        attractions.append({"attraction_id": aid, "name": name, "lat": lat, "lng": lng, "category": cat,
                            "volatility": float(np.exp(rng.normal(0, 0.25)))})
        if cat == "fixed":
            for vid, vname, dna, tags, h, members in FIXED[aid]:
                variants.append({"variant_id": vid, "attraction_id": aid, "name": vname, "dna": dna, "tags": tags, "hours": h})
                for sup, title, p, rating, desc in members:
                    lid = _new_id(f"{sup}:A", f"{vid}|{sup}")
                    listings.append({"listing_id": lid, "supplier_id": sup, "title": title, "description": desc, "price_pp": float(p),
                                     "rating": rating, "reviews": int(rng.integers(40, 2400)), "lat": lat, "lng": lng})
                    truth.append({"listing_id": lid, "variant_id": vid, "attraction_id": aid})
            continue
        for k, (suffix, over, tags, pm, hm) in enumerate(TEMPLATES[cat]):
            h = round(hours * hm * 2) / 2
            dna = {**_BASE, **over, "duration": f"{h:g} h", "stops": name.split(" (")[0]}
            vid = f"{aid}-v{k + 1}"
            vname = suffix[0].upper() + suffix[1:]
            variants.append({"variant_id": vid, "attraction_id": aid, "name": vname, "dna": {key: dna[key] for key in DNA_KEYS},
                             "tags": list(tags), "hours": h})
            w = np.array([ACT_SHARE[s] for s in sups]); w = w / w.sum()
            n = int(rng.integers(2, 4))
            for sup in rng.choice(sups, size=n, replace=False, p=w):
                sup = str(sup)
                lid = _new_id(f"{sup}:A", f"{vid}|{sup}")
                p = price * pm * {"kestrel": 0.94, "sunbird": 0.97}.get(sup, 1.0) * float(np.exp(rng.normal(0, 0.06)))
                listings.append({"listing_id": lid, "supplier_id": sup, "title": _title(name, suffix, sup, rng),
                                 "description": _desc(tags, dna, rng), "price_pp": float(round(p, -1)),
                                 "rating": round(float(min(5.0, max(3.6, rng.normal(4.45, 0.2)))), 1),
                                 "reviews": int(rng.integers(15, 3000)), "lat": lat, "lng": lng})
                truth.append({"listing_id": lid, "variant_id": vid, "attraction_id": aid})
    return attractions, variants, listings, truth
