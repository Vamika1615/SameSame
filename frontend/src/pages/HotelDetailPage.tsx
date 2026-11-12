import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { AlertTriangle, ArrowDown, ArrowLeft, ArrowUp, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import type { CatalogueHotel, HotelDetail, Offer, SourcedFact, Reference } from "@/contracts";
import { inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { ErrorState, Loading } from "@/components/States";
import { FlipBoard, Illustrative, PromiseMeter, Segmented, SupplierBadge, Tip, cn } from "@/components/ui";
import { BookingPanel } from "@/components/BookingPanel";
import { ConnectedTripCard } from "@/components/ConnectedTripCard";
import { PageHeader } from "@/components/PageHeader";
import { RateGrid, Terms } from "@/components/RateGrid";

export default function HotelDetailPage() {
  const { id } = useParams();
  const res = useApi<HotelDetail>(`/api/hotels/${id}`);
  if (res.status === "loading") return <Loading what="Building the golden record" />;
  if (res.status === "error") return <ErrorState error={res.error} onRetry={res.reload} />;
  return <Detail d={res.data} demo={id === "demo"} />;
}

type Tab = "offers" | "sheets" | "about" | "rooms" | "trip";

function Detail({ d, demo }: { d: HotelDetail; demo: boolean }) {
  const [params, setParams] = useSearchParams();
  const tpOn = params.get("tp") === "1";
  const booking = params.get("book") === "1";
  const trip = params.get("trip") === "1";
  const tab: Tab = trip ? "trip" : ((params.get("tab") as Tab) ?? "offers");
  const enrich = params.get("enrich") === "before" ? "before" : "after";
  const bookRef = useRef<HTMLDivElement>(null);
  const set = useCallback((k: string, v: string) => { const n = new URLSearchParams(params); n.set(k, v); setParams(n, { replace: true }); }, [params, setParams]);
  const setTab = (t: Tab) => { const n = new URLSearchParams(params); n.set("tab", t); n.delete("trip"); if (t === "trip") n.set("trip", "1"); setParams(n, { replace: true }); };

  useEffect(() => { if (booking) setTimeout(() => bookRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 450); }, [booking]);
  // Space flips True Price. The booking panel and the trip card handle their own Space.
  usePresenterAction(useCallback(() => { if (!booking && !trip) set("tp", tpOn ? "0" : "1"); }, [booking, trip, tpOn, set]));

  const fact = (k: string) => d.facts.find((f) => f.key === k);
  const p = d.params;
  const cat = useApi<CatalogueHotel>(`/api/catalogue/hotels/${d.cluster_id}`);
  const sheetRates = cat.status === "ready" ? cat.data.rates.length : 0;
  const tabs: [Tab, string][] = [["offers", `Offers · ${d.offers.length}`], ...(sheetRates ? [["sheets", `Sheet rates · ${sheetRates.toLocaleString("en-IN")}`] as [Tab, string]] : []),
    ["about", "About the hotel"], ["rooms", `Rooms · ${d.rooms.length}`], ...(demo ? [["trip", "Trip package"] as [Tab, string]] : [])];
  return (
    <div className="mx-auto max-w-[1400px] px-8 pb-24 pt-6">
      <Link to="/catalogue" className="inline-flex items-center gap-1 text-sm text-ink-mute hover:text-ink"><ArrowLeft className="h-4 w-4" />All hotels</Link>
      <div className="mt-3">
        <PageHeader title={d.name}
          subtitle={<span className="flex flex-wrap items-center gap-x-2">
            {fact("star") && <FactValue f={fact("star")!} />}<span>·</span>{fact("address") && <FactValue f={fact("address")!} />}
            <span>· sold by {new Set(d.offers.map((o) => o.supplier)).size} suppliers</span>
          </span>} />
        {d.lookalike && (
          <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-danger-50 px-3 py-1 text-sm text-danger-700">
            <AlertTriangle className="h-4 w-4" />Not the same hotel as {d.lookalike.other_name}, {Math.round(d.lookalike.distance_m)} m away
          </div>
        )}
      </div>

      <div className="mt-6 flex gap-1 border-b border-paper-line">
        {tabs.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("relative px-4 py-2.5 text-[15px] font-medium transition-colors", tab === k ? "text-ink" : "text-ink-mute hover:text-ink")}>
            {label}{tab === k && <span className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-accent-700" />}
          </button>
        ))}
      </div>

      {tab === "offers" && (
        <>
          <section className="mt-6">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div className="text-ink-mute">
                {p.adults} adults · {p.nights} nights from {new Date(p.checkin).toLocaleDateString("en-IN", { day: "numeric", month: "short" })} · client wants {p.needs.join(", ") || "nothing extra"}
              </div>
              <button onClick={() => set("tp", tpOn ? "0" : "1")} className="flex items-center gap-3 rounded-full border border-paper-line bg-paper px-4 py-2 text-sm font-medium text-ink-soft hover:border-accent-500">
                <span className={cn("relative h-5 w-9 rounded-full transition-colors", tpOn ? "bg-accent-700" : "bg-paper-line")}>
                  <motion.span layout className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow" style={{ left: tpOn ? 18 : 2 }} />
                </span>
                Rank by True Price
              </button>
            </div>
            <OffersTable offers={d.offers} tpOn={tpOn} />
            <p className="mt-3 text-sm text-ink-mute">
              True Price = listed price + extras the client needs + the expected cost of cancellation, price changes and failed bookings − the value of paying later. Hover any term for its assumption.
            </p>
          </section>
          <div ref={bookRef} className="scroll-mt-36"><BookingPanel offers={d.offers} active={booking} /></div>
        </>
      )}
      {tab === "about" && (
        <>
          <EnrichmentSection d={d} mode={enrich} onMode={(m) => set("enrich", m)} />
          {d.reference && <section className="mt-6"><ReferenceSection r={d.reference} /></section>}
        </>
      )}
      {tab === "rooms" && <section className="mt-6"><RoomsSection d={d} /></section>}
      {tab === "sheets" && cat.status === "ready" && (
        <section className="mt-6 space-y-6">
          <div className="flex flex-wrap gap-2">
            {cat.data.sources.map((x) => (
              <Link key={x.import_id + x.as_written} to={`/import?id=${x.import_id}`} className="rounded-full border border-paper-line bg-paper px-3 py-1 text-sm text-ink-soft hover:border-accent-500">
                <b className="text-ink">{x.supplier}</b> · {x.file}{x.as_written !== d.name ? ` · as “${x.as_written}”` : ""}</Link>))}
          </div>
          <div className="rounded-2xl border border-paper-line bg-paper p-5">
            <h2 className="text-xl text-ink">Contracted rates from imported sheets</h2>
            <p className="text-sm text-ink-mute">Each sheet's rooms are mapped onto this hotel's rooms, so these rates line up with the supplier offers.</p>
            <div className="mt-3"><RateGrid rates={cat.data.rates} /></div>
          </div>
          <div className="rounded-2xl border border-paper-line bg-paper p-5"><h2 className="text-xl text-ink">Terms</h2><div className="mt-3"><Terms conditions={cat.data.conditions} /></div></div>
        </section>
      )}
      {tab === "trip" && demo && <ConnectedTripCard active={trip} />}
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
    <section className="mt-6 rounded-2xl border border-paper-line bg-paper p-5">
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
    <div className="mt-4 overflow-visible rounded-2xl border border-paper-line bg-paper">
      <div className="grid grid-cols-[48px_1.25fr_1.2fr_1.5fr_0.9fr_1.2fr_1fr_0.9fr] gap-3 border-b border-paper-line px-4 py-3 text-xs font-medium text-ink-mute">
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
                  <span className={cn("text-xl font-semibold tabular-nums", tpOn && "text-ink-mute")}>{inr(o.price)}</span>
                  {tpOn && <FlipBoard text={inr(o.true_price.total).padStart(8, " ")} className="text-[18px]" tone={i === 0 ? "accent" : "dark"} />}
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
              <div className="flex justify-center"><PromiseMeter rate={o.promise.honour_rate} n={o.promise.n} lo={o.promise.ci_low} hi={o.promise.ci_high} prior={o.promise.prior_weight} /></div>
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
    <div className="rounded-2xl border border-paper-line bg-paper p-5">
      <h2 className="text-xl text-ink">Public reference data</h2>
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
      <p className="text-ink-mute">Every supplier names rooms differently. Each card is one real room type, with the names suppliers use for it.</p>
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {d.rooms.map((r) => (
          <div key={r.room_id} className="rounded-2xl border border-paper-line bg-paper p-4">
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
