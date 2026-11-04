# DATA: what is real, what is synthetic, what is fixed

Built by `python -m samesame.pipeline`. `start.py` runs it automatically when any generator, matcher or eval file changes. The build is deterministic from `config.SEED = 20261104` and takes about 20 s: about 10 s for the data and about 10 s for the matcher and evaluation.

The first build downloads the 87 MB MiniLM embedding model into `data/models/`. If it can't, the matcher runs without that one feature and says so in `matcher.json`.

Counts below are from the current build; `GET /api/meta` → `build.counts` always has the live ones.

## Real
| What | Source | Count |
|---|---|---|
| Hotel names + coordinates | OpenStreetMap snapshot 2026-11-03 (`data/raw/osm/SNAPSHOT.txt`), ODbL | 300 curated from 1,078 named OSM hotels |
| Stars where OSM has them | OSM `stars` tag | 47 of 300 |
| Phone where OSM has it | OSM `phone` / `contact:phone` | 142 of 300 |
| Street where OSM has it (Latin script) | `addr:street` | 61 of 300 |
| District | point-in-polygon on OSM admin boundaries | all |
| Hard negatives: same brand family, different real hotels, < 3 km apart | OSM | 74 pairs (e.g. Citadines Sukhumvit 8 vs Sukhumvit 16, 537 m) |
| Attraction names + approximate locations | hand-written | 25 |

**OSM's own duplicates are collapsed first.** 49 were collapsed, each listed in `osm_duplicates.parquet`. A duplicate is either:
- the same name within 250 m, or
- the same distinctive words within 120 m. This second rule was added in M3 after the matcher kept "wrongly" merging "Coach Boutique Hotel" with "The Coach Hotel" (29 m apart) and "Windsor Suites" with "Windsor Suites Hotel" (61 m). Each is one real hotel mapped twice in OSM, so the matcher was right and our base was wrong.

## Synthetic (generator inputs, all in `backend/samesame/data/`)
**Base attributes the generator fills in** (flagged in `*_source` columns):
- stars where OSM and brand are silent (170; brand map for 83)
- phone (158)
- pool, family rooms, rooms, nightly base rate, amenities, check-in time
- demand volatility

**Six fictional suppliers (`world.py`).** Kestrel, Mynah, Heron, Bulbul, Hornbill and Sunbird differ in:
- coverage and price level
- rate plans
- board and cancellation vocabulary (`BB`, `ROOM W/ ABF`, `Incl. ABF`, `FC 7D`, `cxl free till 72h`, …)
- content completeness

**Feed corruption** across 1,236 listings, each recorded in `hotel_truth.corruptions`:

| Corruption | Count |
|---|---|
| Phone missing | 246 |
| Abbreviated name | 210 |
| Coordinate jitter > 60 m | 178 |
| Geocoded 0.7–1.6 km off (district centroid) | 27 |
| Half-star down | 130 |
| Star missing | 44 |
| **Chain-wide reservations number** used for a branch | 120 |
| City dropped | 91 |
| **Former (pre-rebrand) name** | 43 |
| **Thai-style romanisation** (`Sukhumwit`, `Krungthep`): only in held-out families, never seen in training | 39 |
| "(SHA+)" tag | 37 |
| Wrong amenity | 37 |
| "Hotel" suffix | 33 |
| Typo | 25 |
| Soi inserted | 17 |
| Same-supplier duplicate | 11 |
| Branch number dropped | 7 |

**Rooms.**
- 4,386 supplier room names with abbreviation chaos.
- 151 of them drop the view.

**Offers.**
- 7,268 nightly rates.
- Breakfast is sold only where the hotel serves it, and by ~80% of suppliers there.
- The catalogue median breakfast supplement is ₹560 per person per night.

**Activities.**
- 25 attractions → 67 variants → 162 supplier listings.
- Phrasing varies between suppliers. About 60% of template listings state a duration.

**Images.**
- 5,245 procedural JPEGs; 566 copies are watermarked.
- 30 copies show a sibling hotel's photo.
- Licence: `data/build/images/LICENSES.csv` (CC0, own work).

**Booking log.**
- 24,000 attempts over 180 days, drawn from `world.BEHAVIOUR` × lead-time bucket × hotel volatility.
- 40% come from Indian agents.

## Held-out partition
`config.is_holdout()` hashes the brand family (or the hotel id when there is no brand) and holds out ~15%: 32 of 300 hotels.

Held-out hotels are:
- never used to train the matcher
- never used to choose its thresholds
- the only source of the blind evaluation set

They also get one corruption family (romanisation) that the training data never shows. Attractions are partitioned the same way.

## How the app uses this
| On screen | Comes from |
|---|---|
| Hotel stacks (which listings are one hotel) | **Twin Finder**:<br>1. blocking (2 km + a shared distinctive word, the same brand, or within 100 m)<br>2. 17 pair features (name similarities, MiniLM cosine, distance, phone, stars, address, postcode, image perceptual hash, amenities, …)<br>3. LightGBM<br>4. constrained clustering (never merge different brand families, different branch numbers, or > 1.5 km, checked across whole clusters) |
| Canonical rooms | rule parser on supplier room names (tier, bed, view), grouped within the predicted hotel; confidence shown per name |
| Sightseeing variants | Variant DNA rules on title + description, grouped by compatible DNA. A listing that fits two variants is kept apart and sent to review |
| Spot the Twin queue | the matcher's gray zone and rule-blocked pairs, low-confidence room names, ambiguous activities |
| Promise, popularity | estimated / counted from the booking log |
| Golden record | trust-weighted vote; trust = measured agreement with the cluster majority |
| Booking sandbox outcomes | drawn from `world.BEHAVIOUR` (the sandbox stands in for the live supplier) |
| Simulator | still the M1 closed-form mock (labelled) until M5 |

**Generator truth is used only by:**
- the trainer, as labels (human review labels override them)
- the evaluation report
- `store.world_hotel()`, which gives the sandbox the hotel's demand volatility
- `store.world_relation()`, which gives the ops screen its after-labelling reveal

A test fails if any other module reads a truth table.

## Fixed inputs (disclosed, not tuned)
- **Golden-case hotel:** Radisson Blu Plaza (Sukhumvit 27, 450 m from Asok BTS). These are fixed:
  - its room list
  - its nightly base rate (₹6,600)
  - **Offer A:** Kestrel room only, non-refundable, ₹18,600 for 3 nights
  - **Offer B:** Mynah breakfast, free cancellation to 7 days, ₹20,100
  - Mynah sells no room-only rate there
  - it is excluded from chain-phone and former-name corruption

  The app finds it by name ("Radisson Blu Plaza"), the way an agent would.
- **The golden case moved from M1's Novotel Sukhumvit 20.** Novotel sits outside the 500 m demo radius.
- **Demo scenario seed:** 1. It was the first seed tried, and it is shown on screen.
