"""Remix engine: rebuild a packaged product from parts, and say honestly whether TBO should sell it.

For a target (a packaged variant found by Variant DNA), enumerate parts per role, keep the feasible
combinations, and take the one with the lowest expected cost to TBO:

- ticket       at the attraction: same Variant DNA as the target on every strict field (pickup aside),
               bundleable, with a slot that the transfers can reach
- transfer x2  hotel zone -> meeting point and back, shared or private as the target says, dropping
               off at the ticket's meeting point; arrive >= buffer before the slot, wait <= MAX_WAIT
- lunch        a voucher when the target includes lunch and the ticket doesn't

SAME, never VARIANT: strict fields (pickup, meals, access, stops) must be equal, and so must every
descriptive field (option, slot, cancellation) the package states: if the package promises "Private" and
no part says so, the Remix can't prove it delivers it, so it is a different product. A field only the
Remix states (the package is silent) is listed as unverified, and that Remix needs a human approval.

Pricing, with each risk counted once:
- TBO's expected cost = for every part, sticker + price-change risk + failover risk (the True Price
  engine with that part's fitted Promise) + assembly risk. Assembly risk: if a part can't be secured
  even through its SAME twins, TBO unwinds the Remix and buys the best package instead.
- The agent's True Price of the Remix = sell price + cancellation risk under the strictest part's rule.
  TBO carries the rest, because it runs the failover.
- Sell price: the agent gets AGENT_SHARE of the gap between the best package's True Price and the
  Remix at cost; TBO keeps the rest.
"""
from dataclasses import asdict, dataclass, field, replace

from samesame import config, store
from samesame.data.components import HOTEL_PICKUPS, hhmm, minutes
from samesame.pricing import true_price as tp
from samesame.variants.dna import _family

STRICT = ("pickup", "meals", "access", "stops")
DESCRIPTIVE = ("option", "slot", "cancel")
PRODUCT = {"ticket": "ticket", "addon": "ticket", "transfer": "transfer"}
EVALUATE_TOP = 80              # assemblies priced in full, cheapest first; the cheapest that passes every guardrail wins
MAX_HOPS = 3                    # the sandbox router tries a part and up to two SAME twins
LUNCH_MIN = 60


@dataclass(frozen=True)
class Settings:
    zone: str = "deira"
    pax: int = 2
    lead_days: int = 21
    agent_share: float = 0.50        # share of the gap the agent keeps; TBO keeps the rest
    min_saving: float = 0.03         # publish only if the agent saves at least this on True Price
    min_margin: float = 0.04         # ...and TBO's margin is at least this
    min_promise: float = 0.95        # ...and every part is secured (incl. failover) with this probability
    buffer_min: int = 20             # arrive at least this long before the slot
    max_wait_min: int = 90           # nobody waits longer than this for a slot or a return coach
    transfer_price_mult: float = 1.0  # pessimistic preset: transfers dearer
    failure_mult: float = 1.0         # pessimistic preset: parts fail more often


PESSIMISTIC = Settings(transfer_price_mult=1.3, failure_mult=1.5)


@dataclass
class Part:
    component_id: str
    role: str
    leg: str                         # "ticket", "out", "back", "lunch"
    supplier_id: str
    title: str
    unit_price: float
    price: float                     # for the party
    price_unit: str
    start: int                       # minutes after midnight
    end: int
    cancel: str
    meeting_point_id: str
    twins: list = field(default_factory=list)   # SAME twins (component ids), cheapest first
    vehicle: str | None = None
    mode: str | None = None


# ------------------------------------------------------------------ helpers
def _svc():
    from samesame import service          # late import: service imports this module's callers
    return service


def _risk(supplier: str, product: str, s: Settings) -> tp.Risk:
    r = _svc().risk(supplier, product)
    if s.failure_mult == 1.0:
        return r
    m = s.failure_mult
    return tp.Risk(r.supplier, min(r.p_price_change * m, 0.5), min(r.p_sold_out * m, 0.4), min(r.p_error * m, 0.2), r.exp_increase_pct)


def _cancel_hours(c: str) -> float:
    """Free-until hours before travel; non-refundable = infinitely strict."""
    if c == "Non-refundable":
        return float("inf")
    import re
    m = re.search(r"(\d+)\s*h", c or "")
    return float(m.group(1)) if m else 24.0


def strictest(cancels: list[str]) -> str:
    return max(cancels, key=_cancel_hours)


def compare(target: dict, assembled: dict) -> tuple[list[str], list[str]]:
    """Returns (differences, unverified fields). Any difference means it is not the target product."""
    diffs, unverified = [], []
    for k in STRICT:
        if target.get(k) != assembled.get(k):
            diffs.append(f"{k}: package '{target.get(k)}' vs Remix '{assembled.get(k)}'")
    for k in DESCRIPTIVE:
        a, b = target.get(k), assembled.get(k)
        if a is None and b is None:
            continue
        if a is None:
            unverified.append(k)                               # the package is silent: a human checks
        elif b is None:
            diffs.append(f"{k}: package promises '{a}', no part states it")
        elif _family(k, a) != _family(k, b):
            diffs.append(f"{k}: package '{a}' vs Remix '{b}'")
    return diffs, unverified


def _party_price(c: dict, s: Settings) -> float:
    mult = s.transfer_price_mult if c["role"] == "transfer" else 1.0
    return c["price"] * mult * (1 if c["price_unit"] == "per vehicle" else s.pax)


# ------------------------------------------------------------------ targets
def targets() -> list[dict]:
    """Every packaged sightseeing variant Variant DNA found, with its listings."""
    st = store.get()
    out = []
    for aid, vs in sorted(st.variants_of.items()):
        for v in vs:
            out.append({**v, "attraction": st.attractions[aid]["name"], "members": st.act_listings_of.get(v["variant_id"], [])})
    return out


def multi_part(t: dict) -> bool:
    return t["dna"]["pickup"] in HOTEL_PICKUPS or t["dna"]["meals"] == "Lunch"


# ------------------------------------------------------------------ search
def _ticket_ok(t: dict, c: dict) -> tuple[bool, bool]:
    """(compatible, needs lunch add-on)"""
    d = c["dna"]
    need_lunch = t["dna"]["meals"] == "Lunch" and d["meals"] == "No meals"
    probe = {**d, "pickup": t["dna"]["pickup"], "meals": "Lunch" if need_lunch else d["meals"], "cancel": c["cancel"]}
    diffs, _ = compare(t["dna"], probe)
    return not diffs, need_lunch


def _transfer_slots(c: dict, slot: int, end: int, leg: str, s: Settings) -> list[tuple[int, int]]:
    """(start, end) of the transfer leg if it can serve this ticket slot."""
    travel = int(c["travel_min"])
    if leg == "out":
        if c["mode"] == "private":
            arrive = slot - s.buffer_min
            return [(arrive - travel, arrive)]
        return [(minutes(t) - travel, minutes(t)) for t in c["slots"]
                if minutes(t) <= slot - s.buffer_min and slot - minutes(t) <= s.max_wait_min]
    if c["mode"] == "private":
        leave = end + 10
        return [(leave, leave + travel)]
    return [(minutes(t), minutes(t) + travel) for t in c["slots"] if minutes(t) >= end and minutes(t) - end <= s.max_wait_min]


def _fits_party(c: dict, s: Settings) -> bool:
    return c["price_unit"] != "per vehicle" or c["max_pax"] >= s.pax


def _transfer_pool(t: dict, mp: str, leg: str, s: Settings) -> list[dict]:
    mode = "private" if t["dna"]["pickup"] == "Private hotel pickup" else "shared"
    direction = "to" if leg == "out" else "from"
    pool = [c for c in store.get().components.values() if c["role"] == "transfer" and c["meeting_point_id"] == mp
            and c["zone_id"] == s.zone and c["direction"] == direction and c["mode"] == mode and _fits_party(c, s)]
    # private: per route and supplier, only the smallest vehicle that fits is a sensible choice
    if mode == "private":
        best = {}
        for c in pool:
            k = (c["supplier_id"], c["bundleable"], c["cancel"])
            if k not in best or c["max_pax"] < best[k]["max_pax"]:
                best[k] = c
        pool = list(best.values())
    return pool


def _twins(part: dict, pool: list[dict]) -> list[str]:
    """SAME twins of a chosen part: same role, same structured terms, bundleable, no stricter cancellation."""
    out = [c for c in pool if c["component_id"] != part["component_id"] and c["bundleable"]
           and _cancel_hours(c["cancel"]) <= _cancel_hours(part["cancel"])]
    return [c["component_id"] for c in sorted(out, key=lambda c: c["price"])]


def search(t: dict, s: Settings = Settings()) -> dict:
    """All feasible assemblies for a target, cheapest-to-TBO first, plus the reasons the others failed."""
    st = store.get()
    aid = t["attraction_id"]
    reasons: dict[str, int] = {}

    def no(r):
        reasons[r] = reasons.get(r, 0) + 1

    tickets = [c for c in st.components.values() if c["role"] == "ticket" and c["attraction_id"] == aid]
    if not any(_ticket_ok(t, c)[0] for c in tickets):
        return {"assemblies": [], "reasons": {"no supplier sells a ticket with the same DNA on its own": 1}}
    if not tickets:
        return {"assemblies": [], "reasons": {"no supplier sells this ticket on its own": 1}}
    need_transfer = t["dna"]["pickup"] in HOTEL_PICKUPS
    out = []
    for c in tickets:
        ok, need_lunch = _ticket_ok(t, c)
        if not ok:
            continue
        if not c["bundleable"]:
            no("ticket rate is package-only")
            continue
        lunches = [l for l in st.components.values() if l["role"] == "addon" and l["attraction_id"] == aid] if need_lunch else [None]
        if need_lunch and not any(l["bundleable"] for l in lunches):
            no("no bundleable lunch voucher")
            continue
        outs = _transfer_pool(t, c["meeting_point_id"], "out", s) if need_transfer else [None]
        backs = _transfer_pool(t, c["meeting_point_id"], "back", s) if need_transfer else [None]
        if need_transfer and not (outs and backs):
            no("no transfer to this meeting point")
            continue
        for slot_s in c["slots"]:
            slot, end = minutes(slot_s), minutes(slot_s) + int(round(c["hours"] * 60))
            legs_ok = True
            chosen = {}
            for leg, pool in (("out", outs), ("back", backs)):
                if pool == [None]:
                    chosen[leg] = [(None, None)]
                    continue
                cands = []
                for x in pool:
                    if not x["bundleable"]:
                        no("transfer rate is package-only")
                        continue
                    if x["cancel"] == "Non-refundable" and _family("cancel", t["dna"].get("cancel") or "Free") == "free":
                        no("transfer is non-refundable, the package is not")
                        continue
                    for win in _transfer_slots(x, slot, end, leg, s):
                        cands.append((x, win))
                if not cands:
                    no(f"no {'outbound' if leg == 'out' else 'return'} transfer fits the {slot_s} slot")
                    legs_ok = False
                    break
                chosen[leg] = cands
            if not legs_ok:
                continue
            lunch_opts = [(None, None)]
            if need_lunch:
                lunch_opts = [(l, minutes(ls)) for l in lunches if l["bundleable"] for ls in l["slots"]
                              if slot <= minutes(ls) and minutes(ls) + LUNCH_MIN <= end]
                if not lunch_opts:
                    no(f"lunch doesn't fit inside the {slot_s} visit")
                    continue
            for o, ow in chosen["out"]:
                for b, bw in chosen["back"]:
                    for l, lt in lunch_opts:
                        out.append({"ticket": c, "slot": slot, "end": end, "out": o, "out_win": ow, "back": b, "back_win": bw,
                                    "lunch": l, "lunch_at": lt})
    return {"assemblies": out, "reasons": reasons}


# ------------------------------------------------------------------ pricing
def _part(c: dict, leg: str, start: int, end: int, s: Settings, pool: list[dict]) -> Part:
    return Part(component_id=c["component_id"], role=c["role"], leg=leg, supplier_id=c["supplier_id"], title=c["title"],
                unit_price=c["price"] * (s.transfer_price_mult if c["role"] == "transfer" else 1.0), price=_party_price(c, s),
                price_unit=c["price_unit"], start=start, end=end, cancel=c["cancel"], meeting_point_id=c["meeting_point_id"],
                twins=_twins(c, pool), vehicle=c.get("vehicle"), mode=c.get("mode"))


def _secure(parts_chain: list[tp.Risk]) -> float:
    """P(the router secures the part): it fails only if the part and its twins all sell out or error."""
    p_fail = 1.0
    for r in parts_chain[:MAX_HOPS]:
        p_fail *= r.p_sold_out + r.p_error
    return 1 - p_fail


def price_parts(parts: list[Part], s: Settings) -> dict:
    st = store.get()
    rows, cost = [], 0.0
    p_all, p_clean = 1.0, 1.0
    for p in parts:
        r = _risk(p.supplier_id, PRODUCT[p.role], s)
        twin_price = _party_price(st.components[p.twins[0]], s) if p.twins else None
        t = tp.compute(p.price, set(), [], s.lead_days, _svc()._refund_days(p.cancel), None, r, twin_price)
        tbo = sum(x.amount for x in t.terms if x.key != "cancel_risk")
        chain = [r] + [_risk(st.components[x]["supplier_id"], PRODUCT[p.role], s) for x in p.twins]
        secure = _secure(chain)
        p_all *= secure
        p_clean *= 1 - r.p_price_change - r.p_sold_out - r.p_error
        prom = _svc().promise(p.supplier_id, PRODUCT[p.role], s.lead_days)
        rows.append({**asdict(p), "true_price": t, "tbo_cost": round(tbo, 2), "p_secure": round(secure, 4), "promise": prom})
        cost += tbo
    return {"parts": rows, "cost": cost, "p_all": p_all, "p_clean": p_clean}


def packaged(t: dict, s: Settings) -> dict | None:
    """Best packaged listing of the target on True Price, the way the Sightseeing page prices it."""
    members = t["members"]
    if not members:
        return None
    svc = _svc()
    refund = svc._refund_days(t["dna"].get("cancel"))
    best = None
    for m in members:
        twins = [x["price_pp"] * s.pax for x in members if x["listing_id"] != m["listing_id"]]
        r = svc.risk(m["supplier_id"], "activity")
        price = m["price_pp"] * s.pax
        tpm = tp.compute(price, set(), [], s.lead_days, refund, None, r, min(twins) if twins else None)
        if best is None or tpm.total < best["true_price"].total:
            chain = [r] + [svc.risk(x["supplier_id"], "activity") for x in sorted(members, key=lambda x: x["price_pp"]) if x is not m]
            best = {"listing_id": m["listing_id"], "supplier_id": m["supplier_id"], "title": m["title"], "price": price,
                    "true_price": tpm, "p_secure": _secure(chain), "p_clean": 1 - r.p_price_change - r.p_sold_out - r.p_error}
    return best


def remix(t: dict, s: Settings = Settings()) -> dict:
    """The best Remix of a target and a verdict: publishable, blocked by a guardrail, or not remixable (with why)."""
    st = store.get()
    base = {"variant_id": t["variant_id"], "attraction_id": t["attraction_id"], "attraction": t["attraction"], "name": t["name"],
            "target_dna": t["dna"], "settings": asdict(s)}
    if t.get("ambiguous"):
        return {**base, "status": "not_remixable", "reasons": ["the package's own DNA is still in review"]}
    if not multi_part(t):
        return {**base, "status": "single_part", "reasons": ["one part only: nothing to remix (comparing the same ticket is SameSame's job)"]}
    pkg = packaged(t, s)
    found = search(t, s)
    if not found["assemblies"]:
        why = sorted(found["reasons"].items(), key=lambda kv: -kv[1])
        return {**base, "status": "not_remixable", "reasons": [k for k, _ in why[:3]] or ["no parts"], "packaged": _pkg_out(pkg)}

    priced = []
    for a in found["assemblies"]:
        parts = _parts_of(t, a, s)
        pr = price_parts(parts, s)
        priced.append((pr["cost"], a["slot"], a, parts, pr))
    priced.sort(key=lambda x: (x[0], x[1]))
    verdicts = [_verdict(t, a, parts, pr, pkg, s, base) for _, _, a, parts, pr in priced[:EVALUATE_TOP]]
    ready = [v for v in verdicts if v["status"] == "ready"]
    best = min(ready, key=lambda v: v["tbo_cost"]) if ready else verdicts[0]
    best["alternatives"] = len(priced)
    return best


def _parts_of(t: dict, a: dict, s: Settings) -> list[Part]:
    st = store.get()
    c = a["ticket"]
    tickets_pool = [x for x in st.components.values() if x["role"] == "ticket" and x["meeting_point_id"] == c["meeting_point_id"]
                    and x.get("dna") == c["dna"] and hhmm(a["slot"]) in x["slots"]]
    parts = [_part(c, "ticket", a["slot"], a["end"], s, tickets_pool)]
    for leg in ("out", "back"):
        x = a[leg]
        if x is not None:
            pool = [y for y in _transfer_pool(t, c["meeting_point_id"], leg, s)
                    if y["cancel"] == x["cancel"] and _transfer_slots(y, a["slot"], a["end"], leg, s)]
            parts.append(_part(x, leg, a[f"{leg}_win"][0], a[f"{leg}_win"][1], s, pool))
    if a["lunch"] is not None:
        pool = [y for y in st.components.values() if y["role"] == "addon" and y["attraction_id"] == c["attraction_id"]]
        parts.append(_part(a["lunch"], "lunch", a["lunch_at"], a["lunch_at"] + LUNCH_MIN, s, pool))
    return parts


def _verdict(t: dict, a: dict, parts: list[Part], pr: dict, pkg: dict | None, s: Settings, base: dict) -> dict:
    cost = pr["cost"]
    assembled = {**a["ticket"]["dna"], "pickup": t["dna"]["pickup"] if a["out"] is not None else a["ticket"]["dna"]["pickup"],
                 "meals": "Lunch" if a["lunch"] is not None else a["ticket"]["dna"]["meals"],
                 "cancel": strictest([p.cancel for p in parts])}
    diffs, unverified = compare(t["dna"], assembled)
    assert not diffs, diffs                                   # search only keeps SAME assemblies
    cancel = assembled["cancel"]
    refund = _svc()._refund_days(cancel)
    zero = tp.Risk("TBO", 0, 0, 0, 0)

    def agent_tp(sell):
        return tp.compute(sell, set(), [], s.lead_days, refund, None, zero, sell)

    sticker = sum(p.price for p in parts)
    fallback = max((pkg["price"] if pkg else sticker * (1 + tp.NO_TWIN_PREMIUM)) - sticker, 0) + config.FAILOVER_FRICTION_INR * len(parts)
    assembly = (1 - pr["p_all"]) * fallback
    tbo_cost = cost + assembly
    start = min(p.start for p in parts)
    finish = max(p.end for p in parts)
    slack = min([p.start - a["out_win"][1] for p in parts if p.leg == "ticket"] if a["out"] is not None else [s.buffer_min])
    out = {**base, "assembled_dna": assembled, "unverified": unverified, "parts": pr["parts"], "sticker": round(sticker, 2),
           "assembly_risk": {"amount": round(assembly, 2), "assumption": f"{1 - pr['p_all']:.1%} chance a part can't be secured even via its SAME twins; "
                             f"TBO then unwinds and buys the best package (+{tp.inr(fallback)} incl. friction)"},
           "tbo_cost": round(tbo_cost, 2), "promise": round(pr["p_all"], 4), "p_clean": round(pr["p_clean"], 4), "cancel": cancel,
           "timeline": {"start": hhmm(start), "end": hhmm(finish), "door_to_door_h": round((finish - start) / 60, 1),
                        "slot": hhmm(a["slot"]), "slack_min": slack},
           "suppliers": sorted({p.supplier_id for p in parts}), "packaged": _pkg_out(pkg)}
    if pkg is None:
        return {**out, "status": "not_remixable", "reasons": ["no packaged version to compare with (see gap Remixes)"]}

    best = pkg["true_price"].total
    at_cost = agent_tp(tbo_cost).total
    gap = best - at_cost
    target_tp = best - s.agent_share * gap
    unit = agent_tp(1000.0).total / 1000.0                    # agent True Price per rupee of sell price
    sell = target_tp / unit
    margin = (sell - tbo_cost) / sell if sell > 0 else -1
    saving = (best - agent_tp(sell).total) / best
    out.update({"sell": round(sell, 2), "agent_true_price": agent_tp(sell), "agent_saving": round(saving, 4),
                "agent_saving_inr": round(best - agent_tp(sell).total, 2), "margin": round(margin, 4),
                "margin_inr": round(sell - tbo_cost, 2), "gap": round(gap, 2)})
    blocks = []
    if gap <= 0:
        blocks.append(f"the package is cheaper on True Price by {tp.inr(-gap)}")
    else:
        if saving < s.min_saving:
            blocks.append(f"agent saves {saving:.1%}, below the {s.min_saving:.0%} guardrail")
        if margin < s.min_margin:
            blocks.append(f"TBO margin {margin:.1%}, below the {s.min_margin:.0%} guardrail")
    if pr["p_all"] < s.min_promise:
        blocks.append(f"Remix Promise {pr['p_all']:.1%}, below the {s.min_promise:.0%} guardrail")
    if slack < s.buffer_min:
        blocks.append(f"only {slack} min between drop-off and slot")
    out["status"] = "blocked" if blocks else "ready"
    out["reasons"] = blocks or (["passes every guardrail; needs approval because the package doesn't state: " + ", ".join(unverified)]
                                if unverified else ["passes every guardrail"])
    return out


def _pkg_out(pkg):
    if pkg is None:
        return None
    return {**{k: v for k, v in pkg.items() if k != "true_price"}, "true_price": pkg["true_price"].total, "terms": pkg["true_price"]}


def run_all(s: Settings = Settings()) -> list[dict]:
    return [remix(t, s) for t in targets()]


def with_zone(s: Settings, zone: str) -> Settings:
    return replace(s, zone=zone)
