# PROGRESS

_Update after every milestone. Newest first._

## Status: M1 done → M2 next

### Done: M1, vertical slice (2026-11-04)
All 7 demo beats work end-to-end in `--demo` mode at 1920×1080, with zero console errors and zero non-localhost requests.
- **Engines that are already real** (only their inputs are mocked):
  - `pricing/true_price.py`: mutually exclusive outcomes, every term with its assumption
  - `ranking/score.py`: transparent weighted score plus an honour-floor guardrail
  - `booking/sandbox.py`: seeded outcome draws; failover to SAME twins only, never to worse cancellation terms
- **Mock inputs** (`samesame/mock.py`, `mode.data = "mock"`, badge in the UI):
  - 12 real OSM hotels around Asok BTS
  - 37 supplier listings with naming chaos
  - the brief's golden-case offers at Novotel Sukhumvit 20
  - 3 sightseeing products (Floating Market, Grand Palace, SkyWalk) × 3 variants
  - 6 review pairs
  - placeholder supplier profiles
- **Additions from the brief review:** relevance features in ranking (distance, star fit, family fit, source-market popularity, content) shown as "why" chips with a score breakdown; `access_type` / `activity_option` in schema and DNA strip; Before/After enrichment; DNA-only filters that show measured keyword-search recall.
- **UI:**
  - listing page with Today/SameSame toggle (layout-animated stacks, 570 ms), duplicate counter, look-alike badge + map line, DNA filters
  - hotel detail with golden record (sources on hover), Before/After, canonical rooms, offers table with 5 comparison columns, flip-board True Price and Promise gauges
  - booking sandbox (Book both, Fresh seed, Run 1,000×)
  - sightseeing variants with glowing DNA diffs
  - Spot-the-Twin queue (S/V/D/U, streak, audit log, truth reveal)
  - simulator with sliders + pessimistic preset (MOCK placeholder)
  - supplier report
- **Presenter mode:** keys 1–7, ←/→, Space = the beat's action, `.` = step indicator.
- **Tests: 23 passing:**
  - True Price golden case: A ₹23,912 vs B ₹20,744
  - failover-only-to-SAME (4 cases)
  - every endpoint against the contract
  - blind-set isolation
  - tests can never write into `data/build` (conftest)

### Computed numbers right now (mock inputs; will change in M2–M4)
| Thing | Value |
|---|---|
| Offer A: Kestrel, room only, NRF, ₹18,600 | True Price **₹23,912** (sticker #1 → True #7) |
| Offer B: Mynah, breakfast, free cancel to 7 d, ₹20,100 | True Price **₹20,744** (sticker #6 → True #1) |
| Book both, seed 1 (first seed tried) | Kestrel price change ₹18,600→₹20,860 → SAME twin via Heron ₹19,400; Mynah first time |
| Same basket, seeds 1–1,000 | Kestrel: 72.0% clean, 4.2% paid a rise, 23.8% failover. Mynah: 96.7% / 1.6% / 1.7% |
| Breakfast filter | DNA: 35 listings; keyword search on supplier text: 19 |
| Free-cancellation filter | DNA: 19 listings; keyword search: 11 |

B's True Price (₹20,744) sits just above the brief's ₹20,500–20,700 band. The cause is the cancel-timing assumption: cancellations are spread uniformly over the 21-day lead, so 7/21 of the 9% fall in the penalty window. We kept the formula and report the number.

### Decisions made without asking
- **True Price terms are computed for the booked product.** Failover twins must have the same room and board, and equal or better cancellation (`cancel_rank`).
- **"Book both" means two families on the same hotel:** Shah books the sticker-cheapest offer, Patel books the True-Price pick. This retells the True Price story through the booking beat.
- **Demo seed:** 1, the first seed tried. It is disclosed on screen, along with "Run 1,000×" for the distribution.
- **Review labels** are appended to `data/build/review_labels.jsonl` (label + undo events) for the M3 retrain.
- **DNA filters are measured per listing** (DNA truth vs keyword search on raw text). Measuring per hotel hid the gap.

### Next: M2, synthetic supplier layer (A + B)
- A: curate ~300 base hotels from OSM (de-duplicate OSM's own twins first), generate 6 bird-supplier feeds with all corruptions, ≥20 real hard negatives (the 159 same-family pairs under 3 km), rooms with naming chaos, 25 attractions → activity variants (including access types and options), raster illustrative images + corrupted copies.
- B: behaviour profiles by lead time → booking-attempt log of ≥20k rows.
- Then swap `mock.py` out behind the same payload builders. `DATA_SOURCE` becomes "synthetic".

### Known issues
- The simulator is a closed-form MOCK. In it, the failed-at-booking reduction doesn't move with `failure_scale`. The real Monte-Carlo comes in M5.
- Supplier report CIs on the activity/hotel gauges reuse the point estimate (mock).
- Dev mode under React StrictMode can log a harmless Leaflet canvas error on hot reload; production (`--demo`) is clean.
- Vite warns that the JS chunk is >500 kB (Leaflet + framer-motion). Harmless offline; fix it if load time matters.
- Windows is still untested; a teammate needs to run `py start.py --demo`.
