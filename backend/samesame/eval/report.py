"""Evaluation report, rebuilt on every pipeline run so no number on screen or in METRICS.md is typed by hand.

    python -m samesame.eval.report

Reads the matcher's outputs, generator truth and the frozen blind set; writes data/build/metrics.json
and METRICS.md. Never imports the trainer, never writes anything training reads.
"""
import itertools
import json
import time

import polars as pl

from samesame import config
from samesame.eval import blind


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
    above = d["auto"] + d["gray"] + d["blocked"] + d["human_same"] + d["human_different"]
    routing = {"candidate_pairs": m["candidate_pairs"], "above_gray_low": above, "auto_merged": d["auto"],
               "to_review": d["gray"] + d["blocked"], "review_share": round((d["gray"] + d["blocked"]) / above, 4) if above else 0,
               "llm_share": 0.0 if not config.LLM_ENABLED else None,
               "human_share": round((d["gray"] + d["blocked"]) / above, 4) if above and not config.LLM_ENABLED else None,
               "llm_mode": "on" if config.LLM_ENABLED else "off (every uncertain pair goes to the human queue)",
               "thresholds": {"auto_merge": m["auto_merge"], "gray_low": m["gray_low"],
                              "from_validation": {"auto_merge": m["auto_merge_from_validation"], "gray_low": m["gray_low_from_validation"]}},
               "validation": {"precision_at_auto": m["val_precision_at_auto"], "recall_at_auto": m["val_recall_at_auto"],
                              "n_val": m["n_val"]}}
    return {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "hotels": hotels, "hard_negatives": hard, "rooms": rooms,
            "activities": acts, "routing": routing, "blind": blind_metrics(cl, rm, am), "matcher": {k: m[k] for k in (
                "n_train", "train_pos", "excluded_holdout", "embeddings", "importance", "seconds")}}


def blind_metrics(cl, rm, am) -> dict:
    pairs = blind.ensure()
    human = blind.human_labels()
    out, disagreements, stale = {}, [], 0
    for et in ("hotel", "room", "activity"):
        rows = []
        for p in (x for x in pairs if x["entity_type"] == et):
            a, b = p["left"]["id"], p["right"]["id"]
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


def _f(x):
    return "—" if x is None else f"{x:.3f}"


def render(r: dict) -> str:
    h, rm, a, rt, b, hn = r["hotels"], r["rooms"], r["activities"], r["routing"], r["blind"], r["hard_negatives"]
    lines = [
        "# METRICS",
        "",
        "_Generated by `python -m samesame.eval.report` on every build (" + r["generated_at"] + "). Do not edit by hand._",
        "",
        "## Blind set (frozen in `data/blind/`, sampled only from held-out families)",
        "",
        f"{b['pairs']} pairs; {b['human_labelled']} labelled by a human so far; {b['stale']} stale (ids no longer in this build).",
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
        f"- Hard negatives (real same-brand hotels < 3 km apart): {hn['wrongly_merged']} of {hn['pairs']} wrongly merged; held-out: {hn['held_out_wrongly_merged']} of {hn['held_out_pairs']}.",
        f"- Rooms: {rm['supplier_rooms']} supplier room names; {rm['low_confidence_share']:.1%} mapped with confidence under 0.8.",
        f"- Sightseeing: {a['listings']} listings → {a['predicted_variants']} variants (truth {a['true_variants']}); attraction assignment {a['attraction_accuracy']:.1%}; "
        f"{a['ambiguous_to_review']} listing(s) kept apart for review because they don't say which option they sell.",
        "",
        "## Routing",
        "",
        f"- Candidate hotel pairs after blocking: {rt['candidate_pairs']:,}; {rt['above_gray_low']:,} scored above the gray-zone floor.",
        f"- Auto-merged: {rt['auto_merged']:,}. Sent to review: {rt['to_review']:,} ({rt['review_share']:.1%}).",
        f"- LLM: {rt['llm_mode']}. Share to LLM: {_f(rt['llm_share']) if rt['llm_share'] is not None else 'n/a'}; to humans: {_f(rt['human_share']) if rt['human_share'] is not None else 'n/a'}.",
        f"- Thresholds: auto-merge p ≥ {rt['thresholds']['auto_merge']}, review p ≥ {rt['thresholds']['gray_low']}. Validation (a grouped split of trainable "
        f"families, never held-out data) alone would have chosen {rt['thresholds']['from_validation']['auto_merge']} and {rt['thresholds']['from_validation']['gray_low']}; "
        f"the policy floors (auto ≥ 0.90, review from 0.30) win when stricter. Validation precision at auto-merge {_f(rt['validation']['precision_at_auto'])}, recall {_f(rt['validation']['recall_at_auto'])} (n = {rt['validation']['n_val']:,} pairs).",
        "",
        "## Caveats (read before quoting any number above)",
        "",
        "- **We wrote both the generator and the matcher.** Feature design, the room parser and the Variant DNA rules were written knowing how the "
        "generator corrupts names, so even held-out numbers are an upper bound on real-world performance.",
        "- **Room and sightseeing rules were fixed while looking at errors across the whole catalogue**, held-out attractions included. "
        "Their numbers are not blind; only C's human labels on the blind pairs are an independent check.",
        "- The hotel model never trained or chose thresholds on held-out families, and held-out listings carry a corruption family "
        "(Thai-style romanisation) that never appears in training.",
    ]
    return "\n".join(lines) + "\n"


def main():
    r = compute()
    (config.BUILD / "metrics.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    (config.ROOT / "METRICS.md").write_text(render(r), encoding="utf-8")
    b = r["blind"]["by_type"]
    print("eval:", json.dumps({k: (v["vs_generator"]["precision"], v["vs_generator"]["recall"]) for k, v in b.items()}),
          "hotels all", (r["hotels"]["all"]["precision"], r["hotels"]["all"]["recall"]))


if __name__ == "__main__":
    main()
