"""Hotel Twin Finder, part 2: train the pair classifier and choose precision-first thresholds.

Labels: the generator's truth (same base hotel = SAME), plus any human review labels, which override
it for that pair. Held-out families (config.is_holdout) are excluded from training AND threshold
selection; the evaluation set is drawn only from them.
"""
import json

import lightgbm as lgb
import numpy as np
import polars as pl

from samesame import config
from samesame.matching.hotels import FEATURES

AUTO_MERGE_PRECISION = 0.995          # precision-first: an auto-merge has to be right 199 times in 200
GRAY_RECALL = 0.98                    # below the gray zone we accept losing at most 2% of true twins
# Policy floors. Synthetic validation pairs separate almost perfectly, so the data alone would happily pick a
# bar like p >= 0.14; we never auto-merge below 0.90 and always send 0.30-0.90 to a human, whatever validation says.
AUTO_FLOOR, GRAY_CEILING = 0.90, 0.30
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=20, feature_fraction=0.9,
              bagging_fraction=0.9, bagging_freq=1, lambda_l2=1.0, verbose=-1, seed=config.SEED)


def labels(listing_ids_a, listing_ids_b) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """y (1 = SAME), hotel group of the pair, and a mask of pairs allowed in training (no held-out family)."""
    truth = pl.read_parquet(config.BUILD / "hotel_truth.parquet")
    hotel_of = dict(zip(truth["listing_id"], truth["hotel_id"]))
    base = pl.read_parquet(config.BUILD / "base_hotels.parquet")
    key = {h: f or h for h, f in zip(base["hotel_id"], base["family"])}
    y = np.array([hotel_of[a] == hotel_of[b] for a, b in zip(listing_ids_a, listing_ids_b)], dtype=int)
    grp = np.array([hotel_of[a] for a in listing_ids_a])
    ok = np.array([not (config.is_holdout(key[hotel_of[a]]) or config.is_holdout(key[hotel_of[b]]))
                   for a, b in zip(listing_ids_a, listing_ids_b)])
    # human review labels override the generator for the pairs they cover (replayed in order, undo respected)
    if config.LABELS_PATH.exists():
        human = {}
        for line in config.LABELS_PATH.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("action") == "label" and r.get("left") and r.get("right"):
                human[r["audit_id"]] = (r["left"], r["right"], r["label"] == "S")
            elif r.get("action") == "undo":
                human.pop(r["audit_id"], None)
        idx = {(a, b): i for i, (a, b) in enumerate(zip(listing_ids_a, listing_ids_b))}
        for a, b, same in human.values():
            i = idx.get((a, b), idx.get((b, a)))
            if i is not None:
                y[i] = int(same)
    return y, grp, ok


def fit(X: np.ndarray, y: np.ndarray, grp: np.ndarray, ok: np.ndarray) -> tuple[lgb.Booster, dict]:
    """Grouped 80/20 split by hotel on the trainable pairs; thresholds come from the 20%, never from held-out data."""
    idx = np.nonzero(ok)[0]
    hotels = np.unique(grp[idx])
    rng = np.random.default_rng(config.SEED)
    val_h = set(rng.choice(hotels, size=len(hotels) // 5, replace=False))
    val = np.array([g in val_h for g in grp[idx]])
    tr, va = idx[~val], idx[val]
    booster = lgb.train(PARAMS, lgb.Dataset(X[tr], y[tr], feature_name=FEATURES), num_boost_round=300)
    p = booster.predict(X[va])
    yv = y[va]
    auto_data = _precision_threshold(p, yv, AUTO_MERGE_PRECISION)
    auto = max(auto_data, AUTO_FLOOR)
    pos = np.sort(p[yv == 1])
    gray_data = float(pos[int((1 - GRAY_RECALL) * len(pos))]) if len(pos) else GRAY_CEILING
    gray = min(gray_data, GRAY_CEILING, auto - 0.05)
    info = {"auto_merge": round(auto, 4), "gray_low": round(gray, 4), "auto_merge_from_validation": auto_data,
            "gray_low_from_validation": round(gray_data, 4), "policy_floors": {"auto_merge": AUTO_FLOOR, "gray_low": GRAY_CEILING}, "n_train": int(len(tr)), "n_val": int(len(va)),
            "train_pos": int(y[tr].sum()), "val_pos": int(yv.sum()), "excluded_holdout": int((~ok).sum()),
            "val_precision_at_auto": _prec(p >= auto, yv), "val_recall_at_auto": _rec(p >= auto, yv),
            "importance": dict(zip(FEATURES, [int(v) for v in booster.feature_importance("gain")]))}
    return booster, info


def _prec(pred, y):
    return round(float((pred & (y == 1)).sum() / max(pred.sum(), 1)), 4)


def _rec(pred, y):
    return round(float((pred & (y == 1)).sum() / max((y == 1).sum(), 1)), 4)


def _precision_threshold(p, y, target):
    """Lowest threshold whose precision on validation pairs is at least `target` (searched from the top)."""
    order = np.argsort(-p)
    tp = np.cumsum(y[order] == 1)
    prec = tp / np.arange(1, len(order) + 1)
    ok = np.nonzero(prec >= target)[0]
    if not len(ok):
        return 0.99
    return round(float(p[order][ok[-1]]), 4)               # deepest prefix that still meets the bar
