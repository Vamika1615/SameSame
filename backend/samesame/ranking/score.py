"""Transparent ranking score: sum of weight x normalised feature. Every term becomes a ScoreTerm
so the UI can show "why ranked here" without any hidden model.

Business guardrails: a supplier below the honour floor cannot take rank 1 on price alone;
weights are fixed constants here (changed only by a person, never learned from clicks)."""
import math

from samesame.schemas import ScoreTerm, WhyChip

HOTEL_WEIGHTS = {"true_price": 0.30, "promise": 0.15, "distance": 0.20, "star_fit": 0.08,
                 "family_fit": 0.10, "popularity": 0.10, "content": 0.07}
ACTIVITY_WEIGHTS = {"true_price": 0.35, "promise": 0.15, "popularity": 0.20, "duration_fit": 0.15, "rating": 0.15}
LABELS = {"true_price": "True Price", "promise": "Supplier promise", "distance": "Distance to area",
          "star_fit": "Star fit", "family_fit": "Family fit", "popularity": "Popular with your market",
          "content": "Content complete", "duration_fit": "Duration fit", "rating": "Rating"}
HONOUR_FLOOR = 0.80
DISTANCE_SCALE_M = 800       # value halves roughly every ~550 m


def haversine_m(lat1, lng1, lat2, lng2):
    p = math.radians
    a = math.sin(p(lat2 - lat1) / 2) ** 2 + math.cos(p(lat1)) * math.cos(p(lat2)) * math.sin(p(lng2 - lng1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def price_value(tp: float, lo: float, hi: float) -> float:
    return 1.0 if hi <= lo else 1 - (tp - lo) / (hi - lo)


def distance_value(m: float) -> float:
    return math.exp(-m / DISTANCE_SCALE_M)


def score(features: dict[str, float], details: dict[str, str], weights: dict[str, float]) -> list[ScoreTerm]:
    return [ScoreTerm(feature=f, label=LABELS[f], value=round(features[f], 3), weight=w,
                      contribution=round(w * features[f], 4), detail=details.get(f, ""))
            for f, w in weights.items()]


def total(terms: list[ScoreTerm]) -> float:
    return sum(t.contribution for t in terms)


def rank(items: list[dict]) -> list[dict]:
    """items: dicts with 'score' (list[ScoreTerm]) and 'honour' (best-offer supplier honour).
    Guardrail: an item under the honour floor is never placed first."""
    ordered = sorted(items, key=lambda it: -total(it["score"]))
    if len(ordered) > 1 and ordered[0]["honour"] < HONOUR_FLOOR:
        j = next((i for i, it in enumerate(ordered) if it["honour"] >= HONOUR_FLOOR), None)
        if j:
            ordered.insert(0, ordered.pop(j))
    for i, it in enumerate(ordered, 1):
        it["rank"] = i
    return ordered


def why_chips(terms: list[ScoreTerm], n: int = 3) -> list[WhyChip]:
    """The strongest contributions, phrased with their raw detail."""
    kind = {"true_price": "price", "promise": "promise", "popularity": "popularity", "content": "content"}
    top = sorted((t for t in terms if t.value >= 0.5), key=lambda t: -t.contribution)[:n]
    return [WhyChip(label=t.detail or t.label, kind=kind.get(t.feature, "relevance")) for t in top]
