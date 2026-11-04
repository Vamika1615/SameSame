"""Hotel Twin Finder, part 2: train the pair classifier and choose precision-first thresholds.

Labels: the generator's truth (same base hotel = SAME), plus any human review labels, which override
it for that pair. Held-out families (config.is_holdout) are excluded from training AND threshold
selection; the evaluation set is drawn only from them. Scores are out-of-fold (see fit).
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
FOLDS = 5
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=20, feature_fraction=0.9,
              bagging_fraction=0.9, bagging_freq=1, lambda_l2=1.0, verbose=-1, seed=config.SEED)


def labels(listing_ids_a, listing_ids_b) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """y (1 = SAME), the hotel behind each side, and a mask of pairs allowed in training (no held-out family)."""
    truth = pl.read_parquet(config.BUILD / "hotel_truth.parquet")
    hotel_of = dict(zip(truth["listing_id"], truth["hotel_id"]))
    base = pl.read_parquet(config.BUILD / "base_hotels.parquet")
    key = {h: f or h for h, f in zip(base["hotel_id"], base["family"])}
    y = np.array([hotel_of[a] == hotel_of[b] for a, b in zip(listing_ids_a, listing_ids_b)], dtype=int)
    ha = np.array([hotel_of[a] for a in listing_ids_a])
    hb = np.array([hotel_of[b] for b in listing_ids_b])
    ok = np.array([not (config.is_holdout(key[a]) or config.is_holdout(key[b])) for a, b in zip(ha, hb)])
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
    return y, ha, hb, ok


def fit(X: np.ndarray, y: np.ndarray, ha: np.ndarray, hb: np.ndarray, ok: np.ndarray) -> tuple[lgb.Booster, np.ndarray, dict]:
    """Out-of-fold scoring, grouped by hotel.

    Trainable hotels are split into FOLDS groups. The model for fold k trains only on pairs touching no fold-k
    hotel, and scores the pairs whose first hotel is in fold k, so every score the app shows for a trainable
    hotel comes from a model that never saw that hotel's labels. Held-out pairs are scored by a model trained on
    all trainable pairs. Thresholds are chosen on the out-of-fold scores of trainable pairs only.
    """
    rng = np.random.default_rng(config.SEED)
    hotels = np.unique(np.concatenate([ha[ok], hb[ok]]))
    fold_of = dict(zip(rng.permutation(hotels), np.arange(len(hotels)) % FOLDS))
    fa = np.array([fold_of.get(h, -1) for h in ha])
    fb = np.array([fold_of.get(h, -1) for h in hb])
    p = np.zeros(len(y))
    for k in range(FOLDS):
        tr = ok & (fa != k) & (fb != k)
        b = lgb.train(PARAMS, lgb.Dataset(X[tr], y[tr], feature_name=FEATURES), num_boost_round=300)
        score = ok & (fa == k)
        p[score] = b.predict(X[score])
    final = lgb.train(PARAMS, lgb.Dataset(X[ok], y[ok], feature_name=FEATURES), num_boost_round=300)
    p[~ok] = final.predict(X[~ok])
    po, yo = p[ok], y[ok]
    auto_data = _precision_threshold(po, yo, AUTO_MERGE_PRECISION)
    auto = max(auto_data, AUTO_FLOOR)
    pos = np.sort(po[yo == 1])
    gray_data = float(pos[int((1 - GRAY_RECALL) * len(pos))]) if len(pos) else GRAY_CEILING
    gray = min(gray_data, GRAY_CEILING, auto - 0.05)
    info = {"auto_merge": round(auto, 4), "gray_low": round(gray, 4), "auto_merge_from_validation": auto_data,
            "gray_low_from_validation": round(gray_data, 4), "policy_floors": {"auto_merge": AUTO_FLOOR, "gray_low": GRAY_CEILING},
            "scoring": f"out-of-fold, {FOLDS} folds grouped by hotel", "n_train": int(ok.sum()), "n_val": int(ok.sum()),
            "train_pos": int(yo.sum()), "excluded_holdout": int((~ok).sum()),
            "val_precision_at_auto": _prec(po >= auto, yo), "val_recall_at_auto": _rec(po >= auto, yo),
            "importance": dict(zip(FEATURES, [int(v) for v in final.feature_importance("gain")]))}
    return final, p, info


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
