# PROGRESS

_Update after every milestone. Newest first._

## Status: city switched to Dubai → M4 next

### Done: switch from Bangkok to Dubai (2026-11-04)
**Why Dubai:** TBO is headquartered there, and it's one of the top destinations Indian agents sell. The persona (Meera in Surat, INR) and everything else are unchanged.

**How:** every place-specific value now lives in one file per side: `backend/samesame/city.py` and `frontend/src/lib/city.ts`. These are the bounding box, demo area, phone format, name chaos, transliterations, prices, attractions and Wikimedia lookups. No other module names a place, so switching city again is a config change plus a data pull.

**Data:**
- A new OpenStreetMap snapshot of Dubai (Sharjah excluded) and 25 Dubai attractions.
- Three hand-written demo products: Desert Safari, Burj Khalifa At the Top, and a Dubai Creek dhow cruise.
- Photos and Wikipedia text re-pulled with `pull_wiki.py --city-only`. Every attraction photo was reviewed by eye; the stock photos were kept.

**Demo search:** 4★+ within 500 m of **Baniyas Square Metro, Deira**, the densest hotel cluster in OSM. The golden case is at **Hyatt Place Dubai Baniyas Square**.

**General fixes the switch exposed (they would bite any city):**
- **OSM dedupe** now also catches short/long names of the same building within 80 m, and names with different numbers are never duplicates. Four far-apart OSM duplicates are listed by hand in `city.py`, each found because the matcher kept merging them.
- **Look-alikes:** same brand within 1.2 km counts even when names differ, since Dubai names branches by district.
- **Variant DNA:** reads "BBQ dinner" and sandboarding; a meal is no longer misread as a time-slot option.
- **Ranking:** a listing awaiting review never ranks above confirmed variants.
- **Brand families:** Embassy Suites is now its own brand, so it can't merge with the Hilton Garden Inn next door.

**Tests: 38 passing.** Unit tests now use Dubai-style names.

### Computed numbers right now (Dubai)
| Thing | Value |
|---|---|
| Demo search | 84 listings → 21 hotels, 63 duplicates collapsed |
| Look-alike trap | Flora Hotel Apts. ↔ Flora Al Souq Hotel, 198 m |
| Offer A: Kestrel ₹18,600 | True Price **₹24,178** (sticker #1 → True #4) |
| Offer B: Mynah ₹20,100 | True Price **₹20,760** (sticker #4 → True #1) |
| Book both, seed 1 | Kestrel ₹18,600 → ₹20,860 → SAME twin via Sunbird ₹19,230; Mynah first time |
| Seeds 1–1,000 | Kestrel 55.5% clean / 5.3% paid a rise / 38.7% failover / 0.5% failed; Mynah 95.4 / 2.6 / 2.0 / 0 |
| Hotels, whole catalogue | precision 0.997, recall 0.963 (1 false merge: two generic "Rove" entries 1.2 km apart) |
| Look-alikes merged | 1 of 42 |
| Held-out set (128 pairs) | hotel 1.000 / 0.975, room 1.000 / 0.850, activity 1.000 / 0.933 |
| Sightseeing | desert safari 9 → 3 variants; hotel pickup: DNA 9 listings, keyword 4 |
| First ops item | two hotels named "Rove", 1.1 km apart, p 0.9906 vs bar 0.9907 |

## Earlier status: M3 + review fixes done (Bangkok)

### Done: M3 review fixes + real content (2026-11-04)
**The seven review findings are fixed.**
1. **Out-of-fold scoring** (5 folds grouped by hotel): no hotel is scored, or has thresholds chosen, by a model that saw its labels.
   - With honest scores the data got harder, and that exposed real weaknesses. Each was fixed with a general rule, not a special case:
     - Chain-wide phones and photos shared across separate sites are ignored as evidence.
     - Two established clusters merge only if their names agree and their sites are < 300 m apart.
     - Marriott Executive Apartments is its own brand family.
   - Two more OpenStreetMap self-duplicates were found by the matcher and collapsed (Courtyard by Marriott, Windsor Suites).
2. **Wording:** "blind" is now "held-out" everywhere, with the disclosure that we saw aggregate held-out numbers while building and resampled the set 7 times. It was last resampled before anyone labelled it.
3. **The look-alike claim** now says 3 of the 68 pairs are fully held out and the rest are scored out-of-fold.
4. **Listing and room ids** are hashes of what they identify, so they are stable across generator changes. The report also flags any frozen pair whose listing has changed.
5. **METRICS.md** has no timestamp, so builds don't dirty git.
6. **Review counts:** the report gives the real number of review items, plus pairs that were never compared.
7. **Validation leak:** gone with fix 1.

**README** now says `python3`.

**Real content** (one-time `backend/scripts/pull_wiki.py`; results committed in `data/raw/wiki`, 19 MB):
- **Photos:** Wikimedia Commons only, CC0 / CC BY / CC BY-SA / public domain, every one credited on hover.
  - 41 photos of 16 real Bangkok hotels.
  - 45 attraction photos.
  - 229 stock photos of hotel rooms, pools and lobbies elsewhere.
  - Hotel photos must name the hotel as a phrase and be in Bangkok or Thailand. The loose first pass had attached a Radisson in Oslo and a fighter jet.
  - Every stock photo was reviewed by eye, with 121 rejects.
  - 251 of 300 hotels, and every hotel on the demo screen, now have a real photo. Badges say PHOTO / STOCK PHOTO · NOT THIS EXACT PLACE / ILLUSTRATIVE.
- **A Reference data card** on each hotel page: the matched OSM record (address, phone, website, stars) and the Wikipedia summary where one exists.
- **Wikipedia summaries** on sightseeing pages.
- **Supplier image crops** were reduced to 1–5% (disclosed); 3–15% was harsher than real feeds.

**Tests: 38 passing.** The new one checks that every photo carries a free licence and credit, and that no two hotels within 2.5 km share a stock photo; it caught a real bug during the work.

### Computed numbers right now
| Thing | Value |
|---|---|
| Demo search | 135 listings → 36 hotels, 99 duplicates collapsed |
| Offer A: Kestrel ₹18,600 | True Price **₹23,671** (sticker #1 → True #3) |
| Offer B: Mynah ₹20,100 | True Price **₹20,794** (sticker #4 → True #1) |
| Book both, seed 1 | Kestrel ₹18,600 → ₹20,860 → SAME twin via Heron ₹19,140; Mynah first time |
| Seeds 1–1,000 | Kestrel 77.3% clean / 1.6% paid a rise / 21.1% failover; Mynah 97.0 / 1.6 / 1.4 |
| Hotels, whole catalogue (out-of-fold) | precision 1.000, recall 0.944; held-out families 1.000 / 0.964 |
| Look-alikes merged | 0 of 68 |
| Held-out set (149 pairs) | hotel 1.000 / 0.950, room 1.000 / 0.900, activity 1.000 / 1.000 |
| Routing | 58 hotel review items, 0% to LLM |
| First ops item | two different "Citadines", 832 m apart, p 0.9934 vs bar 0.9938 |

### Still open
- C hand-labels the held-out set at http://localhost:8000/label.
- **Crop-robust image matching** (ORB keypoints) comes in M5. Perceptual hashes can't see through heavy crops.
- **SkyWalk has no licensed photos** (illustrative).
- **Some attraction photos may need another look.** About 49 hotels still fall back to illustrations.
- The simulator is still mock (M5). Windows is untested.

### Done: M3, Twin Finder + Variant DNA + blind set (2026-11-04)
Every stack, room mapping and sightseeing variant on screen is now **predicted from the supplier feeds**; generator truth no longer reaches the UI. Numbers below are from [METRICS.md](METRICS.md), which `samesame.eval.report` regenerates on every build.

- **Hotel Twin Finder** (`matching/`):
  1. Blocking: 2 km plus a shared distinctive word, the same brand, or within 100 m. That gives 36,981 candidate pairs.
  2. 17 features: name similarities, MiniLM cosine, distance, phone, stars, address, postcode, image perceptual hash, amenities, check-in.
  3. LightGBM trained on 23,967 pairs with held-out families excluded.
  4. Constrained union-find clustering: never merge across brand families or branch numbers, or beyond 1.5 km, checked across whole clusters.
  5. Gray zone and rule-blocked pairs go to the review queue.

  Whole catalogue: precision **1.000**, recall **0.978** (0 false merges, 47 missed). 0 of 74 real look-alike pairs were merged.
- **Thresholds** are chosen on a grouped validation split of trainable families, with policy floors on top: never auto-merge below p 0.90, and review from p 0.30 or lower. Validation alone picked p 0.44 because synthetic pairs separate almost perfectly, so the floor wins.
- **Rooms:** a rule parser handles tier, bed and view from the abbreviation chaos. A missing view is borrowed only from a unique sibling name, with lower confidence. Whole catalogue: precision 1.000, recall 0.980. Confidence is shown per supplier name.
- **Sightseeing Variant DNA** (`variants/dna.py`):
  - Rules extract pickup, meals, access, option, cancellation, stops, duration and slot.
  - Inclusions must match exactly; descriptive fields tolerate "not stated".
  - A listing that fits two variants is kept apart and sent to review (one Kestrel SkyWalk ticket).

  Precision 1.000, recall 0.959; 9 Floating Market listings → 3 variants.
- **Real Spot the Twin queue** (`review.py`), 65 items:
  - gray-zone hotel pairs first (most likely merge first), then rule-blocked ones, one item per cluster pair
  - low-confidence room names
  - ambiguous activities

  Labels are saved with both ids. The next build uses them as training labels and as must-link / cannot-link constraints. The first item is a real near-miss: Sofitel vs "Paradox Krungthep Sukhumwit", 73 m apart, p 0.86 but DIFFERENT.
- **Blind set** (`eval/blind.py`): 147 pairs (77 hotel, 40 room, 30 activity) sampled only from held-out families or attractions, frozen in `data/blind/pairs.jsonl` and committed.
  - All 147 are correct on precision; recall is 1.000 for hotels and rooms and 0.867 for activities.
  - **The labelling tool for C** is at `/label` (linked from Ops). It shows no score and no generator label, and writes to `data/blind/labels.jsonl`. METRICS.md then reports precision and recall vs C's labels plus every human-vs-generator disagreement.
- **Metrics in the UI:** a blind-set precision/recall panel on the Simulator page (beat 7), read from `/api/metrics`.
- **Tests: 37 passing.** The new `test_matching.py` covers:
  - the never-merge rules
  - that a chain of pairs can't smuggle a merge
  - that no final cluster breaks a rule
  - human must-link / cannot-link, including undo
  - that held-out families never train
  - the threshold floors

### Computed numbers right now (M3)
| Thing | Value |
|---|---|
| Demo search (500 m of Asok BTS, 4★+) | 135 listings → 31 hotels, 104 duplicates collapsed |
| Offer A: Kestrel, room only, NRF, ₹18,600 | True Price **₹23,926** (sticker #1 → True #3) |
| Offer B: Mynah, breakfast, free cancel 7 d, ₹20,100 | True Price **₹20,763** (sticker #3 → True #1) |
| Book both, seed 1 (first seed tried) | Kestrel sold out → SAME twin via Sunbird ₹19,200; Mynah first time |
| Same basket, seeds 1–1,000 | Kestrel: 78.7% clean, 2.2% paid a rise, 19.1% failover. Mynah: 97.2% / 1.1% / 1.6% / 0.1% failed |
| Look-alike in the demo search | Citadines Sukhumvit 16 ↔ 8, 537 m (95% of one hotel's listings within 110 m) |
| Blind set | hotel P 1.000 / R 1.000 (77), room 1.000 / 1.000 (40), activity 1.000 / 0.867 (30) |
| Routing | 5.8% of likely pairs to human review, 0% to LLM (no key) |

### Decisions made without asking
- **New corruption families**, because synthetic data came out too easy (precision 1.0, recall 0.998, 3 pairs in review). These are not a demo trick: they're the cases we expect in real feeds.
  - chain-wide reservation phones (120)
  - former pre-rebrand names (43)
  - romanisation only in held-out families (39)
- **The OSM dedupe was tightened twice, because the matcher found real OSM duplicates our dedupe missed:** "Coach Boutique Hotel"/"The Coach Hotel" (29 m) and "Windsor Suites"/"Windsor Suites Hotel" (61 m). The rule is now "same distinctive words within 120 m". Disclosed in DATA.md.
- **Supplier listing codes are now unique.** Three random codes had collided and silently merged listings; a test now guards this. Fixing it shifted the random stream, so the blind set was resampled before anyone had labelled it. From now on it is frozen.
- **The golden hotel is found by name** ("Radisson Blu Plaza"), not by a generator id.
- **Sightseeing rules and the room parser were refined while looking at errors across the whole catalogue.** METRICS.md says their numbers are not blind; only C's labels are.

### Next: M4, Promise model (B)
- Beta-binomial Promise model with a prior, shrunk per supplier × product × lead bucket.
- True Price on fitted rates, with a golden integration test through the API.
- Review-label retrain path: `start.py --rebuild` already picks labels up. Add a "labels since last build" counter on Ops.

### Known issues
- The simulator is still the M1 closed form (labelled MOCK). The real Monte-Carlo comes in M5.
- **Room and sightseeing numbers are not blind** (see METRICS caveats). The hotel numbers are an upper bound because we wrote both sides.
- **Blind-set recall for activities is 0.867.** The misses are template listings whose descriptions don't state the option, so they get split instead of merged. The LLM extractor is M6.
- **Today shows 135 cards.** The merge animation's frame rate hasn't been measured on the demo laptop.
- The first build needs network once, for the 87 MB MiniLM model. Without it, the matcher drops that feature and records it.
- Windows is still untested.

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
