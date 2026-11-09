"""Builds every artifact into data/build/. Deterministic from config.SEED.

    python -m samesame.pipeline

Stages: base (OSM curation) -> feeds (6 supplier hotel feeds) -> activities -> booking log -> images
-> short-code listings + Weaver's rate sheet (data/naming.py) -> Remix components -> Promise model (fitted on the booking log) -> matcher (hotels, rooms, Variant DNA) -> evaluation report.
Tables are written as parquet and registered as views in samesame.duckdb. Truth tables (*_truth, rooms,
hard_negatives) are for evaluation and the data card only; the matcher (M3) must never read them.
"""
import json
import time

import duckdb
import numpy as np
import polars as pl

from samesame import config
from samesame.data import activities, booking_log, components, feeds, images_gen, naming, osm_base, search_log
from samesame.pricing import promise

TABLES = ["base_hotels", "osm_duplicates", "hard_negatives", "hotel_listings", "hotel_truth", "rooms", "supplier_rooms",
          "room_truth", "offers", "osm_reference", "attractions", "activity_variants", "activity_listings", "activity_truth", "booking_log", "images",
          "meeting_points", "components", "search_events"]


def _rng(stage: str) -> np.random.Generator:
    return np.random.default_rng([config.SEED, sum(map(ord, stage))])


def _write(name: str, rows: list[dict]):
    rows = [{k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in r.items()} for r in rows]
    pl.DataFrame(rows, infer_schema_length=None).write_parquet(config.BUILD / f"{name}.parquet")


def main(skip_images: bool = False):
    t0 = time.time()
    config.BUILD.mkdir(parents=True, exist_ok=True)
    hotels, dups, hard = osm_base.curate(_rng("base"))
    listings, truth, rooms, sup_rooms, room_truth, offers = feeds.generate(hotels, _rng("feeds"))
    attractions, variants, act_listings, act_truth = activities.generate(_rng("activities"))
    meeting_points, parts = components.generate(attractions, variants, act_listings, act_truth, _rng("components"))
    searches = search_log.generate(variants, act_listings, act_truth, _rng("searches"))
    log = booking_log.generate(hotels, listings, truth, offers, attractions, act_listings, act_truth, _rng("log"), parts)
    airport_mp, airport_parts = components.airport(_rng("airport"))      # after the log: adds no draws to it
    meeting_points, parts = meeting_points + [airport_mp], parts + airport_parts
    imgs = [] if skip_images else images_gen.generate(hotels, listings, truth, attractions, act_listings, act_truth, hard, _rng("images"))
    # short-code listings: extra rows from their own stream, after the log and images, so nothing above changes
    extra = naming.short_code_listings(hotels, listings, truth, rooms, sup_rooms, room_truth, offers, _rng("naming"))
    listings, truth, sup_rooms = listings + extra["listings"], truth + extra["truth"], sup_rooms + extra["sup_rooms"]
    room_truth, offers = room_truth + extra["room_truth"], offers + extra["offers"]
    sheet, sheet_key = naming.weaver_sheet(hotels, rooms, osm_base.reference(), dups, _rng("weaver"))
    naming.write_sheet(sheet)
    _write("weaver_truth", sheet_key)
    data = dict(osm_reference=osm_base.reference(), base_hotels=hotels, osm_duplicates=dups, hard_negatives=hard, hotel_listings=listings, hotel_truth=truth,
                rooms=rooms, supplier_rooms=sup_rooms, room_truth=room_truth, offers=offers, attractions=attractions, activity_variants=variants,
                activity_listings=act_listings, activity_truth=act_truth, booking_log=log, images=imgs,
                meeting_points=meeting_points, components=parts, search_events=searches)
    for name in TABLES:
        if data[name]:
            _write(name, data[name])
    prom, prom_info = promise.fit(pl.read_parquet(config.BUILD / "booking_log.parquet"))
    _write("promise_model", prom)
    (config.BUILD / "promise.json").write_text(json.dumps(prom_info, indent=2), encoding="utf-8")
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    with duckdb.connect(str(config.DB_PATH)) as con:
        for name in TABLES + ["promise_model"]:
            if name == "promise_model" or data[name]:
                con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{(config.BUILD / f'{name}.parquet').as_posix()}')")
    from samesame.matching import run as matcher
    matcher.main()
    counts = {k: len(v) for k, v in data.items()}
    manifest = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "seed": config.SEED, "stages": ["m0", "m2", "m3", "m4", "r1", "n1"],
                "counts": counts, "seconds": None}
    (config.BUILD / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")   # the report reads the app's store
    from samesame.eval import report
    report.main()
    manifest["seconds"] = round(time.time() - t0, 1)
    (config.BUILD / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("pipeline:", json.dumps(counts), f"in {manifest['seconds']}s")


if __name__ == "__main__":
    main()
