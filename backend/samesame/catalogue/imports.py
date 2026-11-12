"""Supplier-sheet imports: kept on disk, applied to the catalogue, decided by people, all reversible.

  data/imports/<import_id>/source.<ext>   the file exactly as uploaded
  data/imports/<import_id>/meta.json      file, supplier, status (draft | applied | removed), timestamps, sha256
  data/imports/<import_id>/result.json    what the import engine read and resolved (ingest/sheet.py)
  data/imports/decisions.jsonl            people's decisions, append-only; undo appends a row

An import changes the catalogue only once it is applied. Removing it takes its hotels and rates back out; nothing is
deleted, so it can be restored. Re-uploading the same file returns the existing import.
"""
import hashlib
import json
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path

from samesame import config

LOCK = threading.Lock()
STATUSES = ("draft", "applied", "removed")


class ImportError_(ValueError):
    pass


def _root() -> Path:
    config.IMPORTS.mkdir(parents=True, exist_ok=True)
    return config.IMPORTS


def _now() -> str:
    return datetime.now().isoformat(timespec="microseconds")   # imports apply in this order; two in one second must not tie


def _dir(import_id: str) -> Path:
    if not re.fullmatch(r"imp-[0-9a-z-]+", import_id or ""):
        raise ImportError_("No such import.")
    d = _root() / import_id
    if not (d / "meta.json").exists():
        raise ImportError_("No such import.")
    return d


def _read(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _write(p: Path, obj):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def supplier_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\b(20\d\d|rates?|usd|inr|v\.?\d+(\.\d+)?|copy|final|\d{6,})\b", " ", stem, flags=re.I)
    words = [w for w in stem.split() if w]
    return " ".join(words[:3]).title() or "Supplier"


# ------------------------------------------------------------------ imports
def list_meta() -> list[dict]:
    out = []
    for d in sorted(_root().glob("imp-*")):
        if (d / "meta.json").exists():
            out.append(_read(d / "meta.json"))
    return sorted(out, key=lambda m: m["uploaded_at"], reverse=True)


def meta(import_id: str) -> dict:
    return _read(_dir(import_id) / "meta.json")


def result(import_id: str) -> dict:
    return _read(_dir(import_id) / "result.json")


def source(import_id: str) -> tuple[bytes, str]:
    d = _dir(import_id)
    m = _read(d / "meta.json")
    return (d / m["stored_as"]).read_bytes(), m["file"]


def create(data: bytes, filename: str, supplier: str | None, resolve) -> tuple[dict, bool]:
    """Store and resolve an upload. resolve(data, filename) -> result. Returns (meta, created?)."""
    sha = hashlib.sha256(data).hexdigest()
    for m in list_meta():
        if m["sha256"] == sha and m["status"] != "removed":
            return m, False
    res = resolve(data, filename)                       # raises SheetError before anything is written
    with LOCK:
        import_id = f"imp-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{sha[:6]}"
        d = _root() / import_id
        d.mkdir(parents=True, exist_ok=False)
        ext = Path(filename).suffix.lower() if Path(filename).suffix.lower() in (".csv", ".xlsx", ".xlsm", ".txt") else ".csv"
        (d / f"source{ext}").write_bytes(data)
        m = {"id": import_id, "file": filename, "supplier": (supplier or "").strip() or supplier_from_filename(filename),
             "status": "draft", "uploaded_at": _now(), "applied_at": None, "removed_at": None, "checked_at": _now(),
             "sha256": sha, "stored_as": f"source{ext}", "bytes": len(data), "layout": res["layout"], "summary": res["summary"]}
        _write(d / "result.json", res)
        _write(d / "meta.json", m)
    return m, True


def set_status(import_id: str, status: str) -> dict:
    if status not in STATUSES:
        raise ImportError_("Unknown status.")
    with LOCK:
        d = _dir(import_id)
        m = _read(d / "meta.json")
        m["status"] = status
        if status == "applied":
            m["applied_at"] = m["applied_at"] or _now()
            m["removed_at"] = None
        if status == "removed":
            m["removed_at"] = _now()
        _write(d / "meta.json", m)
    return m


def recheck(import_id: str, resolve) -> dict:
    """Resolve the stored file again against today's catalogue (after a rebuild, or after earlier imports changed)."""
    data, filename = source(import_id)
    res = resolve(data, filename)
    with LOCK:
        d = _dir(import_id)
        m = _read(d / "meta.json")
        m.update(checked_at=_now(), layout=res["layout"], summary=res["summary"])
        _write(d / "result.json", res)
        _write(d / "meta.json", m)
    return m


def delete_all_for_tests():
    shutil.rmtree(_root(), ignore_errors=True)


# ------------------------------------------------------------------ decisions
def _log() -> Path:
    return _root() / "decisions.jsonl"


def decide(import_id: str, sheet_id: str, kind: str, value: str, room: str | None = None, who: str = "ops") -> dict:
    """kind 'hotel': value is a catalogue hotel id or 'new'. kind 'room': room is the room name as written,
    value a room id of the target hotel or 'new'."""
    if kind not in ("hotel", "room") or not value:
        raise ImportError_("A decision needs a kind (hotel or room) and a value.")
    res = result(import_id)
    h = next((h for h in res["hotels"] if h["sheet_id"] == sheet_id), None)
    if not h:
        raise ImportError_("No such hotel in this import.")
    if kind == "room" and not any(r["raw"] == room for r in h["rooms"]):
        raise ImportError_("No such room in this hotel.")
    with LOCK:
        n = sum(1 for _ in _log().open(encoding="utf-8")) if _log().exists() else 0
        row = {"audit_id": f"d-{n + 1}", "import_id": import_id, "sheet_id": sheet_id, "kind": kind, "room": room, "value": value,
               "who": who, "ts": _now(), "action": "decide"}
        with _log().open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def undo(audit_id: str) -> dict:
    with LOCK:
        rows = log()
        if not any(r["audit_id"] == audit_id and r["action"] == "decide" for r in rows):
            raise ImportError_("No such decision.")
        row = {"audit_id": audit_id, "action": "undo", "ts": _now()}
        with _log().open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    return row


def log() -> list[dict]:
    if not _log().exists():
        return []
    return [json.loads(l) for l in _log().read_text(encoding="utf-8").splitlines() if l.strip()]


def decisions() -> dict[tuple, dict]:
    """Effective decisions: (import_id, sheet_id, kind, room) -> the latest decision that wasn't undone."""
    undone = {r["audit_id"] for r in log() if r["action"] == "undo"}
    out = {}
    for r in log():
        if r["action"] == "decide" and r["audit_id"] not in undone:
            out[(r["import_id"], r["sheet_id"], r["kind"], r["room"])] = r
    return out


def history() -> list[dict]:
    undone = {r["audit_id"] for r in log() if r["action"] == "undo"}
    return [{**r, "undone": r["audit_id"] in undone} for r in reversed(log()) if r["action"] == "decide"]


def stamp() -> tuple:
    """Changes whenever any import, result or decision changes (for caches)."""
    files = [p for p in _root().rglob("*.json*") if p.is_file()]
    return tuple(sorted((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in files))
