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


class WhyChip(BaseModel):
    label: str                          # "Lowest True Price", "Mynah 97% honoured"
    kind: Literal["price", "promise", "content", "relevance", "warning"]


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


class HotelCard(BaseModel):
    card_id: str                        # listing id in "today", cluster id in "samesame"
    cluster_id: str                     # stable across views: the framer-motion layoutId anchor
    name: str
    star: Optional[float]
    lat: float
    lng: float
    district: Optional[str]
    image: Optional[ImageRef]
    supplier: Optional[str] = None      # "today" view: the single supplier of this listing
    suppliers: list[str] = []           # "samesame" view: every supplier in the stack
    member_count: int = 1
    from_price: float
    true_price_from: Optional[float] = None
    rank: int
    why: list[WhyChip] = []
    lookalike: Optional[Lookalike] = None


class ListingCounters(BaseModel):
    raw_listings: int
    unique_hotels: int
    duplicates_collapsed: int


class HotelListing(BaseModel):
    view: Literal["today", "samesame"]
    cards: list[HotelCard]
    counters: ListingCounters


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


class HotelDetail(BaseModel):
    cluster_id: str
    name: str
    facts: list[SourcedFact]
    hero: Optional[ImageRef]
    images: list[ImageRef]
    rooms: list[CanonicalRoom]
    offers: list[Offer]
    needs: dict                         # the scenario the True Price was computed for


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
    key: Literal["pickup", "meals", "duration", "stops", "access", "cancel", "group"]
    label: str
    value: str
    differs: bool


class ActivityListing(BaseModel):
    listing_id: str
    supplier: str
    title: str
    price: float
    image: Optional[ImageRef] = None


class ActivityVariant(BaseModel):
    variant_id: str
    name: str
    dna: list[DnaSegment]
    members: list[ActivityListing]
    price_from: float
    true_price_from: Optional[float] = None
    diff_sentence: Optional[str] = None
    diff_source: Literal["llm", "template"] = "template"


class ActivityGroup(BaseModel):
    group_id: str
    base_product: str
    variants: list[ActivityVariant]


class ActivitySearch(BaseModel):
    query: str
    raw_count: int
    groups: list[ActivityGroup]


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
