"""Payload builders on the generated supplier layer (mode.data = "synthetic").

Same contracts as the M1 mock, now computed from data/build:
- golden records are votes across supplier listings, weighted by a trust score that is itself
  measured (how often each supplier agrees with the majority on checkable fields);
- Promise (honour rate, reprice / sold-out odds, typical increase) is estimated from the booking log;
- popularity is counted in the booking log (Indian agents, last 90 days);
- the breakfast fill cost is the catalogue median of BB-minus-RO supplements.
Clusters and canonical rooms come from store.py (generator truth until M3; the UI says so).
"""
import random
import re
import statistics
from datetime import date, timedelta
from functools import lru_cache

import polars as pl
from rapidfuzz import fuzz

from samesame import config, store
from samesame.booking import sandbox
from samesame.data import world
from samesame.data.booking_log import ANCHOR
from samesame.data.feeds import GOLDEN_HOTEL
from samesame.data.osm_base import family, norm
from samesame.pricing import true_price as tp
from samesame.ranking import score as rk
from samesame.schemas import (ActivityGroup, ActivityListing, ActivitySearch, ActivityVariant, CanonicalRoom, DnaFilter,
                              DnaSegment, Enrichment, HotelCard, HotelDetail, HotelSearch, ImageRef, ListingCounters,
                              Lookalike, LookalikeReason, Offer, Promise, SearchParams, SourcedFact, SupplierRow)

SUPPLIERS = world.SUPPLIERS
NAME_TO_ID = {v: k for k, v in SUPPLIERS.items()}
LEAD_DAYS = 21
CHECKIN = date.today() + timedelta(days=LEAD_DAYS)
RADIUS_M = 500                          # "near Asok BTS": a 6-7 minute walk
PARAMS = SearchParams(area="Asok BTS · Sukhumvit", area_lat=13.7370, area_lng=100.5603, checkin=CHECKIN,
                      nights=3, adults=2, children=0, star_min=4, needs=["breakfast"], source_market="IN")
CANCEL_RANK = lambda d: 0 if d is None else 100 - d  # noqa: E731  more days of free cancellation = more flexible


def _img(path: str, source: str | None = None) -> ImageRef:
    return ImageRef(url=f"/api/images/{path}", illustrative=True, source=source or "generated")


# ------------------------------------------------------------------ estimates from the booking log
@lru_cache
def promise(supplier: str, product: str, lead_days: int = LEAD_DAYS) -> Promise:
    bucket = world.lead_bucket(lead_days)[0]
    log = store.get().log.filter((pl.col("supplier_id") == supplier) & (pl.col("product_type") == product)
                                 & (pl.col("lead_bucket") == bucket))
    n = log.height
    k = {o: log.filter(pl.col("outcome") == o).height for o in ("confirmed", "price_changed", "sold_out", "error")}
    honour = k["confirmed"] / n
    z = 1.96                                                       # Wilson interval
    centre = (honour + z * z / (2 * n)) / (1 + z * z / n)
    half = z * (honour * (1 - honour) / n + z * z / (4 * n * n)) ** 0.5 / (1 + z * z / n)
    rep = log.filter(pl.col("outcome") == "price_changed")
    inc = float((rep["final_price"] / rep["quoted"] - 1).mean()) if rep.height else 0.0
    return Promise(supplier_id=supplier, supplier=SUPPLIERS[supplier], lead_bucket=bucket, honour_rate=round(honour, 3),
                   ci_low=round(centre - half, 3), ci_high=round(min(centre + half, 1), 3), n=n,
                   p_price_change=round(k["price_changed"] / n, 4), p_sold_out=round(k["sold_out"] / n, 4),
                   p_error=round(k["error"] / n, 4), exp_increase_pct=round(inc, 4))


def risk(supplier: str, product: str) -> tp.Risk:
    p = promise(supplier, product)
    return tp.Risk(p.supplier, p.p_price_change, p.p_sold_out, p.p_error, p.exp_increase_pct)


@lru_cache
def popularity() -> dict[str, int]:
    """Bookings by Indian agents in the 90 days before the snapshot, per hotel cluster / activity variant."""
    s = store.get()
    log = s.log.filter((pl.col("source_market") == PARAMS.source_market) & (pl.col("ts") > ANCHOR - timedelta(days=90))
                       & pl.col("outcome").is_in(["confirmed", "price_changed"]))
    out: dict[str, int] = {}
    for lid in log["listing_id"]:
        key = s.cluster_of.get(lid) or s.variant_of.get(lid)
        out[key] = out.get(key, 0) + 1
    return out


@lru_cache
def breakfast_pp() -> float:
    """Catalogue median of (BB - RO) / 2 guests for the same supplier room and cancellation terms."""
    by = {}
    for o in store.get().offer.values():
        by.setdefault((o["supplier_room_id"], o["refundable_days"]), {})[o["board"]] = o["nightly"]
    diffs = [(v["BB"] - v["RO"]) / 2 for v in by.values() if "BB" in v and "RO" in v]
    return round(statistics.median(diffs), -1)


def hotel_needs() -> list[tp.Need]:
    bf = breakfast_pp()
    return [tp.Need("breakfast", "Breakfast", PARAMS.adults * PARAMS.nights * bf,
                    f"{PARAMS.adults} people x {PARAMS.nights} nights x {tp.inr(bf)} (catalogue median breakfast supplement)")]


# ------------------------------------------------------------------ trust + golden records
def _digits(p):
    return re.sub(r"\D", "", p)[-8:] if p else None


@lru_cache
def trust() -> dict[str, float]:
    """Share of checkable fields (star, phone, check-in) on which a supplier agrees with the majority of the cluster."""
    s = store.get()
    agree = {k: [0, 0] for k in SUPPLIERS}
    for ls in s.listings_of.values():
        if len({l["supplier_id"] for l in ls}) < 3:
            continue
        for f, get in (("star", lambda l: l["star"]), ("phone", lambda l: _digits(l["phone"])), ("checkin", lambda l: l["checkin_time"])):
            vals = [get(l) for l in ls]
            known = [v for v in vals if v is not None]
            if len(known) < 3:
                continue
            maj = statistics.mode(known)
            for l, v in zip(ls, vals):
                a = agree[l["supplier_id"]]
                a[1] += 1
                a[0] += v == maj                                    # missing counts as not agreeing
    return {k: round(a / n, 2) for k, (a, n) in agree.items()}


def _vote(values: list[tuple[str, object]], key=lambda v: v):
    """Trust-weighted vote; values = [(supplier_id, value)]. Returns the winning value."""
    t, tally, first = trust(), {}, {}
    for sup, v in values:
        if v is None:
            continue
        k = key(v)
        tally[k] = tally.get(k, 0) + t[sup]
        first.setdefault(k, v)
    return first[max(tally, key=tally.get)] if tally else None


@lru_cache
def golden(hid: str) -> dict:
    s = store.get()
    ls = sorted(s.listings_of[hid], key=lambda l: -trust()[l["supplier_id"]])
    pairs = lambda f: [(l["supplier_id"], l[f]) for l in ls]  # noqa: E731
    # display name: the trust-weighted medoid of the supplier names (a typo or a dropped branch number loses the vote)
    clean = [re.sub(r"\s*\(SHA\+\)", "", l["name"]) for l in ls]
    cand = [c for c in clean if not c.isupper()] or [c.title() for c in clean]
    cand = [c for c in cand if not re.search(r"\b(HTL|BKK|RESI|STES)\b", c)] or cand
    name = max(cand, key=lambda c: sum(trust()[l["supplier_id"]] * fuzz.token_sort_ratio(norm(c), norm(o)) for l, o in zip(ls, clean)))
    lat_m, lng_m = statistics.median(l["lat"] for l in ls), statistics.median(l["lng"] for l in ls)
    near = [l for l in ls if rk.haversine_m(lat_m, lng_m, l["lat"], l["lng"]) < 400] or ls
    lat, lng = statistics.median(l["lat"] for l in near), statistics.median(l["lng"] for l in near)
    star = _vote(pairs("star"))
    phone_val = _vote(pairs("phone"), key=_digits)
    phone = next((l["phone"] for l in ls if l["phone"] and l["phone"].startswith("+66 ") and _digits(l["phone"]) == _digits(phone_val)), phone_val)
    address = next((l["address"] for l in ls if l["postcode"]), ls[0]["address"])
    checkin = _vote(pairs("checkin_time"))
    amen_sources = {}
    for l in ls:
        for a in l["amenities"]:
            amen_sources.setdefault(a, []).append(l["supplier_id"])
    # keep an amenity if two suppliers say so, or one supplier we trust at 0.85+
    amenities = {a: sups for a, sups in amen_sources.items() if len(set(sups)) >= 2 or max(trust()[x] for x in sups) >= 0.85}
    desc_l = max(ls, key=lambda l: (len(l["description"]), trust()[l["supplier_id"]]))
    return dict(name=name, lat=lat, lng=lng, star=star, phone=phone, address=address, checkin=checkin, amenities=amenities,
                description=desc_l["description"], description_source=desc_l["supplier_id"], listings=ls,
                pool=any("pool" in a.lower() for a in amenities), family=("Family rooms" in amenities) or any(
                    r["max_occupancy"] >= 4 for r in s.rooms_of.get(hid, [])), district=s.hotels[hid]["district"],
                family_key=family(name, None))


@lru_cache
def golden_images(hid: str) -> list[dict]:
    """Supplier image copies de-duplicated by perceptual hash; the sharpest copy of each wins."""
    import imagehash
    from PIL import Image
    s = store.get()
    rows = [im for l in s.listings_of[hid] for im in s.images_of.get(l["listing_id"], [])]
    groups: list[list] = []
    for im in rows:
        with Image.open(config.BUILD / "images" / im["path"]) as f:
            h, w = imagehash.phash(f), f.size[0]
        g = next((g for g in groups if g[0][0] - h <= 12), None)
        (g.append((h, w, im)) if g else groups.append([(h, w, im)]))
    return [max(g, key=lambda x: x[1])[2] for g in groups]


def _listing_img(lid: str) -> ImageRef | None:
    ims = store.get().images_of.get(lid)
    return _img(ims[0]["path"], SUPPLIERS[ims[0]["owner_id"].split(":")[0]]) if ims else None


@lru_cache
def twin_radius_m() -> int:
    """95th percentile distance between a listing and its own hotel's golden location (look-alike reason uses it)."""
    s = store.get()
    d = sorted(rk.haversine_m(golden(h)["lat"], golden(h)["lng"], l["lat"], l["lng"]) for h, ls in s.listings_of.items() for l in ls)
    return int(round(d[int(0.95 * len(d))], -1))


# ------------------------------------------------------------------ offers
def entry_room(hid: str) -> dict:
    """The like-for-like room to compare: fits the party, sold by the most suppliers, cheapest tier on ties."""
    s = store.get()
    sups = {}
    for o in s.offers_of.get(hid, []):
        sups.setdefault(o["room_id"], set()).add(o["supplier_id"])
    fits = [r for r in s.rooms_of[hid] if r["max_occupancy"] >= PARAMS.adults + PARAMS.children and r["room_id"] in sups]
    return max(fits, key=lambda r: (len(sups[r["room_id"]]), -r["tier_mult"]))


def _cancel_text(d):
    return "Non-refundable" if d is None else f"Free cancellation until {(CHECKIN - timedelta(days=d)).strftime('%d %b')}"


def _pay_text(d):
    return "Pay now" if d is None else f"Pay {d} days before travel"


def _bookable(o) -> sandbox.BookableOffer:
    return sandbox.BookableOffer(o["offer_id"], SUPPLIERS[o["supplier_id"]], o["nightly"] * PARAMS.nights,
                                 f"{o['room_id']}|{o['board']}", CANCEL_RANK(o["refundable_days"]))


@lru_cache
def priced_offers(hid: str) -> list[Offer]:
    s = store.get()
    room = entry_room(hid)
    pool = [_bookable(o) for o in s.offers_of[hid]]
    out = []
    for o in (o for o in s.offers_of[hid] if o["room_id"] == room["room_id"]):
        b = _bookable(o)
        twins = sandbox.same_twins(b, pool)
        price = tp.compute(b.price, {"breakfast"} if o["board"] == "BB" else set(), hotel_needs(), LEAD_DAYS,
                           o["refundable_days"], o["pay_due_days"], risk(o["supplier_id"], "hotel"), twins[0].price if twins else None)
        out.append(Offer(offer_id=o["offer_id"], supplier_id=o["supplier_id"], supplier=SUPPLIERS[o["supplier_id"]],
                         room_id=room["room_id"], room_name=room["name"], board="Breakfast" if o["board"] == "BB" else "Room only",
                         price=b.price, availability=o["availability"],
                         refundable_until=None if o["refundable_days"] is None else CHECKIN - timedelta(days=o["refundable_days"]),
                         cancel_text=_cancel_text(o["refundable_days"]),
                         pay_terms="pay_now" if o["pay_due_days"] is None else f"pay_later_{o['pay_due_days']}d",
                         pay_text=_pay_text(o["pay_due_days"]), promise=promise(o["supplier_id"], "hotel"), true_price=price,
                         sticker_rank=0, true_rank=0))
    for i, o in enumerate(sorted(out, key=lambda o: (o.price, o.offer_id)), 1):
        o.sticker_rank = i
    for i, o in enumerate(sorted(out, key=lambda o: (o.true_price.total, o.offer_id)), 1):
        o.true_rank = i
    return out


# ------------------------------------------------------------------ search
def _lookalikes(hids: list[str]) -> dict[str, Lookalike]:
    out = {}
    g = {h: golden(h) for h in hids}
    for a in hids:
        best = None
        for b in hids:
            ga, gb = g[a], g[b]
            if a == b or not ga["family_key"] or ga["family_key"] != gb["family_key"]:
                continue
            if fuzz.token_set_ratio(norm(ga["name"]), norm(gb["name"])) < 85:
                continue
            d = rk.haversine_m(ga["lat"], ga["lng"], gb["lat"], gb["lng"])
            if best is None or d < best[1]:
                best = (b, d)
        if best:
            b, d = best
            ga, gb = g[a], g[b]
            reasons = [LookalikeReason(kind="distance", text=f"{d:,.0f} m apart (95% of one hotel's listings sit within {twin_radius_m()} m)")]
            if _digits(ga["phone"]) != _digits(gb["phone"]):
                reasons.append(LookalikeReason(kind="phone", text=f"Different phones: {ga['phone']} vs {gb['phone']}"))
            sa, sb = store.get().hotels[a]["street"], store.get().hotels[b]["street"]
            if sa != sb:
                reasons.append(LookalikeReason(kind="branch", text=f"Different branch: {sa} vs {sb}"))
            out[a] = Lookalike(other_card_id=b, other_name=gb["name"], distance_m=round(d), reasons=reasons)
    return out


HOTEL_KW = {"breakfast": ("breakfast",), "free_cancel": ("free cancellation",), "pool": ("pool",)}   # rate text; pool: amenity text


def _has_kw(text: str, kws) -> bool:
    t = text.lower()
    return any(k in t for k in kws)


def candidates() -> list[str]:
    s = store.get()
    out = []
    for hid in s.listings_of:
        g = golden(hid)
        if (rk.haversine_m(PARAMS.area_lat, PARAMS.area_lng, g["lat"], g["lng"]) <= RADIUS_M and (g["star"] or 0) >= (PARAMS.star_min or 0)
                and s.offers_of.get(hid)):
            out.append(hid)
    return sorted(out)


@lru_cache
def hotel_search() -> HotelSearch:
    s = store.get()
    hids = candidates()
    looks = _lookalikes(hids)
    offers = {h: priced_offers(h) for h in hids}
    best = {h: min(v, key=lambda o: o.true_price.total) for h, v in offers.items()}
    lo, hi = min(b.true_price.total for b in best.values()), max(b.true_price.total for b in best.values())
    pop = popularity()
    max_pop = max([pop.get(h, 0) for h in hids] + [1])
    items = []
    for hid in hids:
        g, b = golden(hid), best[hid]
        dist = rk.haversine_m(PARAMS.area_lat, PARAMS.area_lng, g["lat"], g["lng"])
        n_img = len(golden_images(hid))
        content = (min(n_img, 5) / 5 + min(len(g["amenities"]), 10) / 10 + bool(g["phone"]) + bool(re.search(r"\d{5}", g["address"] or ""))
                   + min(len(g["description"]), 200) / 200) / 5
        p = pop.get(hid, 0)
        star = g["star"]
        feats = {"true_price": rk.price_value(b.true_price.total, lo, hi), "promise": b.promise.honour_rate,
                 "distance": rk.distance_value(dist), "star_fit": 1.0 if star >= (PARAMS.star_min or 0) else 0.3,
                 "family_fit": 0.5 * g["pool"] + 0.5 * g["family"], "popularity": p / max_pop, "content": content}
        details = {"true_price": f"True Price from {tp.inr(b.true_price.total)}",
                   "promise": f"{b.supplier} {b.promise.honour_rate:.0%} honoured",
                   "distance": f"{dist:,.0f} m from {PARAMS.area.split(' ·')[0]}",
                   "star_fit": f"{star:g}★ meets {PARAMS.star_min:g}★+ filter" if star >= PARAMS.star_min else f"{star:g}★ below filter",
                   "family_fit": "Pool + family rooms" if g["pool"] and g["family"] else ("Pool" if g["pool"] else ("Family rooms" if g["family"] else "No pool")),
                   "popularity": f"Booked {p}× by Indian agents (90d)", "content": f"Content {content:.0%} complete"}
        terms = rk.score(feats, details, rk.HOTEL_WEIGHTS)
        tags = sorted({"breakfast" for o in offers[hid] if o.board == "Breakfast"}
                      | {"free_cancel" for o in offers[hid] if o.refundable_until} | ({"pool"} if g["pool"] else set()))
        items.append({"hid": hid, "score": terms, "honour": b.promise.honour_rate, "tags": tags,
                      "card": dict(name=g["name"], star=star, lat=g["lat"], lng=g["lng"], district=g["district"])})
    ranked = rk.rank(items)

    samesame, today, truth_tags = [], [], {}
    for it in ranked:
        hid = it["hid"]
        g = golden(hid)
        ls = g["listings"]
        gi = golden_images(hid)
        samesame.append(HotelCard(card_id=hid, cluster_id=hid, image=_img(gi[0]["path"]) if gi else None,
                                  suppliers=sorted({SUPPLIERS[l["supplier_id"]] for l in ls}), member_ids=[l["listing_id"] for l in ls],
                                  from_price=min(o.price for o in offers[hid]), true_price_from=best[hid].true_price.total,
                                  rank=it["rank"], why=rk.why_chips(it["score"]), score=it["score"], dna_tags=it["tags"],
                                  lookalike=looks.get(hid), **it["card"]))
        room = entry_room(hid)
        for l in ls:
            mine = [o for o in s.offers_by_listing.get(l["listing_id"], []) if o["room_id"] == room["room_id"]] or \
                   s.offers_by_listing.get(l["listing_id"], [])
            if not mine:
                continue
            rates, amen = " ".join(o["raw_rate"] for o in mine), " ".join(l["amenities"])
            truth_tags[l["listing_id"]] = ({"breakfast"} if any(o["board"] == "BB" for o in mine) else set()) | (
                {"free_cancel"} if any(o["refundable_days"] is not None for o in mine) else set()) | ({"pool"} if g["pool"] else set())
            # Today cards carry what keyword search on the listing's own text finds; truth is kept for the filter counts
            today.append(HotelCard(card_id=l["listing_id"], cluster_id=hid, image=_listing_img(l["listing_id"]),
                                   supplier=SUPPLIERS[l["supplier_id"]], from_price=min(o["nightly"] for o in mine) * PARAMS.nights, rank=0,
                                   dna_tags=sorted(k for k, kws in HOTEL_KW.items() if _has_kw(amen if k == "pool" else rates, kws)), name=l["name"],
                                   star=l["star"], lat=l["lat"], lng=l["lng"], district=g["district"]))
        samesame[-1].member_ids = [m for m in samesame[-1].member_ids if m in truth_tags]
    today.sort(key=lambda c: (c.from_price, c.card_id))
    for i, c in enumerate(today, 1):
        c.rank = i
    filters = [DnaFilter(key=key, label=label, count=sum(key in t for t in truth_tags.values()),
                         today_count=sum(key in c.dna_tags for c in today))
               for key, label in [("breakfast", "Breakfast included"), ("free_cancel", "Free cancellation"), ("pool", "Pool")]]
    n_raw = len(today)
    return HotelSearch(params=PARAMS, today=today, samesame=samesame, filters=filters,
                       counters=ListingCounters(raw_listings=n_raw, unique_hotels=len(samesame), duplicates_collapsed=n_raw - len(samesame)))


# ------------------------------------------------------------------ detail
@lru_cache
def hotel_detail(hid: str) -> HotelDetail:
    s = store.get()
    g = golden(hid)
    ls, t = g["listings"], trust()

    def fact(key, label, value, field, show=lambda v: v):
        srcs = [{"supplier": SUPPLIERS[l["supplier_id"]], "value": show(l[field]) if l[field] is not None else "—", "trust": t[l["supplier_id"]]}
                for l in ls]
        return SourcedFact(key=key, label=label, value=str(show(value)) if value is not None else "—", sources=srcs)

    star_fmt = lambda v: f"{v:g}★"  # noqa: E731
    facts = [fact("name", "Name", g["name"], "name"), fact("star", "Stars", g["star"], "star", star_fmt),
             fact("address", "Address", g["address"], "address"), fact("phone", "Phone", g["phone"], "phone"),
             fact("checkin", "Check-in", g["checkin"], "checkin_time")]
    gi = golden_images(hid)
    after_amen = [{"name": a, "sources": sorted({SUPPLIERS[x] for x in sups})} for a, sups in g["amenities"].items()]
    sparse = min(ls, key=lambda l: (len(l["amenities"]) + len(s.images_of.get(l["listing_id"], [])), -t[l["supplier_id"]]))
    sp = sparse["supplier_id"]
    enrich = Enrichment(
        supplier=SUPPLIERS[sp],
        before_facts=[SourcedFact(key=f.key, label=f.label, value=next(x["value"] for x in f.sources if x["supplier"] == SUPPLIERS[sp]),
                                  sources=[x for x in f.sources if x["supplier"] == SUPPLIERS[sp]]) for f in facts],
        before_images=[_img(im["path"], SUPPLIERS[sp]) for im in s.images_of.get(sparse["listing_id"], [])],
        before_amenities=sparse["amenities"], before_description=sparse["description"],
        after_amenities=after_amen, after_description=g["description"], after_description_sources=[SUPPLIERS[g["description_source"]]])
    offers_by_room = {}
    for o in s.offers_of.get(hid, []):
        offers_by_room.setdefault(o["room_id"], set()).add(o["supplier_room_id"])
    rooms = []
    for r in s.rooms_of[hid]:
        members = [{"supplier": SUPPLIERS[s.supplier_rooms[x]["supplier_id"]], "raw_name": s.supplier_rooms[x]["raw_name"], "confidence": None}
                   for x in sorted(offers_by_room.get(r["room_id"], []))]
        if members:
            rooms.append(CanonicalRoom(room_id=r["room_id"], name=r["name"], members=members,
                                       attrs={"tier": r["tier"], "bed": r["bed"], "view": r["view"] or "—", "max_occupancy": str(r["max_occupancy"])}))
    looks = _lookalikes(candidates()) if hid in candidates() else {}
    return HotelDetail(cluster_id=hid, name=g["name"], facts=facts, hero=_img(gi[0]["path"]) if gi else None,
                       images=[_img(im["path"]) for im in gi[:8]], rooms=rooms,
                       offers=sorted(priced_offers(hid), key=lambda o: o.sticker_rank), params=PARAMS,
                       enrichment=enrich, lookalike=looks.get(hid))


# ------------------------------------------------------------------ booking (the sandbox stands in for the real supplier)
def demo_basket() -> list[str]:
    """Golden case A (Kestrel room-only NRF, Shah family) and B (Mynah breakfast + free cancel, Patel family)."""
    offs = priced_offers(GOLDEN_HOTEL)
    a = next(o for o in offs if o.supplier_id == "kestrel" and o.board == "Room only" and o.refundable_until is None)
    b = next(o for o in offs if o.supplier_id == "mynah" and o.board == "Breakfast" and o.refundable_until is not None)
    return [a.offer_id, b.offer_id]


DEMO_SEED = 1                                                             # first seed tried; disclosed in the UI


def book(offer_ids: list[str], seed: int):
    """One RNG for the whole basket, so a seed reproduces the scenario exactly."""
    s = store.get()
    rng = random.Random(seed)
    results = []
    for oid in offer_ids:
        hid = s.offer[oid]["hotel_id"]
        vol = s.hotels[hid]["volatility"]
        pool = [_bookable(o) for o in s.offers_of[hid]]
        offer = next(b for b in pool if b.offer_id == oid)
        results.append(sandbox.book(offer, pool, lambda name: sandbox.Profile(*world.behaviour(NAME_TO_ID[name], "hotel", LEAD_DAYS, vol)), rng))
    return results


# ------------------------------------------------------------------ sightseeing
PICKUP_PP = config.PICKUP_PP_INR
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


def _refund_days(cancel: str):
    if cancel == "Non-refundable":
        return None
    m = re.search(r"(\d+)\s*h", cancel)
    return max(1, int(m.group(1)) // 24) if m else 1


def find_attraction(q: str) -> str:
    s = store.get()
    ql = q.lower().strip()
    return max(s.attractions, key=lambda a: (fuzz.partial_ratio(ql, s.attractions[a]["name"].lower()), a == "floating-market"))


def activity_search(q: str) -> ActivitySearch:
    s = store.get()
    aid = find_attraction(q)
    att = s.attractions[aid]
    pop = popularity()
    today, built = [], []
    for v in sorted(s.variants_of[aid], key=lambda v: v["variant_id"]):
        members = s.act_listings_of.get(v["variant_id"], [])
        if not members:
            continue
        listings = []
        for m in members:
            ims = s.images_of.get(m["listing_id"], [])
            listings.append(ActivityListing(listing_id=m["listing_id"], supplier=SUPPLIERS[m["supplier_id"]], title=m["title"],
                                            price=m["price_pp"], rating=m["rating"], image=_img(ims[0]["path"]) if ims else None))
        today += listings
        needs = [tp.Need("pickup", "Hotel pickup", PICKUP_PP * PARAMS.adults, f"{PARAMS.adults} x {tp.inr(PICKUP_PP)} taxi (assumption)")]
        includes = {"pickup"} if "pickup" in v["tags"] else set()
        refund = _refund_days(v["dna"]["cancel"])
        tps = []
        for m in members:
            twins = [x["price_pp"] for x in members if x["listing_id"] != m["listing_id"]]
            tps.append(tp.compute(m["price_pp"] * PARAMS.adults, includes, needs, LEAD_DAYS, refund, None, risk(m["supplier_id"], "activity"),
                                  min(twins) * PARAMS.adults if twins else None))
        bi = min(range(len(members)), key=lambda i: tps[i].total)
        reviews = sum(m["reviews"] for m in members)
        rating = round(sum(m["rating"] * m["reviews"] for m in members) / reviews, 1)
        built.append(dict(vid=v["variant_id"], name=v["name"], dna=v["dna"], tags=v["tags"], hours=v["hours"], listings=listings,
                          tp=tps[bi], best_sup=members[bi]["supplier_id"], rating=rating, pop=pop.get(v["variant_id"], 0)))
    lo, hi = min(b["tp"].total for b in built), max(b["tp"].total for b in built)
    max_pop = max([b["pop"] for b in built] + [1])
    items = []
    for b in built:
        honour = promise(b["best_sup"], "activity").honour_rate
        feats = {"true_price": rk.price_value(b["tp"].total, lo, hi), "promise": honour, "popularity": b["pop"] / max_pop,
                 "duration_fit": 1.0 if b["hours"] <= 6 else 0.5, "rating": max(0.0, (b["rating"] - 3.5) / 1.5)}
        details = {"true_price": f"True Price {tp.inr(b['tp'].total)} for {PARAMS.adults}", "promise": f"{SUPPLIERS[b['best_sup']]} {honour:.0%} honoured",
                   "popularity": f"Booked {b['pop']}× by Indian agents (90d)",
                   "duration_fit": f"{b['hours']:g} h fits a family day" if b["hours"] <= 6 else f"{b['hours']:g} h is a long day",
                   "rating": f"Rated {b['rating']}"}
        items.append({**b, "score": rk.score(feats, details, rk.ACTIVITY_WEIGHTS), "honour": honour})
    rk.rank(items)
    ordered = sorted(items, key=lambda x: x["rank"])
    out = []
    for b in ordered:
        segs = [DnaSegment(key=k, label=DNA_LABELS[k], value=b["dna"][k], differs=len({x["dna"][k] for x in items}) > 1) for k in DNA_LABELS]
        ref = ordered[1] if b is ordered[0] and len(ordered) > 1 else ordered[0]
        out.append(ActivityVariant(variant_id=b["vid"], name=b["name"], dna=segs, dna_tags=b["tags"], members=b["listings"],
                                   price_from=min(m.price for m in b["listings"]), true_price_from=b["tp"].total, rank=b["rank"],
                                   why=rk.why_chips(b["score"]), score=b["score"],
                                   diff_sentence=diff_sentence(b, ref) if ref is not b else "Only variant.", diff_source="template"))
    raw_text = {m["listing_id"]: m["title"] + " " + m["description"] for v in s.variants_of[aid] for m in s.act_listings_of.get(v["variant_id"], [])}
    tags_of = {m["listing_id"]: v["tags"] for v in s.variants_of[aid] for m in s.act_listings_of.get(v["variant_id"], [])}
    for li in today:
        li.dna_tags = [fk for fk, _, kws in ACT_FILTERS if _has_kw(raw_text[li.listing_id], kws)]
    filters = [DnaFilter(key=fk, label=label, count=sum(fk in tags_of[li.listing_id] for li in today),
                         today_count=sum(fk in li.dna_tags for li in today)) for fk, label, _ in ACT_FILTERS]
    today.sort(key=lambda x: (x.price, x.listing_id))
    return ActivitySearch(query=att["name"], raw_count=len(today), today=today,
                          groups=[ActivityGroup(group_id=aid, base_product=att["name"], variants=out)], filters=filters)


# ------------------------------------------------------------------ supplier report
@lru_cache
def suppliers() -> list[SupplierRow]:
    s = store.get()
    n_by = dict(s.log.group_by("supplier_id").len().iter_rows())
    clusters_with = {h: {l["supplier_id"] for l in ls} for h, ls in s.listings_of.items()}
    rows = []
    for k, name in SUPPLIERS.items():
        mine = [l for l in s.listings.values() if l["supplier_id"] == k]
        dup = sum(len(clusters_with[s.cluster_of[l["listing_id"]]] - {k}) > 0 for l in mine) / max(len(mine), 1)
        spreads = []
        for hid, offs in s.offers_of.items():
            room = entry_room(hid)
            ro = {}
            for o in offs:
                if o["room_id"] == room["room_id"] and o["board"] == "RO":
                    ro[o["supplier_id"]] = min(ro.get(o["supplier_id"], 1e12), o["nightly"])
            if k in ro and len(ro) >= 3:
                med = statistics.median(ro.values())
                spreads.append(abs(ro[k] - med) / med)
        rows.append(SupplierRow(supplier_id=k, supplier=name, honour_rate_hotel=promise(k, "hotel").honour_rate,
                                honour_rate_activity=promise(k, "activity").honour_rate, n_attempts=n_by.get(k, 0),
                                duplicate_share=round(dup, 2), price_spread_pct=round(100 * statistics.median(spreads), 1) if spreads else 0.0,
                                hotel=promise(k, "hotel"), activity=promise(k, "activity")))
    return rows
