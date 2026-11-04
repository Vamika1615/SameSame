"""Hotel and attraction images, and the corrupted copies each supplier carries.

Base images, in order of preference: real Wikimedia Commons photos of that very hotel / attraction
(data/raw/wiki, credited per file); real "stock" photos of other hotels' rooms, pools and lobbies (labelled
"stock photo, not this hotel" in the UI); procedural illustrations only when neither exists.

Each hotel gets up to four of its own photos, topped up to three with one stock room and one stock pool
(or lobby) photo; each attraction gets up to three. Supplier listings carry corrupted copies of those: cropped, resized, recompressed, colour-shifted,
sometimes watermarked, and occasionally a sibling hotel's image (a real-world photo mix-up). M5's
perceptual-hash matcher has to see through the corruption and catch the mix-up.
"""
import hashlib
import json

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

from samesame import config

W, H = 480, 320
SUP_WIDTH = {"kestrel": 320, "mynah": 480, "heron": 400, "bulbul": 360, "hornbill": 420, "sunbird": 300}
SUP_QUALITY = {"kestrel": 45, "mynah": 88, "heron": 75, "bulbul": 60, "hornbill": 80, "sunbird": 55}


def _palette(key: str):
    h = hashlib.md5(key.encode()).digest()
    base = np.array([h[0], h[1], h[2]], dtype=float)
    accent = tuple(int(60 + v * 0.6) for v in base)
    wall = tuple(int(150 + v * 0.35) for v in base[::-1])
    return h, accent, wall


def _sky(d, top=(120, 170, 220), bottom=(235, 225, 210)):
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))


def hotel_image(key: str, kind: str, pool: bool) -> Image.Image:
    h, accent, wall = _palette(key)
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    rnd = np.random.default_rng(int.from_bytes(h[:4], "little"))
    if kind == "facade":
        _sky(d)
        for k in range(int(rnd.integers(2, 4))):
            x0 = int(rnd.integers(20, 300)); bw = int(rnd.integers(90, 170)); top = int(rnd.integers(30, 120))
            col = tuple(int(c * (0.85 + 0.1 * k)) for c in wall)
            d.rectangle([x0, top, x0 + bw, H], fill=col)
            for wy in range(top + 12, H - 20, 18):
                for wx in range(x0 + 10, x0 + bw - 12, 16):
                    d.rectangle([wx, wy, wx + 8, wy + 10], fill=(70, 90, 120) if rnd.random() < 0.7 else (250, 230, 160))
        d.rectangle([0, H - 30, W, H], fill=(90, 95, 100))
        d.rectangle([180, H - 70, 300, H - 30], fill=accent)
    elif kind == "room":
        d.rectangle([0, 0, W, H], fill=wall)
        d.rectangle([0, 220, W, H], fill=(150, 120, 95))
        d.rectangle([300, 40, 450, 170], fill=(180, 210, 235)); d.rectangle([370, 40, 378, 170], fill=wall)
        d.rectangle([60, 160, 300, 250], fill=(245, 245, 240)); d.rectangle([60, 120, 300, 165], fill=accent)
        d.rectangle([80, 170, 150, 195], fill=(255, 255, 255)); d.rectangle([200, 170, 270, 195], fill=(255, 255, 255))
    elif kind == "pool" and pool:
        _sky(d, (110, 175, 230), (200, 230, 245))
        d.rectangle([0, 160, W, H], fill=(225, 215, 195))
        d.rounded_rectangle([40, 190, 440, 300], 18, fill=(60, 170, 210))
        for x in range(60, 430, 60):
            d.ellipse([x, 215, x + 30, 225], fill=(140, 215, 235))
        d.rectangle([0, 100, 120, 160], fill=wall)
        for x in (150, 220, 290):
            d.polygon([(x, 175), (x + 30, 150), (x + 60, 175)], fill=accent)
    elif kind in ("pool", "lobby"):
        d.rectangle([0, 0, W, H], fill=tuple(int(c * 0.9) for c in wall))
        d.rectangle([0, 230, W, H], fill=(205, 195, 180))
        d.rectangle([150, 120, 330, 230], fill=accent); d.rectangle([140, 110, 340, 125], fill=(60, 50, 45))
        for x in (40, 400):
            d.rectangle([x, 60, x + 30, 230], fill=(235, 225, 205))
        d.ellipse([200, 20, 280, 60], fill=(250, 235, 170))
    else:  # view
        _sky(d, (240, 170, 120), (120, 120, 170))
        for k in range(14):
            x0 = int(rnd.integers(0, W - 30)); top = int(rnd.integers(80, 220))
            d.rectangle([x0, top, x0 + int(rnd.integers(20, 60)), H], fill=(50 + k * 4, 50 + k * 3, 70 + k * 4))
    return im


def activity_image(key: str, i: int) -> Image.Image:
    h, accent, wall = _palette(f"{key}:{i}")
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    _sky(d, (110 + 20 * i, 160, 215), (240, 220, 190))
    d.rectangle([0, 220, W, H], fill=(70, 130, 150) if h[3] % 2 else (120, 150, 90))
    cx = 120 + (h[4] % 240)
    for k in range(3):                                   # a stepped temple / tower silhouette
        w = 140 - 40 * k
        d.rectangle([cx - w // 2, 160 - 40 * k, cx + w // 2, 220 - 40 * k], fill=accent if k % 2 else wall)
    d.polygon([(cx - 20, 80), (cx, 20 + h[5] % 30), (cx + 20, 80)], fill=accent)
    if h[6] % 2:
        d.polygon([(40, 250), (140, 250), (120, 270), (60, 270)], fill=(140, 80, 50))
    return im


def corrupt(im: Image.Image, sup: str, rng) -> tuple[Image.Image, list[str]]:
    corr = []
    w, h = im.size
    c = float(rng.uniform(0.95, 0.99))       # real feeds mostly resize + recompress; heavy crops were unrealistic (M3 review)
    dx, dy = int(rng.integers(0, int(w * (1 - c)) + 1)), int(rng.integers(0, int(h * (1 - c)) + 1))
    im = im.crop((dx, dy, dx + int(w * c), dy + int(h * c))); corr.append(f"crop{c:.2f}")
    tw = SUP_WIDTH[sup]
    im = im.resize((tw, int(tw * im.size[1] / im.size[0])))
    if rng.random() < 0.5:
        f = float(rng.uniform(0.85, 1.15)); im = ImageEnhance.Brightness(im).enhance(f); corr.append(f"bright{f:.2f}")
    if rng.random() < 0.3:
        f = float(rng.uniform(0.7, 1.3)); im = ImageEnhance.Color(im).enhance(f); corr.append(f"sat{f:.2f}")
    if sup in ("kestrel", "sunbird") and rng.random() < 0.6:
        d = ImageDraw.Draw(im)
        d.text((im.size[0] - 70, im.size[1] - 16), sup.upper(), fill=(255, 255, 255)); corr.append("watermark")
    return im, corr


WIKI = config.DATA / "raw" / "wiki"
STOCK_REUSE_MIN_M = 2500          # reused only by hotels this far apart: blocking never compares hotels > 2 km apart


def _photos() -> list[dict]:
    f = WIKI / "photos.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def _credit(p: dict | None) -> dict:
    if not p:
        return {"photo_kind": "generated", "credit": "Procedural illustration (CC0, own work)", "credit_url": None}
    kind = "photo" if p["kind"] in ("hotel", "attraction") else "stock"
    return {"photo_kind": kind, "credit": f"{p['author']} · {p['license']} · Wikimedia Commons", "credit_url": p["source"]}


def _load(p: dict) -> Image.Image:
    im = Image.open(WIKI / "photos" / p["file"]).convert("RGB")
    return im.resize((W, int(W * im.size[1] / im.size[0]))) if im.size[0] != W else im


def _assign_stock(hotels, pool: list[dict], rng, avoid: dict | None = None, users: dict | None = None) -> dict[str, dict]:
    """Give each hotel one photo from `pool`, reusing a photo only between hotels > STOCK_REUSE_MIN_M apart
    (and never the photo `avoid` already gave that hotel)."""
    from samesame.ranking.score import haversine_m
    users = {} if users is None else users          # shared across passes over the same pool
    out = {}
    order = list(rng.permutation(len(pool))) if pool else []
    for h in hotels:
        for k in order:
            if (avoid or {}).get(h["hotel_id"]) is pool[k]:
                continue
            if all(haversine_m(h["lat"], h["lng"], u["lat"], u["lng"]) > STOCK_REUSE_MIN_M for u in users.get(k, [])):
                users.setdefault(k, []).append(h)
                out[h["hotel_id"]] = pool[k]
                order.append(order.pop(order.index(k)))          # rotate so photos spread evenly
                break
    return out


def generate(hotels, listings, truth, attractions, act_listings, act_truth, hard_negatives, rng):
    out_dir = config.BUILD / "images"
    (out_dir / "base").mkdir(parents=True, exist_ok=True)
    (out_dir / "feed").mkdir(parents=True, exist_ok=True)
    rows = []
    base: dict[str, list[tuple[str, Image.Image, dict]]] = {}
    photos = _photos()
    own: dict[str, list] = {}
    for p in photos:
        own.setdefault(p["subject"], []).append(p)
    # hand out stock photos from the demo area outwards, so the hotels on screen are the ones that get them
    from samesame.data.osm_base import ASOK
    from samesame.ranking.score import haversine_m
    d = {h["hotel_id"]: haversine_m(*ASOK, h["lat"], h["lng"]) for h in hotels}
    near_first = sorted(hotels, key=lambda h: (not (d[h["hotel_id"]] <= 600 and h["star"] >= 4), d[h["hotel_id"]]))
    room_users: dict = {}
    stock = {k: _assign_stock(near_first, [p for p in photos if p["kind"] == k], rng, users=room_users if k == "stock_room" else None)
             for k in ("stock_room", "stock_pool", "stock_lobby")}
    # second stock photo for hotels whose pool / lobby slot ran dry: another room, never the same one
    room2 = _assign_stock(near_first, [p for p in photos if p["kind"] == "stock_room"], rng, avoid=stock["stock_room"], users=room_users)

    def add(owner_kind, owner, key, im, p):
        im.save(out_dir / "base" / f"{key}.jpg", quality=85)
        cred = _credit(p)
        rows.append({"image_id": key, "path": f"base/{key}.jpg", "owner_kind": owner_kind, "owner_id": owner, "derived_from": None,
                     "corruptions": [], "true_owner_id": owner, **cred})
        base.setdefault(owner, []).append((key, im, cred))

    for h in hotels:
        mine = own.get(h["osm_id"], [])[:4]                     # real photos of this very hotel first
        for i, p in enumerate(mine):
            add("hotel", h["hotel_id"], f"{h['hotel_id']}-own{i}", _load(p), p)
        second = stock["stock_pool" if h["pool"] else "stock_lobby"].get(h["hotel_id"]) or room2.get(h["hotel_id"])
        fill = [stock["stock_room"].get(h["hotel_id"]), second]
        for kind, p in zip(("room", "pool" if h["pool"] else "lobby"), fill):
            if len(base.get(h["hotel_id"], [])) >= 3:
                break
            add("hotel", h["hotel_id"], f"{h['hotel_id']}-{kind}", _load(p) if p else hotel_image(f"{h['hotel_id']}-{kind}", kind, h["pool"]), p)
        while len(base.get(h["hotel_id"], [])) < 2:              # offline / no stock left: procedural illustration
            kind = ("facade", "view")[len(base.get(h["hotel_id"], [])) % 2]
            add("hotel", h["hotel_id"], f"{h['hotel_id']}-{kind}", hotel_image(f"{h['hotel_id']}-{kind}", kind, h["pool"]), None)
    for a in attractions:
        for i, p in enumerate(own.get(a["attraction_id"], [])[:3]):
            add("attraction", a["attraction_id"], f"{a['attraction_id']}-own{i}", _load(p), p)
        i = 0
        while len(base.get(a["attraction_id"], [])) < 1:      # illustration only when there is no real photo at all
            add("attraction", a["attraction_id"], f"{a['attraction_id']}-{i}", activity_image(a["attraction_id"], i), None)
            i += 1

    sibling = {}
    for p in hard_negatives:
        sibling.setdefault(p["a"], p["b"]); sibling.setdefault(p["b"], p["a"])
    hotel_of = {t["listing_id"]: t["hotel_id"] for t in truth}
    att_of = {t["listing_id"]: t["attraction_id"] for t in act_truth}
    jobs = [(l, hotel_of[l["listing_id"]], l["n_images"], "hotel") for l in listings] + \
           [(l, att_of[l["listing_id"]], int(rng.integers(1, 3)), "activity") for l in act_listings]
    for l, owner, k, kind in jobs:
        sup = l["supplier_id"]
        order = rng.permutation(len(base[owner]))[:k]
        for j, idx in enumerate(order):
            src_owner = owner
            extra = []
            if kind == "hotel" and owner in sibling and rng.random() < 0.03:
                src_owner = sibling[owner]; extra = ["sibling_mixup"]          # wrong building's photo
            key, im, cred = base[src_owner][idx % len(base[src_owner])]
            cim, corr = corrupt(im, sup, rng)
            fid = f"{l['listing_id'].replace(':', '-')}-{j}"
            cim.save(out_dir / "feed" / f"{fid}.jpg", quality=SUP_QUALITY[sup])
            rows.append({"image_id": fid, "path": f"feed/{fid}.jpg", "owner_kind": "listing", "owner_id": l["listing_id"],
                         "derived_from": key, "corruptions": corr + extra, "true_owner_id": src_owner, **cred})
    with open(out_dir / "LICENSES.csv", "w", encoding="utf-8") as f:
        f.write("path,kind,credit,source\n")
        for r in rows:
            if r["derived_from"] is None:
                f.write(f'{r["path"]},{r["photo_kind"]},"{r["credit"].replace(chr(34), chr(39))}",{r["credit_url"] or ""}\n')
        f.write('feed/*.jpg,derived,"resized / cropped / recompressed copies of the base image they derive from (same credit)",\n')
    return rows
