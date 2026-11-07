"""What the API serves for Remix: cached engine runs per settings, the demo product, summaries."""
from dataclasses import asdict, replace
from functools import lru_cache

from samesame.remix import book as rb
from samesame.remix import engine as E

SETTING_KEYS = ("zone", "agent_share", "min_saving", "min_margin", "min_promise", "buffer_min")


def settings(preset: str | None = None, **kw) -> E.Settings:
    base = E.PESSIMISTIC if preset == "pessimistic" else E.Settings()
    return replace(base, **{k: v for k, v in kw.items() if v is not None and k in SETTING_KEYS})


@lru_cache(maxsize=64)
def all_results(s: E.Settings) -> list[dict]:
    return E.run_all(s)


def result(variant_id: str, s: E.Settings) -> dict | None:
    return next((r for r in all_results(s) if r["variant_id"] == variant_id), None)


@lru_cache
def demo_variant() -> str:
    """The publishable Remix (default settings) that saves the agent the most rupees: chosen by rule, not by hand."""
    ready = [r for r in all_results(E.Settings()) if r["status"] == "ready"]
    return max(ready, key=lambda r: r["agent_saving_inr"])["variant_id"]


@lru_cache
def demo_seed() -> int:
    return rb.first_seed_with_failover(result(demo_variant(), E.Settings()))


def summary(r: dict) -> dict:
    keep = ("variant_id", "attraction_id", "attraction", "name", "status", "reasons", "target_dna", "unverified", "sticker", "tbo_cost",
            "sell", "agent_saving", "agent_saving_inr", "margin", "margin_inr", "promise", "cancel", "suppliers", "gap")
    out = {k: r.get(k) for k in keep}
    out["packaged_true_price"] = (r.get("packaged") or {}).get("true_price")
    out["agent_true_price"] = r["agent_true_price"].total if r.get("agent_true_price") else None
    out["parts"] = len(r.get("parts") or [])
    return out


def overview(s: E.Settings) -> dict:
    rs = all_results(s)
    multi = [r for r in rs if r["status"] not in ("single_part",) and not (r["status"] == "not_remixable" and "review" in r["reasons"][0])]
    return {"settings": asdict(s), "demo_variant": demo_variant(), "counts": {
                "packaged_products": len(rs), "multi_part": len(multi),
                "remix_exists": sum(1 for r in multi if r.get("parts")),
                "cheaper": sum(1 for r in multi if (r.get("gap") or 0) > 0),
                "ready": sum(1 for r in multi if r["status"] == "ready"),
                "package_wins": sum(1 for r in multi if r.get("gap") is not None and r["gap"] <= 0)},
            "items": [summary(r) for r in multi]}
