# SameSame — Plan

> "Same same, but different. We know exactly how, and what it really costs."

## 1. The goal in five lines

1. TBO already maps hotels (Vervotech). We build the layer **above** mapping: which offer should the agent book, and is it really the same thing?
2. For hotels: consolidate duplicates (keeping look-alikes apart), map room types, build a golden record, and compare offers on **True Price** (what the agent actually pays, if the booking actually goes through).
3. For sightseeing, where no mapping standard exists: the full stack, from finding twins to splitting them into SAME / VARIANT / DIFFERENT with an explicit diff.
4. Supplier reliability is learned from booking logs (Promise model). Failed bookings fail over automatically, to SAME twins only.
5. We win on a 4-minute live demo where every number comes from the engine, with an honesty story the CFO can't break: blind-set metrics, labelled synthetic data and live assumption sliders.

## 2. Repo layout

```
samesame/
  start.py                    # one command: venv + deps + build + run (macOS & Windows)
  PLAN.md PROGRESS.md README.md METRICS.md DEMO.md QA.md
  backend/
    requirements.txt          # CPU torch pinned via extra index
    samesame/
      config.py               # paths, seeds, FX rate, LLM env vars. Plain constants, no config system
      schemas.py              # pydantic models = the data contract (mirrors data_spec)
      llm.py                  # litellm wrapper: disk cache, JSON schema, offline mode
      data/                   # base truth loaders + synthetic supplier generator + booking log
      matching/               # normalize, block, features, scorer (LightGBM), cluster, adjudicate, review
      variants/               # attribute extractor (regex -> LLM), Variant DNA
      golden/                 # golden record vote + image phash
      pricing/                # promise (Beta-binomial), true_price
      ranking/                # transparent score (+ LambdaMART experiment)
      booking/                # supplier sandbox + failover router
      sim/                    # session simulator
      api/                    # FastAPI app; serves built frontend in demo mode
      pipeline.py             # `python -m samesame.pipeline` builds every artifact into data/build/
    scripts/pull_osm.py       # one-off snapshot pull (the only network step for data)
    tests/
  frontend/                   # Vite + React + TS + Tailwind + Radix/shadcn-style components + framer-motion + Leaflet
    src/contracts.ts          # TS mirror of the API JSON contracts
  data/
    raw/osm/                  # committed OSM snapshot (ODbL)
    base/                     # hand-written attractions, chain list, curated hotels
    images/ + LICENSES.csv
    build/                    # generated (gitignored, deterministic from seed)
    blind/                    # blind test set. ONLY eval code may read it (test enforces)
  contracts/                  # example JSON payloads per endpoint (frontend mocks use these)
```

## 3. Milestones (demo runnable at the end of each)

| M | What | Owner(s) | Demo state at end |
|---|------|----------|-------------------|
| **M0** | Scaffold, schemas, contracts, `start.py`, OSM snapshot + offline basemap GeoJSON | all (lead: C for start.py/frontend shell, A for OSM) | `python start.py` opens an app shell with nav + offline Bangkok map |
| **M1** | **Vertical slice on mock JSON**: all 7 beats clickable, presenter keys 1–7, Today/SameSame merge animation, offers table, True Price flip, book-both panel, DNA strip, review queue | C (UI), A+B write contract fixtures | Full demo walkable end-to-end (mock data, labelled MOCK) |
| **M2** | Synthetic supplier layer: 300 hotels → 6 bird suppliers, corruptions, ≥20 real hard negatives, rooms, 25 attractions → activity variants, images, 20k+ booking log, ground truth | A (hotels/rooms/activities), B (behaviour profiles + booking log) | Same UI, endpoints now read generated data |
| **M3** | Twin Finder (block → features → LightGBM → constrained clustering → gray zone) + Variant DNA + room mapping. Blind set + labelling tool; C labels | A; C labels | Real clusters, look-alike trap computed, real review queue |
| **M4** | Promise model + True Price + booking sandbox + failover router. Golden-case tests | B | Real offers table, real flip, real "Book both" |
| **M5** | Golden record + image dedup; ranker (transparent score; LambdaMART only if clearly better); session simulator + sliders + pessimistic preset | A (golden), B (ranker/sim), C (screens) | All 7 beats on real engines |
| **M6** | LLM adjudicator/extractor/diff sentences (cached, optional) + cost report; review-queue feedback retrain; BYO-logs importer; supplier report card | A (LLM matching), B (importer), C (ops UI) | Mode badge shows LLM/offline |
| **M7** | METRICS.md, DEMO.md, QA.md, README; empty/loading/error states; Windows test; rehearsal; optional backup hosting | all | Ship |

Parallelism: after M0 the JSON contracts in `contracts/` are the seam. C builds the UI against them while A and B build engines that must emit exactly those shapes.

## 4. Riskiest unknowns

1. **Synthetic-data credibility.** We generate both the data and the labels, so a 99% precision score proves little. Mitigations: entity-grouped train/test split; held-out corruption families in the blind set; C's human labels compared against generator truth (and we report agreement); every hard negative in the blind set; error analysis published.
2. **Real look-alike pairs in OSM.** We need ≥20 same-chain, nearby, different-branch pairs that really exist. Bangkok has many (Holiday Inn / Express, ibis / ibis Styles, Novotel branches, Citadines), but tagging quality varies. We check right after the pull and fill gaps with clearly fictional pairs.
3. **Install fragility on stage machines.** torch + LightGBM + sentence-transformers on mixed macOS/Windows. Mitigation: CPU wheels, model cached in `data/models/`, and `start.py --demo` serves the prebuilt frontend from FastAPI on **one port**, so there's no Vite dev server on stage.
4. **True Price defensibility.** The CFO will probe double counting. The terms must be mutually exclusive outcomes (see §5.3), and each term needs a visible assumption.
5. **Demo determinism vs honesty.** "Book both" must show one failover live, and the outcome must come from the behaviour model (§5.4).

## 5. Where I disagree with the brief, or would change it

1. **LambdaMART trained on simulated sessions is circular.** The simulator encodes our assumptions about agent behaviour, so a ranker learned from it re-learns those assumptions and will "beat" the baseline on the simulator by construction. A CFO will spot this. **Decision:** the production ranker is a transparent weighted score over True Price, Promise, relevance and content quality, with "why ranked here" chips derived from the actual terms. LambdaMART is built as an experiment, evaluated on a *held-out* simulator config (different seed and different slider settings), and we report it honestly. It ships only if it wins there. I expect it to stay as a backup slide.
2. **Ground truth for the blind set.** The generator already knows the truth, so pure human labelling of synthetic pairs mostly tests whether C agrees with our SAME/VARIANT definitions. That is still useful, because it validates the definitions. **Decision:** the blind set carries both the generator label and C's label. Metrics are reported against the generator label, and C's disagreements are listed as definition ambiguities. Blind-set pairs come from entities whose ids are excluded from training (grouped split) **and** include corruption variants the generator only applies to the blind partition.
3. **"Book both" determinism.** A fixed seed that happens to produce exactly one failover is seed-shopping if we hide it. **Decision:** the sandbox draws outcomes from the Promise-model ground-truth profiles with a seeded RNG. The demo seed is shown on screen ("scenario seed 7, chosen to show a failover; ↻ rerun with a fresh seed") and DEMO.md says so. Pressing ↻ live is our honesty flex: Kestrel fails roughly 26% of the time at this lead time, so judges will usually see a clean confirm, and we say so out loud.
4. **True Price term overlap.** The brief lists "P(price change) × increase" and "P(fails) × next-best-twin delta" separately. **Decision:** we model booking outcomes as mutually exclusive {confirmed, price_changed, sold_out, error} at the offer's lead time. On price_changed the agent pays min(new price, next SAME twin + friction). On sold_out/error the agent pays the next SAME twin + friction. Cancellation exposure applies only to the confirmed path. This avoids double counting and still reproduces the golden case. My back-of-envelope: A ≈ 18,600 + 3,300 + 1,674 + ~270 + ~200 ≈ **₹24,0xx**, and B ≈ 20,100 + ~540 + ~30 ≈ **₹20,6xx**. That is consistent with the brief, with the real numbers to come from the engine.
5. **Images.** Fetching CC-licensed photos per hotel is slow, and the licences are fiddly. Perceptual-hash dedup also needs textured images to be meaningful. **Decision:** procedurally generated, textured "illustrative" images (PIL: gradients, shapes, noise, a building silhouette), and their corrupted copies (crop, resize, watermark, recompress) for dedup. Optionally ~25 CC0 photos for attractions, logged in LICENSES.csv. Everything is labelled "illustrative".
6. **shadcn/ui CLI needs network.** We copy in the handful of components we need (Button, Badge, Tooltip, Switch, Tabs, Table, Slider) as local source on Radix. Same result, no CLI dependency.
7. **Python version.** This machine has 3.13 and no 3.11. We support **3.11–3.13**. `start.py` checks for ≥3.11, and all pinned deps have wheels for 3.11–3.13 on macOS arm64/x86 and Windows.
8. **4 minutes for 7 beats is ~30 s per beat.** The supplier report card is cut from the live demo (it stays in the app for Q&A), and the simulator gets ~20 s showing one slider plus the pessimistic preset.
9. **The 98%-reliable supplier question and exploration share.** The Promise model gives new or low-volume suppliers a shrunk prior plus a small exploration share, so a supplier we down-ranked can still earn its way back. That answers "you're killing my suppliers".

## 6. Key technical decisions (committed)

- **Storage:** DuckDB file `data/build/samesame.duckdb` plus parquet. The API reads precomputed tables, and nothing heavy runs at request time except the sandbox and the simulator.
- **Matching thresholds (precision-first):** auto-merge if p ≥ τ_hi, where τ_hi is picked on the validation fold for precision ≥ 0.99. Gray zone [τ_lo, τ_hi) goes to the LLM (target 5–10% of candidate pairs), and if there is no LLM or it isn't confident, to the human queue. Hard never-merge rules override the model: different chain sub-brand; >1.5 km apart with a different phone; different external map id when both exist.
- **Clustering:** union-find over auto-merge edges with constraint checks at each union, so a never-merge pair can't be joined transitively. A merge that violates a constraint is refused and routed to review.
- **Promise model:** Beta-binomial per (supplier, product type, lead-time bucket), shrunk toward the supplier-wide and then global rate, with outcome shares from a Dirichlet over the 4 outcomes.
- **Frontend in demo mode:** prebuilt `frontend/dist` served by FastAPI at `http://localhost:8000`. In dev mode: Vite on 5173, proxying `/api`.
