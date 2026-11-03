"""FastAPI app. Reads precomputed artifacts; in demo mode also serves the built frontend."""
import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from samesame import config, images, mock
from samesame.schemas import (ActivitySearch, BookResponse, BookStats, HotelDetail, HotelSearch, Meta, Mode, ReviewAck, ReviewItem,
                              ReviewLabel, SimParams, SimResult, SupplierRow)

app = FastAPI(title="SameSame", version="0.0.1")


@lru_cache
def _basemap() -> dict:
    return json.loads((config.RAW_OSM / "basemap.geojson").read_text(encoding="utf-8"))


@lru_cache
def _osm_hotels() -> list[dict]:
    raw = json.loads((config.RAW_OSM / "hotels_raw.json").read_text(encoding="utf-8"))
    out = []
    for el in raw["elements"]:
        t = el.get("tags", {})
        c = el.get("center") or el
        name = t.get("name:en") or t.get("name")
        if name and "lat" in c:
            out.append({"osm_id": f"{el['type']}/{el['id']}", "name": name, "lat": c["lat"], "lng": c["lon"]})
    return out


DATA_SOURCE = "mock"   # M1: hand-written inputs in samesame.mock; becomes "synthetic" once M2 lands


@app.get("/api/meta", response_model=Meta)
def meta():
    manifest = config.BUILD / "manifest.json"
    build = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    return Meta(mode=Mode(**{**config.mode(), "data": DATA_SOURCE}), city=config.CITY, currency=config.CURRENCY, build=build,
                demo={"book_offers": mock.DEMO_BASKET, "book_seed": mock.DEMO_SEED,
                      "book_seed_note": "Seed 1 is the first seed tried; it happens to show a failover. Press Fresh seed for new draws, or Run 1,000× for the distribution."})


@app.get("/api/hotels/search", response_model=HotelSearch)
def hotels_search():
    return mock.hotel_search()


@app.get("/api/hotels/{cluster_id}", response_model=HotelDetail)
def hotel(cluster_id: str):
    if cluster_id not in mock.LISTINGS:
        raise HTTPException(404, f"no hotel {cluster_id}")
    return mock.hotel_detail(cluster_id)


class BookRequest(BaseModel):
    offer_ids: list[str]
    seed: int


@app.post("/api/book", response_model=BookResponse)
def book(req: BookRequest):
    return BookResponse(seed=req.seed, results=mock.book(req.offer_ids, req.seed))


@app.get("/api/book/stats", response_model=BookStats)
def book_stats(offer_ids: str = ",".join(mock.DEMO_BASKET), runs: int = 1000):
    ids = offer_ids.split(",")
    agg = {i: {"offer_id": i, "confirmed_first_time": 0, "paid_price_rise": 0, "via_failover": 0, "failed": 0} for i in ids}
    for seed in range(1, min(runs, 5000) + 1):
        for r in mock.book(ids, seed):
            repriced = any(st.event == "price_changed" for st in r.steps)
            key = ("failed" if r.status == "failed" else "via_failover" if r.via_failover
                   else "paid_price_rise" if repriced else "confirmed_first_time")
            agg[r.offer_id][key] += 1
    return BookStats(runs=min(runs, 5000), per_offer=list(agg.values()))


@app.get("/api/activities/search", response_model=ActivitySearch)
def activities(q: str = "floating market"):
    return mock.activity_search(q)


@app.get("/api/review/queue", response_model=list[ReviewItem])
def review_queue():
    return mock.review_queue()


@app.post("/api/review/{pair_id}/label", response_model=ReviewAck)
def review_label(pair_id: str, body: ReviewLabel):
    r = mock.label(pair_id, body.label, body.reviewer)
    return ReviewAck(ok=True, audit_id=r["audit_id"], streak=r["streak"], model_was_right=r["model_was_right"], truth=r["truth"])


@app.post("/api/review/undo/{audit_id}")
def review_undo(audit_id: str):
    return {"ok": mock.undo(audit_id)}


@app.get("/api/review/audit")
def review_audit():
    return mock.audit_log()


@app.post("/api/sim", response_model=SimResult)
def sim(p: SimParams):
    return mock.simulate(p)


@app.get("/api/suppliers", response_model=list[SupplierRow])
def supplier_report():
    return mock.suppliers()


@app.get("/api/img/{kind}/{key}.svg", include_in_schema=False)
def img(kind: str, key: str):
    svg = images.activity_svg(key) if kind == "activity" else images.hotel_svg(key)
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/basemap")
def basemap():
    return _basemap()


@app.get("/api/base/hotels")
def base_hotels():
    """M0: raw OSM base truth, before any supplier layer exists."""
    return {"source": "OpenStreetMap (ODbL)", "hotels": _osm_hotels()}


# ---- demo mode: serve the built SPA from the same port (one process on stage)
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = config.FRONTEND_DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
