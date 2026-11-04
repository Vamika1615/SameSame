"""25 real Bangkok attractions -> sellable variants (Variant DNA truth) -> six supplier listings each.

Attraction names and approximate coordinates are real; variants, prices, ratings and supplier titles
are synthetic. The three demo products (Floating Market, Grand Palace, SkyWalk) have hand-written
variants and titles because the brief names them; every other attraction is generated from its
category template.
"""
import numpy as np

from samesame.data.feeds import _new_id
from samesame.data.world import SUPPLIERS

DNA_KEYS = ["pickup", "meals", "duration", "stops", "access", "option", "cancel"]

# id, name, lat, lng, category, base price per person (INR, synthetic), typical hours
ATTRACTIONS = [
    ("grand-palace", "Grand Palace & Wat Phra Kaew", 13.7500, 100.4913, "fixed", 1150, 3),
    ("wat-pho", "Wat Pho (Reclining Buddha)", 13.7465, 100.4930, "temple", 450, 2),
    ("wat-arun", "Wat Arun (Temple of Dawn)", 13.7437, 100.4889, "temple", 350, 1.5),
    ("floating-market", "Damnoen Saduak Floating Market", 13.5196, 99.9590, "fixed", 1250, 6),
    ("maeklong", "Maeklong Railway Market", 13.4072, 100.0006, "daytrip", 1400, 6),
    ("ayutthaya", "Ayutthaya Historical Park", 14.3556, 100.5676, "daytrip", 1900, 9),
    ("skywalk", "Mahanakhon SkyWalk (rooftop)", 13.7234, 100.5283, "fixed", 940, 1.5),
    ("baiyoke", "Baiyoke Sky Observation Deck", 13.7543, 100.5403, "observation", 550, 1.5),
    ("dinner-cruise", "Chao Phraya Dinner Cruise", 13.7234, 100.5139, "cruise", 1600, 2),
    ("sea-life", "SEA LIFE Bangkok Ocean World", 13.7462, 100.5347, "park", 1100, 3),
    ("safari-world", "Safari World Bangkok", 13.8606, 100.7053, "park", 1700, 7),
    ("dream-world", "Dream World", 13.9876, 100.6766, "park", 1300, 7),
    ("calypso", "Calypso Cabaret, Asiatique", 13.7044, 100.5030, "show", 1150, 1.5),
    ("muay-thai", "Muay Thai at Rajadamnern Stadium", 13.7597, 100.5092, "show", 2200, 3),
    ("jim-thompson", "Jim Thompson House Museum", 13.7492, 100.5283, "museum", 350, 1.5),
    ("chatuchak", "Chatuchak Weekend Market", 13.7999, 100.5500, "tour", 900, 4),
    ("chinatown-food", "Chinatown (Yaowarat) Street Food", 13.7398, 100.5100, "tour", 1700, 3.5),
    ("tuktuk-night", "Bangkok by Tuk-Tuk at Night", 13.7465, 100.4930, "tour", 1900, 4),
    ("khlong-boat", "Thonburi Canals Long-tail Boat", 13.7437, 100.4889, "tour", 1100, 2),
    ("cooking-class", "Thai Cooking Class, Silom", 13.7262, 100.5265, "tour", 1600, 4),
    ("bang-krachao", "Bang Krachao Bicycle Tour", 13.6936, 100.5650, "tour", 1500, 5),
    ("coral-island", "Pattaya & Coral Island", 12.9236, 100.8825, "daytrip", 2300, 11),
    ("river-kwai", "Kanchanaburi & the Bridge on the River Kwai", 14.0412, 99.5036, "daytrip", 2100, 11),
    ("asiatique-wheel", "Asiatique Sky Ferris Wheel", 13.7044, 100.5030, "observation", 450, 0.5),
    ("wat-pho-massage", "Thai Massage at the Wat Pho School", 13.7465, 100.4930, "museum", 650, 1),
]

# Hand-written variants for the three products the brief names: (vid, name, dna, tags, hours, [(supplier, title, price, rating, desc)])
FIXED = {
    "floating-market": [
        ("fm-rail-shared", "Floating + Railway Market · shared transfer",
         {"pickup": "Shared hotel pickup", "meals": "No meals", "duration": "6 h · half day", "stops": "Floating + Maeklong Railway",
          "access": "Standard", "option": "Boat ride extra", "cancel": "Free until 24 h"}, ["pickup", "free_cancel"], 6, [
            ("kestrel", "Damnoen Saduak Floating Market & Maeklong Railway Market Tour", 1850, 4.5, "Join-in tour, approx. 6 hours. Pick-up from central Bangkok hotels."),
            ("mynah", "Railway Market + Floating Market Half Day (Join-in)", 2050, 4.6, "Shared van with hotel pickup. Duration 6 h. Free cancellation up to 24h."),
            ("hornbill", "Maeklong Train Market and Damnoen Saduak Floating Market Trip from Bangkok", 1990, 4.4, "Collection from your hotel in a shared minivan.")]),
        ("fm-morning", "Floating Market only · morning, meet at Siam",
         {"pickup": "Meeting point (Siam)", "meals": "No meals", "duration": "4.5 h · morning", "stops": "Floating market only",
          "access": "Standard", "option": "Boat ride included", "cancel": "Non-refundable"}, [], 4.5, [
            ("sunbird", "Damnoen Saduak Floating Market Morning Tour", 1250, 4.3, "Meet at Siam BTS exit 4. Boat ride included. About 4.5 hours."),
            ("kestrel", "Floating Market Early Morning (SIC)", 1190, 4.1, "SIC basis from meeting point. NRF."),
            ("bulbul", "Damnoen Saduak Floating Mkt - Half Day Morning", 1320, 4.2, "Boat included. Assemble at Siam Paragon.")]),
        ("fm-private-lunch", "Floating + Railway Market · private car, Thai lunch",
         {"pickup": "Private hotel pickup", "meals": "Thai lunch", "duration": "8 h · full day", "stops": "Floating + Maeklong Railway",
          "access": "Standard", "option": "Private guide (English)", "cancel": "Free until 48 h"}, ["pickup", "free_cancel", "lunch"], 8, [
            ("heron", "Private Floating & Railway Market Tour with Thai Lunch", 4600, 4.8, "Private car and driver, hotel pickup, lunch included. Approx. 8 hours."),
            ("mynah", "Floating Market + Railway Market Private Car incl. Lunch", 4450, 4.7, "Private transfer from hotel. Lunch. Free cancellation 48h."),
            ("bulbul", "PVT Damnoen Saduak + Maeklong w/ lunch", 4800, 4.6, "PVT car ex-hotel, lunch at local restaurant. Duration 8 h.")]),
    ],
    "grand-palace": [
        ("gp-standard", "Entry ticket · standard queue",
         {"pickup": "No transfer", "meals": "No meals", "duration": "3 h", "stops": "Grand Palace + Wat Phra Kaew",
          "access": "Standard", "option": "Self-guided", "cancel": "Free until 24 h"}, ["free_cancel"], 3, [
            ("kestrel", "Grand Palace Entrance Ticket", 1150, 4.2, "Admission ticket. Queue at the gate."),
            ("sunbird", "Grand Palace & Emerald Buddha Ticket", 1190, 4.3, "Entry ticket, free cancellation 24h.")]),
        ("gp-skip", "Skip-the-line entry",
         {"pickup": "No transfer", "meals": "No meals", "duration": "2.5 h", "stops": "Grand Palace + Wat Phra Kaew",
          "access": "Skip-the-line", "option": "Self-guided", "cancel": "Free until 24 h"}, ["free_cancel", "skip_line"], 2.5, [
            ("mynah", "Grand Palace Skip-the-Line Ticket", 1650, 4.6, "Fast-track entrance, avoid the ticket queue."),
            ("heron", "Grand Palace Priority Entry", 1590, 4.5, "Priority access lane. Cancel free 24h.")]),
        ("gp-guide", "Standard entry + English guide, hotel pickup",
         {"pickup": "Shared hotel pickup", "meals": "No meals", "duration": "4 h", "stops": "Grand Palace + Wat Phra Kaew + Wat Pho",
          "access": "Standard", "option": "English-speaking guide", "cancel": "Free until 24 h"}, ["pickup", "free_cancel"], 4, [
            ("hornbill", "Grand Palace & Wat Pho Guided Tour (English)", 2350, 4.7, "English guide, hotel transfer included."),
            ("bulbul", "Grand Palace Half-Day w/ Eng Guide", 2290, 4.5, "Pick up from hotel, licensed English guide.")]),
    ],
    "skywalk": [
        ("sw-day", "Day ticket",
         {"pickup": "No transfer", "meals": "No meals", "duration": "1.5 h", "stops": "Observation deck + glass tray",
          "access": "Time-slot", "option": "Daytime slot", "cancel": "Free until 24 h"}, ["free_cancel"], 1.5, [
            ("sunbird", "Mahanakhon SkyWalk Admission", 990, 4.5, "Entry ticket, choose a daytime slot."),
            ("kestrel", "King Power Mahanakhon Skywalk Ticket", 940, 4.4, "Ticket. NRF after booking.")]),
        ("sw-sunset", "Sunset slot (17:00-18:30)",
         {"pickup": "No transfer", "meals": "No meals", "duration": "1.5 h", "stops": "Observation deck + glass tray",
          "access": "Time-slot", "option": "Sunset slot", "cancel": "Free until 24 h"}, ["free_cancel"], 1.5, [
            ("mynah", "Mahanakhon SkyWalk Sunset Entry", 1290, 4.8, "Sunset time-slot 17:00-18:30."),
            ("hornbill", "SkyWalk Bangkok at Sunset", 1340, 4.7, "Golden-hour slot.")]),
        ("sw-drink", "Day ticket + rooftop drink",
         {"pickup": "No transfer", "meals": "1 drink", "duration": "2 h", "stops": "Observation deck + glass tray + rooftop bar",
          "access": "Time-slot", "option": "With drink", "cancel": "Free until 24 h"}, ["free_cancel"], 2, [
            ("heron", "Mahanakhon SkyWalk with Welcome Drink", 1450, 4.6, "Ticket plus one drink at the rooftop bar."),
            ("bulbul", "SkyWalk + Rooftop Bar Drink", 1390, 4.5, "Entry + 1 beverage.")]),
    ],
}

# Category templates: (suffix, dna overrides, tags, price multiplier, hours multiplier)
_BASE = {"pickup": "No transfer", "meals": "No meals", "access": "Standard", "option": "Self-guided", "cancel": "Free until 24 h"}
TEMPLATES = {
    "temple": [("entry ticket", {}, ["free_cancel"], 1.0, 1.0),
               ("skip-the-line + audio guide", {"access": "Skip-the-line", "option": "Audio guide"}, ["skip_line", "free_cancel"], 1.6, 0.8),
               ("guided walk with hotel pickup", {"pickup": "Shared hotel pickup", "option": "English-speaking guide"}, ["pickup", "free_cancel"], 2.6, 1.6)],
    "daytrip": [("join-in tour, shared transfer", {"pickup": "Shared hotel pickup", "option": "Group (max 15)"}, ["pickup", "free_cancel"], 1.0, 1.0),
                ("private car with lunch", {"pickup": "Private hotel pickup", "meals": "Thai lunch", "option": "Private guide (English)", "cancel": "Free until 48 h"},
                 ["pickup", "lunch", "free_cancel"], 2.4, 1.1),
                ("meet at Victory Monument, no refunds", {"pickup": "Meeting point (Victory Monument)", "cancel": "Non-refundable", "option": "Group (max 30)"}, [], 0.7, 1.0)],
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
           "lunch": ["lunch included", "Thai lunch", "incl. buffet lunch", "meal included"]}
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
                    lid = _new_id(f"{sup}:A", rng)
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
                lid = _new_id(f"{sup}:A", rng)
                p = price * pm * {"kestrel": 0.94, "sunbird": 0.97}.get(sup, 1.0) * float(np.exp(rng.normal(0, 0.06)))
                listings.append({"listing_id": lid, "supplier_id": sup, "title": _title(name, suffix, sup, rng),
                                 "description": _desc(tags, dna, rng), "price_pp": float(round(p, -1)),
                                 "rating": round(float(min(5.0, max(3.6, rng.normal(4.45, 0.2)))), 1),
                                 "reviews": int(rng.integers(15, 3000)), "lat": lat, "lng": lng})
                truth.append({"listing_id": lid, "variant_id": vid, "attraction_id": aid})
    return attractions, variants, listings, truth
