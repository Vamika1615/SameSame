"""Evaluation report, rebuilt on every pipeline run so no number on screen or in METRICS.md is typed by hand.

    python -m samesame.eval.report

Reads the matcher's outputs, generator truth and the frozen blind set; writes data/build/metrics.json
and METRICS.md. Never imports the trainer, never writes anything training reads.
"""
import itertools
import json
import math
import time
from datetime import timedelta

import numpy as np
import polars as pl

from samesame import config
from samesame.eval import blind
from samesame.pricing import promise as pm


def _rows(name):
    return pl.read_parquet(config.BUILD / f"{name}.parquet").to_dicts()


def _pr(ids, same_true, same_pred) -> dict:
    tp = fp = fn = 0
    for a, b in itertools.combinations(ids, 2):
        t, p = same_true(a, b), same_pred(a, b)
        tp += t and p
        fp += p and not t
        fn += t and not p
    return {"precision": round(tp / (tp + fp), 4) if tp + fp else None, "recall": round(tp / (tp + fn), 4) if tp + fn else None,
            "true_pairs": tp + fn, "predicted_pairs": tp + fp, "false_merges": fp, "missed": fn}


def compute() -> dict:
    base = {h["hotel_id"]: h for h in _rows("base_hotels")}
    hold = {h for h, b in base.items() if config.is_holdout(b["family"] or h)}
    truth = {t["listing_id"]: t["hotel_id"] for t in _rows("hotel_truth")}
    cl = dict(pl.read_parquet(config.BUILD / "hotel_clusters.parquet").iter_rows())
    ids = sorted(truth)
    st, sp = (lambda a, b: truth[a] == truth[b]), (lambda a, b: cl[a] == cl[b])
    hotels = {"all": _pr(ids, st, sp), "held_out": _pr([i for i in ids if truth[i] in hold], st, sp),
              "trained_on": _pr([i for i in ids if truth[i] not in hold], st, sp),
              "held_out_hotels": len(hold), "hotels": len(base), "listings": len(ids), "clusters": len(set(cl.values()))}

    hn = []
    by_hotel: dict = {}
    for lid, h in truth.items():
        by_hotel.setdefault(h, []).append(lid)
    for p in _rows("hard_negatives"):
        merged = any(cl[a] == cl[b] for a in by_hotel.get(p["a"], []) for b in by_hotel.get(p["b"], []))
        hn.append({"pair": f"{base[p['a']]['name']} vs {base[p['b']]['name']}", "distance_m": p["distance_m"], "merged": merged,
                   "held_out": p["a"] in hold or p["b"] in hold})
    hard = {"pairs": len(hn), "wrongly_merged": sum(x["merged"] for x in hn),
            "held_out_pairs": sum(x["held_out"] for x in hn), "held_out_wrongly_merged": sum(x["merged"] and x["held_out"] for x in hn),
            "examples": [x for x in hn if x["merged"]][:10]}

    rt = {r["supplier_room_id"]: r["room_id"] for r in _rows("room_truth")}
    rm = {r["supplier_room_id"]: r for r in _rows("room_map")}
    sr = _rows("supplier_rooms")
    rooms_by: dict = {}
    for r in sr:
        rooms_by.setdefault(truth[r["listing_id"]], []).append(r["supplier_room_id"])

    def room_pr(hset):
        tp = fp = fn = 0
        for h, rs in rooms_by.items():
            if h not in hset:
                continue
            for a, b in itertools.combinations(rs, 2):
                t, p = rt[a] == rt[b], rm[a]["room_id"] == rm[b]["room_id"]
                tp += t and p; fp += p and not t; fn += t and not p
        return {"precision": round(tp / (tp + fp), 4) if tp + fp else None, "recall": round(tp / (tp + fn), 4) if tp + fn else None,
                "true_pairs": tp + fn, "false_merges": fp, "missed": fn}
    rooms = {"all": room_pr(set(rooms_by)), "held_out": room_pr(hold), "supplier_rooms": len(sr),
             "low_confidence_share": round(sum(r["confidence"] < 0.8 for r in rm.values()) / len(rm), 4)}

    at = {t["listing_id"]: t for t in _rows("activity_truth")}
    am = {r["listing_id"]: r for r in _rows("activity_map")}
    aids = sorted(am)
    sa = lambda a, b: at[a]["variant_id"] == at[b]["variant_id"]  # noqa: E731
    pa = lambda a, b: am[a]["group_id"] == am[b]["group_id"]      # noqa: E731
    acts = {"all": _pr(aids, sa, pa), "listings": len(aids), "true_variants": len({t["variant_id"] for t in at.values()}),
            "predicted_variants": len({r["group_id"] for r in am.values()}), "ambiguous_to_review": sum(r["ambiguous"] for r in am.values()),
            "attraction_accuracy": round(sum(am[a]["attraction_id"] == at[a]["attraction_id"] for a in aids) / len(aids), 4)}

    m = json.loads((config.BUILD / "matcher.json").read_text(encoding="utf-8"))
    d = m["decisions"]
    pairs = pl.read_parquet(config.BUILD / "hotel_pairs.parquet")
    review_items = len({frozenset((cl[a], cl[b])) for a, b, dec in zip(pairs["a"], pairs["b"], pairs["decision"])
                        if dec in ("gray", "blocked") and cl[a] != cl[b]})
    cand = {frozenset(x) for x in zip(pairs["a"], pairs["b"])}
    true_pairs = [(a, b) for ls in by_hotel.values() for a, b in itertools.combinations(ls, 2)]
    never_compared = sum(frozenset(p) not in cand for p in true_pairs)
    above = d["auto"] + d["gray"] + d["blocked"] + d["human_same"] + d["human_different"]
    routing = {"candidate_pairs": m["candidate_pairs"], "above_gray_low": above, "auto_merged": d["auto"],
               "to_review": d["gray"] + d["blocked"], "review_share": round((d["gray"] + d["blocked"]) / above, 4) if above else 0,
               "review_items": review_items, "never_compared": never_compared, "true_pairs": len(true_pairs),
               "llm_share": 0.0 if not config.LLM_ENABLED else None,
               "human_share": round((d["gray"] + d["blocked"]) / above, 4) if above and not config.LLM_ENABLED else None,
               "llm_mode": "on" if config.LLM_ENABLED else "off (every uncertain pair goes to the human queue)",
               "thresholds": {"auto_merge": m["auto_merge"], "gray_low": m["gray_low"],
                              "from_validation": {"auto_merge": m["auto_merge_from_validation"], "gray_low": m["gray_low_from_validation"]}},
               "validation": {"precision_at_auto": m["val_precision_at_auto"], "recall_at_auto": m["val_recall_at_auto"],
                              "n_val": m["n_val"], "scoring": m.get("scoring", "")}}
    return {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "hotels": hotels, "hard_negatives": hard, "rooms": rooms,
            "activities": acts, "routing": routing, "blind": blind_metrics(cl, rm, am), "promise": promise_metrics(), "remix": remix_metrics(), "naming": naming_metrics(hold), "matcher": {k: m[k] for k in (
                "n_train", "train_pos", "excluded_holdout", "embeddings", "importance", "seconds")}}


def blind_metrics(cl, rm, am) -> dict:
    pairs = blind.ensure()
    human = blind.human_labels()
    out, disagreements, stale = {}, [], 0
    title = {**{l["listing_id"]: l["name"] for l in _rows("hotel_listings")},
             **{r["supplier_room_id"]: r["raw_name"] for r in _rows("supplier_rooms")},
             **{l["listing_id"]: l["title"] for l in _rows("activity_listings")}}
    for et in ("hotel", "room", "activity"):
        rows = []
        for p in (x for x in pairs if x["entity_type"] == et):
            a, b = p["left"]["id"], p["right"]["id"]
            if title.get(a) != p["left"]["title"] or title.get(b) != p["right"]["title"]:
                stale += 1; continue                         # the build changed under this pair: its labels no longer apply
            if et == "hotel":
                if a not in cl or b not in cl:
                    stale += 1; continue
                pred = "SAME" if cl[a] == cl[b] else "DIFFERENT"
            elif et == "room":
                if a not in rm or b not in rm:
                    stale += 1; continue
                pred = "SAME" if rm[a]["room_id"] == rm[b]["room_id"] else "VARIANT" if rm[a]["tier"] == rm[b]["tier"] else "DIFFERENT"
            else:
                if a not in am or b not in am:
                    stale += 1; continue
                pred = "SAME" if am[a]["group_id"] == am[b]["group_id"] else "VARIANT" if am[a]["attraction_id"] == am[b]["attraction_id"] else "DIFFERENT"
            h = {"S": "SAME", "V": "VARIANT", "D": "DIFFERENT"}.get(human.get(p["pair_id"], ""), None)
            rows.append((p, pred, h))
            if h and h != p["generator_label"]:
                disagreements.append({"pair_id": p["pair_id"], "entity_type": et, "generator": p["generator_label"], "human": h,
                                      "left": p["left"]["title"], "right": p["right"]["title"]})

        def score(label_of):
            lab = [(pred, label_of(p, h)) for p, pred, h in rows if label_of(p, h)]
            tp = sum(pr == "SAME" and t == "SAME" for pr, t in lab)
            fp = sum(pr == "SAME" and t != "SAME" for pr, t in lab)
            fn = sum(pr != "SAME" and t == "SAME" for pr, t in lab)
            return {"n": len(lab), "precision": round(tp / (tp + fp), 4) if tp + fp else None,
                    "recall": round(tp / (tp + fn), 4) if tp + fn else None,
                    "accuracy": round(sum(pr == t for pr, t in lab) / len(lab), 4) if lab else None}
        out[et] = {"pairs": len(rows), "vs_generator": score(lambda p, h: p["generator_label"]),
                   "human_labelled": sum(1 for _, _, h in rows if h), "vs_human": score(lambda p, h: h)}
    return {"pairs": len(pairs), "stale": stale, "by_type": out, "disagreements": disagreements,
            "human_labelled": len(human)}


def naming_metrics(hold: set) -> dict:
    """Short-code listings, room names that carry the hotel's name, and Weaver's sample sheet (data/naming.py)."""
    truth = {t["listing_id"]: t for t in _rows("hotel_truth")}
    cl = dict(pl.read_parquet(config.BUILD / "hotel_clusters.parquet").iter_rows())
    short = {l for l, t in truth.items() if "short_code_name" in t["corruptions"]}

    def pairs(ids):
        tp = fp = fn = 0
        for a in ids:
            for b in truth:
                if a == b or (b in ids and b < a):
                    continue
                t, p = truth[a]["hotel_id"] == truth[b]["hotel_id"], cl[a] == cl[b]
                tp += t and p; fp += p and not t; fn += t and not p
        return {"listings": len(ids), "precision": round(tp / (tp + fp), 4) if tp + fp else None,
                "recall": round(tp / (tp + fn), 4) if tp + fn else None, "false_merges": fp, "missed": fn,
                "alone": sum(all(cl[a] != cl[b] for b in truth if b != a and truth[b]["hotel_id"] == truth[a]["hotel_id"]) for a in ids)}
    rt = {r["supplier_room_id"]: r for r in _rows("room_truth")}
    rm = {r["supplier_room_id"]: r for r in _rows("room_map")}
    by: dict = {}
    for r in _rows("supplier_rooms"):
        by.setdefault(truth[r["listing_id"]]["hotel_id"], []).append(r["supplier_room_id"])
    prefixed = {k for k, r in rt.items() if "hotel_in_room_name" in r["corruptions"]}
    tp = fp = fn = 0
    for rs in by.values():
        for a, b in itertools.combinations(rs, 2):
            if a in prefixed or b in prefixed:
                t, p = rt[a]["room_id"] == rt[b]["room_id"], rm[a]["room_id"] == rm[b]["room_id"]
                tp += t and p; fp += p and not t; fn += t and not p
    only = [k for k, r in rt.items() if "room_names_only_hotel" in r["corruptions"]]
    from samesame.ingest import sheet
    w = sheet.ingest_sample()
    return {"short_code": {"all": pairs(short), "held_out": pairs({l for l in short if truth[l]["hotel_id"] in hold})},
            "rooms_with_hotel_name": {"rooms": len(prefixed), "precision": round(tp / (tp + fp), 4) if tp + fp else None,
                                      "recall": round(tp / (tp + fn), 4) if tp + fn else None, "false_merges": fp, "missed": fn},
            "rooms_only_hotel": {"rooms": len(only), "to_person": sum("unmapped" in rm[k]["room_id"] for k in only)},
            "weaver": {"summary": w["summary"], "check": w["check"]}}


def _render_naming(n: dict) -> list[str]:
    sc, ra, ro, w = n["short_code"], n["rooms_with_hotel_name"], n["rooms_only_hotel"], n["weaver"]
    ws, ck = w["summary"], w["check"]
    return [
        "", "## Supplier naming: short codes and rate sheets (data/naming.py, synthetic)", "",
        "Suppliers write one hotel as \"Hilton Garden Inn Dubai Deira\" and \"HGI Dubai Deira\", and rooms as \"HP SUP KG CV\" or just \"Hyatt Place Room\". "
        "The short-code listings are extra rows with no photos; the frozen held-out set predates them and does not contain them.", "",
        "| Slice | Items | Precision | Recall | False merges | Missed pairs | Left on their own |", "|---|---|---|---|---|---|---|",
        *[f"| short-code listings, {k.replace('_', ' ')} | {sc[k]['listings']} | {_f(sc[k]['precision'])} | {_f(sc[k]['recall'])} | {sc[k]['false_merges']} | {sc[k]['missed']} | {sc[k]['alone']} |"
          for k in ("all", "held_out")],
        f"| room names carrying the hotel's name | {ra['rooms']} | {_f(ra['precision'])} | {_f(ra['recall'])} | {ra['false_merges']} | {ra['missed']} | — |",
        "",
        f"- Room names that are only the hotel (\"Hyatt Place Room\"): {ro['rooms']}; {ro['to_person']} sent to a person as unmapped, never pooled with another room.",
        f"- **Weaver's sample sheet** (a fictional 7th supplier, not in the catalogue): {ws['rows']} rows → {ws['names']} hotel names → {ws['hotels']} hotels. "
        f"{ws['matched']} matched automatically, {ws['new']} new to TBO, {ws['review']} to a person, {ws['listed_twice']} listed twice under two names. "
        f"Rooms: {ws['room_names']} names → {ws['rooms_mapped']} mapped, {ws['rooms_person']} to a person, {ws['rooms_new']} new.",
        f"- Against Weaver's answer key: hotels {ck['hotels']['matched_right']}/{ck['hotels']['matched_right'] + ck['hotels']['matched_wrong']} automatic matches right, "
        f"{ck['hotels']['new_right']}/{ck['hotels']['new_right'] + ck['hotels']['new_wrong']} new-hotel calls right; rooms "
        f"{ck['rooms']['mapped_right']}/{ck['rooms']['mapped_right'] + ck['rooms']['mapped_wrong']} automatic mappings right. "
        "We wrote the generator, the matcher and this sheet, so treat these as an upper bound." if ck else "- Weaver's answer key not available.",
    ]


def _f(x):
    return "—" if x is None else f"{x:.3f}"


PROMISE_TEST_DAYS = 30
PROMISE_SUBSAMPLES = (1.0, 0.1, 0.02)


def promise_metrics() -> dict:
    """Time split: fit the Promise model on everything before the last 30 days of the log, score the last 30.
    Also refit on thin random slices of the training window, which is where shrinkage should earn its keep.
    Baselines: each cell's own counts (+0.5 smoothing, what the Wilson estimate used) and one market-wide rate per product."""
    log = pl.read_parquet(config.BUILD / "booking_log.parquet")
    cut = log["ts"].max() - timedelta(days=PROMISE_TEST_DAYS)
    train, test = log.filter(pl.col("ts") <= cut), log.filter(pl.col("ts") > cut)
    keys = list(zip(test["supplier_id"], test["product_type"], test["lead_bucket"]))
    y = [pm.OUTCOMES.index(o) for o in test["outcome"]]

    def loss(prob):
        return round(float(np.mean([-math.log(prob(k)[t]) for k, t in zip(keys, y)])), 4)

    rows = []
    for frac in PROMISE_SUBSAMPLES:
        t = train if frac == 1.0 else train.sample(fraction=frac, seed=config.SEED)
        fitted = pm.predict(pm.fit(t)[0])
        cell = pm._counts(t, ["supplier_id", "product_type", "lead_bucket"])
        glob = pm._counts(t, ["product_type"])
        rows.append({"train_share": frac, "train_attempts": t.height,
                     "model": loss(lambda k: fitted[k]),
                     "cell_counts": loss(lambda k: pm._norm(cell.get(k, np.zeros(4)) + 0.5)),
                     "market_rate": loss(lambda k: pm._norm(glob[(k[1],)] + 0.5))})
    fitted_rows = pm.fit(train)[0]
    calib = []
    for s in sorted(test["supplier_id"].unique()):
        mine = test.filter((pl.col("supplier_id") == s) & (pl.col("product_type") == "hotel"))
        pred = {(r["lead_bucket"]): pm.summarise(r)["honour_rate"] for r in fitted_rows if r["supplier_id"] == s and r["product_type"] == "hotel"}
        calib.append({"supplier_id": s, "attempts": mine.height,
                      "predicted_honour": round(float(np.mean([pred[b] for b in mine["lead_bucket"]])), 4),
                      "observed_honour": round(mine.filter(pl.col("outcome") == "confirmed").height / mine.height, 4)})
    info = json.loads((config.BUILD / "promise.json").read_text(encoding="utf-8"))
    return {"test_days": PROMISE_TEST_DAYS, "test_attempts": test.height, "log_loss": rows, "hotel_calibration": calib,
            "fit": {p: {k: v[k] for k in ("k_supplier", "k_cell", "k_cell_at_grid_edge")} for p, v in info["products"].items()}}


def remix_metrics() -> dict:
    """Remix, recomputed from the engines on every build (no number typed in)."""
    from samesame import city
    from samesame.remix import book as rb
    from samesame.remix import engine as E
    from samesame.remix import gaps, trip
    from samesame.remix import service as rs

    def counts(results):
        multi = [r for r in results if r["status"] != "single_part" and not (r["status"] == "not_remixable" and "review" in r["reasons"][0])]
        return {"multi_part": len(multi), "remix_exists": sum(bool(r.get("parts")) for r in multi),
                "cheaper": sum((r.get("gap") or 0) > 0 for r in multi), "ready": sum(r["status"] == "ready" for r in multi),
                "package_wins": sum(r.get("gap") is not None and r["gap"] <= 0 for r in multi)}, multi

    base, multi = counts(rs.all_results(E.Settings()))
    ready = [r for r in multi if r["status"] == "ready"]
    built = [r for r in multi if r.get("parts")]
    sandbox = []
    for r in ready:
        st = rb.stats(r, 1000)
        secured = 1 - (st["remix"]["compensated"] + st["remix"]["failed"]) / st["runs"]
        sandbox.append({"variant_id": r["variant_id"], "name": f"{r['attraction'].split(':')[0]} · {r['name']}", "estimated_promise": r["promise"],
                        "sandbox_secured": round(secured, 4), **{f"remix_{k}": v for k, v in st["remix"].items()},
                        **{f"package_{k}": v for k, v in st["package"].items()}})
    no_build: dict = {}
    for r in multi:
        if not r.get("parts"):
            no_build[r["reasons"][0]] = no_build.get(r["reasons"][0], 0) + 1
    pess, _ = counts(rs.all_results(E.PESSIMISTIC))
    pess_ready = [r["variant_id"] for r in rs.all_results(E.PESSIMISTIC) if r["status"] == "ready"]
    zones = {z: counts(rs.all_results(E.with_zone(E.Settings(), z)))[0] for z, *_ in city.ZONES}
    g = gaps.find(E.Settings())
    t = trip.build(E.Settings())
    sv = [r["agent_saving"] for r in ready]
    mg = [r["margin"] for r in ready]
    pr = sorted(r["promise"] for r in built)
    return {"counts": base, "ready": [{"variant_id": r["variant_id"], "name": f"{r['attraction'].split(':')[0]} · {r['name']}", "saving": r["agent_saving"],
                                      "saving_inr": r["agent_saving_inr"], "margin": r["margin"], "margin_inr": r["margin_inr"], "promise": r["promise"],
                                      "suppliers": r["suppliers"]} for r in ready],
            "saving": {"avg": round(sum(sv) / len(sv), 4) if sv else None, "min": min(sv, default=None), "max": max(sv, default=None)},
            "margin": {"avg": round(sum(mg) / len(mg), 4) if mg else None, "min": min(mg, default=None), "max": max(mg, default=None)},
            "promise": {"min": pr[0] if pr else None, "median": pr[len(pr) // 2] if pr else None, "max": pr[-1] if pr else None, "n": len(pr)},
            "sandbox": sandbox,
            "package_wins": [{"name": f"{r['attraction'].split(':')[0]} · {r['name']}", "by": round(-r["gap"], 0), "reasons": r["reasons"]}
                             for r in multi if r.get("gap") is not None and r["gap"] <= 0],
            "blocked_cheaper": [{"name": f"{r['attraction'].split(':')[0]} · {r['name']}", "reasons": r["reasons"]}
                                for r in multi if r["status"] == "blocked" and (r.get("gap") or 0) > 0],
            "no_assembly": no_build, "pessimistic": {**pess, "ready_ids": pess_ready}, "zones": zones,
            "gaps": {"searched": len(g), "ready": sum(r["status"] == "ready" for r in g), "blocked": sum(r["status"] == "blocked" for r in g),
                     "top": [{"name": f"{r['attraction'].split(':')[0]} · {r['name']}", "demand": r["demand"], "saving": r["agent_saving"], "margin": r["margin"]}
                             for r in g if r["status"] == "ready"][:6]},
            "trip": {"status": t["status"], "reasons": t["reasons"], "saving": t.get("agent_saving"), "margin": t.get("margin"), "promise": t.get("promise")},
            "settings": {k: v for k, v in E.Settings().__dict__.items()}}


def render(r: dict) -> str:
    h, rm, a, rt, b, hn, pr = r["hotels"], r["rooms"], r["activities"], r["routing"], r["blind"], r["hard_negatives"], r["promise"]
    lines = [
        "# METRICS",
        "",
        "_Generated by `python -m samesame.eval.report` on every build. Do not edit by hand. (Build time is in data/build/metrics.json.)_",
        "",
        "## Held-out evaluation set (frozen in `data/blind/`, sampled only from held-out families)",
        "",
        f"{b['pairs']} pairs; {b['human_labelled']} labelled by a human so far; {b['stale']} stale (listing gone or changed since it was frozen).",
        "",
        "We call this set **held-out**, not blind: the model never trained on these families, but we saw these aggregate "
        "numbers while still changing the generator and matcher (during M3 and again during the M3 review fixes), and resampled "
        "the set seven times as listing ids changed, the last time before anyone labelled it. We never inspected individual pairs. "
        "Matcher rules added in the review (chain phones, shared photos, established-cluster names and sites) were driven by "
        "whole-catalogue errors, held-out families included. The independent check is C's hand labels (the right-hand columns).",
        "",
        "| Entity | Pairs | Precision (SAME) vs generator | Recall vs generator | Human-labelled | Precision vs human | Recall vs human |",
        "|---|---|---|---|---|---|---|",
    ]
    for et, x in b["by_type"].items():
        g, hu = x["vs_generator"], x["vs_human"]
        lines.append(f"| {et} | {x['pairs']} | {_f(g['precision'])} | {_f(g['recall'])} | {x['human_labelled']} | {_f(hu['precision'])} | {_f(hu['recall'])} |")
    if b["disagreements"]:
        lines += ["", "Human vs generator disagreements (definition ambiguities, reported not hidden):", ""]
        lines += [f"- `{d['pair_id']}` {d['entity_type']}: generator {d['generator']}, human {d['human']}: {d['left']} / {d['right']}" for d in b["disagreements"]]
    lines += [
        "",
        "## Whole catalogue vs generator truth (pairwise)",
        "",
        "| Entity | Slice | Precision | Recall | True pairs | False merges | Missed |",
        "|---|---|---|---|---|---|---|",
        *[f"| hotel | {k.replace('_', ' ')} | {_f(h[k]['precision'])} | {_f(h[k]['recall'])} | {h[k]['true_pairs']} | {h[k]['false_merges']} | {h[k]['missed']} |"
          for k in ("all", "held_out", "trained_on")],
        *[f"| room | {k.replace('_', ' ')} | {_f(rm[k]['precision'])} | {_f(rm[k]['recall'])} | {rm[k]['true_pairs']} | {rm[k]['false_merges']} | {rm[k]['missed']} |"
          for k in ("all", "held_out")],
        f"| activity | all | {_f(a['all']['precision'])} | {_f(a['all']['recall'])} | {a['all']['true_pairs']} | {a['all']['false_merges']} | {a['all']['missed']} |",
        "",
        f"- Hotels: {h['listings']} listings → {h['clusters']} clusters (truth: {h['hotels']} hotels; {h['held_out_hotels']} in held-out families).",
        f"- Hard negatives (real same-brand hotels < 3 km apart): {hn['wrongly_merged']} of {hn['pairs']} wrongly merged. Only {hn['held_out_pairs']} of those pairs are "
        f"held out ({hn['held_out_wrongly_merged']} merged); the other {hn['pairs'] - hn['held_out_pairs']} were scored out-of-fold, so the model never saw their labels.",
        f"- Rooms: {rm['supplier_rooms']} supplier room names; {rm['low_confidence_share']:.1%} mapped with confidence under 0.8.",
        f"- Sightseeing: {a['listings']} listings → {a['predicted_variants']} variants (truth {a['true_variants']}); attraction assignment {a['attraction_accuracy']:.1%}; "
        f"{a['ambiguous_to_review']} listing(s) kept apart for review because they don't say which option they sell.",
        "",
        "## Routing",
        "",
        f"- Candidate hotel pairs after blocking: {rt['candidate_pairs']:,}; {rt['above_gray_low']:,} scored above the gray-zone floor.",
        f"- Auto-merged: {rt['auto_merged']:,} pairs. {rt['to_review']:,} pairs ({rt['review_share']:.1%}) fell in the gray zone or were blocked; "
        f"after grouping they become **{rt['review_items']} review items** (one per pair of clusters, skipping pairs joined through stronger links).",
        f"- Never compared: {rt['never_compared']} of {rt['true_pairs']:,} true twin pairs were dropped by blocking before scoring (counted as missed above).",
        f"- LLM: {rt['llm_mode']}. Share to LLM: {_f(rt['llm_share']) if rt['llm_share'] is not None else 'n/a'}; to humans: {_f(rt['human_share']) if rt['human_share'] is not None else 'n/a'}.",
        f"- Scores are {rt['validation']['scoring']}: every hotel's pairs were scored by a model that never saw that hotel's labels.",
        f"- Thresholds: auto-merge p ≥ {rt['thresholds']['auto_merge']}, review p ≥ {rt['thresholds']['gray_low']}. The out-of-fold scores of trainable "
        f"families (never held-out data) alone would have chosen {rt['thresholds']['from_validation']['auto_merge']} and {rt['thresholds']['from_validation']['gray_low']}; "
        f"the policy floors (auto ≥ 0.90, review from 0.30) win when stricter. Validation precision at auto-merge {_f(rt['validation']['precision_at_auto'])}, recall {_f(rt['validation']['recall_at_auto'])} (n = {rt['validation']['n_val']:,} out-of-fold pairs).",
        "",
        "## Promise model (booking reliability)",
        "",
        f"Fitted on the booking log up to {pr['test_days']} days before its end, scored on the last {pr['test_days']} days ({pr['test_attempts']:,} attempts). "
        "Log loss per attempt over the four outcomes (confirmed / price changed / sold out / error); lower is better.",
        "",
        "| Training data | Attempts | Fitted model | Each cell's own counts | One market rate |",
        "|---|---|---|---|---|",
        *[f"| {x['train_share']:.0%} of window | {x['train_attempts']:,} | **{x['model']}** | {x['cell_counts']} | {x['market_rate']} |" for x in pr["log_loss"]],
        "",
        "Hotel honour rate, predicted for the test window's own mix of lead times vs what happened:",
        "",
        "| Supplier | Test attempts | Predicted | Observed |",
        "|---|---|---|---|",
        *[f"| {x['supplier_id']} | {x['attempts']:,} | {x['predicted_honour']:.1%} | {x['observed_honour']:.1%} |" for x in pr["hotel_calibration"]],
        "",
        "- Fitted concentrations (empirical Bayes): " + "; ".join(f"{p}: supplier prior {v['k_supplier']:g}, cell prior "
                                                     + (f"at the search grid's edge ({v['k_cell']:,.0f})" if v["k_cell_at_grid_edge"] else f"{v['k_cell']:g}")
                                                     for p, v in pr["fit"].items())
        + ". A large cell prior means lead-time effects look the same for every supplier, so cells borrow heavily from their supplier "
        "(capped at the bookings that prior was estimated from).",
        "- The log comes from our own behaviour model, so this checks that the estimator recovers it from noisy, time-ordered data, "
        "not that real suppliers behave this way.",
        "",
        *_render_remix(r["remix"]),
        *_render_naming(r["naming"]),
        "",
        "## Caveats (read before quoting any number above)",
        "",
        "- **We wrote both the generator and the matcher.** Feature design, the room parser and the Variant DNA rules were written knowing how the "
        "generator corrupts names, so even held-out numbers are an upper bound on real-world performance.",
        "- **Room and sightseeing rules were fixed while looking at errors across the whole catalogue**, held-out attractions included. "
        "Their numbers are not blind; only C's human labels on the held-out pairs are an independent check.",
        "- The hotel model never trained or chose thresholds on held-out families, and held-out listings carry a corruption family "
        "(alternative transliterations, e.g. Jumeira, Dayra, Dubayy) that never appears in training.",
        "- **Short codes were designed knowing the generator's rule** (initials of the leading words). The matcher's reading of them is general "
        "(any 2-4 letter word that spells the initials of words in the other name), but the brand rule was changed to read written-out names "
        "after we saw it blocking short-code listings across the whole catalogue, held-out families included.",
    ]
    return "\n".join(lines) + "\n"


def main():
    r = compute()
    (config.BUILD / "metrics.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    (config.ROOT / "METRICS.md").write_text(render(r), encoding="utf-8")
    b = r["blind"]["by_type"]
    print("eval:", json.dumps({k: (v["vs_generator"]["precision"], v["vs_generator"]["recall"]) for k, v in b.items()}),
          "hotels all", (r["hotels"]["all"]["precision"], r["hotels"]["all"]["recall"]))


def _render_remix(x: dict) -> list[str]:
    c, st = x["counts"], x["settings"]
    pct = lambda v: "—" if v is None else f"{v:.1%}"  # noqa: E731
    out = ["## Remix (sightseeing, client in Deira, 2 adults, 21 days out)", "",
           f"Guardrails: agent saves ≥ {st['min_saving']:.0%}, TBO margin ≥ {st['min_margin']:.0%}, Remix Promise ≥ {st['min_promise']:.0%}, "
           f"arrive ≥ {st['buffer_min']} min before the slot; the agent gets {st['agent_share']:.0%} of the gap. Reproduce: `python -m samesame.pipeline` "
           "(or `python -m samesame.eval.report` on an existing build). Parts and their prices are synthetic (DATA.md).", "",
           "| Multi-part packages | SAME Remix exists | Cheaper on True Price | Passes every guardrail | Package cheaper |", "|---|---|---|---|---|",
           f"| {c['multi_part']} | {c['remix_exists']} ({c['remix_exists'] / c['multi_part']:.0%}) | {c['cheaper']} | **{c['ready']} ({c['ready'] / c['multi_part']:.0%})** | {c['package_wins']} |", "",
           "| Publishable Remix | Agent saves | TBO margin | Remix Promise (est.) | Secured in sandbox, seeds 1–1,000 | Suppliers |", "|---|---|---|---|---|---|"]
    sb = {s["variant_id"]: s for s in x["sandbox"]}
    for r in x["ready"]:
        out.append(f"| {r['name']} | ₹{r['saving_inr']:,.0f} ({r['saving']:.1%}) | ₹{r['margin_inr']:,.0f} ({r['margin']:.1%}) | {r['promise']:.1%} | "
                   f"{sb[r['variant_id']]['sandbox_secured']:.1%} | {', '.join(r['suppliers'])} |")
    out += ["", f"- Saving to the agent: avg {pct(x['saving']['avg'])}, range {pct(x['saving']['min'])}–{pct(x['saving']['max'])}. "
            f"TBO margin: avg {pct(x['margin']['avg'])}, range {pct(x['margin']['min'])}–{pct(x['margin']['max'])}.",
            f"- Remix Promise across all {x['promise']['n']} buildable Remixes: min {pct(x['promise']['min'])}, median {pct(x['promise']['median'])}, max {pct(x['promise']['max'])}.",
            "- **Estimated vs sandbox:** the sandbox secures fewer Remixes than the estimated Remix Promise (see the table). The estimate uses "
            "each supplier's fitted Promise and assumes parts fail independently; the sandbox draws from the world, where each attraction has "
            "its own demand volatility. We have not separated how much of the gap each explains, so read the Remix Promise as optimistic by "
            "about that much.", "",
            "Sandbox outcomes over seeds 1–1,000 (same draws), Remix vs its best package:", "",
            "| Product | Arm | Clean | Paid a rise | Part / offer failover | Unwound, package bought | Failed |", "|---|---|---|---|---|---|---|"]
    for s in x["sandbox"]:
        out.append(f"| {s['name']} | Remix | {s['remix_clean'] / 10:.1f}% | {s['remix_paid_rise'] / 10:.1f}% | {s['remix_failover'] / 10:.1f}% | {s['remix_compensated'] / 10:.1f}% | {s['remix_failed'] / 10:.1f}% |")
        out.append(f"| | Package | {s['package_clean'] / 10:.1f}% | {s['package_paid_rise'] / 10:.1f}% | {s['package_failover'] / 10:.1f}% | — | {s['package_failed'] / 10:.1f}% |")
    out += ["", "**Where the package beats the Remix** (a strength to show: Remix never pretends):", ""]
    out += [f"- {p['name']}: package cheaper by ₹{p['by']:,.0f} on True Price" for p in x["package_wins"]]
    out += ["", "**Cheaper, but blocked by a guardrail:**", ""] + [f"- {b['name']}: {'; '.join(b['reasons'])}" for b in x["blocked_cheaper"]]
    out += ["", "**No valid assembly (first reason):** " + "; ".join(f"{k} ({v})" for k, v in sorted(x["no_assembly"].items(), key=lambda kv: -kv[1])), "",
            f"**Pessimistic preset** (transfers +30%, part failures ×1.5): {x['pessimistic']['ready']} of {x['pessimistic']['multi_part']} pass "
            f"({', '.join(x['pessimistic']['ready_ids']) or 'none'}).", "",
            "**By client zone** (passes every guardrail): " + ", ".join(f"{z} {v['ready']}" for z, v in x["zones"].items()) + ".", "",
            f"**Gap Remixes** (agents search for it, nobody sells it): {x['gaps']['searched']} searched-for gaps (≥ 10 searches in 90 days), "
            f"{x['gaps']['ready']} pass every guardrail against booking the pieces separately, {x['gaps']['blocked']} blocked. Most searched:", ""]
    out += [f"- {g['name']}: {g['demand']} searches, agent saves {g['saving']:.1%}, TBO margin {g['margin']:.1%}" for g in x["gaps"]["top"]]
    t = x["trip"]
    out += ["", f"**Connected Trip** (golden-case hotel + DXB cars + best tour Remix): {t['status']}; "
            f"agent saves {pct(t['saving'])}, TBO margin {pct(t['margin'])}, Trip Promise {pct(t['promise'])}. {'; '.join(t['reasons'])}.", ""]
    return out


if __name__ == "__main__":
    main()
