"""Read a supplier's rate sheet, whatever its layout, into hotels, rooms, rates and conditions.

Three layouts seen in real supplier sheets:

  flat     one row per rate: Hotel | Room | Price | ... (columns found by their usual spellings)
  grid     a block per hotel: a hotel-name row, then a header row "Room Type | 04 Jan 26 - 05 Feb 26 | ...",
           sub-header rows splitting each season by weekdays (SUN-WED / THU-SAT) and occupancy (SGL & DBL),
           one row per room, extra-guest columns (EXTRA ADULT, CHILD 4-12, OCC MAX) and footnotes below.
           Each tab of a workbook is a rate plan (base, "5 Nts+", "6% OFF" ...).
  rotated  rooms across the columns, seasons down the rows (date from | date to | DBL | SGL | extra ...).

Merged header cells arrive as one value followed by blanks, so headers are filled across their span.
Nothing here knows about the catalogue; resolving hotels and rooms happens in ingest/sheet.py.
"""
import csv
import io
import re
from datetime import date, datetime
from pathlib import Path

MAX_CELLS = 400_000


class SheetError(ValueError):
    pass


# ------------------------------------------------------------------ reading
def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))
    return str(v).replace(" ", " ").strip()


def read_tables(data: bytes, filename: str) -> list[tuple[str, list[list[str]]]]:
    """[(tab title, rows of cell text)] for every non-empty tab (a CSV is one tab)."""
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        try:
            import openpyxl
        except ImportError as e:
            raise SheetError("Reading .xlsx needs openpyxl (pip install openpyxl); or save the sheet as CSV.") from e
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as e:
            raise SheetError(f"Couldn't open this Excel file ({type(e).__name__}). Is it a real .xlsx?") from e
        out, cells = [], 0
        for ws in wb.worksheets:
            rows = []
            for r in ws.iter_rows(values_only=True):
                row = [_cell(v) for v in r]
                while row and not row[-1]:
                    row.pop()
                rows.append(row)
                cells += len(row)
                if cells > MAX_CELLS:
                    raise SheetError("This workbook is too large to read here (over 400,000 cells).")
            while rows and not any(rows[-1]):
                rows.pop()
            if any(any(r) for r in rows):
                out.append((ws.title.strip(), rows))
        if not out:
            raise SheetError("The workbook is empty.")
        return out
    if name.endswith(".xls"):
        raise SheetError("Old .xls files aren't supported; save it as .xlsx or CSV.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")          # Excel's CSV export on Windows
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [[c.replace(" ", " ").strip() for c in r] for r in csv.reader(io.StringIO(text), dialect)]
    if not any(any(r) for r in rows):
        raise SheetError("The sheet is empty.")
    return [(Path(filename).stem, rows)]


def num(v) -> float | None:
    """'4', '4*', '₹ 12,500', '25,2048' (decimal comma), '487.5' -> float. 'NA', 'FREE', '' -> None."""
    t = str(v or "").strip()
    if not t or not re.search(r"\d", t):
        return None
    t = t.replace(",", "") if re.search(r"\d,\d{3}(?!\d)", t) else t.replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(m.group()) if m else None


def is_number(v: str) -> bool:
    return bool(re.fullmatch(r"[$₹€£]?\s*-?\d[\d,]*(\.\d+)?\s*%?", (v or "").strip()))


# ------------------------------------------------------------------ dates
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _side(t: str) -> tuple[int | None, int | None, int | None]:
    """'04 Jan 26' / 'Jan 04, 2026' / '04' / '2026-03-11' -> (day, month, year)."""
    t = t.strip().strip(",").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return int(m[3]), int(m[2]), int(m[1])
    m = re.fullmatch(r"(\d{1,2})\s*([A-Za-z]{3,9})\.?,?\s*(\d{2,4})?", t)
    if m and m[2][:3].lower() in MONTHS:
        return int(m[1]), MONTHS[m[2][:3].lower()], int(m[3]) if m[3] else None
    m = re.fullmatch(r"([A-Za-z]{3,9})\.?\s*(\d{1,2}),?\s*(\d{4})?", t)
    if m and m[1][:3].lower() in MONTHS:
        return int(m[2]), MONTHS[m[1][:3].lower()], int(m[3]) if m[3] else None
    m = re.fullmatch(r"(\d{1,2})", t)
    if m:
        return int(m[1]), None, None
    return None, None, None


def _year(y):
    return None if y is None else (2000 + y if y < 100 else y)


def date_range(text: str) -> tuple[str, str] | None:
    """'04 Jan 26 - 05 Feb 26', '02 - 31 Jan 27', 'May 14 - Aug 09, 2026', 'Dec 18, 2026 - Jan 02, 2027' -> ISO dates."""
    t = re.sub(r"\s+", " ", (text or "").replace("–", "-")).strip()
    if len(t) > 40 or not re.search(r"\d", t):
        return None
    parts = re.split(r"\s*-\s*(?=\d|[A-Za-z]{3})", t, maxsplit=1) if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", t) else [t]
    if len(parts) != 2:
        return None
    (d1, m1, y1), (d2, m2, y2) = _side(parts[0]), _side(parts[1])
    if d1 is None or d2 is None or m2 is None:
        return None
    m1 = m1 or m2
    y2 = _year(y2)
    y1 = _year(y1) or (y2 if y2 is None or m1 <= m2 else y2 - 1)
    if y2 is None:
        return None
    try:
        a, b = date(y1, m1, d1), date(y2, m2, d2)
    except ValueError:
        return None
    return (a.isoformat(), b.isoformat()) if a <= b else None


def one_date(text: str) -> str | None:
    t = (text or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return t
    d, mo, y = _side(t)
    if d and mo and y:
        try:
            return date(_year(y), mo, d).isoformat()
        except ValueError:
            return None
    return None


# ------------------------------------------------------------------ header vocabulary
DAYS = r"(mon|tue|wed|thu|fri|sat|sun)[a-z]*"
DAYS_RE = re.compile(rf"^{DAYS}\s*[-–/]\s*{DAYS}$|^{DAYS}$|^(all days|daily|weekdays?|weekends?)$", re.I)
OCC_RE = re.compile(r"\b(sgl|dbl|tpl|single|double|triple|quad|twin|per room|pax dbl|pax sgl)\b", re.I)
EXTRA_RE = re.compile(r"\b(child|children|teen|infant|extra|underage|adult|occ|max|supplement)\b", re.I)
ROOM_HDR_RE = re.compile(r"^(room\s*type(\s*name)?|room(\s*(category|name|description))?|accommodation|category)$", re.I)
CODE_HDR_RE = re.compile(r"\bcode\b", re.I)
TITLE_RE = re.compile(r"\b(rates?|usd|inr|eur|bw|booking window|dynamic|quoting|season|tto+|groups?|valid|issued|exhibit|inflation|offset|"
                      r"contract|net|market|discount|note|notes|terms|policy|room type|code)\b|^\*", re.I)


def days_label(t: str) -> str | None:
    t = re.sub(r"\s+", "", t or "")
    m = re.fullmatch(rf"{DAYS}[-–/]{DAYS}", t, re.I)
    if m:
        a, b = re.findall(r"(mon|tue|wed|thu|fri|sat|sun)", t, re.I)[:2]
        return f"{a.title()}–{b.title()}"
    return t.title() if DAYS_RE.match(t) else None


def occ_label(t: str) -> str | None:
    """'SGL & DBL', 'SINGLE', 'Pax DBL', 'SGL TO QUAD' -> a short occupancy label; extra-guest headers -> None."""
    t = re.sub(r"\s+", " ", (t or "").strip())
    if not OCC_RE.search(t) or re.search(r"child|teen|infant|underage|extra", t, re.I):
        return None
    t = re.sub(r"(?i)^pax\s+", "", t).upper()
    return t.replace("SINGLE", "SGL").replace("DOUBLE", "DBL").replace("TRIPLE", "TPL")


def currency_of(texts: list[str], filename: str) -> str | None:
    blob = " ".join(texts[:60]) + " " + filename
    for code, pat in (("USD", r"\bUSD\b|US\$|\$"), ("INR", r"\bINR\b|₹|\bRs\.?\b"), ("EUR", r"\bEUR\b|€"), ("AED", r"\bAED\b"), ("GBP", r"\bGBP\b|£")):
        if re.search(pat, blob, re.I if code != "USD" else 0):
            return code
    return None


# ------------------------------------------------------------------ footnotes and conditions
def conditions(lines: list[str]) -> list[dict]:
    """Classify the free-text notes around a grid: discounts, mark-up, minimum-stay fee, booking window, dynamic dates."""
    out, seen = [], set()
    for raw in lines:
        t = re.sub(r"\s+", " ", raw.replace("�", "").strip(" *\"")).strip()
        if not t or t.lower() in seen:
            continue
        seen.add(t.lower())
        c = {"kind": "note", "text": t}
        if m := re.search(r"(\d+)\s*-\s*(\d+)\s*(?:nights?|nts)\b\s*:?\s*(\d+(?:\.\d+)?)\s*%", t, re.I):
            c = {"kind": "discount", "text": t, "min_nights": int(m[1]), "max_nights": int(m[2]), "percent": float(m[3])}
        elif m := re.search(r"(\d+)\s*\+\s*(?:nights?|nts)\b\s*:?\s*(\d+(?:\.\d+)?)\s*%", t, re.I):
            c = {"kind": "discount", "text": t, "min_nights": int(m[1]), "max_nights": None, "percent": float(m[2])}
        elif m := re.search(r"mark(?:ed)?\s*-?\s*up\s*(?:by\s*)?(\d+(?:\.\d+)?)\s*%", t, re.I):
            c = {"kind": "markup", "text": t, "percent": float(m[1])}
        elif re.search(r"minimum length of stay|\bmlos\b|min(imum)? stay", t, re.I):
            m = re.search(r"[$₹€]\s*(\d+(?:\.\d+)?)", t)
            c = {"kind": "min_stay", "text": t, "fee": float(m[1]) if m else None}
        elif re.search(r"\bBW\b|booking window", t):
            r = date_range(re.sub(r"(?i).*?\b(BW|booking window)\b\s*:?\s*", "", t))
            c = {"kind": "booking_window", "text": t, "from": r[0] if r else None, "to": r[1] if r else None}
        elif re.search(r"dynamic", t, re.I):
            c = {"kind": "dynamic_dates", "text": t}
        elif re.search(r"\bnet\b.*\bper room\b|\bper room\b.*\bper night\b", t, re.I):
            c = {"kind": "rate_basis", "text": t}
        out.append(c)
    return out


# ------------------------------------------------------------------ layout detection
def _nonempty(r):
    return [(i, c) for i, c in enumerate(r) if c]


def _grid_header(r) -> tuple[int, list[int]] | None:
    """(room column, season columns) if this row is a grid header."""
    room = next((i for i, c in enumerate(r) if ROOM_HDR_RE.match(re.sub(r"\s+", " ", c))), None)
    if room is None:
        return None
    seasons = [i for i, c in enumerate(r) if i > room and date_range(c)]
    return (room, seasons) if seasons else None


def _date_row(r) -> tuple[str, str, int] | None:
    ne = _nonempty(r)
    if len(ne) < 3:
        return None
    a, b = one_date(ne[0][1]), one_date(ne[1][1])
    if a and b and sum(is_number(c) for _, c in ne[2:]) >= 1:
        return a, b, ne[1][0]
    return None


def detect(rows: list[list[str]]) -> str | None:
    if any(_grid_header(r) for r in rows[:300]):
        return "grid"
    if sum(bool(_date_row(r)) for r in rows[:300]) >= 3:
        return "rotated"
    from samesame.ingest.sheet import map_columns          # the flat reader's header map
    for r in rows[:12]:
        cols, _ = map_columns(r)
        if "name" in cols and "room" in cols:
            return "flat"
    return None


# ------------------------------------------------------------------ grid
def _looks_like_hotel(row) -> str | None:
    ne = _nonempty(row)
    if not 1 <= len(ne) <= 2:
        return None
    t = ne[0][1]
    if len(t) > 80 or not re.search(r"[A-Za-z]{3}", t) or TITLE_RE.search(t) or date_range(t) or is_number(t):
        return None
    return re.sub(r"\s+", " ", t).strip()


def parse_grid(rows: list[list[str]], tab: str) -> tuple[list[dict], list[str]]:
    """Hotel blocks from one grid tab, and the tab-level notes (title rows above the first hotel)."""
    headers = [(i, h) for i, r in enumerate(rows) if (h := _grid_header(r))]
    blocks, prev_end = [], 0
    tab_notes = []
    for bi, (h, (room_col, season_cols)) in enumerate(headers):
        end = headers[bi + 1][0] if bi + 1 < len(headers) else len(rows)
        name, name_row = None, None
        for j in range(h - 1, prev_end - 1, -1):
            if (n := _looks_like_hotel(rows[j])) and not re.search(r"\b(SUN|THU|SGL|DBL)\b", n):
                name, name_row = n, j
                break
        title = [" ".join(c for c in rows[j] if c) for j in range(prev_end, name_row if name_row is not None else h)]
        if bi == 0:
            tab_notes = [t for t in title if t]
        hdr = rows[h]
        code_col = next((i for i in range(room_col) if CODE_HDR_RE.search(hdr[i] or "")), None)
        after = [i for i in range(season_cols[-1] + 1, len(hdr)) if hdr[i] and not date_range(hdr[i])]
        width = max(len(r) for r in rows[h:end] or [hdr])
        spans = []
        for k, c in enumerate(season_cols):
            stop = season_cols[k + 1] if k + 1 < len(season_cols) else (after[0] if after else width)
            spans.append((c, stop, date_range(hdr[c]), hdr[c]))
        # sub-header rows: until the first row with a room name and a number under a season
        j = h + 1
        def is_data(r):
            return len(r) > room_col and r[room_col] and any(is_number(r[c]) or (r[c] or "").upper() in ("NA", "FREE") for c in range(season_cols[0], min(len(r), width)))
        sub = []
        while j < end and not is_data(rows[j]):
            if any(rows[j]):
                sub.append(rows[j])
            j += 1
        labels = _column_labels(sub, spans, width)
        extra_cols = {c: hdr[c] for c in after}
        rooms, rates, last = [], [], j
        while j < end:
            r = rows[j]
            if not is_data(r):
                if r and len(r) > room_col and not r[room_col] and any(occ_label(c) for c in r):
                    labels = _column_labels(sub + [r], spans, width)       # a mid-table header ("SGL TO QUAD")
                    j += 1
                    continue
                if any(r) and _nonempty(r)[0][1].startswith("*"):
                    break
                j += 1
                continue
            room = re.sub(r"\s+", " ", r[room_col]).strip()
            code = r[code_col].strip() if code_col is not None and code_col < len(r) else None
            extras = {}
            for c, (season, days, occ, extra) in labels.items():
                v = r[c] if c < len(r) else ""
                if not v:
                    continue
                if extra:
                    extras[f"{extra} ({season['label']})" if season else extra] = v
                elif is_number(v):
                    rates.append({"room": room, "code": code or None, "plan": tab, "season_from": season["from"], "season_to": season["to"],
                                  "season": season["label"], "days": days, "occupancy": occ, "price": num(v), "row": j + 1})
            for c, label in extra_cols.items():
                if c < len(r) and r[c]:
                    extras[re.sub(r"\s+", " ", label)] = r[c]
            rooms.append({"name": room, "code": code or None, "extras": extras, "row": j + 1})
            last = j
            j += 1
        notes = [" ".join(c for c in rows[k] if c) for k in range(last + 1, end) if any(rows[k]) and not _grid_header(rows[k])]
        if bi + 1 < len(headers):           # rows just above the next header belong to the next block's title
            notes = [n for n in notes if not _looks_like_hotel([n])]
        blocks.append({"name": name, "rooms": rooms, "rates": rates, "notes": notes, "tab": tab, "header_row": h + 1})
        prev_end = last + 1
    # footnotes under the last hotel, when no other hotel has notes of its own, are the whole tab's terms
    if len(blocks) > 1 and blocks[-1]["notes"] and not any(b["notes"] for b in blocks[:-1]):
        tab_notes = tab_notes + blocks[-1]["notes"]
        blocks[-1]["notes"] = []
    return blocks, tab_notes


def _column_labels(sub: list[list[str]], spans, width) -> dict[int, tuple]:
    """column -> (season, days, occupancy, extra label) for every column inside a season span."""
    out = {}
    for start, stop, rng, label in spans:
        season = {"from": rng[0], "to": rng[1], "label": re.sub(r"\s+", " ", label)} if rng else None
        carried_days = None
        for c in range(start, stop):
            days = occ = extra = None
            for r in sub:
                v = r[c] if c < len(r) else ""
                if (d := days_label(v)):
                    days = d
                elif (o := occ_label(v)):
                    occ = o
                elif v and EXTRA_RE.search(v):
                    extra = re.sub(r"\s+", " ", v)
            if days:
                carried_days = days
            elif not extra:
                days = carried_days                            # merged weekday header spanning SGL / DBL columns
            out[c] = (season, days, occ, extra)
    return out


# ------------------------------------------------------------------ rotated
def parse_rotated(rows: list[list[str]], tab: str) -> tuple[list[dict], list[str]]:
    data = [(i, d) for i, r in enumerate(rows) if (d := _date_row(r))]
    first = data[0][0]
    hdr_i = next((k for k in range(first - 1, -1, -1) if sum(bool(occ_label(c) or EXTRA_RE.search(c or "")) for c in rows[k]) >= 2), None)
    room_i = next((k for k in range(hdr_i - 1, -1, -1) if len(_nonempty(rows[k])) >= 2), None) if hdr_i is not None else None
    if hdr_i is None or room_i is None:
        raise SheetError("Found date rows but no room-name header above them.")
    hdr, rr = rows[hdr_i], rows[room_i]
    if any(re.search(r"\b(rack|net|promo|eur vs|inflation|offset)\b", c, re.I) for c in hdr + rr):
        raise SheetError("this looks like a contract workbook (rack, net and promo columns side by side), which isn't supported yet.")
    starts = [i for i, c in enumerate(rr) if c]
    notes = [" ".join(c for c in rows[k] if c) for k in range(0, room_i) if any(rows[k])]
    notes += [c for c in hdr[: data[0][1][2] + 1] if c and not occ_label(c)]
    name = next((n for k in range(room_i - 1, -1, -1) if (n := _looks_like_hotel(rows[k]))), None)
    rooms, rates = [], []
    for k, s in enumerate(starts):
        stop = starts[k + 1] if k + 1 < len(starts) else max(len(r) for r in rows)
        room = re.sub(r"\s+", " ", rr[s])
        extras = {}
        for i, (a, b, _) in data:
            for c in range(s, stop):
                v = rows[i][c] if c < len(rows[i]) else ""
                lab = hdr[c] if c < len(hdr) else ""
                if not is_number(v):
                    continue
                if o := occ_label(lab):
                    rates.append({"room": room, "code": None, "plan": tab, "season_from": a, "season_to": b, "season": f"{a} – {b}",
                                  "days": None, "occupancy": o, "price": num(v), "row": i + 1})
                elif lab:
                    extras.setdefault(f"{lab} (from {a})", v)
        rooms.append({"name": room, "code": None, "extras": dict(list(extras.items())[:6]), "row": room_i + 1})
    end = data[-1][0]
    notes += [" ".join(c for c in rows[k] if c) for k in range(end + 1, len(rows)) if any(rows[k])]
    return [{"name": name, "rooms": rooms, "rates": rates, "notes": [], "tab": tab, "header_row": hdr_i + 1}], notes


def _collapse(extras: dict) -> dict:
    """'CHILD 4-12 (04 Jan 26 - 05 Feb 26)': 'FREE' for every season -> 'CHILD 4-12': 'FREE'."""
    groups: dict = {}
    for k, v in extras.items():
        groups.setdefault(re.sub(r"\s*\((from )?[^()]*\d[^()]*\)$", "", k), []).append((k, v))
    out = {}
    for base, kv in groups.items():
        vals = {v for _, v in kv}
        if len(vals) == 1:
            out[base] = kv[0][1]
        else:
            out.update(kv)
    return out


# ------------------------------------------------------------------ everything
def parse(data: bytes, filename: str) -> dict:
    """{'layout', 'hotels': [...], 'tabs': [...], 'currency', 'warnings'} for any supported sheet.

    Each hotel: name (None if the sheet never says), rooms [{name, code, extras}], rates [normalised rate rows],
    conditions [classified notes]. Hotel blocks with the same name across tabs are merged (tabs = rate plans)."""
    tables = read_tables(data, filename)
    texts = [t for t, _ in tables] + [c for _, rows in tables for r in rows[:15] for c in r if c]
    currency = currency_of(texts, filename)
    hotels: dict[str, dict] = {}
    tabs, warnings, layout_seen = [], [], set()
    for tab, rows in tables:
        layout = detect(rows)
        if layout is None:
            warnings.append(f"Tab “{tab}”: couldn't find a rate table (no 'Room Type' header with season dates, and no hotel and room columns).")
            tabs.append({"tab": tab, "layout": None, "hotels": 0, "rates": 0})
            continue
        layout_seen.add(layout)
        if layout == "flat":
            tabs.append({"tab": tab, "layout": "flat", "hotels": None, "rates": None})
            continue
        try:
            blocks, tab_notes = parse_grid(rows, tab) if layout == "grid" else parse_rotated(rows, tab)
        except SheetError as e:
            warnings.append(f"Tab “{tab}”: {e}")
            tabs.append({"tab": tab, "layout": None, "hotels": 0, "rates": 0})
            continue
        tabs.append({"tab": tab, "layout": layout, "hotels": len(blocks), "rates": sum(len(b["rates"]) for b in blocks)})
        for b in [b for b in blocks if b["rates"]]:
            name = b["name"] or Path(filename).stem
            key = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
            h = hotels.setdefault(key, {"name": name, "name_from_file": b["name"] is None, "rooms": {}, "rates": [], "notes": [], "tabs": [],
                                        "address": None, "phone": None, "lat": None, "lng": None, "star": None})
            h["tabs"].append(b["tab"])
            for r in b["rooms"]:
                k = re.sub(r"[^a-z0-9]+", " ", r["name"].lower()).strip()      # tabs repeat rooms, some without the code column
                room = h["rooms"].setdefault(k, {"name": r["name"], "code": r["code"], "extras": {}, "rows": []})
                room["code"] = room["code"] or r["code"]
                if b["tab"] == h["tabs"][0]:
                    room["extras"].update(_collapse(r["extras"]))
                room["rows"].append(f"{b['tab']}!{r['row']}")
            codes = {re.sub(r"[^a-z0-9]+", " ", r["name"].lower()).strip(): r["code"] for r in b["rooms"]}
            for x in b["rates"]:
                code = x["code"] or h["rooms"].get(re.sub(r"[^a-z0-9]+", " ", x["room"].lower()).strip(), {}).get("code")
                h["rates"].append({**x, "code": code or codes.get(x["room"].lower()), "currency": currency, "row": f"{b['tab']}!{x['row']}"})
            h["notes"] += tab_notes + b["notes"]
        if layout == "rotated" and blocks and blocks[0]["name"] is None:
            warnings.append(f"Tab “{tab}”: the sheet doesn't name the hotel, so it's named after the file. A person should confirm it.")
    out = []
    for h in hotels.values():
        rooms = list(h.pop("rooms").values())
        out.append({**h, "rooms": rooms, "conditions": conditions(h.pop("notes")), "tabs": list(dict.fromkeys(h["tabs"]))})
    layout = "flat" if layout_seen == {"flat"} else ("grid" if "grid" in layout_seen else "rotated" if layout_seen else None)
    if layout is None or (layout != "flat" and not out):
        raise SheetError(warnings[0] if warnings else "Couldn't find a rate table in this file.")
    return {"layout": layout, "hotels": out, "tabs": tabs, "currency": currency, "warnings": warnings,
            "flat_tabs": [t["tab"] for t in tabs if t["layout"] == "flat"]}
