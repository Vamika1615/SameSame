"""FastAPI app. Reads precomputed artifacts; in demo mode also serves the built frontend."""
import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from samesame import city, config, images, placeholders, review, service, store
from samesame.labelling.api import router as labelling_router
from samesame.remix import book as remix_book
from samesame.remix import service as remix
from samesame.schemas import (ActivitySearch, BookResponse, BookStats, HotelDetail, HotelSearch, Meta, Mode, ReviewAck, ReviewItem,
                              ReviewLabel, SimParams, SimResult, SupplierRow)

app = FastAPI(title="Remix", version="0.1.0")
app.include_router(labelling_router)


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


DATA_SOURCE = "synthetic"
SOURCES = {"hotels": "6 synthetic supplier feeds over 300 real OSM hotels",
           "clusters": store.CLUSTER_SOURCE,
           "promise": "fitted on the 30,000-attempt booking log (hotels, tours, tickets, transfers)",
           "remix_parts": "synthetic tickets, lunch vouchers and zone transfers; prices from disclosed tariffs (DATA.md)",
           "review_queue": "the matcher's gray-zone and blocked pairs",
           "metrics": "rebuilt every build: METRICS.md",
           "simulator": "closed-form mock until M5"}


@app.get("/api/meta", response_model=Meta)
def meta():
    manifest = config.BUILD / "manifest.json"
    build = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    return Meta(mode=Mode(**{**config.mode(), "data": DATA_SOURCE}), city=config.CITY, currency=config.CURRENCY, build=build,
                sources=SOURCES,
                demo={"book_offers": service.demo_basket(), "book_seed": service.DEMO_SEED, "golden_hotel": service.demo_hotel(),
                      "book_seed_note": "Seed 1 is the first seed tried; it happens to show a failover. Press Fresh seed for new draws, or Run 1,000× for the distribution.",
                      "remix_variant": remix.demo_variant(), "remix_seed": remix.demo_seed(),
                      "remix_seed_note": f"Seed {remix.demo_seed()} is the first seed that shows a part failing over (chosen to show it). Press Fresh seed for new draws, or Run 1,000× for how often each outcome happens."})


def _remix_settings(zone=None, agent_share=None, min_saving=None, min_margin=None, min_promise=None, buffer_min=None, preset=None):
    return remix.settings(preset, zone=zone, agent_share=agent_share, min_saving=min_saving, min_margin=min_margin,
                          min_promise=min_promise, buffer_min=buffer_min)


@app.get("/api/remix")
def remix_overview(zone: str | None = None, agent_share: float | None = None, min_saving: float | None = None, min_margin: float | None = None,
                   min_promise: float | None = None, buffer_min: int | None = None, preset: str | None = None):
    return remix.overview(_remix_settings(zone, agent_share, min_saving, min_margin, min_promise, buffer_min, preset))


@app.get("/api/remix/{variant_id}")
def remix_detail(variant_id: str, zone: str | None = None, agent_share: float | None = None, min_saving: float | None = None,
                 min_margin: float | None = None, min_promise: float | None = None, buffer_min: int | None = None, preset: str | None = None):
    if variant_id == "demo":
        variant_id = remix.demo_variant()
    r = remix.result(variant_id, _remix_settings(zone, agent_share, min_saving, min_margin, min_promise, buffer_min, preset))
    if r is None:
        raise HTTPException(404, f"no packaged product {variant_id}")
    return r


class RemixBookRequest(BaseModel):
    variant_id: str
    seed: int


@app.post("/api/remix/book")
def remix_book_route(req: RemixBookRequest):
    r = remix.result(req.variant_id, remix.settings())
    if r is None or not r.get("parts"):
        raise HTTPException(404, f"no Remix for {req.variant_id}")
    return remix_book.book(r, req.seed)


@app.get("/api/remix/book/stats")
def remix_book_stats(variant_id: str, runs: int = 1000):
    r = remix.result(variant_id, remix.settings())
    if r is None or not r.get("parts"):
        raise HTTPException(404, f"no Remix for {variant_id}")
    return remix_book.stats(r, min(runs, 2000))


@app.get("/api/hotels/search", response_model=HotelSearch)
def hotels_search():
    return service.hotel_search()


@app.get("/api/hotels/{cluster_id}", response_model=HotelDetail)
def hotel(cluster_id: str):
    if cluster_id == "demo":                     # presenter alias for the golden-case hotel
        cluster_id = service.demo_hotel()
    if cluster_id not in store.get().listings_of:
        raise HTTPException(404, f"no hotel {cluster_id}")
    return service.hotel_detail(cluster_id)


class BookRequest(BaseModel):
    offer_ids: list[str]
    seed: int


@app.post("/api/book", response_model=BookResponse)
def book(req: BookRequest):
    unknown = [o for o in req.offer_ids if o not in store.get().offer]
    if unknown:
        raise HTTPException(404, f"unknown offers {unknown}")
    return BookResponse(seed=req.seed, results=service.book(req.offer_ids, req.seed))


@app.get("/api/book/stats", response_model=BookStats)
def book_stats(offer_ids: str = "", runs: int = 1000):
    ids = offer_ids.split(",") if offer_ids else service.demo_basket()
    agg = {i: {"offer_id": i, "confirmed_first_time": 0, "paid_price_rise": 0, "via_failover": 0, "failed": 0} for i in ids}
    for seed in range(1, min(runs, 5000) + 1):
        for r in service.book(ids, seed):
            repriced = any(st.event == "price_changed" for st in r.steps)
            key = ("failed" if r.status == "failed" else "via_failover" if r.via_failover
                   else "paid_price_rise" if repriced else "confirmed_first_time")
            agg[r.offer_id][key] += 1
    return BookStats(runs=min(runs, 5000), per_offer=list(agg.values()))


@app.get("/api/activities/search", response_model=ActivitySearch)
def activities(q: str = city.DEMO_QUERIES[0][0]):
    return service.activity_search(q)


@app.get("/api/review/queue", response_model=list[ReviewItem])
def review_queue():
    return review.queue()


@app.post("/api/review/{pair_id}/label", response_model=ReviewAck)
def review_label(pair_id: str, body: ReviewLabel):
    if pair_id not in {it.pair_id for it in review.queue()}:
        raise HTTPException(404, f"{pair_id} is not in the review queue")
    r = review.label(pair_id, body.label, body.reviewer)
    return ReviewAck(ok=True, audit_id=r["audit_id"], streak=r["streak"], model_was_right=r["model_was_right"], truth=r["truth"])


@app.post("/api/review/undo/{audit_id}")
def review_undo(audit_id: str):
    return {"ok": review.undo(audit_id)}


@app.get("/api/review/audit")
def review_audit():
    return review.audit_log()


@app.get("/api/metrics")
def metrics():
    """Evaluation report written by samesame.eval.report at build time (also rendered to METRICS.md)."""
    return json.loads((config.BUILD / "metrics.json").read_text(encoding="utf-8"))


@app.post("/api/sim", response_model=SimResult)
def sim(p: SimParams):
    return placeholders.simulate(p)


@app.get("/api/suppliers", response_model=list[SupplierRow])
def supplier_report():
    return service.suppliers()


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


# generated illustrative images (procedural; see data/build/images/LICENSES.csv)
(config.BUILD / "images").mkdir(parents=True, exist_ok=True)
app.mount("/api/images", StaticFiles(directory=config.BUILD / "images"), name="images")


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
