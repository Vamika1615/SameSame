"""Plain constants. Edit here; no config system on purpose."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW_OSM = DATA / "raw" / "osm"
BASE = DATA / "base"
BUILD = DATA / "build"
BLIND = DATA / "blind"          # blind test set: only samesame.eval may read this
IMAGES = DATA / "images"
LLM_CACHE = DATA / "llm_cache"
MODELS = DATA / "models"        # sentence-transformers cache
FRONTEND_DIST = ROOT / "frontend" / "dist"
DB_PATH = BUILD / "samesame.duckdb"
LABELS_PATH = BUILD / "review_labels.jsonl"   # human review labels: training feedback for the matcher

SEED = 20261104
CITY = "Bangkok"
CURRENCY = "INR"

# LLM is optional. No key -> offline mode (rules + templates + human queue).
LLM_MODEL = os.environ.get("LLM_MODEL", "anthropic/claude-haiku-5-5")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_ENABLED = bool(LLM_API_KEY)
USD_INR = 88.0                  # used to report LLM cost in rupees; assumption, update before demo

# True Price assumptions (each one is shown next to its term in the UI)
DEFAULT_AGENT_CANCEL_RATE = 0.09
COST_OF_CAPITAL_ANNUAL = 0.12   # agency working-capital rate
FAILOVER_FRICTION_INR = 500     # agent time + client friction when a booking must be redone
PICKUP_PP_INR = 450             # taxi to a meeting point and back, per person (activities without hotel pickup)

# Matching hard constraints
NEVER_MERGE_DISTANCE_M = 1500


def mode() -> dict:
    return {"llm": LLM_ENABLED, "llm_model": LLM_MODEL if LLM_ENABLED else None, "data": "synthetic"}
