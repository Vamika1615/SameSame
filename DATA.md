# DATA: what is real, what is synthetic, what is fixed

Built by `python -m samesame.pipeline` (run automatically by `start.py` when any generator file changes), deterministic from `config.SEED = 20261104`. About 10 s, ~55 MB in `data/build/` (gitignored). Counts below are from the current build. `GET /api/meta` → `build.counts` always has the live ones.

## Real
| What | Source | Count |
|---|---|---|
| Hotel names + coordinates | OpenStreetMap snapshot 2026-11-03 (`data/raw/osm/SNAPSHOT.txt`), ODbL | 300 curated from 1,078 named hotels |
| Stars where OSM has them | OSM `stars` tag | 46 of 300 |
| Phone where OSM has it | OSM `phone` / `contact:phone` | 142 of 300 |
| Street where OSM has it (Latin script) | `addr:street` | 61 of 300 |
| District | point-in-polygon on OSM admin boundaries | 300 of 300 |
| Hard negatives: same brand family, different real hotels, < 3 km apart | OSM | 72 pairs (e.g. Citadines Sukhumvit 8 vs Sukhumvit 16, 580 m) |
| Attraction names + approximate locations | hand-written | 25 |

**OSM's own duplicates are collapsed first:** a name within 250 m of the same name (token-sort ratio ≥ 92). 35 were collapsed, and every one is listed in `osm_duplicates.parquet` (e.g. Baiyoke Tower II mapped twice, Wyndham Garden Sukhumvit 42 as node and way).

**Curation keeps:**
- everything within 900 m of Asok BTS (the demo area)
- the 40 most confusable hard-negative pairs
- then the richest, most central hotels.

## Synthetic (generator inputs, all in `backend/samesame/data/`)
**Base attributes the generator fills in** (flagged in `*_source` columns):
- stars where OSM and brand are silent (174; brand map for 80)
- phone (158)
- pool, family rooms, room count, nightly base rate, amenities, check-in time
- per-hotel demand volatility

**Six fictional suppliers (`world.py`).** Kestrel, Mynah, Heron, Bulbul, Hornbill and Sunbird differ in:
- coverage and price level (Kestrel 0.94×, Bulbul 1.04×)
- rate plans: non-refundable, free cancellation 7 d / 3 d, pay later
- board and cancellation vocabulary: `BB`, `ROOM W/ ABF`, `Incl. ABF`, `FC 7D`, `cxl free till 72h`, …
- content completeness

**Feed corruption** across 1,195 listings (≈4 per hotel). Every applied corruption is recorded in `hotel_truth.corruptions`:

| Corruption | Count |
|---|---|
| Abbreviated name (BKK, HTL, …) | 251 |
| Phone missing | 215 |
| Phone in another format | every non-intl supplier |
| Coordinate jitter > 60 m | 163 |
| Geocoded to a district centroid 0.7–1.6 km away | 21 |
| Half-star down | 127 |
| Star missing | 44 |
| City dropped from the name | 75 |
| "Hotel" suffix added | 40 |
| "(SHA+)" tag added | 37 |
| Letter-swap typo | 33 |
| Soi inserted | 18 |
| Branch number dropped (the look-alike trap, e.g. `CITADINES SUKHUMVIT BANGKOK`) | 12 |
| Same supplier lists the hotel twice | 11 |
| Amenity the hotel doesn't have | 40 |

**Rooms.**
- 1,696 canonical rooms.
- 4,345 supplier room names with abbreviation chaos (`SUP 1KG`, `DLX TWN PV`, `Superior Double (King)`).
- 139 supplier rooms drop the view, which makes a SAME room look like a VARIANT.

**Offers.** 7,039 nightly rates for 2 adults:
- Breakfast is sold only where the hotel serves it (35–97% by star, lower for serviced apartments), and only by ~80% of suppliers there.
- The breakfast fill cost in True Price is the **catalogue median** BB − RO supplement: currently ₹560 per person per night.

**Activities.**
- 25 attractions → 67 variants → 168 supplier listings.
- Variant DNA: pickup, meals, duration, stops, access type (standard / skip-the-line / VIP / time-slot), option, cancellation.
- Supplier titles and descriptions phrase the same fact differently ("hotel pickup", "collection from your hotel", "ex-hotel transfer", "SIC from hotel"). The Floating Market, Grand Palace and SkyWalk variants are hand-written because the brief names them. The rest come from category templates.

**Images.**
- Procedural illustrative JPEGs, never photos of real hotels: 4 per hotel, 3 per attraction.
- Supplier copies are cropped, resized, recompressed and colour-shifted; 521 are watermarked.
- 40 copies show a sibling hotel's photo (a real-world mix-up for M5 to catch).
- Licence: `data/build/images/LICENSES.csv` (CC0, own work).

**Booking log.** 24,000 attempts over 180 days:
- Suppliers are weighted by market share.
- Listings are weighted by appeal. Indian agents (40% of attempts) favour family rooms, pools and Indian breakfast.
- Lead time is log-normal with a 21-day median.
- Outcomes are drawn from `world.BEHAVIOUR` × lead-time bucket × hotel volatility.

## How the app uses this
| On screen | Comes from |
|---|---|
| Promise (honour rate, CI, reprice / sold-out odds, typical increase) | **estimated from the booking log** (counts + Wilson interval), never read from `world.BEHAVIOUR` |
| "Booked N× by Indian agents (90d)" | counted in the booking log |
| Golden record (name, stars, phone, address, amenities, images) | trust-weighted vote across supplier listings; trust = measured agreement with the cluster majority (Mynah 0.99 … Sunbird 0.80) |
| Image de-duplication on the detail page | perceptual hash across supplier copies |
| Booking sandbox outcomes | drawn from `world.BEHAVIOUR`: the sandbox stands in for the live supplier |
| Hotel clusters and canonical rooms | **generator truth until the M3 matcher** (`store.CLUSTER_SOURCE`, shown in the sidebar tooltip and as "truth" on room mappings) |
| Review queue, simulator | still M1 mock (labelled) until M3 / M5 |

A test (`test_truth_tables_stay_out_of_the_app`) fails if any module other than the generator, pipeline, store or eval reads a truth table.

## Fixed inputs (disclosed, not tuned)
- **Golden-case hotel:** Radisson Blu Plaza (Sukhumvit 27, 450 m from Asok BTS). These are fixed:
  - its room list
  - its nightly base rate (₹6,600, so Kestrel's usual 6% discount lands on the brief's figure)
  - **Offer A:** Kestrel room only, non-refundable, ₹6,200 × 3 = ₹18,600
  - **Offer B:** Mynah breakfast, free cancellation to 7 days, ₹6,700 × 3 = ₹20,100
  - Mynah sells no room-only rate there.

  Every other offer at the hotel is generated like any other hotel's.
- **The golden case moved from M1's Novotel Sukhumvit 20.** Novotel is 745 m from Asok BTS, outside the 500 m search radius, and widening the radius to 800 m would put 270 listings on the Today screen.
- **Demo scenario seed:** 1. It was the first seed tried, and it is shown on screen.
- **Side effect, disclosed:** Offer B is a promo rate. That fixed input is why Radisson Blu Plaza ranks #1 in the SameSame list for the demo search.
