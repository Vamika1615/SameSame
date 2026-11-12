"""FastAPI app. Reads precomputed artifacts; in demo mode also serves the built frontend."""
import json
import threading
from functools import lru_cache

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from samesame import city, config, images, placeholders, review, service, store
from samesame.catalogue import imports as cat_imports
from samesame.catalogue import view as catalogue
from samesame.ingest import sheet as sheets
from samesame.labelling.api import router as labelling_router
from samesame.remix import approvals as remix_approvals
from samesame.remix import book as remix_book
from samesame.remix import business as remix_business
from samesame.remix import gaps as remix_gaps
from samesame.remix import trip as remix_trip
from samesame.remix import service as remix
from samesame.schemas import (ActivitySearch, BookResponse, BookStats, HotelDetail, HotelSearch, Meta, Mode, ReviewAck, ReviewItem,
                              ReviewLabel, SimParams, SimResult, SupplierRow)

app = FastAPI(title="Remix", version="0.1.0")
app.include_router(labelling_router)


@app.on_event("startup")
def _warm_remix():
    """Compute the Remix catalogue, gaps and Connected Trip once at start, so no stage click waits on them."""
    if store.ready():
        remix.overview(remix.settings())
        remix_gaps.find()
        remix_trip.build()
        remix_trip.demo_seed()
        sheets.warm()
        threading.Thread(target=catalogue.summary, daemon=True).start()      # names of every catalogue hotel, once


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
                      "remix_variant": remix.demo_variant(), "remix_seed": remix.demo_seed(), "trip_seed": remix_trip.demo_seed(),
                      "remix_seed_note": f"Seed {remix.demo_seed()} is the first seed that shows a part failing over (chosen to show it). Press Fresh seed for new draws, or Run 1,000× for how often each outcome happens."})


def _remix_settings(zone=None, agent_share=None, min_saving=None, min_margin=None, min_promise=None, buffer_min=None, preset=None):
    return remix.settings(preset, zone=zone, agent_share=agent_share, min_saving=min_saving, min_margin=min_margin,
                          min_promise=min_promise, buffer_min=buffer_min)


@app.get("/api/remix")
def remix_overview(zone: str | None = None, agent_share: float | None = None, min_saving: float | None = None, min_margin: float | None = None,
                   min_promise: float | None = None, buffer_min: int | None = None, preset: str | None = None):
    return remix.overview(_remix_settings(zone, agent_share, min_saving, min_margin, min_promise, buffer_min, preset))


@app.get("/api/trip")
def connected_trip(min_promise: float | None = None):
    return remix_trip.build(remix.settings(min_promise=min_promise))


class TripBookRequest(BaseModel):
    seed: int


@app.post("/api/trip/book")
def connected_trip_book(req: TripBookRequest):
    return remix_trip.book(req.seed)


@app.get("/api/remix/gaps")
def remix_gap_list():
    rs = remix_gaps.find()
    return {"counts": remix_gaps.summary_counts(), "demo": remix.demo_gap(), "items": rs}


@app.get("/api/remix/approvals")
def remix_approval_queue():
    return {"queue": remix_approvals.queue(), "history": remix_approvals.history()}


class ApprovalRequest(BaseModel):
    decision: str
    note: str = ""
    approver: str = "product team"


@app.post("/api/remix/approvals/undo/{audit_id}")
def remix_approval_undo(audit_id: str):
    return remix_approvals.undo(audit_id)


@app.post("/api/remix/approvals/{variant_id}")
def remix_approval_decide(variant_id: str, req: ApprovalRequest):
    if req.decision not in ("approve", "reject"):
        raise HTTPException(400, "decision must be approve or reject")
    try:
        return remix_approvals.decide(variant_id, req.decision, req.approver, req.note)
    except KeyError:
        raise HTTPException(404, f"{variant_id} is not a Remix awaiting approval")


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
    r = remix.result(req.variant_id, remix.settings()) or remix.gap(req.variant_id)
    if r is None or not r.get("parts"):
        raise HTTPException(404, f"no Remix for {req.variant_id}")
    return remix_book.book(r, req.seed)


@app.get("/api/remix/book/stats")
def remix_book_stats(variant_id: str, runs: int = 1000):
    r = remix.result(variant_id, remix.settings())
    if r is None or not r.get("parts") or not r.get("packaged"):
        raise HTTPException(404, f"no Remix with a package to compare for {variant_id}")
    return remix_book.stats(r, min(runs, 2000))


# ------------------------------------------------------------------ Catalogue: past inventory + supplier-sheet imports
def _resolve_new(data: bytes, filename: str):
    return sheets.ingest(data, filename, catalogue.for_matching())


def _import_or_404(fn, *a):
    try:
        return fn(*a)
    except cat_imports.ImportError_ as e:
        raise HTTPException(404 if "No such" in str(e) else 400, str(e))


@app.get("/api/catalogue/summary")
def catalogue_summary():
    return catalogue.summary()


@app.get("/api/catalogue/hotels")
def catalogue_hotels(q: str | None = None, source: str | None = None):
    return catalogue.hotels(q, source)


@app.get("/api/catalogue/hotels/{hotel_id}")
def catalogue_hotel(hotel_id: str):
    h = catalogue.hotel(hotel_id)
    if h is None:
        raise HTTPException(404, "No such hotel in the catalogue.")
    return h


@app.get("/api/catalogue/pending")
def catalogue_pending():
    return catalogue.pending()


@app.get("/api/imports")
def imports_list():
    return {"imports": cat_imports.list_meta(), "samples": [{"name": k, "supplier": v[1], "description": v[2],
            "files": {f: f"/api/sheets/sample/{f}?name={k}" for f in ("csv", "xlsx") if sheets.sample_path(f, k).exists()}}
            for k, v in sheets.SAMPLES.items()]}


@app.post("/api/imports")
async def imports_create(file: UploadFile = File(...), supplier: str | None = Form(None)):
    data = await file.read()
    if len(data) > 15_000_000:
        raise HTTPException(413, "Sheets up to 15 MB, please.")
    try:
        m, created = cat_imports.create(data, file.filename or "sheet.csv", supplier, _resolve_new)
    except sheets.SheetError as e:
        raise HTTPException(400, str(e))
    return {"created": created, "import": catalogue.import_view(m["id"])}


@app.post("/api/imports/samples/{name}")
def imports_sample(name: str):
    if name not in sheets.SAMPLES:
        raise HTTPException(404, "No such sample.")
    p = sheets.sample_path("xlsx" if name == "plover" else "csv", name)
    if not p.exists():
        raise HTTPException(404, "Sample not built yet: run python start.py --rebuild")
    m, created = cat_imports.create(p.read_bytes(), p.name, sheets.SAMPLES[name][1], _resolve_new)
    return {"created": created, "import": catalogue.import_view(m["id"])}


@app.get("/api/imports/decisions")
def imports_decisions():
    return cat_imports.history()


@app.post("/api/imports/decisions/undo/{audit_id}")
def imports_undo(audit_id: str):
    return _import_or_404(cat_imports.undo, audit_id)


@app.get("/api/imports/{import_id}")
def imports_get(import_id: str):
    return _import_or_404(catalogue.import_view, import_id)


@app.get("/api/imports/{import_id}/source")
def imports_source(import_id: str):
    data, filename = _import_or_404(cat_imports.source, import_id)
    return Response(data, media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


class Decision(BaseModel):
    sheet_id: str
    kind: str
    value: str
    room: str | None = None


@app.post("/api/imports/{import_id}/decide")
def imports_decide(import_id: str, d: Decision):
    _import_or_404(cat_imports.decide, import_id, d.sheet_id, d.kind, d.value, d.room)
    return catalogue.import_view(import_id)


@app.post("/api/imports/{import_id}/{action}")
def imports_action(import_id: str, action: str):
    if action == "apply":
        _import_or_404(cat_imports.set_status, import_id, "applied")
    elif action == "remove":
        _import_or_404(cat_imports.set_status, import_id, "removed")
    elif action == "restore":
        _import_or_404(cat_imports.set_status, import_id, "draft")
    elif action == "recheck":
        try:
            _import_or_404(cat_imports.recheck, import_id, lambda d, f: sheets.ingest(d, f, catalogue.for_matching(exclude=import_id)))
        except sheets.SheetError as e:
            raise HTTPException(400, str(e))
    else:
        raise HTTPException(404, "Unknown action.")
    return catalogue.import_view(import_id)


# ------------------------------------------------------------------ Supplier Sheets (single-file preview, kept for compatibility)
@app.get("/api/sheets/sample")
def sheets_sample():
    if not sheets.sample_path("csv").exists():
        raise HTTPException(404, "Weaver's sample sheet isn't built yet: run python start.py --rebuild")
    return {"supplier": "Weaver", "synthetic": True, "rows": sum(1 for _ in sheets.sample_path("csv").open(encoding="utf-8")) - 1,
            "files": {f: f"/api/sheets/sample/{f}" for f in ("csv", "xlsx") if sheets.sample_path(f).exists()}}


@app.get("/api/sheets/sample/{fmt}")
def sheets_sample_file(fmt: str, name: str = "weaver"):
    if fmt not in ("csv", "xlsx") or name not in sheets.SAMPLES or not sheets.sample_path(fmt, name).exists():
        raise HTTPException(404, "no such sample")
    return FileResponse(sheets.sample_path(fmt, name), filename=f"{sheets.SAMPLES[name][0]}_SYNTHETIC.{fmt}")


@app.post("/api/sheets/sample/ingest")
def sheets_ingest_sample():
    return sheets.ingest_sample()


@app.post("/api/sheets/ingest")
async def sheets_ingest(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 10_000_000:
        raise HTTPException(413, "Sheets up to 10 MB, please.")
    try:
        return sheets.ingest(data, file.filename or "sheet.csv")
    except sheets.SheetError as e:
        raise HTTPException(400, str(e))


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
    res = placeholders.simulate(p)
    arm = next(a for a in res.arms if a.arm == "samesame")
    preset = "pessimistic" if p.failure_scale > 1.2 else None
    res.remix = remix_business.case(arm.bookings_per_search, remix.settings(preset))
    return res


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
