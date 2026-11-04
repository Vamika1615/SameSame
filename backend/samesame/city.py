"""Everything that is specific to the city the demo runs in, in one place: Dubai, United Arab Emirates.

Dubai because it is where TBO is headquartered and one of the top destinations Indian agents sell
(see PROGRESS.md). The persona is unchanged: Meera, a travel agent in Surat, prices in INR.
Nothing else in the code should name a place; it reads it from here.
"""
NAME = "Dubai"
COUNTRY = "United Arab Emirates"
BBOX = (24.95, 55.05, 25.36, 55.45)          # south, west, north, east: Dubai's built-up area (OSM pull + basemap)
CORE = (25.2048, 55.2708)                     # Sheikh Zayed Road / Downtown; hotels further out are less likely to be kept

# The search the demo runs: an Indian agent's client wants a 4★+ hotel near Baniyas Square, Deira
DEMO_AREA = ("Baniyas Square Metro · Deira", 25.2697, 55.3078)   # densest hotel cluster in OSM; popular with Indian travellers
DEMO_RADIUS_M = 500
DEMO_KEEP_M = 900                              # curation always keeps every hotel this close to the demo area
DEMO_HOTEL_NAME = "Hyatt Place Dubai Baniyas Square"   # where the brief's golden-case offers live (found by name, like an agent would)

# Phones: +971 4 xxx xxxx landlines (Dubai area code 4), +971 5x mobiles
COUNTRY_CODE = "971"
LANDLINE_PREFIX = "4"

# How suppliers mangle names here (feeds.py) and how the matcher undoes it (matching/hotels.py)
CITY_ABBR = "DXB"
NAME_ABBR = [(NAME, CITY_ABBR), ("Hotel", "HTL"), ("Residence", "RESI"), ("Suites", "STES"), ("Apartments", "APTS")]
SUPPLIER_NAME_RULE = (r"\bAl (\w)", r"Al-\1", "al_hyphenated")         # one supplier writes "Al-Barsha" for "Al Barsha"
# corruption family only held-out families get, never seen in training: alternative transliterations
HOLDOUT_SPELLINGS = [("Jumeirah", "Jumeira"), ("Deira", "Dayra"), ("Dubai", "Dubayy"), ("Sheikh", "Shaikh"), ("Barsha", "Barshaa")]
MATCH_ABBR = {"dxb": "dubai", "dubayy": "dubai", "jumeira": "jumeirah", "dayra": "deira", "shaikh": "sheikh", "barshaa": "barsha"}
GENERIC_WORDS = {"dubai", "uae"}
LOCAL_CONTEXT = r"dubai|\buae\b|united arab emirates|emirates|[؀-ۿ]"   # a photo title placing it here
TRANSIT = "the Metro"
SHOPPING = "Dubai's malls"
MEETING_POINT = "Dubai Mall"

# Nightly rates for a standard room, 2 adults, INR (synthetic; Dubai runs pricier than Bangkok)
BASE_RATE = {2: 3200, 3: 5200, 4: 7200, 5: 15000}
BREAKFAST_PP = {2: 450, 3: 750, 4: 1050, 5: 1900}
WATER = ("Dubai Creek", "Creek")               # OSM waterway for the basemap; room view near it

# Wikimedia / Wikipedia lookups (backend/scripts/pull_wiki.py)
WIKIDATA_CITY = "Q612"
COMMONS_HOTELS = "Category:Hotels in Dubai"

# Sightseeing: the three products the demo walks through (hand-written variants in data/activities.py)
DEMO_QUERIES = [("desert safari", "Desert Safari"), ("burj khalifa", "Burj Khalifa"), ("dhow cruise", "Dhow Cruise")]
DEFAULT_ATTRACTION = "desert-safari"

# OpenStreetMap snapshot (backend/scripts/pull_osm.py)
OSM_AREA = 'area["admin_level"="4"]["name:en"~"^Dubai"]->.a;'   # Dubai Emirate (reference; the pull uses BBOX, Overpass is faster)
OSM_DISTRICT_LEVEL = "10"                                        # Dubai's communities: Al Barsha, Deira, Jumeirah, ...
# OSM's community polygons don't cover all of Dubai, so neighbours caught by BBOX are excluded explicitly
EXCLUDE_BOXES = [(25.29, 55.36, 25.40, 55.50, "Sharjah")]      # south, west, north, east
# One hotel mapped twice in OSM too far apart for the automatic rules; found because the matcher kept merging
# them, then checked by hand. Each pair is collapsed like any other OSM duplicate (listed in osm_duplicates).
OSM_KNOWN_DUPLICATES = [("Address Dubai Mall", "The Address - Dubai Mall"),
                        ("Sofitel Dubai The Palm Resort & Spa", "Sofitel The Palm Jumeirah"),
                        ("ibis One Central", "Ibis World Trade Centre"),
                        ("ibis hotel al Rigga", "IBIS Hotel Dubai Al Rigga")]
OSM_WATER = 'way["waterway"~"^(canal|river)$"]["name:en"~"Dubai Creek|Dubai Water Canal"]'
