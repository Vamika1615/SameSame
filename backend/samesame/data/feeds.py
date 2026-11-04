"""Generate the six supplier hotel feeds: listings, rooms and rate offers, with realistic corruption.

Each corruption applied to a listing is recorded in hotel_truth.corruptions (truth tables never reach
the matcher; they exist for evaluation and the data card). Prices are nightly, for 2 adults.
"""
import re

import numpy as np

from samesame.data.world import RATE_PLANS, RATE_TEXT, STYLE

AMENITIES = ["Outdoor pool", "Fitness centre", "Free Wi-Fi", "Airport shuttle (paid)", "Kids' club", "Spa", "Restaurant",
             "Rooftop bar", "24h front desk", "Family rooms", "Laundry", "Non-smoking rooms", "Connecting rooms",
             "Indian breakfast options", "Parking", "Business centre", "Room service", "Luggage storage"]
TIERS = {"Standard": 0.9, "Superior": 1.0, "Deluxe": 1.15, "Premier": 1.3, "Executive": 1.5, "Junior Suite": 1.8,
         "Suite": 2.4, "Family": 1.45}
TIER_LADDER = {2: ["Standard", "Superior", "Family"], 3: ["Standard", "Superior", "Deluxe", "Family"],
               4: ["Superior", "Deluxe", "Premier", "Executive", "Family"],
               5: ["Deluxe", "Premier", "Executive", "Junior Suite", "Suite", "Family"]}
BREAKFAST_PP = {2: 250, 3: 380, 4: 560, 5: 900}
ABBR = {"Superior": "SUP", "Deluxe": "DLX", "Standard": "STD", "Premier": "PREM", "Executive": "EXEC", "Junior Suite": "JR STE",
        "Suite": "STE", "Family": "FAM", "King": "KG", "Twin": "TWN", "Double": "DBL", "City": "CV", "Pool": "PV",
        "River": "RV", "Garden": "GV"}
NAME_ABBR = [("Bangkok", "BKK"), ("Hotel", "HTL"), ("Sukhumvit", "SUKHUMVIT"), ("Residence", "RESI"), ("Suites", "STES")]

# Radisson Blu Plaza (Sukhumvit 27, 450 m from Asok BTS) hosts the brief's golden case. Fixed inputs here:
# its room list, its nightly base rate (so Kestrel's usual 6% discount lands on the brief's ₹6,200), and the
# two golden offers. Everything else about the hotel's offers is generated like any other hotel.
GOLDEN_HOTEL = "h-way-331963030"
GOLDEN_BASE_RATE = 6600
GOLDEN_ROOMS = [("Superior", "King", None, 2), ("Superior", "Twin", None, 2), ("Deluxe", "Twin", "Pool", 2),
                ("Executive", "King", "City", 2), ("Family", "King + 2 Single", None, 4)]
# Nightly; x3 nights = ₹18,600 (A) and ₹20,100 (B). Mynah sells only its breakfast promo here (None = plan not sold).
GOLDEN_OFFERS = {("kestrel", "RO"): 6200, ("mynah", "BB"): 6700, ("mynah", "RO"): None}


def _m_to_deg(m):
    return m / 111_000


# ------------------------------------------------------------------ naming chaos
def hotel_name(name: str, sup: str, st: dict, rng, corr: list) -> str:
    n = name
    if not re.search(r"bangkok", n, re.I) and rng.random() < 0.4:
        n += " Bangkok"
    if sup == "heron" and re.search(r"Sukhumvit (\d+)", n):
        n = re.sub(r"Sukhumvit (\d+)", r"Sukhumvit Soi \1", n); corr.append("soi_inserted")
    if sup == "hornbill" and rng.random() < 0.5:
        n = re.sub(r"\s*Bangkok\s*", " ", n).strip(); corr.append("city_dropped")
    if sup == "bulbul" and rng.random() < 0.4 and "hotel" not in n.lower():
        n += " Hotel"; corr.append("hotel_suffix")
    if st["drop_number"] and re.search(r"\b\d{1,3}\b", n) and rng.random() < st["drop_number"]:
        n = re.sub(r"\s*\b(Soi\s*)?\d{1,3}\b", "", n).strip(); corr.append("branch_number_dropped")
    if rng.random() < st["abbreviate"]:
        for a, b in NAME_ABBR:
            if a in n and rng.random() < 0.6:
                n = n.replace(a, b); corr.append("abbreviated")
    if sup == "sunbird" and rng.random() < 0.25:
        n += " (SHA+)"; corr.append("tag_suffix")
    if rng.random() < 0.03:                                  # a typo: swap two adjacent letters
        i = int(rng.integers(1, max(len(n) - 2, 2)))
        if n[i].isalpha() and n[i + 1].isalpha():
            n = n[:i] + n[i + 1] + n[i] + n[i + 2:]; corr.append("typo")
    if st["case"] == "upper":
        n = n.upper()
    return re.sub(r"\s+", " ", n).strip()


def phone(p: str, style: str) -> str:
    d = re.sub(r"\D", "", p)[2:]          # national digits without leading 0
    return {"intl": p, "digits": "66" + d, "dashed": f"+66-{d[0]}-{d[1:4]}-{d[4:]}", "local": f"0{d[0]} {d[1:4]} {d[4:]}",
            "compact": f"+66 {d[:4]} {d[4:]}"}[style]


def address(h: dict, sup: str, rng) -> str:
    parts = [h["house_number"], h["street"], h["district"], "Bangkok", h["postcode"] if sup in ("mynah", "heron") else None]
    a = ", ".join(p for p in parts if p)
    if sup == "kestrel":
        a = a.upper().replace("SUKHUMVIT", "SUKHUMVIT RD") if rng.random() < 0.3 else a.upper()
    if sup == "sunbird":
        a = ", ".join(p for p in [h["street"], "Bangkok"] if p)
    return a


DESC = {
    "short": ["Hotel in {district} area.", "{star}-star hotel, {district}.", "Located in {district}."],
    "medium": ["{name} is a {star}-star hotel in {district}, Bangkok. {pool}Rooms have air conditioning and free Wi-Fi.",
               "Set in {district}, {name} offers {star}-star rooms{pool_short}. Close to shopping and BTS."],
    "long": ["{name} sits on {street} in {district}, close to BTS and Bangkok's shopping streets. {pool}{family}"
             "Rooms are modern with city views; the restaurant serves an international breakfast.",
             "A {star}-star stay in {district}: {name} offers {n_rooms} rooms on {street}. {pool}{family}"
             "Guests have free Wi-Fi, a fitness centre and 24-hour front desk."],
}


def description(h, sup, st, rng):
    t = DESC[st["desc"]][int(rng.integers(len(DESC[st["desc"]])))]
    return t.format(name=h["name"], district=h["district"] or "central Bangkok", star=h["star"], street=h["street"] or "a quiet soi",
                    n_rooms=h["room_count"], pool="An outdoor pool is on site. " if h["pool"] else "",
                    pool_short=" and an outdoor pool" if h["pool"] else "",
                    family="Family rooms and connecting rooms are available. " if h["family_rooms"] else "")


# ------------------------------------------------------------------ rooms
def canonical_rooms(h, rng):
    if h["hotel_id"] == GOLDEN_HOTEL:
        spec = GOLDEN_ROOMS
    else:
        ladder = TIER_LADDER[h["star"]]
        n = int(rng.integers(3, min(len(ladder), 5) + 1))
        tiers = ladder[:n - 1] + (["Family"] if h["family_rooms"] else [ladder[n - 1]])
        views = ["City"] + (["Pool"] if h["pool"] else []) + (["River"] if h["river_m"] < 500 else []) + ["Garden"]
        spec = []
        for i, t in enumerate(dict.fromkeys(tiers)):
            if t == "Family":
                spec.append(("Family", "King + 2 Single", None, 4))
                continue
            view = None if i == 0 else str(rng.choice(views))
            spec.append((t, "King", view, 2))
            if i == 0 or rng.random() < 0.4:
                spec.append((t, "Twin", view, 2))
    rooms = []
    for j, (tier, bed, view, occ) in enumerate(spec):
        nm = f"{tier} {'Room' if tier == 'Family' else bed}" + (f", {view} View" if view else "")
        if tier == "Family":
            nm = "Family Room (2 + 2)"
        rooms.append({"room_id": f"{h['hotel_id']}:R{j + 1}", "hotel_id": h["hotel_id"], "name": nm, "tier": tier, "bed": bed,
                      "view": view, "max_occupancy": occ, "tier_mult": TIERS[tier]})
    return rooms


def room_name(r, sup, rng, corr):
    tier, bed, view = r["tier"], r["bed"], r["view"]
    if tier == "Family":
        return {"kestrel": "FAM RM", "mynah": "Family Room 2A+2C", "heron": "FAMILY ROOM", "bulbul": "Family (2A2C)",
                "hornbill": "FAMILY RM KG+2SGL", "sunbird": "Family Room"}[sup]
    if sup == "sunbird" and view and rng.random() < 0.5:
        view = None; corr.append("view_dropped")
    if sup == "kestrel":
        bedw = {"King": "1KG", "Twin": "TWN"}.get(bed, bed)
        return " ".join(x for x in [ABBR.get(tier, tier.upper()), bedw, ABBR.get(view) if view else None] if x)
    if sup == "mynah":
        return f"{tier} Room, {'1 King Bed' if bed == 'King' else '2 Twin Beds'}" + (f", {view} View" if view else "")
    if sup == "heron":
        return f"{tier} {bed}{' ' + view + ' View' if view else ''}".upper()
    if sup == "bulbul":
        if rng.random() < 0.5:
            return " ".join(x for x in [ABBR.get(tier, tier), {"King": "KG", "Twin": "TWN"}[bed], ABBR.get(view) if view else None] if x)
        return f"{tier} {'Double (King)' if bed == 'King' else 'Twin'}" + (f" {view} View" if view else "")
    if sup == "hornbill":
        return f"{tier} {bed} Room" + (f" - {view} View" if view else "")
    return f"{tier} Room {bed}" + (f" {view} View" if view else "")


# ------------------------------------------------------------------ the feed
def generate(hotels: list[dict], rng: np.random.Generator):
    listings, truth, rooms_all, sup_rooms, room_truth, offers = [], [], [], [], [], []
    for h in hotels:
        if h["hotel_id"] == GOLDEN_HOTEL:
            h["base_rate"] = GOLDEN_BASE_RATE
        rooms = canonical_rooms(h, rng)
        rooms_all += rooms
        amen_true = [a for a in AMENITIES if (h["pool"] or "pool" not in a.lower()) and (h["family_rooms"] or a not in ("Family rooms", "Connecting rooms", "Kids' club"))
                     and rng.random() < 0.35 + 0.12 * h["star"]]
        h["amenities"] = amen_true
        bf_pp = BREAKFAST_PP[h["star"]] * float(np.exp(rng.normal(0, 0.15)))
        h["volatility"] = float(np.exp(rng.normal(0, 0.25)))    # demand pressure: drives sold-out / reprice odds
        apartment = bool(re.search(r"citadines|oakwood|somerset|ascott|fraser|residence|suites|apartment", h["name"], re.I))
        h["serves_breakfast"] = h["hotel_id"] == GOLDEN_HOTEL or rng.random() < {2: 0.35, 3: 0.7, 4: 0.9, 5: 0.97}[h["star"]] * (0.6 if apartment else 1)
        for sup, st in STYLE.items():
            p = st["coverage"] * (0.6 + 0.12 * h["star"]) * (1.15 if h["family"] else 1.0)
            if h["hotel_id"] == GOLDEN_HOTEL or rng.random() < min(p, 0.97):
                copies = 2 if rng.random() < st["dup_rate"] else 1
                for c in range(copies):
                    lid = f"{sup}:{sup[:2].upper()}{int(rng.integers(10_000, 99_999))}"
                    corr = ["supplier_duplicate"] if c else []
                    lat, lng = h["lat"], h["lng"]
                    if rng.random() < st["centroid_geocode"]:
                        # geocoded to the district / road centroid rather than the building
                        ang, dist = rng.random() * 6.283, 700 + rng.random() * 900
                        lat += _m_to_deg(dist) * np.sin(ang); lng += _m_to_deg(dist) * np.cos(ang); corr.append(f"geocode_off_{dist:.0f}m")
                    else:
                        j = abs(rng.normal(0, st["coord_m"]))
                        ang = rng.random() * 6.283
                        lat += _m_to_deg(j) * np.sin(ang); lng += _m_to_deg(j) * np.cos(ang)
                        if j > 60:
                            corr.append(f"coord_jitter_{j:.0f}m")
                    star = None if rng.random() < st["star_missing"] else (h["star"] - 0.5 if rng.random() < st["star_half_down"] else float(h["star"]))
                    if star is None:
                        corr.append("star_missing")
                    elif star != h["star"]:
                        corr.append("star_half_down")
                    ph = None if rng.random() < st["phone_missing"] else phone(h["phone"], st["phone"])
                    if ph is None:
                        corr.append("phone_missing")
                    k_img = int(rng.integers(st["images"][0], st["images"][1] + 1))
                    amen = [a for a in amen_true if rng.random() < st["amenity_share"]]
                    if rng.random() < 0.04:                    # suppliers also claim things that aren't there
                        wrong = [a for a in AMENITIES if a not in amen_true]
                        if wrong:
                            amen.append(str(rng.choice(wrong))); corr.append("wrong_amenity")
                    listings.append({
                        "listing_id": lid, "supplier_id": sup, "name": hotel_name(h["name"], sup, st, rng, corr),
                        "lat": round(lat, 6), "lng": round(lng, 6), "address": address(h, sup, rng), "phone": ph, "star": star,
                        "checkin_time": "15:00" if sup == "bulbul" and rng.random() < 0.5 else h["checkin_time"],
                        "amenities": amen, "description": description(h, sup, st, rng), "n_images": k_img,
                        "postcode": h["postcode"] if sup in ("mynah", "heron") else None,
                    })
                    truth.append({"listing_id": lid, "hotel_id": h["hotel_id"], "corruptions": corr})
                    # not every supplier loads a breakfast rate even where the hotel serves breakfast
                    loads_bb = h["serves_breakfast"] and (h["hotel_id"] == GOLDEN_HOTEL or rng.random() < 0.8)
                    carried = [r for i, r in enumerate(rooms) if (i == 0 and rng.random() < 0.95) or rng.random() < 0.55
                               or h["hotel_id"] == GOLDEN_HOTEL and i < 2]
                    for r in carried:
                        rc = []
                        sr_id = f"{lid}:{len(sup_rooms)}"
                        sup_rooms.append({"supplier_room_id": sr_id, "listing_id": lid, "supplier_id": sup, "raw_name": room_name(r, sup, rng, rc)})
                        room_truth.append({"supplier_room_id": sr_id, "room_id": r["room_id"], "corruptions": rc})
                        for board, refund, pay, mult in RATE_PLANS[sup]:
                            if board == "BB" and not loads_bb:
                                continue
                            ro = h["base_rate"] * r["tier_mult"] * st["price"] * mult * float(np.exp(rng.normal(0, 0.04)))
                            price = ro + (2 * bf_pp * float(np.exp(rng.normal(0, 0.08))) if board == "BB" else 0)
                            if h["hotel_id"] == GOLDEN_HOTEL and r["room_id"].endswith(":R1") and (sup, board) in GOLDEN_OFFERS:
                                if GOLDEN_OFFERS[(sup, board)] is None:
                                    continue
                                price = GOLDEN_OFFERS[(sup, board)]
                            words = RATE_TEXT[sup]
                            cxl = words[None] if refund is None else words["flex"].format(d=refund, h=refund * 24)
                            offers.append({
                                "offer_id": f"{sr_id}:{board}", "listing_id": lid, "supplier_room_id": sr_id, "supplier_id": sup,
                                "board": board, "nightly": float(round(price, -1)),
                                "refundable_days": refund, "pay_due_days": pay,
                                "availability": "limited" if rng.random() < (0.25 if sup == "kestrel" else 0.08) else "available",
                                "raw_rate": f"{words[board]} {cxl}",
                            })
    return listings, truth, rooms_all, sup_rooms, room_truth, offers
