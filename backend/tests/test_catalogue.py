"""Canon's catalogue: supplier sheets in any layout -> stored imports -> one catalogue with past inventory, decided by people."""
import io

import pytest
from fastapi.testclient import TestClient

from samesame.api.app import app
from samesame.ingest import layouts as L
from samesame.ingest import sheet as S

client = TestClient(app)

GRID = (
    "2027 USD Rates - Groups,,,,,,,\n"
    "BW May 14 - Aug 09 2026,,,,,,,\n"
    ",,,,,,,\n"
    "SEASIDE TEST RESORT,,,,,,,\n"
    "Code,Room Type,04 Jan 27 - 05 Feb 27,,06 Feb 27 - 28 Mar 27,,EXTRA ADULT,OCC MAX\n"
    ",,SUN-WED,THU-SAT,SUN-WED,THU-SAT,,\n"
    ",,SGL & DBL,SGL & DBL,SGL & DBL,SGL & DBL,,\n"
    "DK1F,Oceanfront King,544,600,552,608,NA,2\n"
    "DQ2F,Oceanfront Two Queen Beds,560,616,568,624,105,4\n"
    ",,,,,,,\n"
    "* 1-4 Nights: 20%,,,,,,,\n"
    "* 5+ Nights: 22%,,,,,,,\n"
    "* Rates must be marked up 25%,,,,,,,\n"
    "* An additional fee of $100 per room per night applies when the Minimum length of stay is not met,,,,,,,\n"
)


def test_dates_in_every_shape_suppliers_write_them():
    assert L.date_range("04 Jan 26 - 05 Feb 26") == ("2026-01-04", "2026-02-05")
    assert L.date_range("02 - 31 Jan 27") == ("2027-01-02", "2027-01-31")
    assert L.date_range("01- 10 Feb 27") == ("2027-02-01", "2027-02-10")
    assert L.date_range("May 14 - Aug 09, 2026") == ("2026-05-14", "2026-08-09")
    assert L.date_range("Dec 18, 2026 - Jan 02, 2027") == ("2026-12-18", "2027-01-02")
    assert L.date_range("Oceanfront King") is None and L.date_range("544") is None


def test_grid_layout_reads_seasons_weekdays_occupancy_extras_and_terms():
    r = L.parse(GRID.encode(), "test_resort_rates.csv")
    assert r["layout"] == "grid" and r["currency"] == "USD"
    [h] = r["hotels"]
    assert h["name"] == "SEASIDE TEST RESORT"
    assert len(h["rates"]) == 2 * 2 * 2                                   # rooms x seasons x weekday columns
    x = next(x for x in h["rates"] if x["room"] == "Oceanfront King" and x["season_from"] == "2027-02-06" and x["days"] == "Thu–Sat")
    assert x["price"] == 608 and x["occupancy"] == "SGL & DBL" and x["code"] == "DK1F"
    room = next(r for r in h["rooms"] if r["code"] == "DQ2F")
    assert room["extras"] == {"EXTRA ADULT": "105", "OCC MAX": "4"}
    kinds = {c["kind"]: c for c in h["conditions"]}
    assert kinds["markup"]["percent"] == 25 and kinds["min_stay"]["fee"] == 100
    assert sorted((c["min_nights"], c["percent"]) for c in h["conditions"] if c["kind"] == "discount") == [(1, 20), (5, 22)]
    assert kinds["booking_window"]["from"] == "2026-05-14"


def test_rotated_layout_and_unnamed_hotel():
    rows = ("BW: March 14 2026,,,,\n,,Suite Garden,,Suite River\n,,Pax DBL,Pax SGL,Pax DBL\n"
            "2026-03-11,2026-03-31,487.5,780,508.5\n2026-04-01,2026-04-30,450,720,471\n2026-05-01,2026-05-31,405,648,426\n")
    r = L.parse(rows.encode(), "HXA_GROUPS.csv")
    assert r["layout"] == "rotated"
    [h] = r["hotels"]
    assert h["name_from_file"] and {x["room"] for x in h["rates"]} == {"Suite Garden", "Suite River"}
    assert any("named after the file" in w for w in r["warnings"])


def test_a_file_with_no_rate_table_is_refused_clearly():
    with pytest.raises(L.SheetError):
        L.parse(b"just some,notes\nnothing,here\n", "notes.csv")


@pytest.fixture()
def plover():
    p = S.sample_path("xlsx", "plover")
    return p.read_bytes()


def test_import_lifecycle(plover):
    base = client.get("/api/catalogue/summary").json()
    assert base["imported_hotels"] == 0 and base["imports"]["applied"] == 0

    r = client.post("/api/imports/samples/plover").json()
    imp = r["import"]
    iid = imp["meta"]["id"]
    assert r["created"] and imp["meta"]["status"] == "draft" and imp["layout"] == "grid"
    assert client.post("/api/imports/samples/plover").json()["created"] is False          # same file: same import
    assert client.get("/api/catalogue/summary").json()["hotels_with_sheets"] == 0        # a draft changes nothing

    applied = client.post(f"/api/imports/{iid}/apply").json()
    assert applied["meta"]["status"] == "applied"
    s = client.get("/api/catalogue/summary").json()
    new = [h for h in applied["hotels"] if h["final"] and h["final"]["kind"] == "new"]
    matched = [h for h in applied["hotels"] if h["final"] and h["final"]["kind"] == "inventory"]
    assert s["imported_hotels"] == len(new) >= 1 and s["hotels_with_sheets"] == len(new) + len(matched)

    # an inventory hotel now carries the sheet's rates, mapped to its own rooms
    hid = matched[0]["final"]["id"]
    d = client.get(f"/api/catalogue/hotels/{hid}").json()
    assert d["kind"] == "inventory" and d["rates"] and all(x["room_id"] for x in d["rates"]) and d["conditions"]
    # a hotel the catalogue didn't have becomes one, with its rooms and rates
    nh = client.get(f"/api/catalogue/hotels/{new[0]['final']['id']}").json()
    assert nh["kind"] == "imported" and nh["rooms"] and len(nh["rates"]) == sum(r["rate_count"] for r in new[0]["rooms"])

    # what waits for a person, and deciding it (then undoing)
    waiting = [p for p in client.get("/api/catalogue/pending").json() if p["import_id"] == iid and p["kind"] == "hotel"]
    assert waiting
    w = waiting[0]
    target = w["candidates"][0]["cluster_id"]
    after = client.post(f"/api/imports/{iid}/decide", json={"sheet_id": w["sheet_id"], "kind": "hotel", "value": target}).json()
    h = next(h for h in after["hotels"] if h["sheet_id"] == w["sheet_id"])
    assert h["final"]["id"] == target and h["by_person"]
    assert client.get(f"/api/catalogue/hotels/{target}").json()["rates"]
    assert not any(p["sheet_id"] == w["sheet_id"] and p["kind"] == "hotel" for p in client.get("/api/catalogue/pending").json())
    client.post(f"/api/imports/decisions/undo/{h['audit_id']}")
    assert any(p["sheet_id"] == w["sheet_id"] for p in client.get("/api/catalogue/pending").json())

    # next year's sheet: the hotel the first import created is matched, not duplicated
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(io.BytesIO(plover))
    ws = wb.worksheets[0]
    ws["A1"] = "2028 USD Group Rates - Plover Travel (SYNTHETIC SAMPLE)"
    buf = io.BytesIO()
    wb.save(buf)
    r2 = client.post("/api/imports", files={"file": ("plover_2028.xlsx", buf.getvalue())}, data={"supplier": "Plover"}).json()
    iid2 = r2["import"]["meta"]["id"]
    again = next(h for h in r2["import"]["hotels"] if h["name"] == new[0]["name"])
    assert again["candidates"][0]["kind"] == "imported" and again["decision"] == "matched"
    client.post(f"/api/imports/{iid2}/apply")
    s2 = client.get("/api/catalogue/summary").json()
    assert s2["imported_hotels"] == s["imported_hotels"]                                   # no duplicate hotel
    assert len(client.get(f"/api/catalogue/hotels/{new[0]['final']['id']}").json()["sources"]) == 2

    # removing the first import takes its hotels and rates back out; restoring makes it a draft again
    client.post(f"/api/imports/{iid}/remove")
    s3 = client.get("/api/catalogue/summary").json()
    assert s3["imports"]["removed"] == 1 and s3["sheet_rates"] < s2["sheet_rates"]
    assert client.post(f"/api/imports/{iid}/restore").json()["meta"]["status"] == "draft"


def test_upload_errors_are_clear():
    bad = client.post("/api/imports", files={"file": ("notes.csv", b"hello,world\n1,2\n")})
    assert bad.status_code == 400 and bad.json()["detail"]
    assert client.get("/api/imports/imp-nope").status_code == 404
    assert client.get("/api/catalogue/hotels/nope").status_code == 404
