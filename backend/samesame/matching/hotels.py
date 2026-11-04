"""Hotel Twin Finder, part 1: normalisation, blocking and pair features.

Reads only what a supplier feed contains (listing fields + listing images). No truth, no base table.
"""
import re
import unicodedata

import numpy as np
from rapidfuzz import fuzz

from samesame import config
from samesame.data.osm_base import family as brand_family
from samesame.ranking.score import haversine_m

BLOCK_RADIUS_M = 2000
ABBR = {"bkk": "bangkok", "htl": "hotel", "resi": "residence", "stes": "suites", "suk": "sukhumvit", "krungthep": "bangkok",
        "sukhumwit": "sukhumvit", "seelom": "silom", "asoke": "asok", "intl": "international", "apt": "apartment",
        "rd": "road", "st": "street", "&": "and"}
STOP = {"hotel", "bangkok", "the", "by", "and", "soi", "a", "an", "at", "of", "road", "sha", "plus", "thailand"}


def norm(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(sha\+?\)", " ", s)
    s = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", s)          # SUKHUMVIT20 -> sukhumvit 20
    toks = re.findall(r"[a-z0-9@&]+", s)
    return " ".join(ABBR.get(t, t) for t in toks)


def core(n: str) -> set[str]:
    return {t for t in n.split() if t not in STOP}


def numbers(n: str) -> set[str]:
    return {t for t in n.split() if t.isdigit() and len(t) <= 3}


def digits(p: str | None) -> str | None:
    return re.sub(r"\D", "", p)[-8:] if p else None


CHAIN_LINE_M = 600   # a number listed at places this far apart is a central reservations line, not the hotel's


def spans_sites(points: list[tuple[float, float]]) -> bool:
    """True if the points form 3+ separate sites (600 m single linkage), or 2 sites with 2+ listings each.
    One misplaced pin of the hotel's own listing makes a lone extra site and is not enough."""
    sites: list[list] = []
    for p in points:
        hit = [s for s in sites if any(haversine_m(*p, *q) <= CHAIN_LINE_M for q in s)]
        merged = [p] + [q for s in hit for q in s]
        sites = [s for s in sites if s not in hit] + [merged]
    return len(sites) >= 3 or sum(len(s) >= 2 for s in sites) >= 2


def prep(listings: list[dict]) -> list[dict]:
    out = []
    for l in listings:
        n = norm(l["name"])
        out.append({**l, "_n": n, "_core": core(n), "_num": numbers(n), "_fam": brand_family(n, None),
                    "_phone": digits(l["phone"]), "_addr": norm(l["address"]), "_amen": set(l["amenities"] or [])})
    # suppliers list a chain's central number for every branch: such a phone says nothing about which building it is
    at: dict = {}
    for p in out:
        if p["_phone"]:
            at.setdefault(p["_phone"], []).append((p["lat"], p["lng"]))
    shared = {ph for ph, pts in at.items() if spans_sites(pts)}
    for p in out:
        p["_chain_phone"] = p["_phone"] in shared
    return out


def block(P: list[dict]) -> list[tuple[int, int]]:
    """Candidate pairs: within 2 km AND (a shared distinctive name token, the same brand family, or within 100 m)."""
    lat = np.array([p["lat"] for p in P]); lng = np.array([p["lng"] for p in P])
    pairs = []
    for i in range(len(P)):
        d = haversine_vec(lat[i], lng[i], lat[i + 1:], lng[i + 1:])
        for k in np.nonzero(d <= BLOCK_RADIUS_M)[0]:
            j = i + 1 + int(k)
            a, b = P[i], P[j]
            if (a["_core"] & b["_core"]) or (a["_fam"] and a["_fam"] == b["_fam"]) or d[k] <= 100:
                pairs.append((i, j))
    return pairs


def haversine_vec(lat1, lng1, lat2, lng2):
    r = 6_371_000
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lng2 - lng1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


FEATURES = ["name_set", "name_sort", "name_partial", "core_jaccard", "num_match", "family_match", "dist_log", "phone_match",
            "star_delta", "addr_sort", "postcode_match", "emb_cos", "img_min_ham", "img_close", "same_supplier", "amen_jaccard",
            "checkin_eq"]


def _tri(a, b):
    """1 equal, -1 both present and different, 0 one side missing."""
    if not a or not b:
        return 0
    return 1 if a == b else -1


def pair_features(a: dict, b: dict, emb_cos: float, img: tuple[float, int]) -> dict:
    na, nb = " ".join(sorted(a["_core"])), " ".join(sorted(b["_core"]))
    u = a["_core"] | b["_core"]
    num = 0 if not (a["_num"] and b["_num"]) else (1 if a["_num"] == b["_num"] else -1)
    fam = 0 if not (a["_fam"] and b["_fam"]) else (1 if a["_fam"] == b["_fam"] else -1)
    am = a["_amen"] | b["_amen"]
    return {
        "name_set": fuzz.token_set_ratio(na, nb) / 100, "name_sort": fuzz.token_sort_ratio(a["_n"], b["_n"]) / 100,
        "name_partial": fuzz.partial_ratio(na, nb) / 100, "core_jaccard": len(a["_core"] & b["_core"]) / len(u) if u else 0.0,
        "num_match": num, "family_match": fam,
        "dist_log": float(np.log1p(haversine_m(a["lat"], a["lng"], b["lat"], b["lng"]))),
        "phone_match": 0 if a["_chain_phone"] or b["_chain_phone"] else _tri(a["_phone"], b["_phone"]),
        "star_delta": abs(a["star"] - b["star"]) if a["star"] is not None and b["star"] is not None else np.nan,
        "addr_sort": fuzz.token_sort_ratio(a["_addr"], b["_addr"]) / 100, "postcode_match": _tri(a["postcode"], b["postcode"]),
        "emb_cos": emb_cos, "img_min_ham": img[0], "img_close": img[1],
        "same_supplier": float(a["supplier_id"] == b["supplier_id"]),
        "amen_jaccard": len(a["_amen"] & b["_amen"]) / len(am) if am else np.nan,
        "checkin_eq": float(a["checkin_time"] == b["checkin_time"]),
    }


def embed(texts: list[str]) -> np.ndarray | None:
    """MiniLM sentence embeddings (normalised). None if the model can't be loaded (feature becomes missing)."""
    try:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(config.EMBED_MODEL, cache_folder=str(config.MODELS), device="cpu")
        return m.encode(texts, normalize_embeddings=True, batch_size=128, show_progress_bar=False)
    except Exception as e:                                   # offline first run: keep going without the feature
        print("matcher: embeddings unavailable, feature left missing:", type(e).__name__, e)
        return None


GENERIC_IMAGE_HAM = 6          # copies of one photo sit within this many bits of each other


def image_hashes(image_rows: list[dict], P: list[dict]) -> dict[str, list]:
    """Perceptual hashes per listing, minus generic images.

    Like a chain's phone number, an image that shows up (near-identically) at several separate sites (spans_sites)
    is a stock / placeholder picture: it says nothing about which building a listing is, so it is dropped here.
    """
    import imagehash
    from PIL import Image
    pos = {p["listing_id"]: (p["lat"], p["lng"]) for p in P}
    rows = [im for im in image_rows if im["owner_kind"] == "listing" and im["owner_id"] in pos]    # hotel listings only
    hs = []
    for im in rows:
        with Image.open(config.BUILD / "images" / im["path"]) as f:
            hs.append(imagehash.phash(f))
    bits = np.array([int(str(h), 16) for h in hs], dtype=np.uint64)
    lat = np.array([pos[im["owner_id"]][0] for im in rows]); lng = np.array([pos[im["owner_id"]][1] for im in rows])
    popcount = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)
    generic = np.zeros(len(rows), dtype=bool)
    for i in range(len(rows)):
        x = (bits ^ bits[i]).view(np.uint8).reshape(-1, 8)
        near = popcount[x].sum(1) <= GENERIC_IMAGE_HAM
        if near.sum() > 2 and spans_sites(list(zip(lat[near], lng[near]))):
            generic[i] = True
    out: dict[str, list] = {}
    for im, h, g in zip(rows, hs, generic):
        if not g:
            out.setdefault(im["owner_id"], []).append(h)
    return out


def img_sim(ha: list, hb: list) -> tuple[float, int]:
    if not ha or not hb:
        return (np.nan, 0)
    d = [x - y for x in ha for y in hb]
    return (float(min(d)), int(sum(v <= 10 for v in d)))


# ------------------------------------------------------------------ never-merge constraints
def conflict(a: dict, b: dict) -> str | None:
    """A reason two listings can never be the same hotel, or None."""
    if a["_fam"] and b["_fam"] and a["_fam"] != b["_fam"]:
        return f"different brand family ({a['_fam']} vs {b['_fam']})"
    if a["_num"] and b["_num"] and not (a["_num"] & b["_num"]):
        return f"different branch number ({'/'.join(sorted(a['_num']))} vs {'/'.join(sorted(b['_num']))})"
    d = haversine_m(a["lat"], a["lng"], b["lat"], b["lng"])
    if d > config.NEVER_MERGE_DISTANCE_M:
        return f"{d:,.0f} m apart (over the {config.NEVER_MERGE_DISTANCE_M:,} m rule)"
    return None
