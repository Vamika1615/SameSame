"""One-off pull of the OpenStreetMap snapshot SameSame is built on.

Run once with network access; the outputs are committed so nothing depends on the
network again. Stdlib only, so it runs before the venv exists.

    python backend/scripts/pull_osm.py

Outputs (data/raw/osm/):
  hotels_raw.json      every tourism=hotel in the city (samesame/city.py) (nodes/ways/relations, with centers)
  basemap.geojson      river, major roads and district outlines, simplified for an offline map
  SNAPSHOT.txt         timestamp + query provenance

Data (c) OpenStreetMap contributors, ODbL 1.0.
"""
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "osm"
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter"]
UA = "SameSame-hackathon/0.1 (offline snapshot, one-off)"

sys.path.insert(0, str(ROOT / "backend"))
from samesame import city  # noqa: E402  (stdlib-only module: no venv needed)

BBOX = city.BBOX                     # (south, west, north, east) for basemap layers
AREA = city.OSM_AREA

QUERIES = {
    "hotels": '[out:json][timeout:300];nwr["tourism"="hotel"]({},{},{},{});out center tags;'.format(*BBOX),
    "river": '[out:json][timeout:180];{}({},{},{},{});out geom;'.format(city.OSM_WATER, *BBOX),
    "roads": '[out:json][timeout:240];way["highway"~"^(motorway|trunk|primary)$"]({},{},{},{});out geom;'.format(*BBOX),
    "districts": '[out:json][timeout:300];rel["boundary"="administrative"]["admin_level"="{}"]({},{},{},{});out geom;'.format(
        city.OSM_DISTRICT_LEVEL, *BBOX),
}


def overpass(query: str) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for attempt in range(9):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.load(r)
        except Exception as e:  # network errors, 429, 504
            last = e
            print(f"  {url} failed ({e}); retrying", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Overpass failed: {last}")


def _perp(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def simplify(pts, tol):
    """Iterative Douglas-Peucker on [lng, lat] points."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        dmax, idx = 0.0, None
        for k in range(i + 1, j):
            d = _perp(pts[k], pts[i], pts[j])
            if d > dmax:
                dmax, idx = d, k
        if idx is not None and dmax > tol:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [p for p, k in zip(pts, keep) if k]


def line(geom, tol):
    pts = [[round(g["lon"], 5), round(g["lat"], 5)] for g in geom]
    return simplify(pts, tol)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stamps = {}

    print("hotels ...")
    hotels = overpass(QUERIES["hotels"])
    stamps["hotels"] = hotels["osm3s"]["timestamp_osm_base"]
    (OUT / "hotels_raw.json").write_text(json.dumps(hotels, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {len(hotels['elements'])} hotel elements")

    features = []
    print("river ...")
    river = overpass(QUERIES["river"])
    stamps["river"] = river["osm3s"]["timestamp_osm_base"]
    for el in river["elements"]:
        features.append({"type": "Feature", "properties": {"layer": "river", "name": city.WATER[0]},
                         "geometry": {"type": "LineString", "coordinates": line(el["geometry"], 0.0002)}})

    print("roads ...")
    roads = overpass(QUERIES["roads"])
    stamps["roads"] = roads["osm3s"]["timestamp_osm_base"]
    for el in roads["elements"]:
        t = el.get("tags", {})
        coords = line(el["geometry"], 0.0003)
        if len(coords) >= 2:
            features.append({"type": "Feature",
                             "properties": {"layer": "road", "class": t.get("highway"),
                                            "name": t.get("name:en") or t.get("name")},
                             "geometry": {"type": "LineString", "coordinates": coords}})

    print("districts ...")
    districts = overpass(QUERIES["districts"])
    stamps["districts"] = districts["osm3s"]["timestamp_osm_base"]
    for el in districts["elements"]:
        t = el.get("tags", {})
        lines = [line(m["geometry"], 0.0004) for m in el.get("members", [])
                 if m.get("type") == "way" and m.get("role") == "outer" and m.get("geometry")]
        lines = [l for l in lines if len(l) >= 2]
        if not lines:
            continue
        pts = [p for l in lines for p in l]
        cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        features.append({"type": "Feature",
                         "properties": {"layer": "district", "name": t.get("name:en") or t.get("name"),
                                        "label_lng": round(cx, 5), "label_lat": round(cy, 5)},
                         "geometry": {"type": "MultiLineString", "coordinates": lines}})

    gj = {"type": "FeatureCollection", "features": features,
          "attribution": "(c) OpenStreetMap contributors, ODbL 1.0"}
    (OUT / "basemap.geojson").write_text(json.dumps(gj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    counts = {k: sum(1 for f in features if f["properties"]["layer"] == k) for k in ("river", "road", "district")}
    print(f"  basemap features: {counts}")

    (OUT / "SNAPSHOT.txt").write_text(
        "OpenStreetMap snapshot for SameSame (data (c) OpenStreetMap contributors, ODbL 1.0)\n"
        f"pulled_at_utc: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
        + "".join(f"osm_base[{k}]: {v}\n" for k, v in stamps.items())
        + "".join(f"query[{k}]: {q}\n" for k, q in QUERIES.items()),
        encoding="utf-8")
    print("done ->", OUT)


if __name__ == "__main__":
    main()
