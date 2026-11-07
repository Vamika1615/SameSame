# DATA: what is real, what is synthetic, what is fixed

**City: Dubai, United Arab Emirates.**
- Every place-specific value lives in `backend/samesame/city.py` (backend) and `frontend/src/lib/city.ts` (frontend).
- We chose Dubai because TBO is headquartered there and it's one of the top destinations Indian agents sell. The persona is unchanged: Meera, a travel agent in Surat, quoting INR.

**Building the data.** Run `python3 -m samesame.pipeline` from `backend/`. `start.py` runs it automatically whenever a generator, matcher or eval file changes. It's deterministic from `config.SEED = 20261104` and takes about 22 s.

**One-time network steps** (outputs are committed, so teammates never re-download):
- `backend/scripts/pull_osm.py`: the OpenStreetMap snapshot.
- `backend/scripts/pull_wiki.py`: photos and Wikipedia text. Use `--city-only` when switching city.
- The first build caches the MiniLM model (87 MB) in `data/models/`.

Live counts are always in `GET /api/meta` → `build.counts`.

## Real
| What | Source | Count |
|---|---|---|
| Hotel names + coordinates | OpenStreetMap snapshot 2026-11-04 (Dubai bounding box, Sharjah excluded), ODbL | 300 curated from 779 named hotels |
| Stars / phone / street where OSM has them | OSM tags | 84 / 131 / 157 of 300 |
| Communities (Al Rigga, Deira, Jumeirah, …) | OSM admin level 10 boundaries | 115 polygons |
| Reference data on each hotel page (address, phone, website, stars) | the same OSM snapshot, unmodified | all named hotels |
| Hard negatives: same brand, different real hotels, < 3 km apart | OSM | 42 pairs, e.g. Flora Hotel Apts. vs Flora Al Souq Hotel, 198 m apart |
| Photos of the actual hotel | Wikimedia Commons, CC0 / CC BY / CC BY-SA / public domain, credited | 6 photos of 3 hotels (Raffles, Atlantis, Carlton Tower) |
| Photos of the attraction | Wikimedia Commons, via its Wikipedia article or a Commons search | 42 photos, plus 7 local photos labelled stock, across 22 of 25 attractions |
| Stock photos (real rooms, pools, lobbies elsewhere, labelled "STOCK PHOTO · NOT THIS EXACT PLACE") | Wikimedia Commons, same licences, every one reviewed by eye | 141 rooms, 68 pools, 16 lobbies |
| Descriptions | Wikipedia summaries, CC BY-SA 4.0, linked | 25 attractions + 20 hotels |

**Photo vetting** (`pull_wiki.vet()`, precision first):
- A hotel photo must name the hotel as a phrase *and* place it in Dubai or the UAE.
- Every attraction photo was reviewed by eye. 16 Dubai rejects (archive shots, crowds and dignitaries, a car exhibit, military helicopters, coffee and cake for Dubai Opera) are listed in the script.
- A hotel description must be an article about that hotel. The search fallback had attached *Downtown Dubai* to a hotel, and that rule removed it.

**OSM duplicates collapsed before anything else:** 40 of them, listed in `osm_duplicates.parquet`. The automatic rules are:
- the same name within 250 m;
- the same distinctive words within 120 m;
- same brand with one name contained in the other, within 80 m (for example "rove hotel" / "Rove City Walk" at 6 m, or "Voco Dubai" / "Voco Hotel and Nassima Towers" at 14 m), unless one is the apartments and the other the hotel.

Names with different numbers ("Silver Sands 1" / "2") are never duplicates.

Four more are a short list in `city.py`, checked by hand. Each pair was mapped too far apart for the rules, and was found because the matcher kept merging them: "Address Dubai Mall" / "The Address - Dubai Mall" (721 m), Sofitel The Palm, ibis One Central / World Trade Centre, and "ibis hotel al Rigga" / "IBIS Hotel Dubai Al Rigga" (604 m).

## Synthetic (generator inputs in `backend/samesame/data/`, city values in `city.py`)
- **Base attributes:**
  - stars where OSM and brand are silent (121; a brand map covers 95)
  - phone (169, as +971 4 …)
  - pool, family rooms, rates, amenities, check-in time
- **Rates:**
  - Nightly rate for a standard room, 2 adults, by star: ₹3,200 / ₹5,200 / ₹7,200 / ₹15,000, times centrality.
  - The breakfast fill cost is the catalogue median of ₹580 per person per night.
- **Six fictional suppliers (`world.py`), unchanged.**
- **Feed corruption** across 1,218 listings, recorded in `hotel_truth.corruptions`:

| Corruption | Count |
|---|---|
| Abbreviated name (DXB, HTL, STES, APTS) | 246 |
| Phone missing | 239 |
| Coordinate jitter > 60 m | 183 |
| Geocoded 0.7–1.6 km off | 26 |
| Half-star down | 121 |
| Star missing | 35 |
| Chain-wide reservations number | 138 |
| City dropped | 79 |
| "Al Barsha" written "Al-Barsha" (one supplier) | 22 |
| **Alternative transliterations** (Jumeira, Dayra, Dubayy, Shaikh), held-out families only (recorded as `holdout_romanisation`) | 46 |
| Former name | 36 |
| "(SHA+)" tag | 34 |
| Wrong amenity | 48 |
| "Hotel" suffix | 37 |
| Typo | 12 |
| Same-supplier duplicate | 8 |

- **Rooms:** 4,469 supplier room names; 141 drop the view. Rooms near Dubai Creek get a "Creek" view.
- **Sightseeing:** 25 Dubai attractions → 68 variants → 168 listings.
  - Three demo products are hand-written:
    - **Desert Safari:** evening shared 4x4 with BBQ dinner; morning dune bashing with sandboarding; private 4x4 with dinner.
    - **Burj Khalifa At the Top:** daytime slot; sunset prime time; SKY level 148 VIP lounge.
    - **Dubai Creek dhow cruise:** pier check-in; with hotel transfer; VIP upper deck.
  - The other 22 come from category templates.
- **Images:** every hotel shows a real photo, its own or stock. Stock photos are only reused between hotels more than 2.5 km apart, and the demo-search hotels are served first.
  - Supplier copies are lightly cropped and recompressed; 505 are watermarked.
  - 10 copies show a sibling hotel's photo (a mix-up planted for M5 to catch).
- **Booking log:** 24,000 attempts drawn from the behaviour model.

## Remix parts (synthetic, R1)
`backend/samesame/data/components.py`.
- **Catalogue:** 159 entry tickets with slots, 12 lunch vouchers, and 1,840 one-way transfers between 6 hotel zones (`city.ZONES`) and 25 meeting points. Of these, 313 rates are package-only.
- **Ticket price:** the median price of packages selling the same core without a transfer, times a per-supplier net factor (0.95–1.02). Where no such package exists, the package price is cut by 20% (shared pickup) or 30% (private).
- **Transfers:**
  - Private: ₹1,600 + ₹55/km per sedan (SUV ×1.35).
  - Shared: ₹350 + ₹9/km per seat.
  - Road km = straight line × 1.35. Speed: 25 km/h for the first 15 km, 65 km/h after.
  - Shared coaches run a fixed timetable and spend 30 min collecting.
- **Resale terms:** 35% of Kestrel's rates and 10% of others are package-only. 30% of Kestrel's private transfers and 5% of others are non-refundable.
- **Booking log:** +6,000 part attempts from new `ticket` and `transfer` behaviour profiles in `world.py`.
- These parameters were set before any Remix result was computed.

## Held-out partition
`config.is_holdout()` holds out about 15% of brand families. In Dubai none of the 42 look-alike pairs fall in a held-out family, so that number is scored out-of-fold only. The held-out evaluation set has 128 pairs: 58 hotel, 40 room, 30 activity.

## How the app uses this
Unchanged from M3. The Twin Finder is scored out-of-fold with constrained clustering. Rooms come from the parser, and sightseeing groups from Variant DNA. Promise and popularity come from the booking log, and the golden record is a trust-weighted vote. Generator truth is used only by:
- the trainer
- the eval report
- `store.world_hotel()`, for the sandbox
- `store.world_relation()`, for the ops reveal

A test enforces this.

**One Dubai-specific rule:** two hotels of the same brand count as a *look-alike* within 1.2 km, even when their names differ. Dubai branches are named after their district ("Hyatt Place Baniyas Square" vs "Hyatt Place Wasl District"), not numbered.

## Fixed inputs (disclosed, not tuned)
- **Demo search:** 4★+, within 500 m of Baniyas Square Metro, Deira. This is the densest hotel cluster in OSM, and popular with Indian travellers.
- **Golden-case hotel:** Hyatt Place Dubai Baniyas Square, 270 m from the Metro. These are fixed:
  - its room list
  - its base rate of ₹6,600 a night
  - **Offer A:** Kestrel room only, non-refundable, ₹18,600 for 3 nights
  - **Offer B:** Mynah breakfast, free cancellation to 7 days, ₹20,100
  - Mynah sells no room-only rate there

  The app finds it by name.
- **Demo scenario seed:** 1, the first seed tried, shown on screen.
- The Bangkok version of all of this is in git history (commit `527167c`).
