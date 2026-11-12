# PROGRESS

_Update after every milestone. Newest first._

## Status: Canon (C1 + C2) on branch `canon`: the catalogue is the product, supplier sheets are the way in

### Done: C1 + C2, Canon (2026-11-12)
The team decided the catalogue is the product and Remix is secondary, and asked for supplier sheets to be the main entry point. The product is renamed **Canon** ("every supplier sheet, one clean catalogue"). Remix is now **Bundles**, the last section.
- **Layout reader (`ingest/layouts.py`):** flat sheets, price grids and rotated grids.
  - Price grids: seasons × weekday × occupancy columns, a code column, extra-guest columns, merged headers, several hotels per sheet, and one tab per rate plan.
  - Footnotes are classified into discount tiers, mark-up, minimum-stay fee, booking window and dynamic dates.
  - Contract workbooks (rack, net and promo side by side) are refused with a clear message.
- **Import engine (`ingest/sheet.py`):**
  - **Sheets with no location** (real grids never give one) are matched by name, writing out only the sheet's own short codes.
  - **Auto-match rule:** only an identical name shared by exactly one catalogue hotel matches on its own; names that are close go to a person.
  - **Name score:** token_set averaged with token_sort, so "Riviera Hotel" isn't 100% like "Hard Rock Hotel Riviera Maya".
  - **Hotels created by earlier imports** are matched too, so next year's sheet attaches to this year's hotel.
  - **Rooms** map by code, then name, then tier + bed + view. A new hotel's rooms are kept as written.
- **Persistence (`catalogue/imports.py`, `catalogue/view.py`):**
  - Each import is stored in `data/imports/` (git-ignored): the original file, the result, and a status of draft, applied or removed.
  - Decisions go to an append-only log, with undo.
  - The catalogue is past inventory, plus applied imports in the order they were applied, plus decisions. Re-check, remove and restore all work.
  - **Bug found by tests:** two imports applied in the same second tied on the timestamp and created a duplicate hotel. Timestamps now carry microseconds.
- **API:** `/api/imports` (upload, samples, apply, remove, restore, recheck, decide, undo, download the original) and `/api/catalogue` (summary, hotels, hotel, pending).
- **UI:**
  - Navigation: **Catalogue** (Import sheets · All hotels · Agent search · Tours · Uncertain matches) · **Insights** · **Bundles** (Rebuild packages · New products · Approvals). The Review section is gone.
  - New pages: Import sheets (upload, samples, import history, per-hotel and per-room decisions, add/remove), All hotels (search and filters), a page for hotels added from sheets (rate grid, rooms, terms), and Uncertain matches (sheet decisions and listing pairs).
  - Hotel pages get a **Sheet rates** tab.
  - Presenter beats now tell the catalogue story first.
- **Samples:**
  - **Plover**, a synthetic two-tab grid with 5 Dubai hotels: 3 matched, 1 short code for a person, 1 new, all right against its answer key.
  - **Weaver** now scores 28/28 automatic hotel matches (was 27/27, because a name-only match is now allowed) and 67/67 rooms (was 63/63).
- **Real TBO sample sheets (tested locally only, never committed):** 6 of 7 distinct files import.
  - AVA Cancún: CSV, and a 4-tab workbook that attaches to the hotel the CSV created.
  - Hard Rock: 5 hotels, about 5,100 rates.
  - UNICO: two properties, kept apart.
  - HXA: rotated grid; the hotel is named after the file, with a warning.
  - The USA-market contract workbook is refused.
  - Overall: 9 hotels and 7,836 rates, with no false match against the Dubai catalogue.

**Tests: 96 passing** (6 new in `test_catalogue.py`: layouts, the import lifecycle, errors).


### Done: N1, supplier naming and the Supplier Sheets page (2026-11-09)
Prompted by TBO's CTO: suppliers send spreadsheets where one hotel is "Radisson Plaza Room", "Radisson Room" or "RP Room".
- **Generator (`data/naming.py`, synthetic, disclosed in DATA.md):**
  - 49 *short-code listings*: a supplier re-loads a hotel under its initials ("HGI Dubai Deira", "HP Dubai Al Rigga"), with no photos.
  - Their room names carry the hotel's name ("Hyatt Place Superior King", "HP SUP KG CV") or are only the hotel ("Hyatt Place Room").
  - They are extra rows from their own random stream, added after the booking log and images. **Nothing that existed before changed:** Remix and Promise metrics are byte-identical, and the frozen held-out set has 0 stale pairs.
  - Weaver, a fictional 7th supplier, sends a 136-row rate sheet (CSV + XLSX) that is not in the catalogue. Its answer key is read only by `eval/sheet_check.py`.
- **Matcher (`matching/hotels.py`):** a 2–4 letter word that spells the initials of consecutive words in the other name is written out before the name features are computed. There is a new `short_code` feature and a blocking rule for it.
- **Room parser (`matching/rooms.py`):** the hotel's name, as any listing in its cluster writes it, is removed from the start or end of the room name before parsing. A name that is only the hotel goes to a person as its own "unmapped" room and is never pooled with another room. This also fixed a latent bug: "Hilton Garden Inn Superior King" used to read as a *Garden view* room.
- **Supplier Sheets page (`/sheets`, `ingest/sheet.py`):**
  - Drop in a CSV or XLSX; columns are found by their usual spellings.
  - Each hotel as the sheet writes it goes through the same trained model and thresholds as the catalogue, and is matched, sent to a person, or marked new to TBO. Rooms are mapped to the hotel's catalogue rooms.
  - Hotels listed twice in one sheet are flagged.
  - A person's decisions are made inline and included in "Download cleaned sheet". They are kept on the page only; they are not written to the Ops queue or used for training.

**Before and after, measured once with the new data (disclosed):**

| | Old matcher + new data | Short-code reading | + brand rule on written-out names |
|---|---|---|---|
| Short-code listings: pair recall / left on their own | 0.900 / 5 | 0.900 / 3 | **0.961 / 0** |
| Rooms carrying the hotel's name: pair recall | 0.934 | 0.938 | **0.975** |
| Whole catalogue hotels: precision / false merges | 0.985 / 33 | 1.000 / 0 | **1.000 / 0** |
| Held-out hotels: recall | 0.963 | 0.982 | **0.982** |

- The 33 false merges with the old matcher were almost all one cluster: Andaz Dubai The Palm and Andaz Dubai The Palm Apartments. More training rows had moved the threshold. We did not tune for it; the new feature removed it.
- **Disclosure:** the brand rule ("different brand family never merges") was changed to read written-out names *after* we saw it blocking "FP by Sheraton" against "Four Points by Sheraton" across the whole catalogue, held-out families included. Only 1 short-code listing is in a held-out family, so held-out evidence for short codes is thin.
- **Weaver's sheet:** 136 rows → 33 names → 30 hotels. 27 matched automatically (27/27 right), 4 new (4/4 right), 2 to a person, 3 listed twice. Rooms: 63 mapped (63/63 right), 16 to a person, 8 new. This is an upper bound, because we wrote the generator, the matcher and the sheet.
- The demo hotel search is now **86 listings → 20 hotels**: two short-code listings were added, and two clusters of one hotel are now joined.

**Tests: 90 passing** (19 new: `test_naming.py`, `test_sheets.py`). One of them checks that an uploaded sheet never reads a truth table.


### Done: R5, Connected Trip, metrics, simulator, docs (2026-11-07)
- **Connected Trip (`remix/trip.py`; hotel page, key 6):** the golden-case hotel's #1 True Price offer + private DXB cars both ways + the best sightseeing Remix from that zone, as one product with one price, one Promise and one cancellation rule.
  - Airport cars are generated in their own pipeline stage after the booking log, so no earlier draw moves. They use each supplier's fitted transfer Promise.
  - **Result: blocked.** The agent would save 8.3% (₹7,798) and TBO keep 9.1%, but four independent parts multiply to a 92.9% Promise, under the 95% floor. The UI says so and has a Promise slider. I didn't swap the activity or loosen the guardrail to make it pass.
  - A first version picked airport cars on cost alone and gave them no twins (87.1%). It was aligned with the activity engine (smallest fitting car per supplier as twins; cheapest that clears the floor).
- **METRICS.md → Remix section**, rebuilt every build:
  - coverage funnel and per-Remix saving / margin / Promise
  - sandbox seeds 1–1,000, Remix vs package
  - every product where the package wins, and every product that is cheaper but blocked
  - why the others can't be assembled
  - pessimistic preset, per-zone counts, gap Remixes, Connected Trip
  - the estimated-vs-sandbox Promise gap (sandbox 1–3 points lower; disclosed as making the estimate optimistic)
- **Simulator:** a Remix business case per 1,000 sightseeing searches, labelled SIMULATED. Searches are matched to publishable Remixes, using computed margins and savings and the simulator's conversion rate.
- **Rebrand:** remaining "SameSame" labels in the UI now say Twin Finder / With Remix. The page title is "Remix · TBO".
- **Docs:** README (headline, how it works, Mermaid diagram, provenance), DEMO.md (8 beats, 3 presenters, computed numbers, fallbacks), QA.md (new; Remix answers plus the matching/pricing answers that still apply).
- **Tests: 71 passing.** All 48 pre-pivot tests still pass; none was obsolete.
- **Server:** warms the Remix catalogue, gaps and trip at start-up, so no stage click waits (first gap list was 2 s).

### Remix numbers right now (Deira, 2 adults, 21 days out, default guardrails)
| Thing | Value |
|---|---|
| Multi-part packages → SAME Remix exists → cheaper → publishable | 30 → 17 → 10 → **4** |
| Publishable | Helicopter + private pickup (agent −11.9%, TBO 13.5%); Ski Dubai + lunch (7.2%, 7.8%); IMG Worlds + lunch (4.7%, 4.9%); Old Dubai food tour + private pickup (4.0%, 4.1%) |
| Package cheaper | 7, e.g. morning desert safari by ₹4,006, private desert safari by ₹3,178, dhow cruise with transfer by ₹371 |
| Demo Remix (rule: largest rupee saving) | Helicopter: package ₹65,940 (True Price ₹67,341) → Remix sells ₹59,076 (agent True Price ₹59,329); TBO keeps ₹7,977 |
| Book Remix, seed 22 (first seed with a failover) | Transfer out via Mynah failed → SAME transfer via Heron; whole trip confirmed |
| Sandbox, seeds 1–1,000 (helicopter) | secured 93.0% vs 95.7% estimated; 6.8% unwound and package bought |
| Gap Remixes | 78 searched-for, 18 publishable; demo: Dolphinarium + private pickup, 86 searches, agent −4.9%, TBO 5.2% |
| Connected Trip | blocked: Trip Promise 92.9% (< 95%); would save the agent 8.3% |
| Pessimistic preset | 2 publishable (helicopter, IMG Worlds) |
| Simulated business case | 18.1% of sightseeing searches hit a publishable Remix; ≈ ₹52,000 TBO margin per 1,000 searches (≈ ₹29,000 pessimistic) |

### Decisions taken without asking (Remix)
1. A Remix needs ≥ 2 parts; single-part products are Twin Finder's job.
2. SAME rule: strict fields equal, every field the package states equal; package-silent fields go to the approver.
3. Duration is descriptive (as in Variant DNA). The Remix shows door-to-door time instead.
4. Parts carry structured terms, but their text is read by the same Variant DNA extractor as packages.
5. TBO carries the price-change and failover risk. The agent's True Price is the sell price plus cancellation risk under the strictest part's rule.
6. Defaults, fixed before results: agent share 50%; saving ≥ 3%; margin ≥ 4%; Promise ≥ 95%; buffer 20 min; max wait 90 min.
7. Gaps are priced against booking the pieces separately, with the same rule and guardrails. Friction is ₹500 per extra booking.
8. The demo products and seeds are chosen by rule and disclosed on screen.
9. Changed after seeing results, and disclosed: booking-log part attempts are sampled by role, not SKU; the private-safari VARIANT leak was closed.
10. The `remix` branch is not merged into `main`; the user decides.


### Done: R4, gap Remixes and the approvals queue (2026-11-07)
- **Agent searches (synthetic, `data/search_log.py`):** 5,000 sightseeing searches over 90 days.
  - Each search is an attraction (weighted by listing count), one of its ticket-level products, and a pickup wish: none 50%, shared 25%, private 25%.
  - Drawn independently, so demand lands on combinations nobody packages. The gap finder sees only the events and the catalogue.
- **Gap finder (`remix/gaps.py`):** a gap is a standalone ticket (DNA read from its text) plus a hotel pickup, where no packaged variant is SAME. It must have ≥ 10 searches in 90 days.
  - **Decision:** with no package to beat, the baseline is what the agent does today. That is the best ticket-only package plus two transfers booked separately, at their True Price (the agent carries the risk), plus ₹500 friction per extra booking.
  - Pricing and guardrails are the same as catalogue Remixes. (A first draft used a flat 10% margin; that priced most gaps just above doing it yourself, so it was dropped for consistency.)
  - **Result:**

| Gaps searched for | Pass every guardrail | Blocked | Can't be assembled |
|---|---|---|---|
| 78 | 18 | 38 | 22 |

  - The most-searched publishable gap (demo, by rule) is the Dubai Dolphinarium standard seat with private pickup from Deira: 86 searches, the agent saves 4.9%, TBO keeps 5.2%. Burj Khalifa daytime with private pickup saves 7.7%.
  - With no package to fall back on, a gap Remix whose part can't be secured is unwound and refunded.
- **Approvals (`remix/approvals.py`, Ops → Remix approvals):**
  - Every Remix that passes its guardrails (4 catalogue + 18 gap) waits for a person: recipe, suppliers, sell price, margin, saving, Promise, cancellation, and any unverified field to check. A / R keys work.
  - The log is append-only and undo appends. Each decision snapshots what was approved; if a rebuild changes the recipe or numbers, the Remix returns to the queue.
  - Remix Studio says "awaiting approval" or "published". The matcher's held-out metrics sit under the queue (beat 7).
- **Tests: 69 passing** (+2: a gap Remix is something nobody sells, at the threshold, SAME; approve → published → undo; unknown id 404; a gap with no package unwinds to a refund).


### Done: R3, Remix Studio, Book Remix, rebrand (2026-11-07)
- **Decision (yours):** build on the publishable winners.
- **Chrome is now "Remix"**, with the tagline in the footer and logo tooltip. The `samesame` package name stays.
- **Remix Studio** (`/remix`):
  - a funnel: multi-part → SAME Remix exists → cheaper → passes guardrails
  - a product picker, with "package wins" and "blocked" shown, not hidden
  - the packaged version (DNA, best package on True Price) next to the TBO Remix card: recipe with supplier, price, twins and per-part Promise gauge; a pickup → slot → return timeline; a SAME check per DNA field
  - the True Price proof (bars plus the full arithmetic) and the publish guardrails as live sliders (zone, agent share, saving, margin, Promise, buffer, pessimistic preset)
- **Book Remix:** riskiest part first, per-part failover to SAME twins, compensation (unwind, then buy the package), and seeds 1–1,000 compared against the best package. The demo product is chosen by rule (largest rupee saving among publishable Remixes): the helicopter tour with private pickup. The demo seed is the first that shows a part failing over (seed 22), disclosed on screen.
- **The Sightseeing ranking** shows a TBO Remix card above the packages when that attraction has a publishable Remix.
- **Presenter:** 8 new beats (keys 1–8). Beats 5–6 land in R4–R5.
- **Tests: 67 passing** (+7: per-part SAME failover, compensation exercised, riskiest-first, seed reproduction, API, no typed-in numbers).

### Correction to the R2 gate (found while building R3)
1. **The R2 gate numbers came from a stale build.** I changed the day-trip meeting point after the last pipeline run. A fresh build shifted the random draws, and at first gave **0** publishable Remixes, because every Remix Promise fell.
2. **Root cause, a generator design flaw:** part attempts were sampled per SKU. Transfers are ~92% of SKUs, so each supplier had only 24–57 ticket attempts per lead bucket, and the Promise model rightly leaned on the market average (Sunbird tickets estimated at 6.5% failure vs 2.5% true).
3. **Fix:** attempts are now sampled by role, half tickets and half transfers (`booking_log.TICKET_SHARE`). This was changed **after** seeing the gate, and is disclosed here and in DATA.md.
4. **After the fix**, the same 4 products pass:

| Product | Agent saves | TBO margin | Remix Promise |
|---|---|---|---|
| Helicopter + private pickup | 11.9% | 13.5% | 95.7% |
| Ski Dubai + lunch | 7.2% | 7.8% | 95.5% |
| IMG Worlds + lunch | 4.7% | 4.9% | 97.6% |
| Food tour + private pickup | 4.0% | 4.1% | 95.1% |

5. **Honest reading:** the winners sit close to the guardrails, so the count is sensitive to random draws. The food tour clears the 4% margin by 0.1 point.
6. **Sandbox vs estimate:** over 1,000 seeds the helicopter Remix is secured about 93% of the time, against the estimated 95.7%. Helicopter demand is more volatile than the average the Promise model sees. METRICS will report this gap.

## Earlier: R1 + R2, stopped at the R2 gate

### Pivot (2026-11-07)
The headline moves from SameSame to **Remix**: TBO products assembled from parts suppliers already sell (ticket + transfers + lunch), published only when the Remix is the SAME product as a package, cheaper on True Price, and leaves TBO a margin. The plan is in [REMIX_PLAN.md](REMIX_PLAN.md). Every existing engine is reused unchanged, and all 48 earlier tests still pass.

### Done: R1, component catalogue (synthetic, disclosed in DATA.md)
- `data/components.py`:
  - 159 entry tickets with slots
  - 12 lunch vouchers
  - 1,840 one-way transfers between 6 hotel zones and 25 meeting points: 1,500 private (sedan/SUV, on request), 340 shared (fixed timetable)
  - 313 rates are "package only" and never bundled
- **Ticket price** is the market's own price for that ticket alone. The per-supplier net factor averages ~1.0, so parts carry no planted discount. Where every package of a core includes a transfer, the ticket is priced at the package minus 20% (shared) or 30% (private).
- **Transfer prices** are Dubai-style tariffs on road distance: private ₹1,600 + ₹55/km per sedan; shared ₹350 + ₹9/km per seat.
- All parameters were fixed before any Remix result was computed.
- **Booking log:** +6,000 part attempts, appended after the existing 24,000 so earlier numbers are unchanged. The Promise model now fits `ticket` and `transfer` with no code change.

### Done: R2, recipe search, pricing, guardrails (`remix/engine.py`, `tests/test_remix.py`)
- **Search:** enumerate ticket × outbound × return × lunch. Keep only bundleable parts, drop-off at the ticket's meeting point, arrival ≥ 20 min before the slot, waits ≤ 90 min. Take the cheapest assembly that passes every guardrail.
- **SAME, never VARIANT:** strict fields must be equal, and so must every descriptive field the package states. A field only the package is silent on becomes "unverified" and needs approval.
  - The first gate run caught the engine building a *private* desert safari from a *shared* 4x4 ticket whose text didn't state its option. That is now a difference, and a test guards it.
- **Pricing:**
  - TBO's cost is the sum of part True Prices (fitted Promise per part) plus assembly risk (unwind and buy the package).
  - The agent's True Price is the sell price plus cancellation risk under the strictest part's rule.
  - The agent gets 50% of the gap.
  - Guardrails: saving ≥ 3%, margin ≥ 4%, Remix Promise ≥ 95%, slack ≥ 20 min.
- **Tests: 60 passing** (+12).

### R2 gate: honest numbers (Deira, 2 adults, 21 days out, default settings)
| | Count of 30 multi-part packages |
|---|---|
| A SAME Remix exists (bundleable, feasible timing) | 17 (57%) |
| Remix cheaper than the best package on True Price | 9 (30%) |
| **Passes every guardrail** | **4 (13%)** |
| Package cheaper (reported, not hidden) | 8 |
| No valid assembly | 13 |

- **Publishable:**

| Product | Agent saves | TBO margin | Remix Promise |
|---|---|---|---|
| Helicopter tour + private pickup | 12.2% | 13.9% | 96.3% |
| Ski Dubai + lunch | 7.2% | 7.8% | 95.8% |
| IMG Worlds + lunch | 5.0% | 5.2% | 99.4% |
| Old Dubai food tour + private pickup | 5.0% | 5.2% | 99.5% |

- **Cheaper, but blocked only by the Promise guardrail:** Aquaventure + shared transfer (9.3%, Promise 89.4%), Aquarium + shared transfer (6.6%, 90.7%), Ski Dubai + shared transfer (11.7%, 94.3%).
- **Package wins:**

| Product | Package cheaper by |
|---|---|
| Morning desert safari | ₹3,438 |
| Private desert safari | ₹2,180 |
| Dubai Fountain private | ₹1,635 |
| Dhow cruise with transfer | ₹282 |

  Also Miracle Garden, Global Village and Old Dubai. Pooled operator transfers beat standalone ones.
- **No valid assembly:**
  - Day trips: the coach is the tour, and the "meet at the mall" version is a different product.
  - Evening shows and the evening desert safari: the shared coach arrives 15 min before the start, under the 20-min buffer.
  - Parks: the last return coach leaves more than 90 min after closing.
  - Some routes are only sold package-only.
- **The three hand-written demo products have no publishable Remix:** Burj Khalifa is ticket-only (one part), and the desert safari and dhow cruise lose or fail on timing.
- **Other zones:** 2–5 publishable (fewest from the Marina). **Pessimistic preset** (transfers +30%, part failures ×1.5): 2 publishable.

## Earlier status: M4 done

### Done: M4, fitted Promise model (2026-11-06)
- **Promise is now a fitted model** (`backend/samesame/pricing/promise.py`), not raw Wilson counts. It is a hierarchical Dirichlet-multinomial (a Beta-binomial on the honour rate):
  - per product: market-wide outcome shares, plus how each lead bucket shifts them
  - supplier × product: shrunk toward the market
  - supplier × product × lead bucket: shrunk toward its supplier, moved by the market's lead-time shift
- **How the priors are set:**
  - Concentrations are fitted by empirical Bayes (maximum marginal likelihood on the log).
  - The supplier prior is capped at 200 bookings (assumption): a few similar suppliers can't make us sure about the next one. It fits at 39 (hotels) and 55 (activities), so the cap doesn't bind today.
  - A cell's prior is capped at the bookings it was estimated from, so intervals stay honest.
  - Price-rise size is shrunk with 20 pseudo-observations (assumption).
- **Pipeline:** a new stage after the booking log writes `promise_model.parquet` and `promise.json`. The API serves posterior means, a 95% credible interval, and the share borrowed from the prior (shown in the gauge tooltip).
- **Honest check (METRICS.md, rebuilt every build):** fit on the log up to 30 days before its end, score the last 30 days (3,987 attempts). Log loss:

| Training data | Fitted model | Cell's own counts | Market rate |
|---|---|---|---|
| 100% (20,013 attempts) | **0.465** | 0.467 | 0.516 |
| 10% | **0.482** | 0.499 | 0.519 |
| 2% (400 attempts) | **0.505** | 0.587 | 0.522 |

  - The model wins at every data size, and by the most when data is thin, which is when shrinkage should matter.
  - Hotel honour calibration on the test window: Kestrel predicted 72.0% vs observed 68.7%, Mynah 96.0 vs 96.8.
- **Tests: 48 passing** (+10).
  - `test_golden_api.py`: the brief's golden case through the HTTP API. A is cheaper on sticker and ≥ ₹2,000 dearer on True Price, and the ranks are consistent. Risk terms use the same fitted Promise the supplier report shows. Over 40 seeds, "Book both" fails over at least once and only ever to the same hotel, room and board. A seed reproduces its story exactly.
  - `test_promise.py`: 3 failures don't condemn a new supplier, and its interval stays wide. Lots of evidence overrides the prior. An empty cell borrows its supplier's behaviour. Shares sum to 1. The model never reads the generator's behaviour table.
- **What didn't change:** the sandbox still draws outcomes from the world's behaviour model, not from our estimate (the estimate is the app; the sandbox is the world), so the "Book both" story at seed 1 is identical.

### Done: visual redesign (2026-11-05)
- **Palette** from the "Sunseeker" reference: deep navy, dusty sky blue, warm cream and sand, with burnt orange as the single accent. Red stays reserved for "Looks the same, isn't". Colours are tokens in `tailwind.config.js`.
- **Type:** headings use Playfair Display (installed locally, still offline); Inter for UI.
- **Shell:** a top navigation bar with a sun logo mark replaces the sidebar. City and data-mode pills sit top right, and the credits move to a footer.
- **Hotels page:**
  - a hero with a serif headline, a search bar holding the real search parameters, and an original Dubai skyline SVG
  - a three-column layout: DNA filters and "About the data" on the left; Today/SameSame and the cards in the middle; the look-alike alert card and map on the right
  - cards with a big photo, rank badge, serif name, distance, supplier avatars, From and True Price, and "Why ranked here" chips
- **Every other page** opens with the same coastal header band. Sightseeing variants get a photo panel, and DNA segments, gauges and bars use the palette.
- **Unchanged:** behaviour, data, the presenter beats and the Today→SameSame animation. All seven beats were checked on the production build with no console errors.


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
| Demo search | 84 listings → 21 hotels, 63 duplicates collapsed (86 → 20 since N1) |
| Look-alike trap | Flora Hotel Apts. ↔ Flora Al Souq Hotel, 198 m |
| Offer A: Kestrel ₹18,600 | True Price **₹24,175** (sticker #1 → True #4) |
| Offer B: Mynah ₹20,100 | True Price **₹20,773** (sticker #4 → True #1) |
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

### Next: M5
- Real Monte-Carlo session simulator (replaces the MOCK closed form), crop-robust image matching.
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
