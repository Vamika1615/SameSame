# PROGRESS

_Update after every milestone. Newest first._

## Status: M2 done → M3 next

### Done: M2, synthetic supplier layer (2026-11-04)
`python -m samesame.pipeline` builds every table in ~10 s, deterministic from the seed. `start.py` reruns it whenever a generator file changes. Full data card: [DATA.md](DATA.md).
- **Base:** 300 real OSM hotels.
  - 35 OSM self-duplicates collapsed first, each listed.
  - 72 real hard-negative pairs (same brand, < 3 km).
  - Districts by point-in-polygon on OSM boundaries.
  - Stars, phone and street come from OSM where present; otherwise they are synthetic and flagged per field.
- **Six supplier feeds:** 1,195 listings, 4,345 supplier room names, 7,039 rates.
  - Every corruption is recorded in truth tables: abbreviation, case, typos, dropped branch numbers, coordinate jitter, centroid geocodes, phone formats, half-stars, missing fields, same-supplier duplicates, wrong amenities, view-less room names.
  - Board and cancellation vocabularies differ by supplier.
- **Sightseeing:** 25 attractions → 67 variants (access type and option in the DNA) → 168 listings with varied phrasing.
- **Images:** 5,102 procedural JPEGs, i.e. base images plus supplier copies.
  - Copies are cropped, recompressed and colour-shifted; some are watermarked.
  - 40 copies show a sibling hotel's photo.
  - Licences in `LICENSES.csv`.
- **Booking log:** 24,000 attempts over 180 days from the supplier-behaviour model, with lead-time buckets and per-hotel volatility. 40% of attempts come from Indian agents.
- **API swapped from `mock.py` to `service.py`** (same contracts, `mode.data = "synthetic"`):
  - Promise is estimated from the log, with a Wilson CI; the supplier report now shows real CIs and n.
  - Popularity is counted in the log.
  - The breakfast fill is the catalogue median (₹560).
  - The golden record is a trust-weighted vote, where trust is measured agreement with the cluster majority. Images are de-duplicated by perceptual hash.
  - Look-alike reasons are computed (distance vs the measured 95th-percentile twin radius, phone, branch).
  - The booking sandbox draws from the behaviour model.
- **Tests: 30 passing.** New `test_data.py`:
  - OSM dedupe, ≥ 20 hard negatives, corruption present
  - the log has ≥ 20k rows and reflects the behaviour model
  - golden inputs present, determinism
  - no app module reads truth tables

### Computed numbers right now (M2 synthetic data; clusters still generator truth)
| Thing | Value |
|---|---|
| Demo search (500 m of Asok BTS, 4★+) | 131 listings → 29 hotels, 102 duplicates collapsed |
| Offer A: Kestrel, room only, NRF, ₹18,600 | True Price **₹23,859** (sticker #1 → True #4) |
| Offer B: Mynah, breakfast, free cancel to 7 d, ₹20,100 | True Price **₹20,799** (sticker #4 → True #1) |
| Kestrel hotel Promise at 15-45 d | 72.9% honoured (n = 2,553); reprices 19.1% |
| Book both, seed 1 (first seed tried) | Kestrel ₹18,600 → ₹20,860 → SAME twin via Sunbird ₹18,930; Mynah first time |
| Same basket, seeds 1–1,000 | Kestrel: 68.5% clean, 0% paid a rise, 31.3% failover, 0.2% failed. Mynah: 96.6% / 1.6% / 1.8% / 0% |
| Look-alikes in the demo search | Citadines Sukhumvit 16 ↔ 8 (580 m); Citadines (Asok Montri) → 16 (723 m) |
| Breakfast filter (listings) | Variant DNA: 97; keyword search on rate text: 48 |
| Free-cancellation filter | 59 vs 27 |
| Floating Market | 9 listings → 3 variants; hotel pickup: DNA 6, keyword 2 |

Both golden values sit inside the brief's bands (A 23,500–24,500; B 20,400–20,900).

### Decisions made without asking
- **The golden case moved from Novotel Sukhumvit 20 to Radisson Blu Plaza.** Novotel is 745 m from Asok, and a radius that includes it puts 270 cards on the Today screen. Radisson's room list, base rate and the two brief offers are fixed inputs, disclosed in DATA.md.
  - A side effect is that Radisson ranks #1 in the list.
  - Kestrel is no longer guaranteed the cheapest sticker by construction. It currently is, from generated prices.
- **Clusters and room mappings come from generator truth until M3**, behind `store.py` (one swap point). They are labelled in the sidebar tooltip, and room mappings show "truth" instead of a confidence.
- **Feed tables carry no truth.** Hotel and room ids live only in `*_truth` tables, and a test enforces it.
- **Keyword search for DNA filters reads only the rate text** (breakfast, cancellation) and amenity text (pool). Including amenities gave false "breakfast" hits from "Indian breakfast options".
- **Breakfast isn't sold everywhere** (by star, lower for serviced apartments, ~80% of suppliers load it). Otherwise the breakfast filter matched every listing.
- **Booking-panel labels are computed from the offer's ranks** ("booked on sticker · cheapest, True Price #4"), so they can't go stale.
- **`mock.py` is deleted.** The review queue and simulator moved to `placeholders.py` and stay labelled MOCK until M3 / M5.
- **`/api/hotels/demo`** is a presenter alias for the golden hotel, so beat URLs survive data changes.

### Next: M3, Twin Finder (A) + blind set (C)
- **Blocking:** geo cells + brand family + name tokens.
- **Features:**
  - name similarity
  - MiniLM embedding similarity
  - distance (vs the 100 m twin radius)
  - phone digits
  - address tokens
  - star delta
  - image phash overlap
- **Model:** LightGBM, trained on generator-labelled pairs that exclude the blind set.
- **Clustering:** constrained; never-merge on different brand family or > 1.5 km.
- **Gray zone** goes to the review queue, which replaces `placeholders.REVIEW`.
- **Room matcher:** parse tier, bed and view from the abbreviation chaos.
- **Blind set:** C labels ~150 pairs with a small labelling tool into `data/blind/`. Report precision and recall per entity type.
- Then swap `store.cluster_of` / `room_of` to the matcher output.

### Known issues
- The simulator is still the M1 closed form (labelled MOCK). The real Monte-Carlo comes in M5.
- The review queue is still the 6 M1 mock pairs (labelled MOCK). Its rv-1 refers to Novotel Sukhumvit 20, which is no longer the golden hotel.
- **Today shows 131 cards.** I couldn't measure the merge animation's frame rate in the background browser pane. Check it on the demo laptop; if it stutters, cap the animated ghosts to on-screen cards.
- Dev mode under React StrictMode can log a harmless Leaflet canvas error on hot reload; production (`--demo`) is clean.
- Vite warns that the JS chunk is > 500 kB (Leaflet + framer-motion). Harmless offline.
- Windows is still untested; a teammate needs to run `py start.py --demo`.
