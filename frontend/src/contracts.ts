// Mirror of backend/samesame/schemas.py (API payloads). Change both together.

export type Relation = "SAME" | "VARIANT" | "DIFFERENT";
export type EntityType = "hotel" | "room" | "activity";

export interface Mode { llm: boolean; llm_model: string | null; data: "synthetic" | "mock" | "real" }
export interface Meta { mode: Mode; city: string; currency: string; build: Record<string, unknown> }

export interface WhyChip { label: string; kind: "price" | "promise" | "content" | "relevance" | "warning" }
export interface LookalikeReason { kind: "distance" | "phone" | "branch" | "brand" | "address"; text: string }
export interface Lookalike { other_card_id: string; other_name: string; distance_m: number; reasons: LookalikeReason[] }
export interface ImageRef { url: string; illustrative: boolean; source?: string | null }

export interface HotelCard {
  card_id: string; cluster_id: string; name: string; star: number | null;
  lat: number; lng: number; district: string | null; image: ImageRef | null;
  supplier?: string | null; suppliers: string[]; member_count: number;
  from_price: number; true_price_from?: number | null; rank: number;
  why: WhyChip[]; lookalike?: Lookalike | null;
}
export interface HotelListing {
  view: "today" | "samesame"; cards: HotelCard[];
  counters: { raw_listings: number; unique_hotels: number; duplicates_collapsed: number };
}

export interface SourcedFact { key: string; label: string; value: string; sources: { supplier: string; value: string; trust: number }[] }
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
export interface HotelDetail {
  cluster_id: string; name: string; facts: SourcedFact[]; hero: ImageRef | null; images: ImageRef[];
  rooms: CanonicalRoom[]; offers: Offer[]; needs: Record<string, unknown>;
}

export interface BookingStep {
  t_ms: number; event: "request" | "price_changed" | "sold_out" | "error" | "failover" | "confirmed" | "failed";
  supplier: string; offer_id: string; price?: number | null; detail: string;
}
export interface BookingResult { offer_id: string; steps: BookingStep[]; status: "confirmed" | "failed"; final_supplier: string | null; final_price: number | null; via_failover: boolean }
export interface BookResponse { seed: number; results: BookingResult[] }

export interface DnaSegment { key: "pickup" | "meals" | "duration" | "stops" | "access" | "cancel" | "group"; label: string; value: string; differs: boolean }
export interface ActivityListing { listing_id: string; supplier: string; title: string; price: number; image?: ImageRef | null }
export interface ActivityVariant {
  variant_id: string; name: string; dna: DnaSegment[]; members: ActivityListing[];
  price_from: number; true_price_from?: number | null; diff_sentence?: string | null; diff_source: "llm" | "template";
}
export interface ActivityGroup { group_id: string; base_product: string; variants: ActivityVariant[] }
export interface ActivitySearch { query: string; raw_count: number; groups: ActivityGroup[] }

export interface ReviewSide { id: string; supplier: string; title: string; fields: Record<string, string>; image?: ImageRef | null }
export interface ReviewItem {
  pair_id: string; entity_type: EntityType; left: ReviewSide; right: ReviewSide;
  model_p: number; model_relation: Relation; routed_by: "gray_zone" | "llm_unsure" | "constraint_block"; reasons: string[];
}
export interface ReviewAck { ok: boolean; audit_id: string; streak: number; model_was_right: boolean }
