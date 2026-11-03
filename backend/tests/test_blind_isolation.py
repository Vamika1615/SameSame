"""The blind test set must never reach training or tuning code.

Only samesame/eval/ (metrics reporting) and the labelling tool may reference it.
This is a static check: any other module that mentions config.BLIND or a data/blind
path fails the build.
"""
import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "samesame"
ALLOWED = {PKG / "config.py"}                      # defines the path
ALLOWED_DIRS = {PKG / "eval", PKG / "labelling"}   # read it, never train on it
PATTERN = re.compile(r"\bBLIND\b|data[/\\]+blind|[\"']blind[\"']")


def test_only_eval_touches_blind_set():
    offenders = []
    for py in PKG.rglob("*.py"):
        if py in ALLOWED or any(d in py.parents for d in ALLOWED_DIRS):
            continue
        if PATTERN.search(py.read_text(encoding="utf-8")):
            offenders.append(str(py.relative_to(PKG)))
    assert not offenders, f"modules referencing the blind set: {offenders}"


def test_eval_modules_do_not_write_training_data():
    """Eval may read the blind set but must not import the trainer (no tuning on blind)."""
    for d in ALLOWED_DIRS:
        for py in d.rglob("*.py") if d.exists() else []:
            src = py.read_text(encoding="utf-8")
            assert "matching.train" not in src, f"{py.name} imports the trainer"
