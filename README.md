# SameSame

**Same same, but different. We know exactly how, and what it really costs.**

SameSame finds every copy of the same hotel, room or tour across suppliers, shows exactly what is different, and ranks offers by **True Price**: what the agent will actually pay for the same thing, if the booking actually goes through.

Built for the TBO Tek hackathon, Track 2 (Multi-supplier Inventory). All supplier data is **synthetic**; images are **illustrative**.

## Run it

Requirements: Python 3.11+ and Node.js 18+. First run needs network; after that it runs fully offline.

macOS / Linux:
```bash
python3 start.py
```

Windows (PowerShell):
```powershell
py start.py
```

| Command (Windows: `py` instead of `python3`) | What it does |
|---|---|
| `python3 start.py` | dev: API on :8000, UI on :5173 with hot reload |
| `python3 start.py --demo` | stage mode: builds the UI once and serves everything from http://localhost:8000 |
| `python3 start.py --rebuild` | re-run the data/model pipeline |
| `python3 start.py --test` | run backend tests |
| `python3 start.py --skip-install` | offline start, no pip/npm |

**macOS + LightGBM:** if `lightgbm` fails to import, run `brew install libomp`. `start.py` also tries an automatic venv-only fallback that uses the libomp bundled with scikit-learn.

**LLM (optional):** set `LLM_API_KEY` (and optionally `LLM_MODEL`, default `anthropic/claude-haiku-5-5`). Without a key, everything still runs: gray-zone pairs go to the human review queue, extraction is rules-only, and diff sentences use templates. The sidebar shows which mode is active.

## Data provenance and licences

- Hotel base truth, river, roads and district outlines: © OpenStreetMap contributors, licensed under the [ODbL 1.0](https://opendatacommons.org/licenses/odbl/). Snapshot in `data/raw/osm/` (see `SNAPSHOT.txt` for timestamps and queries). Pulled once with `backend/scripts/pull_osm.py`.
- Supplier feeds, room names, offers, activities, booking logs: synthetic, generated from the base truth with a fixed seed by `python -m samesame.pipeline` (~10 s; `start.py` runs it when needed).
- Images: procedural, never photos of real hotels. Licences in `data/build/images/LICENSES.csv` (CC0, own work). All are labelled "illustrative" in the UI.
- **[DATA.md](DATA.md)** lists exactly what is real, what is synthetic, and the few fixed inputs (the brief's golden-case offers).
- The first build downloads the MiniLM sentence-embedding model (87 MB) into `data/models/` once; after that everything runs offline. Without network the matcher drops that one feature and records it in `data/build/matcher.json`.
- **Matcher quality:** [METRICS.md](METRICS.md) is regenerated on every build from the frozen blind set in `data/blind/`. Teammates label that set (without seeing the model's answer) at http://localhost:8000/label.

_Architecture diagram, metrics and honest limitations: coming in later milestones (see PLAN.md, PROGRESS.md)._
