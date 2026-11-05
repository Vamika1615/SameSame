"""Promise model: how often a supplier honours a booking, per (supplier, product, lead-time bucket).

Each attempt ends in one of four exclusive outcomes. A cell's outcome shares get a Dirichlet prior
(a Beta-binomial for the honour rate alone), built in two levels:

    product, all suppliers      ->  global shares, and how each lead bucket shifts them
    supplier x product          ->  shrunk toward the global shares            (concentration k_supplier)
    supplier x product x bucket ->  shrunk toward the supplier's shares, moved by
                                    the global lead-bucket shift               (concentration k_cell)

Both concentrations are fitted by empirical Bayes (maximum Dirichlet-multinomial marginal likelihood
on the log), not chosen by hand; the supplier-level one is capped at SUPPLIER_KAPPA_MAX. A prior is never worth more bookings than it was estimated from: a cell's
prior weight is capped at k_supplier + the supplier's attempts in the other buckets, so the interval stays
honest even when the data says cells hardly deviate from their supplier. A thin cell leans on its supplier, a thin supplier on the market, so a
new supplier starts near average and earns its rate from bookings. The size of a price rise is shrunk the
same way, with a fixed weight of INCREASE_PRIOR_N pseudo-observations (an assumption, disclosed).

Reads only the booking log. Never the generator's behaviour table.
"""
import math

import numpy as np
import polars as pl
from scipy.special import gammaln
from scipy.stats import beta

OUTCOMES = ["confirmed", "price_changed", "sold_out", "error"]
GRID = np.exp(np.linspace(math.log(1), math.log(100_000), 70))     # candidate concentrations
INCREASE_PRIOR_N = 20
SUPPLIER_KAPPA_MAX = 200   # the market prior is worth at most 200 bookings: a new supplier proves itself (or not) within a few hundred,
                           # and a handful of look-alike suppliers can't make us certain about the next one (assumption, disclosed)


def _counts(log: pl.DataFrame, keys: list[str]) -> dict[tuple, np.ndarray]:
    g = log.group_by(keys + ["outcome"]).len()
    out: dict[tuple, np.ndarray] = {}
    for r in g.iter_rows(named=True):
        k = tuple(r[c] for c in keys)
        out.setdefault(k, np.zeros(len(OUTCOMES)))[OUTCOMES.index(r["outcome"])] += r["len"]
    return out


def _dm_loglik(counts: np.ndarray, alpha: np.ndarray) -> float:
    """Dirichlet-multinomial log marginal likelihood (without the multinomial coefficient, constant in alpha)."""
    a0, n = alpha.sum(), counts.sum()
    return float(gammaln(a0) - gammaln(a0 + n) + (gammaln(alpha + counts) - gammaln(alpha)).sum())


def _fit_kappa(pairs: list[tuple[np.ndarray, np.ndarray]]) -> float:
    """pairs: (counts, prior mean). Picks the concentration that best explains all cells at once."""
    ll = [sum(_dm_loglik(c, k * np.maximum(m, 1e-6)) for c, m in pairs) for k in GRID]
    return float(GRID[int(np.argmax(ll))])


def _norm(x: np.ndarray) -> np.ndarray:
    return x / x.sum()


def fit(log: pl.DataFrame) -> tuple[list[dict], dict]:
    """Returns one row per (supplier, product, bucket) with posterior Dirichlet parameters, plus fit info."""
    rows, info = [], {"model": "hierarchical Dirichlet-multinomial (Beta-binomial on honour)", "attempts": log.height,
                      "increase_prior_n": INCREASE_PRIOR_N, "products": {}}
    suppliers = sorted(log["supplier_id"].unique())
    buckets = sorted(log["lead_bucket"].unique())
    for product in sorted(log["product_type"].unique()):
        lp = log.filter(pl.col("product_type") == product)
        glob = _norm(sum(_counts(lp, []).values()) + 0.5)
        by_bucket = {b: _norm(c + 0.5) for (b,), c in _counts(lp, ["lead_bucket"]).items()}
        shift = {b: by_bucket.get(b, glob) / glob for b in buckets}            # how lead time moves each outcome, market-wide
        sup = _counts(lp, ["supplier_id"])
        k_sup_fit = _fit_kappa([(sup.get((s,), np.zeros(4)), glob) for s in suppliers])
        k_sup = min(k_sup_fit, SUPPLIER_KAPPA_MAX)
        sup_mean = {s: _norm(k_sup * glob + sup.get((s,), np.zeros(4))) for s in suppliers}
        cell = _counts(lp, ["supplier_id", "lead_bucket"])
        prior_mean = {(s, b): _norm(sup_mean[s] * shift[b]) for s in suppliers for b in buckets}
        k_cell = _fit_kappa([(cell.get(k, np.zeros(4)), m) for k, m in prior_mean.items()])

        rep = lp.filter(pl.col("outcome") == "price_changed").with_columns((pl.col("final_price") / pl.col("quoted") - 1).alias("inc"))
        inc_glob = float(rep["inc"].mean()) if rep.height else 0.0
        inc = {r["supplier_id"]: (r["s"], r["n"]) for r in rep.group_by("supplier_id").agg(pl.col("inc").sum().alias("s"), pl.len().alias("n")).iter_rows(named=True)}
        for s in suppliers:
            s_inc, n_inc = inc.get(s, (0.0, 0))
            exp_inc = (s_inc + INCREASE_PRIOR_N * inc_glob) / (n_inc + INCREASE_PRIOR_N)
            for b in buckets:
                c = cell.get((s, b), np.zeros(4))
                k = min(k_cell, k_sup + sup.get((s,), np.zeros(4)).sum() - c.sum())
                alpha = k * prior_mean[(s, b)] + c
                rows.append({"supplier_id": s, "product_type": product, "lead_bucket": b, "n": int(c.sum()),
                             **{f"alpha_{o}": float(a) for o, a in zip(OUTCOMES, alpha)},
                             "prior_weight": round(k / (k + c.sum()), 4), "exp_increase_pct": round(exp_inc, 4)})
        info["products"][product] = {"k_supplier": round(k_sup, 1), "k_supplier_fitted": round(k_sup_fit, 1), "k_cell": round(k_cell, 1), "k_cell_at_grid_edge": bool(k_cell >= GRID[-1]), "global_shares": [round(x, 4) for x in glob],
                                     "lead_shift": {b: [round(x, 3) for x in v] for b, v in shift.items()}, "global_increase": round(inc_glob, 4)}
    return rows, info


def summarise(row: dict) -> dict:
    """Posterior means and a 95% credible interval on the honour rate."""
    a = np.array([row[f"alpha_{o}"] for o in OUTCOMES])
    m = a / a.sum()
    lo, hi = beta.ppf([0.025, 0.975], a[0], a.sum() - a[0])
    return {"honour_rate": float(m[0]), "p_price_change": float(m[1]), "p_sold_out": float(m[2]), "p_error": float(m[3]),
            "ci_low": float(lo), "ci_high": float(hi)}


def predict(rows: list[dict]) -> dict[tuple, np.ndarray]:
    return {(r["supplier_id"], r["product_type"], r["lead_bucket"]): _norm(np.array([r[f"alpha_{o}"] for o in OUTCOMES])) for r in rows}
