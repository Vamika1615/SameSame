"""Read-only access to the pipeline's tables, loaded once into plain Python structures.

Since M3 everything the app shows comes from what the matcher predicted from the supplier feeds:
hotel clusters (hotel_clusters), canonical rooms (room_map) and sightseeing variants (activity_map).
Generator truth is reachable only through the two `world_*` helpers below, used by the booking
sandbox (which stands in for the real supplier) and by the ops screen's after-the-fact answer reveal.
"""
import json
from dataclasses import dataclass, field
from functools import lru_cache

import polars as pl

from samesame import config
from samesame.variants import dna

CLUSTER_SOURCE = "Twin Finder (LightGBM + constrained clustering) on the supplier feeds"
TIER_ORDER = {"Standard": 0.9, "Superior": 1.0, "Deluxe": 1.15, "Premier": 1.3, "Executive": 1.5, "Junior Suite": 1.8,
              "Suite": 2.4, "Family": 1.45, "Unknown": 3.0}


def _rows(name: str) -> list[dict]:
    return pl.read_parquet(config.BUILD / f"{name}.parquet").to_dicts()


def _group(rows, key):
    out: dict = {}
    for r in rows:
        out.setdefault(r[key], []).append(r)
    return out


@dataclass
class Store:
    listings: dict
    cluster_of: dict                     # listing_id -> cluster_id (matcher)
    listings_of: dict                    # cluster_id -> [listing]
    rooms_of: dict                       # cluster_id -> [canonical room] (room parser)
    supplier_rooms: dict                 # supplier_room_id -> row (+ room_id, confidence, note)
    offers_of: dict                      # cluster_id -> [offer]
    offers_by_listing: dict
    offer: dict                          # offer_id -> offer
    attractions: dict
    variants_of: dict                    # attraction_id -> [variant (Variant DNA group)]
    act_listings_of: dict                # variant_id -> [listing]
    variant_of: dict                     # activity listing_id -> variant_id
    images_of: dict                      # owner_id -> [image row]
    image_meta: dict                     # path -> image row (photo kind + credit)
    osm_reference: list                  # real OSM fields for every named hotel in the city (reference data, not truth)
    descriptions: dict                   # Wikipedia summaries by attraction id / osm id
    pairs: pl.DataFrame                  # every scored hotel candidate pair
    matcher: dict
    log: pl.DataFrame
    promise: dict                        # (supplier, product, lead bucket) -> fitted Promise row (pricing/promise.py)
    components: dict                     # Remix parts: component_id -> row; tickets/add-ons carry Variant DNA read from their text
    meeting_points: dict
    manifest: dict = field(default_factory=dict)


@lru_cache
def get() -> Store:
    listings = {l["listing_id"]: l for l in _rows("hotel_listings")}
    cluster_of = dict(pl.read_parquet(config.BUILD / "hotel_clusters.parquet").iter_rows())
    rmap = {r["supplier_room_id"]: r for r in _rows("room_map")}
    offers = [{**o, "hotel_id": cluster_of[o["listing_id"]], "room_id": rmap[o["supplier_room_id"]]["room_id"]} for o in _rows("offers")]
    rooms_of: dict = {}
    for r in rmap.values():
        rooms = rooms_of.setdefault(r["cluster_id"], {})
        rooms.setdefault(r["room_id"], {"room_id": r["room_id"], "hotel_id": r["cluster_id"], "name": r["name"], "tier": r["tier"],
                                        "bed": r["bed"], "view": r["view"], "max_occupancy": r["max_occupancy"],
                                        "tier_mult": TIER_ORDER.get(r["tier"], 3.0)})
    acts = {l["listing_id"]: l for l in _rows("activity_listings")}
    amap = _rows("activity_map")
    variants_of: dict = {}
    act_listings_of: dict = {}
    for gid, ms in _group(amap, "group_id").items():
        members = [{**acts[m["listing_id"]], "dna": json.loads(m["dna"]), "variant_id": gid} for m in ms]
        act_listings_of[gid] = members
        variants_of.setdefault(ms[0]["attraction_id"], []).append(
            {"variant_id": gid, "attraction_id": ms[0]["attraction_id"], "ambiguous": any(m["ambiguous"] for m in ms), **dna.summarise(members)})
    images = _rows("images") if (config.BUILD / "images.parquet").exists() else []
    return Store(
        listings=listings, cluster_of=cluster_of,
        listings_of=_group([{**l, "hotel_id": cluster_of[l["listing_id"]]} for l in listings.values()], "hotel_id"),
        rooms_of={c: list(v.values()) for c, v in rooms_of.items()},
        supplier_rooms={r["supplier_room_id"]: {**r, "room_id": rmap[r["supplier_room_id"]]["room_id"],
                                                 "confidence": rmap[r["supplier_room_id"]]["confidence"], "note": rmap[r["supplier_room_id"]]["note"]}
                        for r in _rows("supplier_rooms")},
        offers_of=_group(offers, "hotel_id"), offers_by_listing=_group(offers, "listing_id"), offer={o["offer_id"]: o for o in offers},
        attractions={a["attraction_id"]: a for a in _rows("attractions")}, variants_of=variants_of,
        act_listings_of=act_listings_of, variant_of={m["listing_id"]: m["group_id"] for m in amap},
        images_of=_group(images, "owner_id"), image_meta={im["path"]: im for im in images},
        osm_reference=_rows("osm_reference"), descriptions=_descriptions(), pairs=pl.read_parquet(config.BUILD / "hotel_pairs.parquet"),
        matcher=json.loads((config.BUILD / "matcher.json").read_text(encoding="utf-8")),
        log=pl.read_parquet(config.BUILD / "booking_log.parquet"),
        promise={(r["supplier_id"], r["product_type"], r["lead_bucket"]): r for r in _rows("promise_model")},
        components=_components(), meeting_points={m["meeting_point_id"]: m for m in _rows("meeting_points")},
        manifest=json.loads((config.BUILD / "manifest.json").read_text(encoding="utf-8")),
    )


def _components() -> dict:
    """Parts as suppliers send them: structured slots, meeting point, vehicle and terms; tickets and add-ons also get
    Variant DNA read from their title and description by the same extractor that reads packages."""
    out = {}
    for c in _rows("components"):
        if c["role"] != "transfer":
            c["dna"] = dna.extract(c["title"], c["description"])
        out[c["component_id"]] = c
    return out


def _descriptions() -> dict:
    f = config.DATA / "raw" / "wiki" / "descriptions.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


# ------------------------------------------------------------------ the world behind the feeds (not for matching or display)
@lru_cache
def _world():
    truth = dict(pl.read_parquet(config.BUILD / "hotel_truth.parquet").select("listing_id", "hotel_id").iter_rows())
    base = {h["hotel_id"]: h for h in _rows("base_hotels")}
    return truth, base


def world_hotel(listing_id: str) -> dict:
    """The real hotel behind a listing. Only the booking sandbox (demand volatility) may use this."""
    truth, base = _world()
    return base[truth[listing_id]]


def world_same(a: str, b: str) -> bool:
    """Generator label for a hotel pair. Only the ops screen's after-labelling reveal may use this."""
    truth, _ = _world()
    return truth[a] == truth[b]


@lru_cache
def _world_rooms_acts():
    rt = dict(pl.read_parquet(config.BUILD / "room_truth.parquet").select("supplier_room_id", "room_id").iter_rows())
    tier = dict(pl.read_parquet(config.BUILD / "rooms.parquet").select("room_id", "tier").iter_rows())
    at = {t["listing_id"]: t for t in _rows("activity_truth")}
    return rt, tier, at


def world_relation(entity_type: str, a: str, b: str) -> str:
    """Generator label for a pair. Only the ops screen's after-labelling reveal may use this."""
    if entity_type == "hotel":
        return "SAME" if world_same(a, b) else "DIFFERENT"
    rt, tier, at = _world_rooms_acts()
    if entity_type == "room":
        return "SAME" if rt[a] == rt[b] else "VARIANT" if tier[rt[a]] == tier[rt[b]] else "DIFFERENT"
    if at[a]["variant_id"] == at[b]["variant_id"]:
        return "SAME"
    return "VARIANT" if at[a]["attraction_id"] == at[b]["attraction_id"] else "DIFFERENT"


def ready() -> bool:
    m = config.BUILD / "manifest.json"
    return m.exists() and "m4" in json.loads(m.read_text(encoding="utf-8")).get("stages", [])
