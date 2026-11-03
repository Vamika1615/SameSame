# PROGRESS

_Update after every milestone. Newest first._

## Status: M0 done → M1 next

### Done (M0, 2026-11-04)
- PLAN.md with build order, risks and pushback.
- Repo scaffold: `backend/samesame/*` packages, `frontend/` (Vite + React + TS + Tailwind + framer-motion + Leaflet), `data/` layout.
- `backend/samesame/schemas.py`: core tables + **API contracts**, mirrored in `frontend/src/contracts.ts`. This is the seam for parallel work.
- `start.py`: venv, CPU torch, pip, npm, pipeline, dev mode (8000 + 5173) and `--demo` single-port mode, `--test`, `--skip-install` (offline).
- OSM snapshot committed in `data/raw/osm/`: 1,257 hotel elements (1,187 named) plus a basemap of 64 river segments, 4,500 major-road segments and 50 district outlines, simplified to 0.9 MB.
- Offline map component: Leaflet with no tile server, verified at 1920×1080 with **zero non-localhost requests**.
- Tests (5 passing): API smoke tests; blind-set isolation guard (static scan, live from day one).

### Findings worth knowing
- **Real look-alikes exist**: 159 same-family hotel pairs under 3 km in OSM, e.g. Citadines Sukhumvit 8 vs 16 (551 m), Grande Centre Point Ratchadamri vs Prestige (64 m), Hilton Sukhumvit vs DoubleTree Sukhumvit (79 m), and Park Hyatt vs Hyatt Place (600 m). The ≥20 hard-negative target is easily met with real pairs.
- **OSM itself has duplicates** (e.g. "Mercure Bangkok Makkasan" twice, 5 m apart; "Holiday inn express Bangkok sathron" twice). M2 must de-duplicate the base truth before generating suppliers, or the ground truth will be wrong. This is also a good pitch line: even the open map has twins.
- Only 334 of 1,187 hotels have phones in OSM. The generator will synthesise phones (marked synthetic) so the phone feature is meaningful.

### Decisions made without asking (see PLAN.md §5)
- Python 3.11–3.13 supported (this Mac has 3.13).
- Light shadcn-style components are written locally (no shadcn CLI, so no network dependency).
- Accent colour is deep teal `#0b7a70`, with red reserved for the look-alike badge.
- **macOS LightGBM**: Homebrew here refuses to run because of an untrusted third-party tap (`mongodb/brew`). We did not touch tap trust. Instead, `start.py` automatically re-links the venv's `lib_lightgbm.dylib` to the `libomp.dylib` bundled in scikit-learn's wheel (adds an rpath and ad-hoc re-signs; venv only). `brew install libomp` remains the documented first choice.

### Next: M1 (vertical slice on mock JSON)
- C: listing page (Today/SameSame with layoutId merge animation + counter), look-alike badge + map pins, hotel detail with offers table + True Price flip, book-both panel, sightseeing DNA strips, review queue with S/V/D keys, simulator skeleton, presenter mode (keys 1–7 + step indicator).
- A + B: write `contracts/*.json` fixtures (valid against `schemas.py`, enforced by a test) served by `/api/*` with `mode.data = "mock"` until engines land.

### Known issues
- Starlette prints a deprecation warning about httpx in TestClient (harmless).
- District outlines are faint at projector brightness; revisit in the M1 polish.
- Windows not yet tested (start.py handles `Scripts/python.exe` and `npm.cmd`); to verify in M1 on a teammate's laptop.
