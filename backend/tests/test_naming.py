"""Short-code naming: the generator's new mess, the matcher's short-code reading, and the room parser's hotel stripping."""
import polars as pl
import pytest

from samesame import config
from samesame.data.naming import short_code
from samesame.matching import hotels as hm
from samesame.matching import rooms as rm


def _p(name):
    return hm.prep([dict(listing_id=name, name=name, phone=None, address="", amenities=[], lat=25.0, lng=55.0, star=None, postcode=None,
                         supplier_id="mynah", checkin_time="14:00")])[0]


def test_short_codes_are_initials_of_the_leading_distinctive_words():
    assert short_code("Hilton Garden Inn Dubai Deira") == ("HGI Dubai Deira", "Hilton Garden Inn")
    assert short_code("Hyatt Place Dubai Baniyas Square") == ("HP Dubai Baniyas Square", "Hyatt Place")
    assert short_code("Jumeirah Marsa Al Arab")[0] == "JM Al Arab"          # never ends a code on a particle
    assert short_code("Radisson Royal") == ("RR Hotel", "Radisson Royal")
    assert short_code("Sadaf Hotel") is None                                # one distinctive word: no code


def test_matcher_writes_a_short_code_out_from_the_other_name():
    a, b = _p("HGI Dubai Deira"), _p("Hilton Garden Inn Dubai Deira")
    fa, fb, note = hm.expand(a, b)
    assert fa == fb and note == "HGI = Hilton Garden Inn"
    assert hm.expand(b, a)[2] == note
    f = hm.pair_features(a, b, float("nan"), (float("nan"), 0))
    assert f["short_code"] == 1.0 and f["name_set"] == 1.0
    assert hm.expand(_p("Al Rigga Hotel"), _p("Arabian Lodge"))[2] is None   # "al" is a word, not a code


def test_brand_rule_reads_the_written_out_name():
    a, b = _p("FP by Sheraton Bur Dubai"), _p("Four Points by Sheraton Bur Dubai")
    assert hm.conflict(a, b) is None
    assert hm.conflict(_p("Hyatt Place Dubai Deira"), _p("Hilton Garden Inn Dubai Deira")) is not None


@pytest.mark.parametrize("raw,names,expect", [
    ("Hyatt Place Superior King", ["HP Dubai Al Rigga", "Hyatt Place Dubai Al Rigga"], ("Superior", "King", None)),
    ("HP SUP KG CV", ["HP Dubai Al Rigga"], ("Superior", "King", "City")),
    ("Hilton Garden Inn Deluxe Twin", ["Hilton Garden Inn Dubai Deira"], ("Deluxe", "Twin", None)),   # not a "Garden" view
    ("Premier Inn Standard Double", ["Premier Inn Dubai Al Jaddaf"], ("Standard", "King", None)),
    ("Premier King", ["Landmark Premier Hotel"], ("Premier", "King", None)),                          # room word kept
])
def test_room_parser_removes_the_hotel_name(raw, names, expect):
    a = rm.parse_in_hotel(raw, names)
    assert (a["tier"], a["bed"], a["view"]) == expect


def test_a_room_named_only_by_its_hotel_goes_to_a_person_and_is_never_pooled():
    a = rm.parse_in_hotel("Hyatt Place Room", ["Hyatt Place Dubai Al Rigga"])
    assert a["confidence"] == rm.ONLY_HOTEL_CONFIDENCE and "person" in a["note"]
    rows = rm.map_rooms({"c1": [{"supplier_room_id": "x:R1", "raw_name": "Hyatt Place Room"}, {"supplier_room_id": "y:R1", "raw_name": "HP Room"}]},
                        {"c1": ["Hyatt Place Dubai Al Rigga", "HP Dubai Al Rigga"]})
    assert len({r["room_id"] for r in rows}) == 2 and all("unmapped" in r["room_id"] for r in rows)


def test_stripping_leaves_the_six_suppliers_own_room_names_alone():
    """Every room name the original feeds produce parses the same with or without the hotel's names."""
    sr = pl.read_parquet(config.BUILD / "supplier_rooms.parquet").to_dicts()
    lst = {l["listing_id"]: l["name"] for l in pl.read_parquet(config.BUILD / "hotel_listings.parquet").to_dicts()}
    short = {t["listing_id"] for t in pl.read_parquet(config.BUILD / "hotel_truth.parquet").to_dicts() if "short_code_name" in t["corruptions"]}
    changed = [r["raw_name"] for r in sr if r["listing_id"] not in short
               and {k: v for k, v in rm.parse(r["raw_name"]).items()} != {k: v for k, v in rm.parse_in_hotel(r["raw_name"], [lst[r["listing_id"]]]).items() if k != "hotel_words"}]
    assert not changed, changed[:5]


def test_short_code_listings_are_extra_rows_with_their_own_truth():
    truth = pl.read_parquet(config.BUILD / "hotel_truth.parquet").to_dicts()
    short = [t for t in truth if "short_code_name" in t["corruptions"]]
    assert short, "the generator should add short-code listings"
    lst = {l["listing_id"]: l for l in pl.read_parquet(config.BUILD / "hotel_listings.parquet").to_dicts()}
    for t in short:
        assert lst[t["listing_id"]]["n_images"] == 0
