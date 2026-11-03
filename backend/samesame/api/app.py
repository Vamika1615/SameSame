"""FastAPI app. Reads precomputed artifacts; in demo mode also serves the built frontend."""
import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from samesame import config
from samesame.schemas import Meta, Mode

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


@app.get("/api/meta", response_model=Meta)
def meta():
    manifest = config.BUILD / "manifest.json"
    build = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    return Meta(mode=Mode(**config.mode()), city=config.CITY, currency=config.CURRENCY, build=build)


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
