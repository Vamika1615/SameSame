"""Read-only access to the pipeline's tables, loaded once into plain Python structures.

`cluster_of` maps a supplier listing to its hotel, and `room_of` a supplier room to its canonical
room. Until the M3 matcher lands both come from the generator's truth tables, and the UI says so;
M3 swaps in the matcher's output here, in one place.
"""
import json
from dataclasses import dataclass, field
from functools import lru_cache

import polars as pl

from samesame import config

CLUSTER_SOURCE = "generator truth (matcher lands in M3)"


def _rows(name: str) -> list[dict]:
    return pl.read_parquet(config.BUILD / f"{name}.parquet").to_dicts()


def _group(rows, key):
    out: dict = {}
    for r in rows:
        out.setdefault(r[key], []).append(r)
    return out


@dataclass
class Store:
    hotels: dict
    listings: dict
    cluster_of: dict                     # listing_id -> hotel_id (cluster)
    listings_of: dict                    # hotel_id -> [listing]
    rooms_of: dict                       # hotel_id -> [canonical room]
    supplier_rooms: dict                 # supplier_room_id -> row
    offers_of: dict                      # hotel_id -> [offer]
    offers_by_listing: dict
    offer: dict                          # offer_id -> offer
    attractions: dict
    variants_of: dict                    # attraction_id -> [variant]
    act_listings_of: dict                # variant_id -> [listing]
    variant_of: dict                     # activity listing_id -> variant_id
    images_of: dict                      # owner_id -> [image row]
    hard_negatives: list
    log: pl.DataFrame
    manifest: dict = field(default_factory=dict)


@lru_cache
def get() -> Store:
    hotels = {h["hotel_id"]: h for h in _rows("base_hotels")}
    listings = {l["listing_id"]: l for l in _rows("hotel_listings")}
    truth = _rows("hotel_truth")
    cluster_of = {t["listing_id"]: t["hotel_id"] for t in truth}
    room_of = {t["supplier_room_id"]: t["room_id"] for t in _rows("room_truth")}
    offers = [{**o, "hotel_id": cluster_of[o["listing_id"]], "room_id": room_of[o["supplier_room_id"]]} for o in _rows("offers")]
    variants = _rows("activity_variants")
    for v in variants:
        v["dna"] = json.loads(v["dna"])
    act_truth = {t["listing_id"]: t["variant_id"] for t in _rows("activity_truth")}
    act = _rows("activity_listings")
    images = _rows("images") if (config.BUILD / "images.parquet").exists() else []
    return Store(
        hotels=hotels, listings=listings, cluster_of=cluster_of,
        listings_of=_group([{**l, "hotel_id": cluster_of[l["listing_id"]]} for l in listings.values()], "hotel_id"),
        rooms_of=_group(_rows("rooms"), "hotel_id"),
        supplier_rooms={r["supplier_room_id"]: {**r, "room_id": room_of[r["supplier_room_id"]]} for r in _rows("supplier_rooms")},
        offers_of=_group(offers, "hotel_id"), offers_by_listing=_group(offers, "listing_id"), offer={o["offer_id"]: o for o in offers},
        attractions={a["attraction_id"]: a for a in _rows("attractions")}, variants_of=_group(variants, "attraction_id"),
        act_listings_of=_group([{**l, "variant_id": act_truth[l["listing_id"]]} for l in act], "variant_id"),
        variant_of=act_truth, images_of=_group(images, "owner_id"), hard_negatives=_rows("hard_negatives"),
        log=pl.read_parquet(config.BUILD / "booking_log.parquet"),
        manifest=json.loads((config.BUILD / "manifest.json").read_text(encoding="utf-8")),
    )


def ready() -> bool:
    m = config.BUILD / "manifest.json"
    return m.exists() and "m2" in json.loads(m.read_text(encoding="utf-8")).get("stages", [])
