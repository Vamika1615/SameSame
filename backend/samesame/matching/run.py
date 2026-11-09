"""Matcher stage of the pipeline: hotels (block -> features -> LightGBM -> constrained clusters -> gray
zone), rooms (parser) and sightseeing (Variant DNA). Writes the outputs store.py serves:

  hotel_pairs.parquet     every candidate pair: p(SAME), decision, reason, features
  hotel_clusters.parquet  listing_id -> cluster_id
  room_map.parquet        supplier_room_id -> canonical room (+ confidence)
  activity_map.parquet    listing_id -> attraction, variant group, extracted DNA
  matcher.json            thresholds, training sizes, feature importance, timings
"""
import json
import time

import numpy as np
import polars as pl

from samesame import config
from samesame.matching import cluster as clu
from samesame.matching import hotels as hm
from samesame.matching import rooms as rm
from samesame.matching import train
from samesame.variants import dna


def _rows(name):
    return pl.read_parquet(config.BUILD / f"{name}.parquet").to_dicts()


def main():
    t0 = time.time()
    listings = _rows("hotel_listings")
    P = hm.prep(listings)
    pairs = hm.block(P)
    emb = hm.embed([p["_n"] for p in P])
    hashes = hm.image_hashes(_rows("images"), P) if (config.BUILD / "images.parquet").exists() else {}
    t_feat = time.time()
    feats = [hm.pair_features(P[i], P[j], float(emb[i] @ emb[j]) if emb is not None else np.nan,
                              hm.img_sim(hashes.get(P[i]["listing_id"], []), hashes.get(P[j]["listing_id"], [])))
             for i, j in pairs]
    X = np.array([[f[k] for k in hm.FEATURES] for f in feats], dtype=float)
    a_ids = [P[i]["listing_id"] for i, _ in pairs]
    b_ids = [P[j]["listing_id"] for _, j in pairs]
    y, ha, hb, ok = train.labels(a_ids, b_ids)
    booster, p, info = train.fit(X, y, ha, hb, ok)
    cluster_of, decisions = clu.cluster(P, pairs, p, info["auto_merge"], info["gray_low"])
    dec = {k: (d, r) for k, d, r in decisions}
    pl.DataFrame(infer_schema_length=None, data=[{"a": a_ids[k], "b": b_ids[k], "p": float(p[k]), "decision": dec[k][0], "reason": dec[k][1], **feats[k]}
                  for k in range(len(pairs))]).write_parquet(config.BUILD / "hotel_pairs.parquet")
    pl.DataFrame([{"listing_id": l, "cluster_id": c} for l, c in cluster_of.items()]).write_parquet(config.BUILD / "hotel_clusters.parquet")
    booster.save_model(str(config.BUILD / "hotel_matcher.txt"))

    # rooms, within each predicted hotel cluster
    by_cluster: dict = {}
    for r in _rows("supplier_rooms"):
        by_cluster.setdefault(cluster_of[r["listing_id"]], []).append(r)
    names: dict = {}
    for l in listings:
        names.setdefault(cluster_of[l["listing_id"]], []).append(l["name"])
    pl.DataFrame(rm.map_rooms(by_cluster, names), infer_schema_length=None).write_parquet(config.BUILD / "room_map.parquet")

    # sightseeing Variant DNA
    atts = _rows("attractions")
    acts = _rows("activity_listings")
    for a in acts:
        a["dna"] = dna.extract(a["title"], a["description"])
        a["attraction_id"] = dna.assign_attraction(a, atts)
    amap = []
    for aid in sorted({a["attraction_id"] for a in acts}):
        groups, ambiguous = dna.group([a for a in acts if a["attraction_id"] == aid])
        for gi, ms in enumerate(groups):
            for m in ms:
                amap.append({"listing_id": m["listing_id"], "attraction_id": aid, "group_id": f"{aid}-g{gi + 1}", "dna": json.dumps(m["dna"]),
                             "ambiguous": m["listing_id"] in ambiguous})
    pl.DataFrame(amap, infer_schema_length=None).write_parquet(config.BUILD / "activity_map.parquet")

    counts = {d: sum(1 for _, x, _ in decisions if x == d) for d in ("auto", "gray", "blocked", "different", "human_same", "human_different")}
    info.update({"listings": len(P), "candidate_pairs": len(pairs), "clusters": len(set(cluster_of.values())),
                 "decisions": counts, "embeddings": emb is not None, "seconds": round(time.time() - t0, 1),
                 "feature_seconds": round(time.time() - t_feat, 1)})
    (config.BUILD / "matcher.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print("matcher:", json.dumps({k: info[k] for k in ("auto_merge", "gray_low", "candidate_pairs", "clusters", "decisions", "seconds")}))


if __name__ == "__main__":
    main()
