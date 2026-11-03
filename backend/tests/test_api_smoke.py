from fastapi.testclient import TestClient

from samesame.api.app import app

client = TestClient(app)


def test_meta_reports_mode():
    r = client.get("/api/meta")
    assert r.status_code == 200
    m = r.json()["mode"]
    assert m["data"] in ("mock", "synthetic", "real")
    assert isinstance(m["llm"], bool)


def test_basemap_is_offline_geojson():
    gj = client.get("/api/basemap").json()
    layers = {f["properties"]["layer"] for f in gj["features"]}
    assert {"river", "road", "district"} <= layers


def test_base_hotels_from_snapshot():
    hotels = client.get("/api/base/hotels").json()["hotels"]
    assert len(hotels) > 300
