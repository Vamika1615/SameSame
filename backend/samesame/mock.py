"""M1 MOCK scenario (mode.data = "mock").

Hand-written *inputs* only: a dozen real OSM hotels around Asok BTS, their supplier listings and
offers, three sightseeing products, and placeholder supplier profiles. Every *output* (True Price,
ranking, filter counts, look-alike distance, booking outcomes) is computed by the real engine
functions. M2-M4 replace this module's inputs with the generated supplier layer and fitted models,
behind the same payload builders.

Novotel Sukhumvit 20 carries the brief's golden-case offers (A: Kestrel ₹18,600 room-only
non-refundable; B: Mynah ₹20,100 breakfast, free cancellation to 7 days).
"""
import hashlib
import random
import re
from datetime import date, timedelta
from functools import lru_cache

from samesame import config
from samesame.booking import sandbox
from samesame.pricing import true_price as tp
from samesame.ranking import score as rk
from samesame.schemas import (ActivityGroup, ActivityListing, ActivitySearch, ActivityVariant, CanonicalRoom, DnaFilter,
                              DnaSegment, Enrichment, HotelCard, HotelDetail, HotelSearch, ImageRef, ListingCounters,
                              Lookalike, LookalikeReason, Offer, Promise, ReviewItem, ReviewSide, SearchParams,
                              SimArm, SimParams, SimResult, SourcedFact, SupplierRow)

SUPPLIERS = {"kestrel": "Kestrel", "mynah": "Mynah", "heron": "Heron",
             "bulbul": "Bulbul", "hornbill": "Hornbill", "sunbird": "Sunbird"}

# Placeholder behaviour at 15-45 days lead (M4 replaces with the Beta-binomial fit on the booking log).
# (p_price_change, p_sold_out, p_error, exp_increase, n_attempts)
PROFILES = {
    ("kestrel", "hotel"): (0.18, 0.06, 0.02, 0.09, 4210), ("kestrel", "activity"): (0.12, 0.05, 0.02, 0.08, 1830),
    ("mynah", "hotel"): (0.015, 0.01, 0.005, 0.05, 3980), ("mynah", "activity"): (0.02, 0.01, 0.005, 0.05, 1620),
    ("heron", "hotel"): (0.03, 0.03, 0.01, 0.06, 3310), ("heron", "activity"): (0.10, 0.09, 0.03, 0.07, 940),
    ("bulbul", "hotel"): (0.05, 0.04, 0.02, 0.06, 2150), ("bulbul", "activity"): (0.04, 0.03, 0.02, 0.05, 1300),
    ("hornbill", "hotel"): (0.04, 0.03, 0.01, 0.05, 2620), ("hornbill", "activity"): (0.03, 0.02, 0.01, 0.05, 1410),
    ("sunbird", "hotel"): (0.08, 0.04, 0.02, 0.07, 1790), ("sunbird", "activity"): (0.03, 0.02, 0.01, 0.04, 2240),
}
LEAD_DAYS = 21
CHECKIN = date.today() + timedelta(days=LEAD_DAYS)
BREAKFAST_PP_NIGHT = 550        # city median of breakfast add-ons in the catalogue (mock value)
PICKUP_PP = 450                 # city median hotel-transfer add-on per person (mock value)

PARAMS = SearchParams(area="Asok BTS · Sukhumvit", area_lat=13.7370, area_lng=100.5603, checkin=CHECKIN,
                      nights=3, adults=2, children=0, star_min=4, needs=["breakfast"], source_market="IN")

# ------------------------------------------------------------------ hotels (real OSM names + coords)
# id, name, lat, lng, star, chain, phone, street, pool, family_rooms, popularity (IN agents, 90d, mock)
HOTELS = [
    ("novotel-suk20", "Novotel Bangkok Sukhumvit 20", 13.73152, 100.56428, 4, "Novotel", "+66 2 009 4999", "Sukhumvit Soi 20", True, True, 61),
    ("sheraton-grande", "Sheraton Grande Sukhumvit", 13.73741, 100.55906, 5, "Sheraton", "+66 2 649 8888", "Sukhumvit Road", True, False, 34),
    ("westin-grande", "The Westin Grande Sukhumvit Bangkok", 13.73838, 100.55964, 5, "Westin", "+66 2 207 8000", "Sukhumvit Soi 19", True, True, 29),
    ("hilton-asoke", "Hilton Bangkok Grande Asoke", 13.73901, 100.56211, 5, "Hilton", "+66 2 204 4000", "Asok Montri Road", True, True, 22),
    ("citadines-16", "Citadines Sukhumvit 16 Bangkok", 13.73358, 100.56080, 4, "Citadines", "+66 2 663 8777", "Sukhumvit Soi 16", True, True, 41),
    ("citadines-8", "Citadines Sukhumvit 8", 13.73569, 100.55618, 4, "Citadines", "+66 2 250 9333", "Sukhumvit Soi 8", True, True, 18),
    ("hyatt-regency", "Hyatt Regency Bangkok Sukhumvit", 13.73991, 100.55716, 5, "Hyatt Regency", "+66 2 098 1234", "Sukhumvit Soi 13", True, False, 15),
    ("holiday-inn-suk22", "Holiday Inn Bangkok Sukhumvit", 13.73297, 100.56546, 4, "Holiday Inn", "+66 2 683 4888", "Sukhumvit Soi 22", True, True, 47),
    ("sofitel-suk", "Sofitel Bangkok Sukhumvit", 13.73950, 100.55778, 5, "Sofitel", "+66 2 126 9999", "Sukhumvit Soi 13", True, False, 12),
    ("grand-mercure-asoke", "Grand Mercure Bangkok Asoke Residence", 13.74158, 100.56074, 4, "Grand Mercure", "+66 2 204 1222", "Sukhumvit Soi 19", True, True, 26),
    ("ibis-suk4", "Ibis Bangkok Sukhumvit 4", 13.73799, 100.55345, 3, "Ibis", "+66 2 659 2888", "Sukhumvit Soi 4", False, False, 38),
    ("park-plaza-suk", "Park Plaza Sukhumvit", 13.73484, 100.56045, 4, "Park Plaza", "+66 2 263 5000", "Sukhumvit Soi 18", True, False, 9),
]
# Supplier listings per hotel and the raw name each supplier uses (naming chaos is the point)
LISTINGS = {
    "novotel-suk20": [("kestrel", "NOVOTEL BKK SUKHUMVIT20"), ("mynah", "Novotel Bangkok Sukhumvit 20"),
                      ("heron", "Novotel Sukhumvit Soi 20 Bangkok"), ("bulbul", "Novotel Bangkok Sukhumvit Soi 20 Hotel"),
                      ("hornbill", "Novotel Sukhumvit 20"), ("sunbird", "NOVOTEL SUKHUMVIT 20 (SHA+)")],
    "sheraton-grande": [("kestrel", "SHERATON GRANDE SUKHUMVIT LUXURY COLLECTION"), ("mynah", "Sheraton Grande Sukhumvit, a Luxury Collection Hotel"),
                        ("hornbill", "Sheraton Grande Sukhumvit Bangkok")],
    "westin-grande": [("mynah", "The Westin Grande Sukhumvit"), ("heron", "Westin Grande Sukhumvit Bangkok"),
                      ("sunbird", "WESTIN GRANDE SUKHUMVIT")],
    "hilton-asoke": [("kestrel", "HILTON BKK GRANDE ASOKE"), ("mynah", "Hilton Bangkok Grande Asoke"),
                     ("bulbul", "Hilton Grande Asoke Bangkok"), ("hornbill", "Hilton Bangkok Grande Asoke Hotel")],
    "citadines-16": [("kestrel", "CITADINES SUKHUMVIT 16"), ("mynah", "Citadines Sukhumvit 16 Bangkok"),
                     ("sunbird", "Citadines Sukhumvit Bangkok")],
    "citadines-8": [("heron", "Citadines Sukhumvit 8 Bangkok"), ("bulbul", "CITADINES SUKHUMVIT 8")],
    "hyatt-regency": [("mynah", "Hyatt Regency Bangkok Sukhumvit"), ("heron", "HYATT REGENCY BKK SUKHUMVIT")],
    "holiday-inn-suk22": [("kestrel", "HOLIDAY INN BKK SUKHUMVIT"), ("mynah", "Holiday Inn Bangkok Sukhumvit"),
                          ("heron", "Holiday Inn Sukhumvit 22 Bangkok"), ("sunbird", "Holiday Inn Bangkok Sukhumvit by IHG")],
    "sofitel-suk": [("mynah", "Sofitel Bangkok Sukhumvit"), ("hornbill", "SOFITEL BKK SUKHUMVIT")],
    "grand-mercure-asoke": [("kestrel", "GRAND MERCURE ASOKE RESIDENCE"), ("mynah", "Grand Mercure Bangkok Asoke Residence"),
                            ("bulbul", "Grand Mercure Asoke Residence Bangkok")],
    "ibis-suk4": [("kestrel", "IBIS BKK SUKHUMVIT 4"), ("mynah", "ibis Bangkok Sukhumvit 4"), ("sunbird", "Ibis Sukhumvit Soi 4")],
    "park-plaza-suk": [("mynah", "Park Plaza Sukhumvit Bangkok"), ("heron", "PARK PLAZA SUKHUMVIT")],
}
BASE_PRICE = {"novotel-suk20": 19800, "sheraton-grande": 31500, "westin-grande": 27800, "hilton-asoke": 24600,
              "citadines-16": 16900, "citadines-8": 14800, "hyatt-regency": 29900, "holiday-inn-suk22": 18200,
              "sofitel-suk": 26400, "grand-mercure-asoke": 17600, "ibis-suk4": 9800, "park-plaza-suk": 15900}
# supplier style: price factor, refundable_until_days (None = NRF), pay_due_days (None = pay now), raw RO / BB text
STYLE = {"kestrel": (0.94, None, None, "RO NRF", "BB NRF"),
         "mynah": (1.0, 7, None, "Room Only - Free Cancellation", "Bed and Breakfast - Free Cancellation"),
         "heron": (0.98, None, None, "ROOM ONLY NON REFUNDABLE", "ROOM W/ ABF NON REFUNDABLE"),
         "bulbul": (1.04, 3, 3, "Room only, cxl free till 72h", "Incl. ABF, cxl free till 72h"),
         "hornbill": (1.0, 7, None, "Room only, refundable", "Breakfast incl., refundable"),
         "sunbird": (0.97, None, None, "Room only NRF", "With breakfast NRF")}
# The brief's golden case + its neighbours, at Novotel (supplier, board, price, refundable_days, pay_due_days)
NOVOTEL_OFFERS = [("kestrel", "RO", 18600, None, None), ("kestrel", "BB", 21300, None, None),
                  ("mynah", "BB", 20100, 7, None), ("mynah", "RO", 19700, 7, None),
                  ("heron", "RO", 19400, None, None), ("bulbul", "BB", 21350, 3, 3),
                  ("hornbill", "RO", 19900, 7, None), ("sunbird", "BB", 19800, None, None)]
AMENITIES = ["Outdoor pool", "Fitness centre", "Free Wi-Fi", "Airport shuttle (paid)", "Kids' club", "Spa", "Restaurant",
             "Rooftop bar", "24h front desk", "Family rooms", "Laundry", "Non-smoking rooms", "Connecting rooms", "Indian breakfast options"]


def _h(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)


def promise(supplier: str, product: str) -> Promise:
    pc, so, err, inc, n = PROFILES[(supplier, product)]
    honour = 1 - pc - so - err
    half = 1.96 * (honour * (1 - honour) / n) ** 0.5
    return Promise(supplier_id=supplier, supplier=SUPPLIERS[supplier], lead_bucket="15-45 days", honour_rate=round(honour, 3),
                   ci_low=round(honour - half, 3), ci_high=round(min(honour + half, 1), 3), n=n,
                   p_price_change=pc, p_sold_out=so, p_error=err, exp_increase_pct=inc)


def risk(supplier: str, product: str) -> tp.Risk:
    pc, so, err, inc, _ = PROFILES[(supplier, product)]
    return tp.Risk(SUPPLIERS[supplier], pc, so, err, inc)


def hotel_needs() -> list[tp.Need]:
    cost = PARAMS.adults * PARAMS.nights * BREAKFAST_PP_NIGHT
    return [tp.Need("breakfast", "Breakfast", cost,
                    f"{PARAMS.adults} people x {PARAMS.nights} nights x {tp.inr(BREAKFAST_PP_NIGHT)} (city median)")]


CANCEL_RANK = lambda d: 0 if d is None else 100 - d  # noqa: E731  more days of free cancellation = more flexible


def _cancel_text(d):
    return "Non-refundable" if d is None else f"Free cancellation until {(CHECKIN - timedelta(days=d)).strftime('%d %b')}"


def _pay_text(d):
    return "Pay now" if d is None else f"Pay {d} days before travel"


@lru_cache
def hotel_offers(hid: str) -> list[dict]:
    """Raw offers for a hotel (inputs), before True Price."""
    if hid == "novotel-suk20":
        rows = NOVOTEL_OFFERS
    else:
        rows = []
        for sup, _ in LISTINGS[hid]:
            f, rd, pd, _, _ = STYLE[sup]
            jitter = 1 + ((_h(hid + sup) % 50) - 25) / 1000
            ro = round(BASE_PRICE[hid] * f * jitter, -1)
            rows += [(sup, "RO", ro, rd, pd), (sup, "BB", round(ro + 2800 + _h(sup + hid) % 600, -1), rd, pd)]
    return [{"offer_id": f"{hid}:{s}:{b}", "supplier": s, "board": b, "price": float(p), "refundable": rd, "pay_due": pd,
             "raw_rate": STYLE[s][3 if b == "RO" else 4]} for s, b, p, rd, pd in rows]


@lru_cache
def priced_offers(hid: str) -> list[Offer]:
    raw = hotel_offers(hid)
    pool = [sandbox.BookableOffer(o["offer_id"], o["supplier"], o["price"], o["board"], CANCEL_RANK(o["refundable"])) for o in raw]
    out = []
    for o, b in zip(raw, pool):
        twins = sandbox.same_twins(b, pool)
        price = tp.compute(o["price"], {"breakfast"} if o["board"] == "BB" else set(), hotel_needs(), LEAD_DAYS,
                           o["refundable"], o["pay_due"], risk(o["supplier"], "hotel"), twins[0].price if twins else None)
        out.append(Offer(offer_id=o["offer_id"], supplier_id=o["supplier"], supplier=SUPPLIERS[o["supplier"]],
                         room_id=f"{hid}:R1", room_name="Superior King" if hid == "novotel-suk20" else "Deluxe King",
                         board="Breakfast" if o["board"] == "BB" else "Room only", price=o["price"],
                         availability="limited" if o["supplier"] == "kestrel" else "available",
                         refundable_until=None if o["refundable"] is None else CHECKIN - timedelta(days=o["refundable"]),
                         cancel_text=_cancel_text(o["refundable"]), pay_terms="pay_now" if o["pay_due"] is None else f"pay_later_{o['pay_due']}d",
                         pay_text=_pay_text(o["pay_due"]), promise=promise(o["supplier"], "hotel"), true_price=price,
                         sticker_rank=0, true_rank=0))
    for i, o in enumerate(sorted(out, key=lambda o: o.price), 1):
        o.sticker_rank = i
    for i, o in enumerate(sorted(out, key=lambda o: o.true_price.total), 1):
        o.true_rank = i
    return out


def _img(kind: str, key: str) -> ImageRef:
    return ImageRef(url=f"/api/img/{kind}/{key}.svg", illustrative=True, source="generated")


def _lookalikes() -> dict[str, Lookalike]:
    a, b = (next(h for h in HOTELS if h[0] == k) for k in ("citadines-16", "citadines-8"))
    d = rk.haversine_m(a[2], a[3], b[2], b[3])

    def mk(x, y):
        return Lookalike(other_card_id=y[0], other_name=y[1], distance_m=round(d), reasons=[
            LookalikeReason(kind="distance", text=f"{d:,.0f} m apart (twins sit within 400 m)"),
            LookalikeReason(kind="phone", text=f"Different phones: {x[6]} vs {y[6]}"),
            LookalikeReason(kind="branch", text=f"Different branch: {x[7]} vs {y[7]}")])
    return {a[0]: mk(a, b), b[0]: mk(b, a)}


def _district(street: str) -> str:
    """Sukhumvit's even sois run south into Khlong Toei, odd sois north into Watthana."""
    m = re.search(r"Soi (\d+)", street)
    return "Watthana" if m and int(m.group(1)) % 2 else "Khlong Toei"


HOTEL_KW = {"breakfast": ("breakfast",), "free_cancel": ("free cancellation",)}   # pool: no feed has it as text


def _listing_has(hid: str, sup: str, key: str) -> bool:
    mine = [o for o in hotel_offers(hid) if o["supplier"] == sup]
    return any(o["board"] == "BB" for o in mine) if key == "breakfast" else any(o["refundable"] is not None for o in mine)


def _has_kw(text: str, kws: tuple[str, ...]) -> bool:
    t = text.lower()
    return any(k in t for k in kws)


@lru_cache
def hotel_search() -> HotelSearch:
    looks = _lookalikes()
    offers = {h[0]: priced_offers(h[0]) for h in HOTELS}
    best = {k: min(v, key=lambda o: o.true_price.total) for k, v in offers.items()}
    lo, hi = min(b.true_price.total for b in best.values()), max(b.true_price.total for b in best.values())
    max_pop = max(h[10] for h in HOTELS)
    items = []
    for hid, name, lat, lng, star, chain, phone, street, pool, fam, pop in HOTELS:
        b = best[hid]
        dist = rk.haversine_m(PARAMS.area_lat, PARAMS.area_lng, lat, lng)
        content = 0.6 + 0.4 * len(LISTINGS[hid]) / 6
        feats = {"true_price": rk.price_value(b.true_price.total, lo, hi), "promise": b.promise.honour_rate,
                 "distance": rk.distance_value(dist), "star_fit": 1.0 if star >= (PARAMS.star_min or 0) else 0.3,
                 "family_fit": 0.5 * pool + 0.5 * fam, "popularity": pop / max_pop, "content": content}
        details = {"true_price": f"True Price from {tp.inr(b.true_price.total)}",
                   "promise": f"{b.supplier} {b.promise.honour_rate:.0%} honoured",
                   "distance": f"{dist:,.0f} m from {PARAMS.area.split(' ·')[0]}",
                   "star_fit": f"{star}★ meets {PARAMS.star_min:.0f}★+ filter" if star >= PARAMS.star_min else f"{star}★ below filter",
                   "family_fit": "Pool + family rooms" if pool and fam else ("Pool" if pool else "No pool"),
                   "popularity": f"Booked {pop}× by Indian agents (90d)", "content": f"Content {content:.0%} complete"}
        terms = rk.score(feats, details, rk.HOTEL_WEIGHTS)
        tags = sorted({"breakfast" for o in offers[hid] if o.board == "Breakfast"}
                      | {"free_cancel" for o in offers[hid] if o.refundable_until} | ({"pool"} if pool else set()))
        items.append({"hid": hid, "score": terms, "honour": b.promise.honour_rate, "tags": tags,
                      "card": dict(name=name, star=star, lat=lat, lng=lng, district=_district(street))})
    ranked = rk.rank(items)

    samesame, today, truth_tags = [], [], {}
    for it in ranked:
        hid = it["hid"]
        members = [f"{s}:{hid}" for s, _ in LISTINGS[hid]]
        prices = [o.price for o in offers[hid]]
        samesame.append(HotelCard(card_id=hid, cluster_id=hid, image=_img("hotel", hid + ":0"),
                                  suppliers=[SUPPLIERS[s] for s, _ in LISTINGS[hid]], member_ids=members,
                                  from_price=min(prices), true_price_from=best[hid].true_price.total, rank=it["rank"],
                                  why=rk.why_chips(it["score"]), score=it["score"], dna_tags=it["tags"],
                                  lookalike=looks.get(hid), **it["card"]))
        for s, raw in LISTINGS[hid]:
            sup_prices = [o.price for o in offers[hid] if o.supplier_id == s]
            raw_rates = " ".join(o["raw_rate"] for o in hotel_offers(hid) if o["supplier"] == s)
            truth = {k for k in ("breakfast", "free_cancel") if k in it["tags"] and _listing_has(hid, s, k)} | (
                {"pool"} if "pool" in it["tags"] else set())
            # Today cards carry what keyword search on raw rate text can find; truth is kept for the counts
            today.append(HotelCard(card_id=f"{s}:{hid}", cluster_id=hid, image=_img("hotel", f"{hid}:{_h(s) % 3}"),
                                   supplier=SUPPLIERS[s], from_price=min(sup_prices), rank=0,
                                   dna_tags=sorted(k for k, kws in HOTEL_KW.items() if _has_kw(raw_rates, kws)),
                                   **{**it["card"], "name": raw}))
            truth_tags[f"{s}:{hid}"] = truth
    today.sort(key=lambda c: c.from_price)
    for i, c in enumerate(today, 1):
        c.rank = i

    # DNA filters, measured per listing: truly has it (Variant DNA on structured offers) vs keyword search finds it
    filters = [DnaFilter(key=key, label=label, count=sum(key in t for t in truth_tags.values()),
                         today_count=sum(key in c.dna_tags for c in today))
               for key, label in [("breakfast", "Breakfast included"), ("free_cancel", "Free cancellation"), ("pool", "Pool")]]

    n_raw = len(today)
    return HotelSearch(params=PARAMS, today=today, samesame=samesame, filters=filters,
                       counters=ListingCounters(raw_listings=n_raw, unique_hotels=len(samesame), duplicates_collapsed=n_raw - len(samesame)))


TRUST = {"mynah": 0.9, "heron": 0.85, "hornbill": 0.8, "bulbul": 0.7, "sunbird": 0.65, "kestrel": 0.55}


@lru_cache
def hotel_detail(hid: str) -> HotelDetail:
    h = next(x for x in HOTELS if x[0] == hid)
    _, name, lat, lng, star, chain, phone, street, pool, fam, _ = h
    sups = [s for s, _ in LISTINGS[hid]]
    raw_names = dict(LISTINGS[hid])

    def fact(key, label, truth, noisy):
        """Each supplier reports a value; the golden value is the trust-weighted vote."""
        srcs = [{"supplier": SUPPLIERS[s], "value": noisy(s) or truth, "trust": TRUST[s]} for s in sups]
        votes = {}
        for x in srcs:
            votes[x["value"]] = votes.get(x["value"], 0) + x["trust"]
        return SourcedFact(key=key, label=label, value=max(votes, key=votes.get), sources=srcs)

    facts = [fact("name", "Name", name, lambda s: raw_names[s]),
             fact("star", "Stars", f"{star}★", lambda s: f"{star - 0.5}★" if s in ("kestrel", "sunbird") else None),
             fact("address", "Address", f"{street}, Khlong Toei, Bangkok 10110",
                  lambda s: f"{street.upper()}, BKK" if s == "kestrel" else (f"{street}, Bangkok" if s == "sunbird" else None)),
             fact("phone", "Phone", phone, lambda s: phone.replace(" ", "") if s in ("kestrel", "heron") else None),
             fact("checkin", "Check-in", "14:00", lambda s: "15:00" if s == "bulbul" else None)]
    amen = [a for i, a in enumerate(AMENITIES) if (pool or "pool" not in a.lower()) and (fam or "Family" not in a) and _h(hid + a) % 5]
    after_amen = [{"name": a, "sources": [SUPPLIERS[s] for s in sups if _h(s + a) % 3] or [SUPPLIERS[sups[-1]]]} for a in amen]
    sparse = sups[0]
    desc = (f"{name} sits on {street}, a short walk from Asok BTS and Terminal 21. "
            f"{'An outdoor pool and family rooms make it popular with families. ' if pool and fam else ''}"
            f"Rooms are modern with city views; the restaurant serves breakfast with Indian options.")
    enrich = Enrichment(
        supplier=SUPPLIERS[sparse],
        before_facts=[SourcedFact(key=f.key, label=f.label, value=next(x["value"] for x in f.sources if x["supplier"] == SUPPLIERS[sparse]),
                                  sources=[x for x in f.sources if x["supplier"] == SUPPLIERS[sparse]]) for f in facts],
        before_images=[_img("hotel", f"{hid}:{_h(sparse) % 3}")],
        before_amenities=[a["name"] for a in after_amen[:3]],
        before_description=f"Hotel in {street.split()[0]} area.",
        after_amenities=after_amen, after_description=desc,
        after_description_sources=[SUPPLIERS[s] for s in sups if s in ("mynah", "heron", "hornbill")][:2] or [SUPPLIERS[sups[-1]]])
    rooms = [CanonicalRoom(room_id=f"{hid}:R1", name="Superior King" if hid == "novotel-suk20" else "Deluxe King",
                           attrs={"tier": "Superior", "bed": "1 King", "view": "City", "max_occupancy": "2"},
                           members=[{"supplier": SUPPLIERS[s], "raw_name": r, "confidence": c} for s, r, c in
                                    [("kestrel", "SUP 1KG", 0.97), ("mynah", "Superior Room, 1 King Bed", 0.99),
                                     ("heron", "SUPERIOR KING", 0.99), ("bulbul", "Superior Double (King)", 0.93),
                                     ("hornbill", "Superior King Room", 0.99), ("sunbird", "Superior Room King", 0.95)] if s in sups]),
             CanonicalRoom(room_id=f"{hid}:R2", name="Deluxe Twin, Pool View",
                           attrs={"tier": "Deluxe", "bed": "2 Twin", "view": "Pool", "max_occupancy": "2"},
                           members=[{"supplier": SUPPLIERS[s], "raw_name": r, "confidence": c} for s, r, c in
                                    [("mynah", "Deluxe Twin Pool View", 0.99), ("bulbul", "DLX TWN PV", 0.91),
                                     ("heron", "Deluxe Room, 2 Twin Beds, Pool View", 0.98)] if s in sups]),
             CanonicalRoom(room_id=f"{hid}:R3", name="Family Room (2 + 2)",
                           attrs={"tier": "Family", "bed": "1 King + 2 Single", "view": "City", "max_occupancy": "4"},
                           members=[{"supplier": SUPPLIERS[s], "raw_name": r, "confidence": c} for s, r, c in
                                    [("mynah", "Family Room 2A+2C", 0.98), ("hornbill", "FAMILY RM KG+2SGL", 0.9)] if s in sups])]
    return HotelDetail(cluster_id=hid, name=name, facts=facts, hero=_img("hotel", hid + ":0"),
                       images=[_img("hotel", f"{hid}:{i}") for i in range(5)], rooms=[r for r in rooms if r.members],
                       offers=sorted(priced_offers(hid), key=lambda o: o.sticker_rank), params=PARAMS,
                       enrichment=enrich, lookalike=_lookalikes().get(hid))


# ------------------------------------------------------------------ booking
DEMO_BASKET = ["novotel-suk20:kestrel:RO", "novotel-suk20:mynah:BB"]   # golden-case A (Shah family) and B (Patel family)
DEMO_SEED = 1                                                             # first seed tried; disclosed in the UI


def _profile(supplier_name: str) -> sandbox.Profile:
    key = next(k for k, v in SUPPLIERS.items() if v == supplier_name)
    pc, so, err, inc, _ = PROFILES[(key, "hotel")]
    return sandbox.Profile(pc, so, err, inc)


def book(offer_ids: list[str], seed: int):
    """One RNG for the whole basket, so a seed reproduces the scenario exactly."""
    rng = random.Random(seed)
    results = []
    for oid in offer_ids:
        pool = [sandbox.BookableOffer(o["offer_id"], SUPPLIERS[o["supplier"]], o["price"], o["board"], CANCEL_RANK(o["refundable"]))
                for o in hotel_offers(oid.split(":")[0])]
        offer = next(b for b in pool if b.offer_id == oid)
        results.append(sandbox.book(offer, pool, _profile, rng))
    return results


# ------------------------------------------------------------------ sightseeing
# variant: (variant_id, name, dna{key: value}, tags, duration_h, true-price needs-fill flag)
ACTIVITIES = {
    "floating market": ("Damnoen Saduak Floating Market", [
        ("fm-rail-shared", "Floating + Railway Market · shared transfer",
         {"pickup": "Shared hotel pickup", "meals": "No meals", "duration": "6 h · half day", "stops": "Floating + Maeklong Railway",
          "access": "Standard", "option": "Boat ride extra", "cancel": "Free until 24 h"}, ["pickup", "free_cancel"], 6, [
            ("kestrel", "Damnoen Saduak Floating Market & Maeklong Railway Market Tour", 1850, 4.5, "Join-in tour. Pick-up from central Bangkok hotels."),
            ("mynah", "Railway Market + Floating Market Half Day (Join-in)", 2050, 4.6, "Shared van with hotel pickup. Free cancellation up to 24h."),
            ("hornbill", "Maeklong Train Market and Damnoen Saduak Floating Market Trip from Bangkok", 1990, 4.4, "Collection from your hotel in a shared minivan.")]),
        ("fm-morning", "Floating Market only · morning, meet at Siam",
         {"pickup": "Meeting point (Siam)", "meals": "No meals", "duration": "4.5 h · morning", "stops": "Floating market only",
          "access": "Standard", "option": "Boat ride included", "cancel": "Non-refundable"}, [], 4.5, [
            ("sunbird", "Damnoen Saduak Floating Market Morning Tour", 1250, 4.3, "Meet at Siam BTS exit 4. Boat ride included."),
            ("kestrel", "Floating Market Early Morning (SIC)", 1190, 4.1, "SIC basis from meeting point. NRF."),
            ("bulbul", "Damnoen Saduak Floating Mkt - Half Day Morning", 1320, 4.2, "Boat included. Assemble at Siam Paragon.")]),
        ("fm-private-lunch", "Floating + Railway Market · private car, Thai lunch",
         {"pickup": "Private hotel pickup", "meals": "Thai lunch", "duration": "8 h · full day", "stops": "Floating + Maeklong Railway",
          "access": "Standard", "option": "Private guide (English)", "cancel": "Free until 48 h"}, ["pickup", "free_cancel", "lunch"], 8, [
            ("heron", "Private Floating & Railway Market Tour with Thai Lunch", 4600, 4.8, "Private car and driver, hotel pickup, lunch included."),
            ("mynah", "Floating Market + Railway Market Private Car incl. Lunch", 4450, 4.7, "Private transfer from hotel. Lunch. Free cancellation 48h."),
            ("bulbul", "PVT Damnoen Saduak + Maeklong w/ lunch", 4800, 4.6, "PVT car ex-hotel, lunch at local restaurant.")]),
    ]),
    "grand palace": ("Grand Palace & Wat Phra Kaew", [
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
    ]),
    "skywalk": ("Mahanakhon SkyWalk (rooftop)", [
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
    ]),
}
ACT_FILTERS = [("pickup", "Hotel pickup", ("hotel pickup", "pickup")), ("skip_line", "Skip-the-line", ("skip-the-line", "skip the line")),
               ("free_cancel", "Free cancellation", ("free cancellation",)), ("lunch", "Lunch included", ("lunch",))]
DNA_LABELS = {"pickup": "Pickup", "meals": "Meals", "duration": "Duration", "stops": "Stops", "access": "Access",
              "option": "Option", "cancel": "Cancellation"}


def diff_sentence(v: dict, ref: dict, limit: int = 3) -> str:
    """Template fallback for the LLM diff sentence: what you get vs the reference variant."""
    priority = ["pickup", "meals", "access", "option", "duration", "cancel", "stops"]   # what a client notices first
    diffs = [k for k in priority if v["dna"][k] != ref["dna"][k]]
    parts = [f"{v['dna'][k]} (not {ref['dna'][k]})" for k in diffs[:limit]]
    more = f" +{len(diffs) - limit} more" if len(diffs) > limit else ""
    return f"vs #{ref['rank']}: " + "; ".join(parts) + more + "."


def activity_search(q: str) -> ActivitySearch:
    key = next((k for k in ACTIVITIES if k in q.lower()), "floating market")
    base, variants = ACTIVITIES[key]
    today, built = [], []
    all_prices = []
    for vid, name, dna, tags, hours, members in variants:
        listings = [ActivityListing(listing_id=f"{vid}:{s}", supplier=SUPPLIERS[s], title=t, price=p, rating=r,
                                    image=_img("activity", f"{key}:{_h(s + vid) % 4}")) for s, t, p, r, _ in members]
        today += listings
        tps = []
        for s, _, p, _, _ in members:
            needs = [tp.Need("pickup", "Hotel pickup", PICKUP_PP * PARAMS.adults, f"{PARAMS.adults} x {tp.inr(PICKUP_PP)} taxi (city median)")]
            includes = {"pickup"} if "pickup" in tags else set()
            refund = None if dna["cancel"] == "Non-refundable" else (1 if "24" in dna["cancel"] else 2)
            twins = [m[2] for m in members if m[0] != s]
            tps.append(tp.compute(p * PARAMS.adults, includes, needs, LEAD_DAYS, refund, None, risk(s, "activity"),
                                  min(twins) * PARAMS.adults if twins else None))
        best_i = min(range(len(members)), key=lambda i: tps[i].total)
        built.append(dict(vid=vid, name=name, dna=dna, tags=tags, hours=hours, listings=listings, tp=tps[best_i],
                          best_sup=members[best_i][0], rating=max(m[3] for m in members), pop=sum(_h(m[1]) % 40 for m in members)))
        all_prices.append(tps[best_i].total)
    lo, hi = min(all_prices), max(all_prices)
    max_pop = max(b["pop"] for b in built)
    items = []
    for b in built:
        honour = promise(b["best_sup"], "activity").honour_rate
        feats = {"true_price": rk.price_value(b["tp"].total, lo, hi), "promise": honour, "popularity": b["pop"] / max_pop,
                 "duration_fit": 1.0 if b["hours"] <= 6 else 0.5, "rating": (b["rating"] - 3.5) / 1.5}
        details = {"true_price": f"True Price {tp.inr(b['tp'].total)} for 2", "promise": f"{SUPPLIERS[b['best_sup']]} {honour:.0%} honoured",
                   "popularity": f"Booked {b['pop']}× by Indian agents (90d)", "duration_fit": f"{b['hours']:g} h fits a family day",
                   "rating": f"Rated {b['rating']}"}
        items.append({**b, "score": rk.score(feats, details, rk.ACTIVITY_WEIGHTS), "honour": honour})
    rk.rank(items)
    out = []
    ordered = sorted(items, key=lambda x: x["rank"])
    for b in ordered:
        segs = [DnaSegment(key=k, label=DNA_LABELS[k], value=v, differs=len({x["dna"][k] for x in items}) > 1) for k, v in b["dna"].items()]
        sentence = diff_sentence(b, ordered[1] if b is ordered[0] else ordered[0])
        out.append(ActivityVariant(variant_id=b["vid"], name=b["name"], dna=segs, dna_tags=b["tags"], members=b["listings"],
                                   price_from=min(m.price for m in b["listings"]), true_price_from=b["tp"].total, rank=b["rank"],
                                   why=rk.why_chips(b["score"]), score=b["score"], diff_sentence=sentence, diff_source="template"))
    # DNA filters per listing: variant truly has it vs keyword search on the raw title + description finds it
    raw_text = {f"{vid}:{s}": (t + " " + d) for vid, _, _, _, _, ms in variants for s, t, _, _, d in ms}
    tags_of = {vid: tags for vid, _, _, tags, _, _ in variants}
    for li in today:
        li.dna_tags = [fk for fk, _, kws in ACT_FILTERS if _has_kw(raw_text[li.listing_id], kws)]
    filters = [DnaFilter(key=fk, label=label, count=sum(fk in tags_of[li.listing_id.split(":")[0]] for li in today),
                         today_count=sum(fk in li.dna_tags for li in today)) for fk, label, _ in ACT_FILTERS]
    today.sort(key=lambda x: x.price)
    return ActivitySearch(query=base, raw_count=len(today), today=today, groups=[ActivityGroup(group_id=key, base_product=base, variants=out)],
                          filters=filters)


# ------------------------------------------------------------------ ops review queue (truth = generator label)
def _side(i, sup, title, fields, kind=None):
    return ReviewSide(id=i, supplier=SUPPLIERS[sup], title=title, fields=fields, image=_img(kind, i) if kind else None)


REVIEW = [
    (ReviewItem(pair_id="rv-1", entity_type="hotel", model_p=0.81, model_relation="SAME", routed_by="gray_zone",
                left=_side("kestrel:novotel-suk20", "kestrel", "NOVOTEL BKK SUKHUMVIT20", {"Address": "SUKHUMVIT SOI 20, BKK", "Phone": "+6620094999", "Stars": "3.5★", "Lat/Lng": "13.7315, 100.5643"}, "hotel"),
                right=_side("mynah:novotel-suk4", "mynah", "Novotel Bangkok Sukhumvit 4", {"Address": "Sukhumvit Soi 4, Bangkok", "Phone": "+66 2 659 2888", "Stars": "4★", "Lat/Lng": "13.7394, 100.5534"}, "hotel"),
                reasons=["Name similarity high (same brand + 'Sukhumvit')", "Model says SAME at 0.81, below the 0.90 auto-merge bar",
                         f"{rk.haversine_m(13.73152, 100.56428, 13.73936, 100.55335):,.0f} m apart: under the 1,500 m never-merge rule, so only the threshold saved it"]), "DIFFERENT"),
    (ReviewItem(pair_id="rv-2", entity_type="hotel", model_p=0.64, model_relation="SAME", routed_by="gray_zone",
                left=_side("kestrel:grand-mercure-asoke", "kestrel", "GRAND MERCURE ASOKE RESIDENCE", {"Address": "SUKHUMVIT 19", "Phone": "—", "Stars": "4★", "Lat/Lng": "13.7419, 100.5604"}, "hotel"),
                right=_side("bulbul:grand-mercure-asoke", "bulbul", "Grand Mercure Asoke Residence Bangkok", {"Address": "50/5 Sukhumvit 19, Bangkok", "Phone": "+66 2 204 1222", "Stars": "4★", "Lat/Lng": "13.7416, 100.5607"}, "hotel"),
                reasons=["Phone missing on one side", "38 m apart", "Gray zone 0.55-0.90"]), "SAME"),
    (ReviewItem(pair_id="rv-3", entity_type="hotel", model_p=0.66, model_relation="SAME", routed_by="constraint_block",
                left=_side("heron:holiday-inn-suk22", "heron", "Holiday Inn Sukhumvit 22 Bangkok", {"Address": "Sukhumvit Soi 22", "Brand": "Holiday Inn", "Stars": "4★"}, "hotel"),
                right=_side("sunbird:hix-suk11", "sunbird", "Holiday Inn Express Bangkok Sukhumvit 11", {"Address": "Sukhumvit Soi 11", "Brand": "Holiday Inn Express", "Stars": "3★"}, "hotel"),
                reasons=["Same parent chain", "Blocked: different sub-brand (never-merge rule)"]), "DIFFERENT"),
    (ReviewItem(pair_id="rv-4", entity_type="room", model_p=0.71, model_relation="SAME", routed_by="gray_zone",
                left=_side("bulbul:R2", "bulbul", "DLX TWN PV", {"Hotel": "Novotel Sukhumvit 20", "Bed": "2 twin (parsed)", "View": "PV → pool (parsed)"}),
                right=_side("mynah:R2", "mynah", "Deluxe Twin Pool View", {"Hotel": "Novotel Sukhumvit 20", "Bed": "2 twin", "View": "Pool"}),
                reasons=["Abbreviation expansion confidence 0.74"]), "SAME"),
    (ReviewItem(pair_id="rv-5", entity_type="room", model_p=0.58, model_relation="SAME", routed_by="gray_zone",
                left=_side("sunbird:R1cv", "sunbird", "Superior King City View", {"Hotel": "Novotel Sukhumvit 20", "Bed": "1 king", "View": "City"}),
                right=_side("heron:R1", "heron", "SUPERIOR KING", {"Hotel": "Novotel Sukhumvit 20", "Bed": "1 king", "View": "—"}),
                reasons=["View missing on one side"]), "VARIANT"),
    (ReviewItem(pair_id="rv-6", entity_type="activity", model_p=0.69, model_relation="SAME", routed_by="llm_unsure",
                left=_side("fm-rail-shared:mynah", "mynah", "Railway Market + Floating Market Half Day (Join-in)", {"Pickup": "Shared", "Meals": "—", "Duration": "6 h"}, "activity"),
                right=_side("fm-private-lunch:heron", "heron", "Private Floating & Railway Market Tour with Thai Lunch", {"Pickup": "Private", "Meals": "Lunch", "Duration": "8 h"}, "activity"),
                reasons=["Same stops", "Different pickup + meals + duration"]), "VARIANT"),
]
_labels: list[dict] = []


def review_queue() -> list[ReviewItem]:
    done = {x["pair_id"] for x in _labels if not x.get("undone")}
    return [it for it, _ in REVIEW if it.pair_id not in done]


def review_truth(pair_id: str) -> str:
    return next(t for it, t in REVIEW if it.pair_id == pair_id)


def label(pair_id: str, lab: str, reviewer: str) -> dict:
    truth = review_truth(pair_id)
    right = {"S": "SAME", "V": "VARIANT", "D": "DIFFERENT"}[lab] == truth
    entry = {"audit_id": f"au-{len(_labels) + 1}", "pair_id": pair_id, "label": lab, "reviewer": reviewer, "truth": truth, "correct": right}
    _labels.append(entry)
    _append_label({**entry, "action": "label"})
    streak = 0
    for x in reversed([x for x in _labels if not x.get("undone")]):
        if not x["correct"]:
            break
        streak += 1
    model = next(it for it, _ in REVIEW if it.pair_id == pair_id).model_relation
    return {**entry, "streak": streak, "model_was_right": model == truth}


def undo(audit_id: str) -> bool:
    for x in _labels:
        if x["audit_id"] == audit_id:
            x["undone"] = True
            _append_label({"audit_id": audit_id, "pair_id": x["pair_id"], "action": "undo"})
            return True
    return False


def _append_label(row: dict):
    """Append-only training feedback; the trainer replays label/undo events in order (M3)."""
    import json
    from datetime import datetime
    config.BUILD.mkdir(parents=True, exist_ok=True)
    with open(config.BUILD / "review_labels.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({**row, "ts": datetime.now().isoformat(timespec="seconds")}) + "\n")


def audit_log() -> list[dict]:
    return list(reversed(_labels))


# ------------------------------------------------------------------ simulator (placeholder until M5)
def simulate(p: SimParams) -> SimResult:
    """MOCK: closed-form stand-in with the same knobs as the M5 Monte-Carlo simulator."""
    fail_today = min(0.95, 0.11 * p.failure_scale)
    fail_ss = min(0.95, 0.035 * p.failure_scale)
    base = 0.30
    today_b = base * (1 - p.dup_abandon * 2.2) * (1 - fail_today) * (1 - 0.15 * p.price_sensitivity * 0.3)
    ss_b = base * (1 - p.dup_abandon * 0.3) * (1 - fail_ss)
    arms = [SimArm(arm="today", bookings_per_search=round(today_b, 4), failed_at_booking=round(fail_today, 4), avg_true_cost=22950),
            SimArm(arm="samesame", bookings_per_search=round(ss_b, 4), failed_at_booking=round(fail_ss, 4), avg_true_cost=21310)]
    return SimResult(params=p, arms=arms, lift_bookings_pct=round((ss_b / today_b - 1) * 100, 1),
                     failed_reduction_pct=round((1 - fail_ss / fail_today) * 100, 1),
                     note="MOCK closed-form placeholder; the 50,000-session simulator replaces this in M5.")


def suppliers() -> list[SupplierRow]:
    import statistics
    rows = []
    for k, name in SUPPLIERS.items():
        hh, aa = promise(k, "hotel"), promise(k, "activity")
        mine = [hid for hid, v in LISTINGS.items() if any(s == k for s, _ in v)]
        dup = sum(len(LISTINGS[hid]) > 1 for hid in mine) / max(len(mine), 1)
        spreads = []
        for hid in mine:
            ro = [o["price"] for o in hotel_offers(hid) if o["board"] == "RO"]
            own = [o["price"] for o in hotel_offers(hid) if o["board"] == "RO" and o["supplier"] == k]
            if ro and own:
                med = statistics.median(ro)
                spreads.append(abs(own[0] - med) / med)
        rows.append(SupplierRow(supplier_id=k, supplier=name, honour_rate_hotel=hh.honour_rate, honour_rate_activity=aa.honour_rate,
                                n_attempts=hh.n + aa.n, duplicate_share=round(dup, 2),
                                price_spread_pct=round(100 * statistics.median(spreads), 1) if spreads else 0.0))
    return rows
