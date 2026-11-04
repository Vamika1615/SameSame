"""The data contract. Two halves:

1. Core tables (mirror the data spec; stored in DuckDB/parquet).
2. API payloads (the JSON seam between backend and frontend; mirrored by frontend/src/contracts.ts).

Extensions beyond the brief's spec are marked EXT with the reason.
"""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Relation = Literal["SAME", "VARIANT", "DIFFERENT"]
Outcome = Literal["confirmed", "price_changed", "sold_out", "error"]
EntityType = Literal["hotel", "room", "activity"]


# ---------------------------------------------------------------- core tables

class SupplierProperty(BaseModel):
    supplier_id: str
    sup_prop_id: str
    name: str
    address: str
    lat: float
    lng: float
    phone: Optional[str] = None
    star: Optional[float] = None
    chain: Optional[str] = None
    amenities: list[str] = []
    images: list[str] = []
    external_map_id: Optional[str] = None
    postcode: Optional[str] = None      # EXT: missing-postcode corruption needs a field to be missing from


class SupplierRoom(BaseModel):
    supplier_id: str
    sup_prop_id: str
    sup_room_id: str
    raw_name: str
    bed: Optional[str] = None
    occupancy: Optional[int] = None
    size_m2: Optional[float] = None


class SupplierActivity(BaseModel):
    supplier_id: str
    sup_act_id: str
    title: str
    description: str
    duration_min: Optional[int] = None
    pickup: Optional[str] = None        # none | shared | private (raw text before extraction)
    meals: Optional[str] = None
    price: float
    cancel_policy: Optional[str] = None
    images: list[str] = []              # EXT: activity image dedup uses the same phash path as hotels
    # EXT (brief: "access types, activity options"): raw supplier text; Variant DNA normalises them
    access_type: Optional[str] = None   # standard | skip-the-line | VIP | time-slot
    activity_option: Optional[str] = None   # sunset slot, with drink, English guide, ...
    stops: list[str] = []
    rating: Optional[float] = None      # EXT: sightseeing ranking uses rating + popularity
    review_count: Optional[int] = None


class OfferRow(BaseModel):
    offer_id: str
    supplier_id: str
    entity_id: str                      # sup_prop_id or sup_act_id
    room_or_variant_id: str
    price: float
    board: Literal["RO", "BB", "HB", "FB", "AI", "NA"]   # NA for activities
    refundable_until: Optional[date] = None              # None = non-refundable
    pay_terms: str                      # "pay_now" | "pay_later_<n>d" (n days before travel)
    currency: str = "INR"
    availability: Literal["available", "limited", "on_request"] = "available"   # EXT: brief's comparison column


class BookingAttempt(BaseModel):
    attempt_id: str
    offer_id: str
    agency_id: str
    quoted_price: float
    lead_days: int
    outcome: Outcome
    final_price: Optional[float] = None
    ts: datetime
    supplier_id: str                    # EXT: denormalised so imported real logs need no offer table
    product_type: Literal["hotel", "activity"] = "hotel"   # EXT: Heron is strong on hotels, weak on activities


class Cluster(BaseModel):
    cluster_id: str
    entity_type: EntityType
    member_ids: list[str]
    confidence: float
    method: Literal["auto", "llm", "human"]
    audit: list[dict] = []


class VariantEdge(BaseModel):
    a_id: str
    b_id: str
    relation: Relation
    diff_json: dict = {}


# ---------------------------------------------------------------- API payloads

class Mode(BaseModel):
    llm: bool
    llm_model: Optional[str]
    data: Literal["synthetic", "mock", "real"]


class Meta(BaseModel):
    mode: Mode
    city: str
    currency: str
    build: dict = {}                    # artifact timestamps, counts
    demo: dict = {}                     # scenario defaults (book seed + offers); shown on screen, never hidden
    sources: dict = {}                  # where each part of the screen comes from (synthetic / truth / mock)


class BookStats(BaseModel):
    """Outcome distribution of the same basket over many seeds: the honest context for one live draw."""
    runs: int
    per_offer: list[dict]               # [{offer_id, confirmed_first_time, paid_price_rise, via_failover, failed}]


class WhyChip(BaseModel):
    label: str                          # "Lowest True Price", "Mynah 97% honoured", "400 m from the Metro"
    kind: Literal["price", "promise", "content", "relevance", "popularity", "warning"]


class ScoreTerm(BaseModel):
    """One line of the transparent ranking score: contribution = weight * value."""
    feature: Literal["true_price", "promise", "distance", "star_fit", "family_fit",
                     "popularity", "content", "duration_fit", "rating"]
    label: str
    value: float                        # normalised 0..1, higher is better
    weight: float
    contribution: float
    detail: str                         # human-readable raw value, e.g. "420 m from Mall of the Emirates Metro"


class SearchParams(BaseModel):
    city: str = "Dubai"
    area: str                           # client's chosen area or anchor attraction
    area_lat: float
    area_lng: float
    checkin: date
    nights: int
    adults: int
    children: int = 0
    star_min: Optional[float] = None
    needs: list[str] = []               # "breakfast", "transfer", ...
    source_market: str = "IN"


class DnaFilter(BaseModel):
    """Filters that only work because Variant DNA normalised the supplier text."""
    key: str                            # "free_cancel", "breakfast", "pickup", "skip_line", "lunch"
    label: str
    count: int                          # listings that truly have it (Variant DNA on structured data)
    today_count: int                    # listings keyword search on raw supplier text finds today


class LookalikeReason(BaseModel):
    kind: Literal["distance", "phone", "branch", "brand", "address"]
    text: str


class Lookalike(BaseModel):
    other_card_id: str
    other_name: str
    distance_m: float
    reasons: list[LookalikeReason]


class ImageRef(BaseModel):
    url: str
    illustrative: bool = True
    source: Optional[str] = None
    kind: Literal["photo", "stock", "generated"] = "generated"   # photo: this very place; stock: real photo, not this hotel
    credit: Optional[str] = None                                 # "Author · CC BY-SA 4.0 · Wikimedia Commons"
    credit_url: Optional[str] = None


class HotelCard(BaseModel):
    card_id: str                        # listing id in "today", cluster id in "samesame"
    cluster_id: str
    name: str
    star: Optional[float]
    lat: float
    lng: float
    district: Optional[str]
    image: Optional[ImageRef]
    supplier: Optional[str] = None      # "today" view: the single supplier of this listing
    suppliers: list[str] = []           # "samesame" view: every supplier in the stack
    member_ids: list[str] = []          # "samesame" view: today-card ids merged here (animation anchors)
    from_price: float
    true_price_from: Optional[float] = None
    rank: int
    why: list[WhyChip] = []
    score: list[ScoreTerm] = []
    dna_tags: list[str] = []            # SameSame: DnaFilter keys (DNA truth); Today: keyword matches on raw text
    lookalike: Optional[Lookalike] = None


class ListingCounters(BaseModel):
    raw_listings: int
    unique_hotels: int
    duplicates_collapsed: int


class HotelSearch(BaseModel):
    """Both views in one payload so the toggle is instant (no loading on stage)."""
    params: SearchParams
    today: list[HotelCard]              # one card per supplier listing, sticker-price order
    samesame: list[HotelCard]           # one card per cluster, ranked
    counters: ListingCounters
    filters: list[DnaFilter]


class SourcedFact(BaseModel):
    key: str
    label: str
    value: str
    sources: list[dict]                 # [{supplier, value, trust}]


class CanonicalRoom(BaseModel):
    room_id: str
    name: str                           # "Deluxe King, City View"
    attrs: dict                         # {tier, bed, view, ...}
    members: list[dict]                 # [{supplier, raw_name, confidence}]


class Promise(BaseModel):
    supplier_id: str
    supplier: str
    lead_bucket: str
    honour_rate: float
    ci_low: float
    ci_high: float
    n: int
    p_price_change: float
    p_sold_out: float
    p_error: float
    exp_increase_pct: float


class PriceTerm(BaseModel):
    key: Literal["sticker", "fill_needs", "cancel_risk", "price_change", "failover", "pay_later"]
    label: str
    amount: float
    assumption: str                     # shown next to the number, always


class TruePrice(BaseModel):
    total: float
    terms: list[PriceTerm]


class Offer(BaseModel):
    offer_id: str
    supplier_id: str
    supplier: str
    room_id: str
    room_name: str
    board: str
    price: float
    availability: str
    refundable_until: Optional[date]
    cancel_text: str
    pay_terms: str
    pay_text: str
    promise: Promise
    true_price: TruePrice
    sticker_rank: int
    true_rank: int


class Enrichment(BaseModel):
    """Before/After: one supplier's sparse listing vs the golden record."""
    supplier: str
    before_facts: list[SourcedFact]
    before_images: list[ImageRef]
    before_amenities: list[str]
    before_description: str
    after_amenities: list[dict]         # [{name, sources: [supplier]}]
    after_description: str
    after_description_sources: list[str]


class HotelDetail(BaseModel):
    cluster_id: str
    name: str
    facts: list[SourcedFact]
    hero: Optional[ImageRef]
    images: list[ImageRef]
    rooms: list[CanonicalRoom]
    offers: list[Offer]
    params: SearchParams                # the scenario the True Price was computed for
    enrichment: Enrichment
    lookalike: Optional[Lookalike] = None
    reference: Optional[dict] = None    # real OpenStreetMap / Wikipedia data for the linked property, with sources


class BookingStep(BaseModel):
    t_ms: int
    event: Literal["request", "price_changed", "sold_out", "error", "failover", "confirmed", "failed"]
    supplier: str
    offer_id: str
    price: Optional[float] = None
    detail: str


class BookingResult(BaseModel):
    offer_id: str
    steps: list[BookingStep]
    status: Literal["confirmed", "failed"]
    final_supplier: Optional[str]
    final_price: Optional[float]
    via_failover: bool


class BookResponse(BaseModel):
    seed: int
    results: list[BookingResult]


class DnaSegment(BaseModel):
    key: Literal["pickup", "meals", "duration", "stops", "access", "option", "cancel", "group"]
    label: str
    value: str
    differs: bool                       # differs from at least one sibling variant -> glows


class ActivityListing(BaseModel):
    listing_id: str
    supplier: str
    title: str
    price: float
    rating: Optional[float] = None
    image: Optional[ImageRef] = None
    dna_tags: list[str] = []            # Today view: what keyword search on raw text finds


class ActivityVariant(BaseModel):
    variant_id: str
    name: str
    dna: list[DnaSegment]
    dna_tags: list[str] = []
    members: list[ActivityListing]      # SAME twins of each other
    price_from: float
    true_price_from: Optional[float] = None
    rank: int
    why: list[WhyChip] = []
    score: list[ScoreTerm] = []
    diff_sentence: Optional[str] = None
    diff_source: Literal["llm", "template"] = "template"


class ActivityGroup(BaseModel):
    group_id: str
    base_product: str
    variants: list[ActivityVariant]
    description: Optional[dict] = None  # {text, source, license} from Wikipedia


class ActivitySearch(BaseModel):
    query: str
    raw_count: int
    today: list[ActivityListing]        # raw listings as suppliers send them
    groups: list[ActivityGroup]
    filters: list[DnaFilter]


class SimParams(BaseModel):
    sessions: int = 50000
    price_sensitivity: float = 0.6      # 0..1: how strongly agents chase the lowest sticker
    dup_abandon: float = 0.08           # extra abandonment per duplicate-heavy result page
    failure_scale: float = 1.0          # multiplier on supplier failure rates
    seed: int = 7


class SimArm(BaseModel):
    arm: Literal["today", "samesame"]
    bookings_per_search: float
    failed_at_booking: float
    avg_true_cost: float


class SimResult(BaseModel):
    params: SimParams
    arms: list[SimArm]
    lift_bookings_pct: float
    failed_reduction_pct: float
    note: str


class ReviewSide(BaseModel):
    id: str
    supplier: str
    title: str
    fields: dict
    image: Optional[ImageRef] = None


class ReviewItem(BaseModel):
    pair_id: str
    entity_type: EntityType
    left: ReviewSide
    right: ReviewSide
    model_p: float
    model_relation: Relation
    routed_by: Literal["gray_zone", "llm_unsure", "constraint_block"]
    reasons: list[str]


class ReviewLabel(BaseModel):
    label: Literal["S", "V", "D"]
    reviewer: str = "ops"


class ReviewAck(BaseModel):
    ok: bool
    audit_id: str
    streak: int
    model_was_right: bool
    truth: Relation                     # generator ground truth, revealed after labelling


class AuditEntry(BaseModel):
    audit_id: str
    ts: datetime
    pair_id: str
    action: Literal["label", "undo", "merge", "unmerge"]
    label: Optional[str] = None
    reviewer: str
    reversible: bool = True


class SupplierRow(BaseModel):
    supplier_id: str
    supplier: str
    honour_rate_hotel: float
    honour_rate_activity: float
    n_attempts: int
    duplicate_share: float              # share of its listings that have a twin elsewhere
    price_spread_pct: float             # median |price - cluster median| / cluster median
    hotel: Optional[Promise] = None   # full estimates behind the two honour rates (CI, n)
    activity: Optional[Promise] = None
