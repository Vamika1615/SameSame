import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { AlertTriangle, ArrowDown, ArrowLeft, ArrowUp, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import type { HotelDetail, Offer, SourcedFact, Reference } from "@/contracts";
import { inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { ErrorState, Loading } from "@/components/States";
import { FlipBoard, Illustrative, PromiseMeter, Segmented, SupplierBadge, Tip, cn } from "@/components/ui";
import { BookingPanel } from "@/components/BookingPanel";
import { PageHeader } from "@/components/PageHeader";

export default function HotelDetailPage() {
  const { id } = useParams();
  const res = useApi<HotelDetail>(`/api/hotels/${id}`);
  if (res.status === "loading") return <Loading what="Building the golden record" />;
  if (res.status === "error") return <ErrorState error={res.error} onRetry={res.reload} />;
  return <Detail d={res.data} />;
}

function Detail({ d }: { d: HotelDetail }) {
  const [params, setParams] = useSearchParams();
  const tpOn = params.get("tp") === "1";
  const booking = params.get("book") === "1";
  const enrich = params.get("enrich") === "before" ? "before" : "after";
  const bookRef = useRef<HTMLDivElement>(null);
  const offersRef = useRef<HTMLElement>(null);
  const set = useCallback((k: string, v: string) => { const n = new URLSearchParams(params); n.set(k, v); setParams(n, { replace: true }); }, [params, setParams]);

  useEffect(() => { if (booking) setTimeout(() => bookRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 450); }, [booking]);
  useEffect(() => { if (tpOn && !booking) offersRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [tpOn, booking]);
  // Beat 3: Space flips True Price. Beat 4's Space is handled by the booking panel.
  usePresenterAction(useCallback(() => { if (!booking) set("tp", tpOn ? "0" : "1"); }, [booking, tpOn, set]));

  const fact = (k: string) => d.facts.find((f) => f.key === k);
  const p = d.params;
  return (
    <div className="mx-auto max-w-[1500px] px-8 pb-[50vh] pt-6">
      <Link to="/hotels?view=samesame" className="inline-flex items-center gap-1 text-ink-mute hover:text-ink"><ArrowLeft className="h-4 w-4" />Back to results</Link>
      <div className="mt-3">
        <PageHeader eyebrow={`Hotel · ${d.params.city}`} title={d.name}
          subtitle={<span className="flex flex-wrap items-center gap-3">
            {fact("star") && <FactValue f={fact("star")!} />}·{fact("address") && <FactValue f={fact("address")!} />}
            <span className="rounded-full bg-accent-700 px-3 py-0.5 text-sm font-semibold text-white">{new Set(d.offers.map((o) => o.supplier)).size} suppliers · {d.offers.length} offers</span>
          </span>}
          right={d.lookalike && (
            <div className="flex items-center gap-2 rounded-2xl bg-danger-50 px-4 py-2.5 text-danger-700 shadow-card">
              <AlertTriangle className="h-4 w-4" />Not the same as <b>{d.lookalike.other_name}</b> ({Math.round(d.lookalike.distance_m)} m away)
            </div>
          )} />
      </div>

      <EnrichmentSection d={d} mode={enrich} onMode={(m) => set("enrich", m)} />

      <section ref={offersRef} className="mt-10 scroll-mt-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-[28px] font-semibold text-accent-700">Compare offers</h2>
            <div className="mt-1 text-ink-mute">
              {p.adults} adults · {p.nights} nights · travel {new Date(p.checkin).toLocaleDateString("en-IN", { day: "numeric", month: "short" })} · client wants {p.needs.join(", ") || "nothing extra"}
            </div>
          </div>
          <button onClick={() => set("tp", tpOn ? "0" : "1")}
            className={cn("flex items-center gap-3 rounded-xl border-2 px-5 py-3 text-lg font-semibold transition-colors",
              tpOn ? "border-accent-600 bg-accent-600 text-white" : "border-ink bg-paper text-ink hover:bg-paper-warm")}>
            <span className={cn("relative h-6 w-11 rounded-full transition-colors", tpOn ? "bg-white/30" : "bg-paper-line")}>
              <motion.span layout className="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow" style={{ left: tpOn ? 22 : 2 }} />
            </span>
            True Price
          </button>
        </div>
        <OffersTable offers={d.offers} tpOn={tpOn} />
        <p className="mt-3 text-sm text-ink-mute">
          True Price = sticker + missing needs + cancellation risk + price-change risk + booking-failure risk − pay-later value. Hover any term for its assumption.
          The sticker stays the big number; True Price can be switched off.
        </p>
      </section>

      {d.reference && <section className="mt-10"><ReferenceSection r={d.reference} /></section>}
      <section className="mt-10"><RoomsSection d={d} /></section>

      <div ref={bookRef} className="scroll-mt-6">
        <BookingPanel offers={d.offers} active={booking} />
      </div>
    </div>
  );
}

function FactValue({ f }: { f: SourcedFact }) {
  return (
    <Tip side="bottom" content={<div>
      <div className="mb-1 font-semibold">{f.label}: trust-weighted vote</div>
      {f.sources.map((s) => (
        <div key={s.supplier} className={cn("flex justify-between gap-4", s.value === f.value ? "text-white" : "text-white/50")}>
          <span>{s.supplier} <span className="text-white/50">(trust {s.trust.toFixed(2)})</span></span><span>{s.value}</span>
        </div>
      ))}
    </div>}>
      <span className="cursor-help border-b border-dotted border-ink-mute">{f.value}</span>
    </Tip>
  );
}

function EnrichmentSection({ d, mode, onMode }: { d: HotelDetail; mode: "before" | "after"; onMode: (m: "before" | "after") => void }) {
  const e = d.enrichment;
  const before = mode === "before";
  const images = before ? e.before_images : d.images;
  const facts = before ? e.before_facts : d.facts;
  return (
    <section className="mt-6 rounded-3xl border border-paper-line bg-paper shadow-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Segmented size="md" value={mode} onChange={onMode}
            options={[{ value: "before", label: `Before · ${e.supplier} only` }, { value: "after", label: <span className="flex items-center gap-1.5"><Sparkles className="h-4 w-4" />After · golden record</span> }]} />
        </div>
        <div className="flex gap-6 text-sm">
          <Stat label="images" a={e.before_images.length} b={d.images.length} before={before} />
          <Stat label="amenities" a={e.before_amenities.length} b={e.after_amenities.length} before={before} />
          <Stat label="description words" a={e.before_description.split(" ").length} b={e.after_description.split(" ").length} before={before} />
        </div>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-[1.1fr_1fr]">
        <div className="grid grid-cols-4 grid-rows-2 gap-2">
          <Illustrative img={images[0]} className={cn("row-span-2 h-[300px] rounded-2xl", images.length > 1 || before ? "col-span-3" : "col-span-4")} />
          {before
            ? [1, 2].map((i) => images[i]   // Before: the gaps are the point (this supplier sends fewer photos)
              ? <Illustrative key={i} img={images[i]} className="h-[146px] rounded-2xl" label={false} />
              : <div key={i} className="flex h-[146px] items-center justify-center rounded-2xl border border-dashed border-sand-300 bg-sand-100/60 text-sm text-ink-mute">no photo from {d.enrichment.supplier}</div>)
            : images.slice(1, 3).map((im, i, arr) => (
              <Illustrative key={i} img={im} className={cn("rounded-2xl", arr.length === 1 ? "row-span-2 h-[300px]" : "h-[146px]")} label={false} />))}
        </div>
        <div>
          <dl className="grid grid-cols-[110px_1fr] gap-x-4 gap-y-2">
            {facts.map((f) => (
              <div key={f.key} className="contents">
                <dt className="text-ink-mute">{f.label}</dt>
                <dd className="font-medium">{before ? f.value : <FactValue f={f} />}</dd>
              </div>
            ))}
          </dl>
          <div className="mt-3 text-[15px] leading-relaxed text-ink-soft">
            {before ? e.before_description : (
              <Tip content={<>Merged from {e.after_description_sources.join(", ")}</>}><span className="cursor-help">{e.after_description}</span></Tip>
            )}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <AnimatePresence initial={false}>
              {(before ? e.before_amenities.map((n) => ({ name: n, sources: [e.supplier] })) : e.after_amenities).map((a) => (
                <motion.span key={a.name} layout initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }} transition={{ duration: 0.25 }}>
                  <Tip content={<>Source: {a.sources.join(", ")}</>}>
                    <span className="cursor-help rounded-md bg-paper-warm px-2 py-1 text-sm text-ink-soft">{a.name}</span>
                  </Tip>
                </motion.span>
              ))}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, a, b, before }: { label: string; a: number; b: number; before: boolean }) {
  return (
    <div className="text-right">
      <div className="text-2xl font-bold tabular-nums">{before ? a : <><span className="text-ink-mute line-through decoration-1">{a}</span> → <span className="text-accent-700">{b}</span></>}</div>
      <div className="text-ink-mute">{label}</div>
    </div>
  );
}

const TERM_SHORT: Record<string, string> = { fill_needs: "needs", cancel_risk: "cancel", price_change: "price-chg", failover: "fail", pay_later: "pay-later" };

function OffersTable({ offers, tpOn }: { offers: Offer[]; tpOn: boolean }) {
  const rows = [...offers].sort((a, b) => tpOn ? a.true_rank - b.true_rank : a.sticker_rank - b.sticker_rank);
  return (
    <div className="mt-4 overflow-visible rounded-3xl border border-paper-line bg-paper shadow-card">
      <div className="grid grid-cols-[48px_1.25fr_1.2fr_1.5fr_0.9fr_1.2fr_1fr_0.9fr] gap-3 border-b border-paper-line px-4 py-3 text-sm font-semibold uppercase tracking-wide text-ink-mute">
        <div>#</div><div>Supplier</div><div>Room · board</div><div>Price</div><div>Availability</div><div>Cancellation</div><div>Payment</div><div className="text-center">Reliability</div>
      </div>
      <LayoutGroup>
        {rows.map((o, i) => {
          const moved = o.sticker_rank - o.true_rank;
          return (
            <motion.div key={o.offer_id} layout transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className={cn("grid grid-cols-[48px_1.25fr_1.2fr_1.5fr_0.9fr_1.2fr_1fr_0.9fr] items-center gap-3 border-b border-paper-line px-4 py-3 last:border-0",
                tpOn && i === 0 && "bg-accent-50")}>
              <div className="text-xl font-bold tabular-nums text-ink-mute">
                {tpOn ? o.true_rank : o.sticker_rank}
                {tpOn && moved !== 0 && (
                  <div className={cn("flex items-center text-xs font-semibold", moved > 0 ? "text-ok-700" : "text-danger-700")}>
                    {moved > 0 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}{Math.abs(moved)}
                  </div>
                )}
              </div>
              <div><SupplierBadge name={o.supplier} /></div>
              <div><div className="font-medium">{o.room_name}</div><div className={cn("text-sm", o.board === "Room only" ? "text-ink-mute" : "font-semibold text-ok-700")}>{o.board}</div></div>
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-2xl font-bold tabular-nums">{inr(o.price)}</span>
                  <FlipBoard text={tpOn ? inr(o.true_price.total).padStart(8, " ") : "  TRUE  "} className="text-[21px]" tone={tpOn && i === 0 ? "accent" : "dark"} />
                </div>
                {tpOn && (
                  <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mt-1 flex flex-wrap gap-x-1.5 text-[13px] text-ink-mute">
                    {o.true_price.terms.map((t) => t.key === "sticker" || Math.abs(t.amount) < 1 ? null : (
                      <Tip key={t.key} content={<><b>{t.label}</b>: {inr(t.amount)}<br />{t.assumption}</>}>
                        <span className={cn("cursor-help whitespace-nowrap", Math.abs(t.amount) >= 500 && "font-semibold text-ink-soft")}>
                          {t.amount < 0 ? "−" : "+"}{inr(Math.abs(t.amount))} {TERM_SHORT[t.key]}
                        </span>
                      </Tip>
                    ))}
                  </motion.div>
                )}
              </div>
              <div className={cn("text-sm font-medium", o.availability === "limited" ? "text-warn-500" : "text-ok-700")}>{o.availability === "limited" ? "Limited" : "Available"}</div>
              <div className={cn("text-sm", o.refundable_until ? "text-ok-700" : "text-danger-700")}>{o.cancel_text}</div>
              <div className="text-sm">{o.pay_text}</div>
              <div className="flex justify-center"><PromiseMeter rate={o.promise.honour_rate} n={o.promise.n} lo={o.promise.ci_low} hi={o.promise.ci_high} /></div>
            </motion.div>
          );
        })}
      </LayoutGroup>
    </div>
  );
}

/** Real public data for the matched property: shown beside the supplier vote, never mixed into it. */
function ReferenceSection({ r }: { r: Reference }) {
  return (
    <div className="rounded-3xl border border-paper-line bg-paper shadow-card p-5">
      <h2 className="text-[28px] font-semibold text-accent-700">Reference data</h2>
      <p className="mt-1 text-ink-mute">Matched to <a className="underline" href={r.url} target="_blank" rel="noreferrer">OpenStreetMap {r.osm_id}</a> ({r.match}). Real, public data, not from any supplier.</p>
      <dl className="mt-3 grid grid-cols-[120px_1fr] gap-y-1.5">
        {([["Name", r.name], ["Address", r.address], ["Phone", r.phone], ["Website", r.website], ["Stars", r.stars && `${r.stars}★`]] as const)
          .filter(([, v]) => v).map(([k, v]) => <div key={k} className="contents"><dt className="text-ink-mute">{k}</dt><dd>{v}</dd></div>)}
      </dl>
      <div className="mt-1 text-xs text-ink-mute">{r.license}</div>
      {r.description && (
        <div className="mt-4 border-t border-paper-line pt-3">
          <p className="text-[15px] leading-relaxed">{r.description.text}</p>
          <div className="mt-1 text-xs text-ink-mute">From Wikipedia, <a className="underline" href={r.description.source} target="_blank" rel="noreferrer">{r.description.title}</a> · {r.description.license}</div>
        </div>
      )}
    </div>
  );
}

function RoomsSection({ d }: { d: HotelDetail }) {
  return (
    <>
      <h2 className="text-[28px] font-semibold text-accent-700">Room types, mapped</h2>
      <p className="mt-1 text-ink-mute">Every supplier names rooms differently. SameSame maps them to one canonical room.</p>
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {d.rooms.map((r) => (
          <div key={r.room_id} className="rounded-2xl border border-paper-line bg-paper shadow-card p-4">
            <div className="text-lg font-bold">{r.name}</div>
            <div className="mt-1 flex flex-wrap gap-1.5 text-xs">{Object.entries(r.attrs).map(([k, v]) => <span key={k} className="rounded bg-accent-50 px-1.5 py-0.5 text-accent-700">{k.replace("_", " ")}: {v}</span>)}</div>
            <ul className="mt-3 space-y-1.5">
              {r.members.map((m) => (
                <li key={m.supplier + m.raw_name} className="flex items-center justify-between gap-2 text-sm">
                  <span className="flex min-w-0 items-center gap-2"><SupplierBadge name={m.supplier} small /><span className="truncate font-mono text-ink-soft">{m.raw_name}</span></span>
                  <Tip content={<>{m.note ?? "Tier, bed and view parsed from the supplier's room name."}</>}>
                    <span className={cn("cursor-help tabular-nums", (m.confidence ?? 1) < 0.8 ? "font-semibold text-warn-500" : "text-ink-mute")}>
                      {m.confidence == null ? "—" : `${Math.round(m.confidence * 100)}%`}
                    </span>
                  </Tip>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </>
  );
}
