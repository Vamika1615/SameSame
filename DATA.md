# DATA: what is real, what is synthetic, what is fixed

Built by `python3 -m samesame.pipeline` (run from `backend/`). `start.py` runs it automatically when any generator, matcher or eval file changes. The build is deterministic from `config.SEED = 20261104` and takes about 20 s.

Three things need network, once each:
- The OSM snapshot: `backend/scripts/pull_osm.py`.
- Wikimedia photos and Wikipedia text: `backend/scripts/pull_wiki.py`. Their output is committed in `data/raw/`, so teammates never re-download.
- The 87 MB MiniLM model, cached in `data/models/` on the first build. Without it, the matcher drops that one feature and says so in `matcher.json`.

Live counts are always in `GET /api/meta` → `build.counts`.

## Real
| What | Source | Count |
|---|---|---|
| Hotel names + coordinates | OpenStreetMap snapshot 2026-11-03, ODbL | 300 curated from 1,187 named OSM hotels |
| Reference data shown on each hotel page (address, phone, website, stars) | the same OSM snapshot, unmodified | all 1,187 named hotels |
| Hard negatives: same brand family, different real hotels, < 3 km apart | OSM | 68 pairs (e.g. Citadines Sukhumvit 16 vs Sukhumvit 8, 551 m) |
| **Photos of the actual hotel** | Wikimedia Commons, CC0 / CC BY / CC BY-SA / public domain, each credited | 41 photos of 16 real Bangkok hotels |
| **Photos of the actual attraction** | Wikimedia Commons, via the attraction's Wikipedia article | 45 photos of 22 attractions |
| **Stock photos** (real hotel rooms, pools and lobbies elsewhere; labelled "STOCK PHOTO · NOT THIS EXACT PLACE") | Wikimedia Commons, same licences | 141 rooms, 68 pools, 16 lobbies, 4 activity |
| Attraction and hotel descriptions | Wikipedia summaries, CC BY-SA 4.0, linked | 25 attractions + 15 hotels |

**How a photo gets attached** (`pull_wiki.vet()`): precision first, so a photo is only labelled as a place if its own title says so.
- **A hotel photo** must contain the hotel's distinctive name *as a phrase* and place it in Bangkok or Thailand. The first, looser pass attached a Radisson in Oslo, a Sukhoi fighter jet and a shoe advert to our hotels, and this rule removed them.
- **Stock photos** must be titled as a room, pool or lobby. Every remaining one was then reviewed by eye: 121 rejects (people in shot, postcards, menus, an elephant, duplicates), all listed in the script.
- **Photos for generic attraction topics** (tuk-tuks, Thai massage, cooking) must be Thai and are labelled stock.

**OSM's own duplicates are collapsed first:** 50 of them, listed in `osm_duplicates.parquet`. A duplicate is either:
- the same name within 250 m, or
- the same distinctive words within 120 m. This rule was added after the matcher kept "wrongly" merging pairs such as "Coach Boutique Hotel"/"The Coach Hotel" (29 m) and "Courtyard by Marriott Bangkok"/"Courtyard by marriott Thailand" (11 m). In each case the matcher was right about the world and our base was wrong.

## Synthetic (generator inputs, all in `backend/samesame/data/`)
**Base attributes** the generator fills in (flagged in `*_source` columns): stars where OSM and brand are silent (174; brand map for 80), phone (158), pool, family rooms, rates, amenities, check-in time, demand volatility.

**Six fictional suppliers (`world.py`).** Kestrel, Mynah, Heron, Bulbul, Hornbill and Sunbird differ in:
- coverage and price level
- rate plans
- board and cancellation vocabulary
- content completeness

**Feed corruption** across 1,211 listings, each recorded in `hotel_truth.corruptions`:

| Corruption | Count |
|---|---|
| Abbreviated name | 217 |
| Phone missing | 216 |
| Coordinate jitter > 60 m | 164 |
| Geocoded 0.7–1.6 km off | 15 |
| Half-star down | 133 |
| Star missing | 43 |
| **Chain-wide reservations number** | 114 |
| City dropped | 90 |
| **Former (pre-rebrand) name** | 37 |
| **Thai-style romanisation**, held-out families only | 48 |
| Wrong amenity | 40 |
| "Hotel" suffix | 37 |
| "(SHA+)" tag | 36 |
| Typo | 24 |
| Soi inserted | 17 |
| Branch number dropped | 13 |
| Same-supplier duplicate | 5 |

**Rooms, offers and activities.**
- 4,262 supplier room names; 120 of them drop the view.
- 6,955 nightly rates. The breakfast fill cost is the catalogue median of ₹520 per person per night.
- 25 attractions → 67 variants → 169 listings.

**Supplier image copies.**
- Each copy is the base photo resized, lightly cropped (1–5%), recompressed and colour-shifted; 496 are watermarked.
- 28 copies show a sibling hotel's photo (a planted mix-up for M5 to catch).
- Crops were 3–15% until the M3 review. That was harsher than real feeds, which mostly resize and recompress, so they were reduced, as disclosed here.

**Stock photo reuse.** A stock photo is only reused between hotels more than 2.5 km apart. Blocking never compares hotels more than 2 km apart, so a shared stock photo can't fake a match, and a test enforces this. Hotels that match the demo search are served first. In total, 251 of 300 hotels have a real photo (their own or stock); the rest fall back to a procedural illustration, labelled as such.

**Booking log.** 24,000 attempts drawn from `world.BEHAVIOUR` × lead-time bucket × hotel volatility; 40% come from Indian agents.

## Held-out partition
`config.is_holdout()` hashes the brand family (or the hotel id when there is no brand) and holds out ~15%: 32 of 300 hotels.

Held-out hotels:
- never train the matcher
- never choose its thresholds
- are the only source of the 149-pair evaluation set
- are the only hotels that get the romanisation corruption

## How the app uses this
| On screen | Comes from |
|---|---|
| Hotel stacks | **Twin Finder**:<br>1. blocking<br>2. 17 pair features<br>3. LightGBM, **scored out-of-fold**: 5 folds grouped by hotel, so no hotel is scored by a model that saw its labels<br>4. constrained clustering<br><br>The clustering rules:<br>- never merge different brand families, branch numbers, or > 1.5 km<br>- two established clusters merge only if their names agree and their sites are < 300 m apart<br>- phones and photos that appear at several separate sites (chain lines, stock photos) are ignored as evidence |
| Canonical rooms | rule parser (tier, bed, view) inside each predicted hotel, with per-name confidence |
| Sightseeing variants | Variant DNA rules on title + description. Ambiguous listings are kept apart and sent to review |
| Reference data card | the matched hotel looked up in the real OSM data (nearby + same name), plus Wikipedia if linked |
| Promise, popularity | estimated / counted from the booking log |
| Golden record | trust-weighted vote; trust = measured agreement with the cluster majority |
| Booking sandbox | draws from `world.BEHAVIOUR` (it stands in for the live supplier) |
| Simulator | still the M1 closed-form mock (labelled) until M5 |

**Generator truth is used only by:**
- the trainer, as labels (human review labels override them)
- the eval report
- `store.world_hotel()`, for the sandbox
- `store.world_relation()`, for the ops reveal

A test enforces this.

## Fixed inputs (disclosed, not tuned)
- **Golden-case hotel:** Radisson Blu Plaza (Sukhumvit 27). These are fixed:
  - its room list
  - its base rate of ₹6,600
  - **Offer A:** Kestrel room only, non-refundable, ₹18,600 for 3 nights
  - **Offer B:** Mynah breakfast, free cancellation to 7 days, ₹20,100
  - Mynah sells no room-only rate there
  - it is excluded from chain-phone and former-name corruption

  The app finds it by name.
- **Demo scenario seed:** 1. It was the first seed tried, and it is shown on screen.
