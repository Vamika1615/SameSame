"""One-time pull of real, freely licensed photos and descriptions (needs network; the demo never does).

    .venv/bin/python backend/scripts/pull_wiki.py

Writes (all committed, so the demo stays offline):
  data/raw/wiki/photos/*.jpg     640 px thumbnails from Wikimedia Commons
  data/raw/wiki/photos.json      one row per photo: subject, kind (hotel | stock_room | stock_pool | stock_lobby |
                                 attraction), title, author, licence, licence URL, source page
  data/raw/wiki/descriptions.json  Wikipedia summaries (CC BY-SA 4.0) for attractions and hotels that have an article

Only CC0, CC BY, CC BY-SA and public-domain files are kept. Hotel photos are attached to an OSM hotel only by
an explicit OSM/Wikidata link, or a Commons category / file title that names the hotel (checked below).
"""
import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "wiki"
PHOTOS = OUT / "photos"
UA = {"User-Agent": "SameSame-hackathon/0.1 (offline demo; contact aryandahiya1706@gmail.com)"}
FREE = re.compile(r"^(cc0|cc[- ]by(-sa)?( \d\.\d)?|public domain|pd)", re.I)
WIDTH = 500                       # a standard Wikimedia thumbnail step (pre-rendered, fast)
ASOK = (13.7370, 100.5603)

# attraction id -> English Wikipedia article (descriptions + the article's own photos)
ARTICLES = {
    "grand-palace": "Grand Palace", "wat-pho": "Wat Pho", "wat-arun": "Wat Arun",
    "floating-market": "Damnoen Saduak floating market", "maeklong": "Maeklong Railway Market",
    "ayutthaya": "Ayutthaya Historical Park", "skywalk": "King Power Mahanakhon", "baiyoke": "Baiyoke Tower II",
    "dinner-cruise": "Chao Phraya River", "sea-life": "Sea Life Bangkok Ocean World", "safari-world": "Safari World",
    "dream-world": "Dream World (Thailand)", "calypso": "Asiatique The Riverfront", "muay-thai": "Rajadamnern Stadium",
    "jim-thompson": "Jim Thompson House", "chatuchak": "Chatuchak Weekend Market", "chinatown-food": "Yaowarat Road",
    "tuktuk-night": "Auto rickshaw", "khlong-boat": "Long-tail boat", "cooking-class": "Thai cuisine",
    "bang-krachao": "Bang Krachao", "coral-island": "Ko Lan", "river-kwai": "Death Railway",
    "asiatique-wheel": "Asiatique The Riverfront", "wat-pho-massage": "Thai massage",
}
STOCK = {"stock_room": ("Category:Hotel rooms", 90), "stock_pool": ("Category:Hotel swimming pools", 80),
         "stock_lobby": ("Category:Hotel lobbies", 47)}
GENERIC = {"the", "hotel", "hotels", "bangkok", "by", "and", "a", "resort", "boutique", "residence", "suites", "inn", "thailand", "of"}


def get(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode({**params, "format": "json"})
    for attempt in range(4):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read())
        except Exception as e:                       # noqa: BLE001  transient API errors: back off and retry
            if attempt == 3:
                raise
            print("  retry", e); time.sleep(3 * (attempt + 1))


def summary(title: str) -> dict:
    """Wikipedia summary; if the title doesn't exist, use the top search hit instead (logged)."""
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/"
    try:
        return get(url + urllib.parse.quote(title.replace(" ", "_")))
    except Exception:                                    # noqa: BLE001
        hits = get("https://en.wikipedia.org/w/api.php", {"action": "query", "list": "search", "srsearch": title, "srlimit": 1})
        hits = hits["query"]["search"]
        if not hits:
            print("  no article for", title); return {}
        print("  article", title, "->", hits[0]["title"])
        return get(url + urllib.parse.quote(hits[0]["title"].replace(" ", "_")))


def commons(params):
    return get("https://commons.wikimedia.org/w/api.php", params)


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


def core(s):
    return {t for t in norm(s).split() if t not in GENERIC}


def strip_html(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def file_info(titles: list[str]) -> list[dict]:
    """Thumbnail URL + licence metadata for File: titles (batches of 40)."""
    out = []
    for i in range(0, len(titles), 40):
        r = commons({"action": "query", "titles": "|".join(titles[i:i + 40]), "prop": "imageinfo",
                     "iiprop": "url|extmetadata|size|mime", "iiurlwidth": WIDTH})
        for p in r["query"]["pages"].values():
            ii = (p.get("imageinfo") or [None])[0]
            if not ii or ii.get("mime") not in ("image/jpeg", "image/png"):
                continue
            md = ii.get("extmetadata", {})
            lic = strip_html(md.get("LicenseShortName", {}).get("value", ""))
            if not FREE.match(lic) or ii["width"] < 500 or ii["width"] < ii["height"] * 0.9:   # free, big enough, landscape-ish
                continue
            out.append({"title": p["title"], "thumb": ii.get("thumburl") or ii["url"], "source": ii["descriptionurl"],
                        "author": strip_html(md.get("Artist", {}).get("value", ""))[:120] or "unknown",
                        "license": lic, "license_url": md.get("LicenseUrl", {}).get("value", "")})
    return out


def members(cat: str, kind: str = "file", limit: int = 500) -> list[str]:
    out, cont = [], {}
    while len(out) < limit:
        r = commons({"action": "query", "list": "categorymembers", "cmtitle": cat, "cmtype": kind, "cmlimit": 500, **cont})
        out += [m["title"] for m in r["query"]["categorymembers"]]
        if "continue" not in r:
            break
        cont = r["continue"]
    return out[:limit]


def download(rows: list[dict], kind: str, subject: str, n: int, seen: set) -> list[dict]:
    kept = []
    for row in rows:
        if len(kept) >= n or row["title"] in seen:
            continue
        name = re.sub(r"[^A-Za-z0-9]+", "_", row["title"][5:])[:80].strip("_") + ".jpg"
        dest = PHOTOS / name
        if not dest.exists():
            data = None
            for attempt in range(3):
                try:
                    data = urllib.request.urlopen(urllib.request.Request(row["thumb"], headers=UA), timeout=60).read()
                    break
                except Exception as e:                   # noqa: BLE001  thumbnail server hiccup: retry, then skip the file
                    print("  thumb retry", row["title"], e); time.sleep(2 * (attempt + 1))
            if data is None:
                continue
            dest.write_bytes(data)
            time.sleep(0.1)
        seen.add(row["title"])
        kept.append({**{k: row[k] for k in ("title", "author", "license", "license_url", "source")}, "file": name, "kind": kind,
                     "subject": subject})
    return kept


def osm_hotels() -> list[dict]:
    raw = json.loads((ROOT / "data" / "raw" / "osm" / "hotels_raw.json").read_text(encoding="utf-8"))["elements"]
    out = []
    for el in raw:
        t = el.get("tags", {})
        c = el.get("center") or el
        name = t.get("name:en") or t.get("name")
        if name and "lat" in c:
            out.append({"osm_id": f"{el['type']}/{el['id']}", "name": name, "lat": c["lat"], "lng": c["lon"], "tags": t})
    return out


def dist_m(a, b, c, d):
    from math import asin, cos, radians, sin, sqrt
    p1, p2 = radians(a), radians(c)
    h = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(d - b) / 2) ** 2
    return 2 * 6_371_000 * asin(sqrt(h))


def best_osm(name: str, hotels, near=None, max_m=250) -> dict | None:
    """OSM hotel whose distinctive words match `name` exactly (or are a superset with >= 2 shared words)."""
    want = core(name)
    if not want:
        return None
    cands = []
    for h in hotels:
        if near and dist_m(near[0], near[1], h["lat"], h["lng"]) > max_m:
            continue
        have = core(h["name"])
        if have == want or (len(want & have) >= 2 and (want <= have or have <= want)):
            cands.append(h)
    return cands[0] if len(cands) == 1 else None             # ambiguous -> no photo rather than a wrong one


# Stock photos must describe the room / pool / lobby itself; event, archive and people shots are out.
STOCK_TITLE = {"stock_room": r"room|suite|bed", "stock_pool": r"pool|swimming", "stock_lobby": r"lobby|reception|foyer"}
STOCK_BAD = (r"postcard|vintage|card|advert|19[0-8]\d|18\d\d|meeting|conference|visit|team|staff|delegat|party|wedding|construction|"
             r"damage|abandon|ruin|demoli|businessman|children|child|baboon|monkey|people|\bman\b|woman|girl|boy|dog|cat\b|president|"
             r"minister|interview")
# Removed after a visual review of every remaining stock photo (people in shot, an elephant, snow, derelict, too dark)
STOCK_REJECTED = set(["Breakfast_serving_room_in_hotel_jpg.jpg", "Hotel_Room_37456623550_jpg.jpg", "Hotel_Room_Lamp_46385514474_jpg.jpg", "Hotel_room_2086685536_jpg.jpg", "Inside_a_hotel_room_20100911_120542_jpg.jpg", "Luxurious_rooms_jpg.jpg", "Alpenresort_Schwarz_interior_pool_24723499948_png.jpg", "Bavaro_Iberostar_pool_bar_JPG.jpg", "Current_situation_of_the_Grande_Hotel_high_polluted_swimming_pool_JPG.jpg", "Elephant_Mole_Motel_pool_jpg.jpg", "Four_seasons_pool_in_buenos_aires_jpg.jpg", "Guitar_Pool_geograph_org_uk_1658918_jpg.jpg", "AcropoleHotelKhartoum_Lobby_RomanDeckert02022016_jpg.jpg", "Detalles_Lobby_Hotel_Contempo_panoramio_jpg.jpg", "Grande_Hotel_interior_of_original_lobby_on_the_ground_floor_of_block_A_March_201.jpg", "IMG_20170717_hotel_mirage_lobby_struga_2017_jpg.jpg", "Lobby_Testing_21174745_jpg.jpg", "Bed_Room_Arcadia_hotel_fire_LCCN2014694942_jpg.jpg", "GD_Guangdong_Guangzhou_Huangpu_MUSTEL_Hotel_Knowledge_City_bed_room_double_sigle.jpg", "GD_Guangdong_Guangzhou_Huangpu_MUSTEL_Hotel_Knowledge_City_bed_room_double_sigle.jpg", "GD_Guangdong_Guangzhou_Huangpu_MUSTEL_Hotel_Knowledge_City_bed_room_double_sigle.jpg", "Gladstone_Hotel_Come_up_to_my_room_floating_bed_2D_version_jpg.jpg", "Hotel_Room_Bed_40144499253_jpg.jpg", "Hotel_room_in_Mumbai_238516872_jpg.jpg", "Pensacola_Hotel_Room_Fun_July_2017_Lounging_jpg.jpg", "Poshekhonye_Soga_Hotel_five_bed_room_DSCF5433_JPG.jpg", "Restaurant_room_of_Amantaka_luxury_Resort_Hotel_in_Luang_Prabang_Laos_jpg.jpg", "Room_Hotel_Sofitel_Strasbourg_jpg.jpg", "Gladstone_Hotel_Come_up_to_my_room_floating_bed_jpg.jpg", "MC_Macau_Cotai_Grand_Lisboa_Palace_hotel_two_beds_room_14pm_afternoon_November_2.jpg", "MC_Macau_Cotai_Grand_Lisboa_Palace_hotel_two_beds_room_14pm_afternoon_November_2.jpg", "MC_Macau_Cotai_Grand_Lisboa_Palace_hotel_two_beds_room_14pm_afternoon_November_2.jpg", "Typical_bed_room_new_Hotel_Waldorf_Toledo_Ohio_DPLA_66b7a28c328211b088004dc3a322.jpg", "Typical_bed_room_new_Hotel_Waldorf_Toledo_Ohio_DPLA_66b7a28c328211b088004dc3a322.jpg", "Banquet_Room_interior_Brother_Hotel_20130212_jpg.jpg", "Belmond_Grand_Hotel_Europe_Saint_Petersburg_sitting_room_stairways_jpg.jpg", "Hotel_Room_Interior_2026_10_13_3_jpg.jpg", "Hotel_room_window_Guoman_Tower_Hotel_2014_03_05_jpg.jpg", "Interior_of_a_room_at_City_Lodge_OR_Tambo_Airport_hotel_February_2025_jpg.jpg", "Skyline_dining_room_Terrace_Plaza_Hotel_Cincinnati_Ohio_79213_jpg.jpg", "Trump_Hotel_dinner_room_service_jpg.jpg", "University_Arms_Hotel_room_interior_1999_jpg.jpg", "Belmond_Grand_Hotel_Europe_Saint_Petersburg_sitting_room_2_jpg.jpg", "Burgh_Island_Hotel_Dining_Room_geograph_6005073_jpg.jpg", "Dombay_Room_interior_Soviet_modernism_Karachay_Cherkessia_jpg.jpg", "GD_Zhaoqing_Pearl_Hotel_Starlake_interior_hall_waiting_room_July_2012_JPG.jpg", "Room_Hotel_Florence_San_Diego_Calif_jpg.jpg", "Room_in_Hotel_jpg.jpg", "Wyndham_New_Orleans_at_Canal_Place_hotel_room_2002_02_jpg.jpg", "Boscolo_Hotel_Atlantic_Deluxe_Room_Nice_panoramio_jpg.jpg", "Deluxe_room_jpg.jpg", "Deluxe_room_hotels_in_gili_trawangan_jpg.jpg", "Marquette_Inn_Room_Service_Menu_DPLA_a2d923c1a44a85dd32b6905102c6d83c_page_2_jpg.jpg", "Marquette_Inn_Room_Service_Menu_DPLA_a2d923c1a44a85dd32b6905102c6d83c_page_3_jpg.jpg", "Marquette_Inn_Room_Service_Menu_DPLA_a2d923c1a44a85dd32b6905102c6d83c_page_4_jpg.jpg", "Astoria_Hotel_bedroom_in_the_Royal_Suite_png.jpg", "Canopy_bed_and_wardrobes_in_Khan_Pool_Suite_at_Amantaka_luxury_Resort_Hotel_in_L.jpg", "Canopy_bed_of_Amantaka_Suite_in_Amantaka_luxury_Resort_Hotel_in_Luang_Prabang_La.jpg", "Canopy_bed_of_Khan_Pool_Suite_in_Amantaka_luxury_Resort_Hotel_in_Luang_Prabang_L.jpg", "Suite_bedroom_at_Union_Station_Nashville_jpg.jpg", "Bedrooms_Titanic_Hotel_Guest_Suite_Bathroom_37604041486_jpg.jpg", "Broadmoor_Hotel_suite_jpg.jpg", "Copper_Point_Resort_2_Bedroom_Loft_Suite_9611675574_jpg.jpg", "COVID_19_Swimming_Pool_Measures_Cactus_Hotel_Rhodes_3_September_2024_jpg.jpg", "Hotel_Swimming_Pool_geograph_org_uk_3353507_jpg.jpg", "JW_Marriott_Hotel_New_Orleans_Swimming_Pool_2003_jpg.jpg", "Miami_Swimming_Pool_Hotel_Royal_Palm_jpg.jpg", "Miami_Beach_Swimming_pool_Ocean_Haven_Hotel_01_jpg.jpg", "Miami_Beach_Swimming_pool_Prince_Michael_Hotel_jpg.jpg", "Miami_Beach_Swimming_pool_The_Delmonico_Hotel_01_jpg.jpg", "P_rtschach_Hauptstrasse_161_P_rtschacher_Hof_Swimming_Pool_21012016_0244_jpg.jpg", "Swimming_Pool_in_a_hotel_in_Tamil_Nadu_03_jpg.jpg", "Havana_Pool_Hotel_Nacional_jpg.jpg", "Miami_Beach_Swimming_Pool_The_Sands_Hotel_jpg.jpg", "Miami_Beach_Swimming_pool_Atlantis_Hotel_jpg.jpg", "Miami_Beach_Swimming_pool_Coral_Reef_Hotel_jpg.jpg", "Miami_Beach_Swimming_pool_Strath_Haven_Hotel_jpg.jpg", "Miami_Beach_Swimming_pool_The_Delmonico_Hotel_02_jpg.jpg", "Miami_Beach_Swimming_pool_The_Poinciana_Hotel_jpg.jpg", "Poinsett_Hotel_Rooftop_swimming_pool_jpg.jpg", "Shillingford_Bridge_Hotel_swimming_pool_geograph_org_uk_1295735_jpg.jpg", "Swimming_pool_Traders_Hotel_Singapore_20070123_01_jpg.jpg", "Swimming_pool_Traders_Hotel_Singapore_20070123_05_jpg.jpg", "Swimming_pool_in_a_Hotel_of_Guatemala_jpg.jpg", "Bathroom_of_Khan_Pool_Suite_in_Amantaka_luxury_Resort_Hotel_in_Luang_Prabang_Lao.jpg", "Bathtub_of_Khan_Pool_Suite_in_Amantaka_luxury_Resort_Hotel_in_Luang_Prabang_Laos.jpg", "Indoor_pool_and_shower_of_spa_at_Amantaka_luxury_Resort_Hotel_in_Luang_Prabang_L.jpg", "Indoor_pool_and_showers_of_the_spa_at_Amantaka_luxury_Resort_Hotel_in_Luang_Prab.jpg", "Indoor_pool_of_spa_with_open_door_at_Amantaka_luxury_Resort_Hotel_in_Luang_Praba.jpg", "Olympic_sized_Swimming_Pool_and_Piscine_for_Kids_Eden_Roc_Resort_Hotel_Rhodes_24.jpg", "Swimming_pool_of_Unzen_Resort_Hotel_jpg.jpg", "Tachibana_Bay_and_swimming_pool_of_Unzen_Resort_Hotel_2_jpg.jpg", "The_pool_room_inside_Manor_Resort_jpg.jpg", "Fullerton_Bay_Hotel_rooftop_swimming_pool_20170306_jpg.jpg", "Infinity_Pool_at_Marina_Bay_Sands_SkyPark_Singapore_Ank_Kumar_Infosys_Limited_01.jpg", "Infinity_Pool_at_Marina_Bay_Sands_SkyPark_Singapore_Ank_Kumar_Infosys_Limited_02.jpg", "Infinity_Pool_at_Marina_Bay_Sands_SkyPark_Singapore_Ank_Kumar_Infosys_Limited_03.jpg", "Infinity_Pool_at_Marina_Bay_Sands_SkyPark_Singapore_Ank_Kumar_Infosys_Limited_04.jpg", "Infinity_Pool_at_Marina_Bay_Sands_SkyPark_Singapore_Ank_Kumar_Infosys_Limited_05.jpg", "Infinity_Pool_at_Marina_Bay_Sands_SkyPark_Singapore_Ank_Kumar_Infosys_Limited_06.jpg", "Infinity_Pool_at_Marina_Bay_Sands_SkyPark_Singapore_Ank_Kumar_Infosys_Limited_07.jpg", "Infinity_Pool_at_Marina_Bay_Sands_SkyPark_Singapore_Ank_Kumar_Infosys_Limited_08.jpg", "Le_Pavillon_Hotel_New_Orleans_rooftop_pool_jpg.jpg", "Marina_Bay_Sands_Rooftop_SkyPark_Infinity_Pool_view_from_the_side_jpg.jpg", "New_Orleans_Rooftop_Pool_All_Mine_June_2012_jpg.jpg", "Rio_hotel_upstairs_pool_jpeg.jpg", "Rio_hotel_upstairs_pool_14_14_20_881000_jpeg.jpg", "Rio_hotel_upstairs_pool_14_14_35_177000_jpeg.jpg", "Rio_hotel_upstairs_pool_14_14_49_144000_jpeg.jpg", "Rooftop_Pool_Tulum_Quintana_Roo_Mexico_June_2024_jpg.jpg", "Rooftop_Pool_in_Australian_Drought_465917674_jpg.jpg", "Rooftop_pool_Nairobi_20250808_P1048999_jpg.jpg", "Rooftop_pool_4628729613_jpg.jpg", "Schloss_Elmau_Rooftop_Pool_jpg.jpg", "The_Standard_Down_Town_Los_Angeles_rooftop_pool_2014_04_28_22_19_42_by_Blake_Pat.jpg", "Westin_New_Orleans_Canal_Place_rooftop_pool_jpg.jpg", "DZ3_0919_Night_reflections_over_Pattaya_city_lights_mirrored_in_a_rooftop_infini.jpg", "Pool_mit_Blick_zum_S_ntis_jpg.jpg"])
ATTRACTION_REJECTED = set(["Arrival_of_the_King_of_Siam_at_the_Temple_of_Sleeping_Idol_Wellcome_L0020127_jpg.jpg", "Caribou_from_Wagon_Trails_jpg.jpg", "Koh_Larn_Island_from_the_Bird_and_Bees_resort_by_Don_Ramey_Logan_jpg.jpg", "Bridge_over_the_River_Kwai_Art_IWMARTLD6035_jpg.jpg"])   # visual review: archive crowd photo, a reindeer, a satellite map, a drawing
GENERIC_TOPICS = {"tuktuk-night", "khlong-boat", "cooking-class", "wat-pho-massage", "dinner-cruise"}
THAI = re.compile(r"bangkok|thailand|\bthai\b|krung ?thep|[\u0e00-\u0e7f]", re.I)


def vet(photos: list[dict], hotels: list[dict]) -> list[dict]:
    """Precision first: a photo is labelled as showing a place only if its own title says so.

    hotel:      the title contains the hotel's distinctive name as a phrase AND places it in Bangkok / Thailand
                (Commons categories and name searches also return the street outside, a namesake in Oslo, a jet)
    attraction: articles about a whole topic (tuk-tuks, Thai massage) keep only Thai photos, relabelled as stock
    """
    names = {h["osm_id"]: h["name"] for h in hotels}
    out = []
    for p in photos:
        t = p["title"]
        if p["kind"] == "hotel":
            phrase = " ".join(w for w in norm(names.get(p["subject"], "")).split() if w not in GENERIC)
            if not phrase or f" {phrase} " not in f" {norm(t)} " or not THAI.search(t) or re.search(r"demolish|construction|logo", t, re.I):
                continue
        elif p["kind"] in STOCK_TITLE:
            if (not re.search(STOCK_TITLE[p["kind"]], t, re.I) or re.search(STOCK_BAD, t, re.I)
                    or p["file"] in STOCK_REJECTED):
                continue
        elif p["kind"] == "attraction" and p["file"] in ATTRACTION_REJECTED:
            continue
        elif p["kind"] == "attraction" and p["subject"] in GENERIC_TOPICS:
            if not THAI.search(t):
                continue
            p = {**p, "kind": "stock_activity"}
        out.append(p)
    return out


def main():
    PHOTOS.mkdir(parents=True, exist_ok=True)
    hotels = osm_hotels()
    seen: set = set()
    photos, desc, links = [], {}, []

    # 1. hotels with an explicit Wikidata link (OSM tag) or Wikidata coordinates nearby
    q = """SELECT ?h ?hLabel ?lat ?lng ?img ?cat ?article WHERE { ?h wdt:P31 ?t. VALUES ?t {wd:Q27686 wd:Q1631129 wd:Q5056668 wd:Q63099748}
      ?h wdt:P131* wd:Q1861; p:P625/psv:P625 [wikibase:geoLatitude ?lat; wikibase:geoLongitude ?lng].
      OPTIONAL{?h wdt:P18 ?img} OPTIONAL{?h wdt:P373 ?cat}
      OPTIONAL{?article schema:about ?h; schema:isPartOf <https://en.wikipedia.org/>}
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }"""
    wd = get("https://query.wikidata.org/sparql", {"query": q})["results"]["bindings"]
    by_q: dict = {}
    for x in wd:
        by_q.setdefault(x["h"]["value"].rsplit("/", 1)[1], x)
    osm_by_q = {h["tags"]["wikidata"]: h for h in hotels if "wikidata" in h["tags"]}
    hotel_cats: dict[str, set] = {}
    for qid, x in by_q.items():
        h = osm_by_q.get(qid) or best_osm(x["hLabel"]["value"], hotels, (float(x["lat"]["value"]), float(x["lng"]["value"])))
        if not h:
            continue
        hotel_cats.setdefault(h["osm_id"], set())
        if "cat" in x:
            hotel_cats[h["osm_id"]].add("Category:" + x["cat"]["value"])
        if "img" in x:
            hotel_cats[h["osm_id"]].add("File:" + urllib.parse.unquote(x["img"]["value"].rsplit("/", 1)[1]))
        if "article" in x:
            links.append((h["osm_id"], urllib.parse.unquote(x["article"]["value"].rsplit("/", 1)[1])))
    for h in hotels:
        t = h["tags"]
        if t.get("wikimedia_commons"):
            hotel_cats.setdefault(h["osm_id"], set()).add(t["wikimedia_commons"])
        if t.get("wikipedia", "").startswith("en:"):
            links.append((h["osm_id"], t["wikipedia"][3:]))
    # 2. Commons "Hotels in Bangkok" subcategories, matched to OSM by name
    for cat in members("Category:Hotels in Bangkok", "subcat"):
        h = best_osm(re.sub(r"\s*\(.*\)", "", cat.split(":", 1)[1]), hotels)
        if h:
            hotel_cats.setdefault(h["osm_id"], set()).add(cat)
    # 3. demo area: file titles that name the hotel (all distinctive words must appear in the title)
    for h in hotels:
        if dist_m(*ASOK, h["lat"], h["lng"]) > 1200 or h["osm_id"] in hotel_cats or len(core(h["name"])) < 2:
            continue
        r = commons({"action": "query", "list": "search", "srsearch": h["name"], "srnamespace": 6, "srlimit": 10})
        hits = [s["title"] for s in r["query"]["search"] if core(h["name"]) <= core(s["title"])]
        if hits:
            hotel_cats[h["osm_id"]] = set(hits[:4])
    print("hotels with a real photo source:", len(hotel_cats))
    for osm_id, srcs in sorted(hotel_cats.items()):
        files = []
        for s in sorted(srcs):
            files += [s] if s.startswith("File:") else members(s, "file", 40)
        photos += download(file_info(files), "hotel", osm_id, 4, seen)

    # 4. stock photos: real hotel rooms / pools / lobbies, shown as "stock photo, not this hotel"
    for kind, (cat, n) in STOCK.items():
        files = members(cat, "file", 400)
        photos += download(file_info(files), kind, kind, n, seen)
        print(kind, sum(p["kind"] == kind for p in photos))

    # 5. attractions: Wikipedia summary + up to 3 photos used in the article
    for aid, title in ARTICLES.items():
        s = summary(title)
        title = s.get("title", title)
        desc[aid] = {"text": s.get("extract", ""), "title": s.get("title", title),
                     "source": s.get("content_urls", {}).get("desktop", {}).get("page", ""),
                     "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/"}
        r = get("https://en.wikipedia.org/w/api.php", {"action": "query", "titles": title, "prop": "images", "imlimit": 50})
        files = [i["title"] for p in r["query"]["pages"].values() for i in p.get("images", [])
                 if re.search(r"\.(jpe?g)$", i["title"], re.I) and not re.search(r"map|logo|flag|icon|seal", i["title"], re.I)]
        photos += download(file_info(files), "attraction", aid, 3, seen)
    for osm_id, title in links:
        s = summary(title)
        if s.get("extract"):
            desc[osm_id] = {"text": s["extract"], "title": s.get("title", title),
                            "source": s.get("content_urls", {}).get("desktop", {}).get("page", ""),
                            "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/"}

    photos = vet(photos, hotels)
    (OUT / "photos.json").write_text(json.dumps(photos, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "descriptions.json").write_text(json.dumps(desc, indent=1, ensure_ascii=False), encoding="utf-8")
    kinds = {}
    for p in photos:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    print("photos:", kinds, "hotels with own photos:", len({p["subject"] for p in photos if p["kind"] == "hotel"}),
          "descriptions:", len(desc))


STOCK_SEARCH = {"stock_room": ["hotel room bed", "hotel room interior", "deluxe room hotel", "hotel suite bedroom"],
                "stock_pool": ["hotel swimming pool", "hotel pool resort", "rooftop pool hotel"]}


def more_stock(per_query: int = 60):
    """Top up the stock pool with Commons file searches (same licence rules and vetting)."""
    photos = json.loads((OUT / "photos.json").read_text(encoding="utf-8"))
    seen = {p["title"] for p in photos}
    for kind, queries in STOCK_SEARCH.items():
        for q in queries:
            r = commons({"action": "query", "list": "search", "srsearch": f"{q} filetype:bitmap", "srnamespace": 6, "srlimit": per_query})
            files = [x["title"] for x in r["query"]["search"]]
            photos += download(file_info(files), kind, kind, per_query, seen)
    photos = vet(photos, osm_hotels())
    (OUT / "photos.json").write_text(json.dumps(photos, indent=1, ensure_ascii=False), encoding="utf-8")
    print({k: sum(p["kind"] == k for p in photos) for k in ("stock_room", "stock_pool", "stock_lobby")})


def revet():
    """Re-apply vet() to an existing download and delete files no longer used (no network)."""
    photos = vet(json.loads((OUT / "photos.json").read_text(encoding="utf-8")), osm_hotels())
    (OUT / "photos.json").write_text(json.dumps(photos, indent=1, ensure_ascii=False), encoding="utf-8")
    keep = {p["file"] for p in photos}
    for f in PHOTOS.iterdir():
        if f.name not in keep:
            f.unlink()
    print("kept", len(photos), "photos;", len({p["subject"] for p in photos if p["kind"] == "hotel"}), "hotels with their own photos")


if __name__ == "__main__":
    sys.exit(revet() if "--vet-only" in sys.argv else more_stock() if "--more-stock" in sys.argv else main())
