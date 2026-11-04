"""Variant DNA for sightseeing: read each supplier listing's title + description into structured fields,
assign it to a catalogue attraction, and group listings whose DNA is compatible into one variant.

Rules only (the LLM extractor for prose the rules miss is M6). Inclusions (pickup, meals, access,
extra stops) are advertised when they exist, so an unmentioned one means "not included" and must
match exactly. Descriptive fields (option, cancellation, duration) may simply be unstated: unknown
matches anything, two different stated values split the listings.
"""
import re

from rapidfuzz import fuzz

from samesame.ranking.score import haversine_m

FIELDS = ["pickup", "meals", "access", "option", "cancel", "stops", "duration", "slot"]


def _has(t, *pats):
    return any(re.search(p, t) for p in pats)


def extract(title: str, desc: str) -> dict:
    t = f"{title} {desc}".lower()
    d: dict = {}
    private = _has(t, r"\bprivate\b", r"\bpvt\b")
    pickup = _has(t, r"pick[- ]?up", r"collection from your h", r"ex-hotel", r"transfer", r"\bsic\b", r"from (your )?h(o)?t(e)?l", r"\bhtl\b")
    if _has(t, r"meet(ing)? (at|point)", r"\bassemble\b", r"meeting point"):
        d["pickup"] = "Meeting point"
    elif _has(t, r"\bpier\b"):
        d["pickup"] = "Pier check-in"
    elif pickup and private:
        d["pickup"] = "Private hotel pickup"
    elif pickup:
        d["pickup"] = "Shared hotel pickup"
    if _has(t, r"\bbbq\b|barbecue"):
        d["meals"] = "BBQ dinner"
    elif _has(t, r"buffet dinner"):
        d["meals"] = "Buffet dinner"
    elif _has(t, r"set (menu|dinner)"):
        d["meals"] = "Set dinner"
    elif _has(t, r"lunch", r"meal included"):
        d["meals"] = "Lunch"
    elif _has(t, r"\bdrink\b", r"beverage"):
        d["meals"] = "1 drink"
    if _has(t, r"skip[- ]the[- ]line", r"fast-?track", r"priority", r"no queu"):
        d["access"] = "Skip-the-line"
    elif _has(t, r"\bvip\b"):
        d["access"] = "VIP"
    elif _has(t, r"timed entry"):
        d["access"] = "Time-slot"
    for pat, val in [(r"sunset|golden[- ]hour|17:00", "Sunset slot"), (r"audio guide", "Audio guide"),
                     (r"(eng(lish)?)[- ]?(speaking )?guide|eng guide|guided|with guide", "Guide"),
                     (r"small group", "Small group"), (r"\bprivate\b|\bpvt\b", "Private"),
                     (r"window seat", "Window seat"), (r"vip (deck|seat)", "VIP seat/deck"), (r"standard seat", "Standard seat"),
                     (r"boat (ride )?included|boat included", "Boat ride included"), (r"sandboard", "Sandboarding"),
                     (r"vip lounge", "VIP lounge"), (r"daytime slot|day ticket", "Daytime slot"),
                     (r"evening slot", "Evening slot")]:
        if re.search(pat, t):
            d["option"] = val
            break
    if _has(t, r"\bnrf\b", r"non-?refundable", r"no refunds"):
        d["cancel"] = "Non-refundable"
    elif m := re.search(r"(free|cancel|refundable|fc)[^.]{0,25}?(\d+)\s*h", t):
        d["cancel"] = f"Free until {m.group(2)} h"
    elif _has(t, r"free cancellation", r"refundable"):
        d["cancel"] = "Free cancellation"
    if m := re.search(r"(?:duration|approx\.?|about)\s*:?\s*(\d+(?:\.\d)?)\s*(?:h\b|hrs?\b|hours?\b)", t):
        d["duration"] = f"{float(m.group(1)):g} h"
    if _has(t, r"\bmorning\b"):
        d["slot"] = "Morning"
    for k, v in DEFAULTS.items():
        d.setdefault(k, v)
    return d


DEFAULTS = {"pickup": "No transfer", "meals": "No meals", "access": "Standard", "stops": "Main site only"}
STRICT = tuple(DEFAULTS)


def assign_attraction(listing: dict, attractions: list[dict]) -> str:
    """Catalogue attractions within 250 m of the listing's location; the title picks among them (longest name wins ties,
    so "Burj Khalifa: At the Top" beats a shorter name it contains)."""
    near = [a for a in attractions if haversine_m(listing["lat"], listing["lng"], a["lat"], a["lng"]) <= 250] or attractions
    title = listing["title"].lower()
    short = lambda a: a["name"].lower().split(" (")[0].split(",")[0]  # noqa: E731
    return max(near, key=lambda a: (fuzz.partial_ratio(short(a), title), len(short(a))))["attraction_id"]


def compatible(a: dict, b: dict) -> bool:
    for k in STRICT:
        if a[k] != b[k]:
            return False
    for k in ("option", "cancel", "duration", "slot"):
        if k in a and k in b and _family(k, a[k]) != _family(k, b[k]):
            return False
    return True


def _family(k, v):
    """Coarse equivalence: 'Free until 24 h' and 'Free cancellation' are the same promise to a client."""
    if k == "cancel":
        return "nrf" if v == "Non-refundable" else "free"
    return v


def group(listings: list[dict]) -> tuple[list[list[dict]], set[str]]:
    """Most-specific listings seed groups; each listing joins the one group it is compatible with. A listing that
    fits two groups (it doesn't say which slot or option it sells) is kept apart and sent to review: precision first."""
    # listings that say which option they sell seed the groups first; vaguer ones are placed afterwards
    ordered = sorted(listings, key=lambda l: (-(2 * ("option" in l["dna"]) + ("duration" in l["dna"]) + ("slot" in l["dna"])),
                                              -len(l["dna"]), l["listing_id"]))
    groups: list[tuple[dict, list]] = []
    ambiguous = set()
    for l in ordered:
        fits = [(sig, ms) for sig, ms in groups if compatible(sig, l["dna"])]
        if len(fits) == 1:
            sig, ms = fits[0]
            ms.append(l)
            for k, v in l["dna"].items():
                sig.setdefault(k, v)
        else:
            if fits:
                ambiguous.add(l["listing_id"])
            groups.append((dict(l["dna"]), [l]))
    return [ms for _, ms in groups], ambiguous




def summarise(members: list[dict]) -> dict:
    """One variant's DNA from its listings: strict fields agree by construction; descriptive ones take the first
    listing that states them. Tags drive the DNA-only filters; the name is built from what makes it different."""
    d = dict(members[0]["dna"])
    for m in members[1:]:
        for k, v in m["dna"].items():
            d.setdefault(k, v)
    tags = []
    if "pickup" in d["pickup"].lower():
        tags.append("pickup")
    if d.get("cancel") and d["cancel"] != "Non-refundable":
        tags.append("free_cancel")
    if d["access"] == "Skip-the-line":
        tags.append("skip_line")
    if d["meals"] == "Lunch":
        tags.append("lunch")
    hours = float(d["duration"].split()[0]) if d.get("duration") else None
    option = None if d.get("option") == "Private" and d["pickup"].startswith("Private") else d.get("option")
    access = d["access"] if d["access"] != "Standard" and d["access"] not in (option or "") else None
    parts = [option, d.get("slot") and f"{d['slot']} departure", access,
             d["meals"] if d["meals"] != "No meals" else None, d["pickup"] if d["pickup"] != "No transfer" else None,
             d["stops"] if d["stops"] != "Main site only" else None]
    name = " · ".join(p for p in parts if p) or "Entry ticket"
    return {"dna": d, "tags": tags, "hours": hours, "name": name}
