"""Supplier Sheets: reading messy spreadsheets, resolving rows to the catalogue, and never reading the answer key."""
import io

import polars as pl
import pytest
from fastapi.testclient import TestClient

from samesame.api.app import app
from samesame.ingest import sheet as S

client = TestClient(app)


def test_columns_are_found_by_their_usual_spellings():
    cols, unused = S.map_columns(["Property Name", "Lat", "Longitude", "Tel", "Room Category", "Board Basis", "Net Rate (INR)", "Notes"])
    assert cols == {"name": 0, "lat": 1, "lng": 2, "phone": 3, "room": 4, "meal": 5, "price": 6}
    assert unused == ["Notes"]


def test_semicolon_csv_with_decimal_commas():
    data = "Hotel;Room;Latitude;Longitude;Rate\nHyatt Place Dubai Baniyas Square;HP Superior King;25,2690;55,3086;6.200\n".encode()
    rows, info = S.parse_rows(data, "x.csv")
    assert rows[0]["lat"] == pytest.approx(25.269) and rows[0]["room"] == "HP Superior King"


def test_a_sheet_without_a_room_column_is_refused_with_its_headers():
    with pytest.raises(S.SheetError, match="room"):
        S.parse_rows(b"Hotel,Price\nA,1\n", "x.csv")


def test_xlsx_is_read():
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.active.append(["Hotel", "Room Type"])
    wb.active.append(["Rafee Hotel", "Deluxe King"])
    buf = io.BytesIO()
    wb.save(buf)
    rows, _ = S.parse_rows(buf.getvalue(), "r.xlsx")
    assert rows[0]["name"] == "Rafee Hotel"


@pytest.fixture(scope="module")
def sample():
    return S.ingest_sample()


def test_every_decision_follows_the_matcher_thresholds(sample):
    auto, gray = sample["thresholds"]["auto_merge"], sample["thresholds"]["review_floor"]
    for h in sample["hotels"]:
        top = h["candidates"][0] if h["candidates"] else None
        if h["decision"] == "matched":
            assert top["p"] >= auto
        if h["decision"] == "new":
            assert top is None or top["p"] < gray
        for room in h["rooms"]:
            assert (room["status"] == "mapped") == (room["room_id"] is not None)
            if room["status"] == "mapped":
                assert h["decision"] == "matched" and room["room_id"] in {o["room_id"] for o in h["options"]}


def test_listed_twice_is_symmetric(sample):
    for t in sample["listed_twice"]:
        named = [h for h in sample["hotels"] if h["name"] in t["as"]]
        assert len(named) == len(t["as"]) >= 2 and all(h.get("also_as") for h in named)


def test_ingest_never_reads_the_answer_key(monkeypatch):
    """An uploaded sheet (anything but Weaver's exact bytes) is resolved without touching any truth table."""
    data = S.sample_path("csv").read_bytes() + b"\n"
    real = pl.read_parquet

    def guarded(path, *a, **k):
        assert "truth" not in str(path), f"ingest read {path}"
        return real(path, *a, **k)
    monkeypatch.setattr(pl, "read_parquet", guarded)
    out = S.ingest(data, "upload.csv")
    assert out["check"] is None and out["summary"]["rows"] > 0


def test_upload_endpoint():
    r = client.post("/api/sheets/ingest", files={"file": ("r.csv", b"Hotel,Room,Lat,Lng\nRafee Hotel,Deluxe King,25.27,55.30\n", "text/csv")})
    assert r.status_code == 200 and r.json()["summary"]["names"] == 1
    bad = client.post("/api/sheets/ingest", files={"file": ("r.csv", b"just,one\n1,2\n", "text/csv")})
    assert bad.status_code == 400
    assert client.get("/api/sheets/sample").json()["synthetic"] is True
