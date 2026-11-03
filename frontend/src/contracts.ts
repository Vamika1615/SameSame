// Mirror of backend/samesame/schemas.py (API payloads). Change both together.

export type Relation = "SAME" | "VARIANT" | "DIFFERENT";
export type EntityType = "hotel" | "room" | "activity";

export interface Mode { llm: boolean; llm_model: string | null; data: "synthetic" | "mock" | "real" }
export interface Meta {
  mode: Mode; city: string; currency: string; build: Record<string, unknown>;
  demo: { book_offers?: string[]; book_seed?: number; book_seed_note?: string };
}
export interface BookStats {
  runs: number;
  per_offer: { offer_id: string; confirmed_first_time: number; paid_price_rise: number; via_failover: number; failed: number }[];
}

export interface WhyChip { label: string; kind: "price" | "promise" | "content" | "relevance" | "popularity" | "warning" }
export interface ScoreTerm { feature: string; label: string; value: number; weight: number; contribution: number; detail: string }
export interface LookalikeReason { kind: "distance" | "phone" | "branch" | "brand" | "address"; text: string }
export interface Lookalike { other_card_id: string; other_name: string; distance_m: number; reasons: LookalikeReason[] }
export interface ImageRef { url: string; illustrative: boolean; source?: string | null }

export interface SearchParams {
  city: string; area: string; area_lat: number; area_lng: number; checkin: string; nights: number;
  adults: number; children: number; star_min: number | null; needs: string[]; source_market: string;
}
export interface DnaFilter { key: string; label: string; count: number; today_count: number }

export interface HotelCard {
  card_id: string; cluster_id: string; name: string; star: number | null;
  lat: number; lng: number; district: string | null; image: ImageRef | null;
  supplier?: string | null; suppliers: string[]; member_ids: string[];
  from_price: number; true_price_from?: number | null; rank: number;
  why: WhyChip[]; score: ScoreTerm[]; dna_tags: string[]; lookalike?: Lookalike | null;
}
export interface HotelSearch {
  params: SearchParams; today: HotelCard[]; samesame: HotelCard[];
  counters: { raw_listings: number; unique_hotels: number; duplicates_collapsed: number };
  filters: DnaFilter[];
}

export interface Source { supplier: string; value: string; trust: number }
export interface SourcedFact { key: string; label: string; value: string; sources: Source[] }
export interface CanonicalRoom { room_id: string; name: string; attrs: Record<string, string>; members: { supplier: string; raw_name: string; confidence: number }[] }
export interface Promise_ {
  supplier_id: string; supplier: string; lead_bucket: string; honour_rate: number;
  ci_low: number; ci_high: number; n: number; p_price_change: number; p_sold_out: number; p_error: number; exp_increase_pct: number;
}
export interface PriceTerm { key: "sticker" | "fill_needs" | "cancel_risk" | "price_change" | "failover" | "pay_later"; label: string; amount: number; assumption: string }
export interface TruePrice { total: number; terms: PriceTerm[] }
export interface Offer {
  offer_id: string; supplier_id: string; supplier: string; room_id: string; room_name: string; board: string;
  price: number; availability: string; refundable_until: string | null; cancel_text: string; pay_terms: string; pay_text: string;
  promise: Promise_; true_price: TruePrice; sticker_rank: number; true_rank: number;
}
export interface Enrichment {
  supplier: string; before_facts: SourcedFact[]; before_images: ImageRef[]; before_amenities: string[]; before_description: string;
  after_amenities: { name: string; sources: string[] }[]; after_description: string; after_description_sources: string[];
}
export interface HotelDetail {
  cluster_id: string; name: string; facts: SourcedFact[]; hero: ImageRef | null; images: ImageRef[];
  rooms: CanonicalRoom[]; offers: Offer[]; params: SearchParams; enrichment: Enrichment; lookalike?: Lookalike | null;
}

export interface BookingStep {
  t_ms: number; event: "request" | "price_changed" | "sold_out" | "error" | "failover" | "confirmed" | "failed";
  supplier: string; offer_id: string; price?: number | null; detail: string;
}
export interface BookingResult { offer_id: string; steps: BookingStep[]; status: "confirmed" | "failed"; final_supplier: string | null; final_price: number | null; via_failover: boolean }
export interface BookResponse { seed: number; results: BookingResult[] }

export type DnaKey = "pickup" | "meals" | "duration" | "stops" | "access" | "option" | "cancel" | "group";
export interface DnaSegment { key: DnaKey; label: string; value: string; differs: boolean }
export interface ActivityListing { listing_id: string; supplier: string; title: string; price: number; rating?: number | null; image?: ImageRef | null; dna_tags: string[] }
export interface ActivityVariant {
  variant_id: string; name: string; dna: DnaSegment[]; dna_tags: string[]; members: ActivityListing[];
  price_from: number; true_price_from?: number | null; rank: number; why: WhyChip[]; score: ScoreTerm[];
  diff_sentence?: string | null; diff_source: "llm" | "template";
}
export interface ActivityGroup { group_id: string; base_product: string; variants: ActivityVariant[] }
export interface ActivitySearch { query: string; raw_count: number; today: ActivityListing[]; groups: ActivityGroup[]; filters: DnaFilter[] }

export interface ReviewSide { id: string; supplier: string; title: string; fields: Record<string, string>; image?: ImageRef | null }
export interface ReviewItem {
  pair_id: string; entity_type: EntityType; left: ReviewSide; right: ReviewSide;
  model_p: number; model_relation: Relation; routed_by: "gray_zone" | "llm_unsure" | "constraint_block"; reasons: string[];
}
export interface ReviewAck { ok: boolean; audit_id: string; streak: number; model_was_right: boolean; truth: Relation }

export interface SimParams { sessions: number; price_sensitivity: number; dup_abandon: number; failure_scale: number; seed: number }
export interface SimArm { arm: "today" | "samesame"; bookings_per_search: number; failed_at_booking: number; avg_true_cost: number }
export interface SimResult { params: SimParams; arms: SimArm[]; lift_bookings_pct: number; failed_reduction_pct: number; note: string }

export interface SupplierRow {
  supplier_id: string; supplier: string; honour_rate_hotel: number; honour_rate_activity: number;
  n_attempts: number; duplicate_share: number; price_spread_pct: number;
}
