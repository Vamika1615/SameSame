import { LayoutGroup, motion } from "framer-motion";
import { AlertTriangle, Layers, MapPin, Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { HotelCard, HotelSearch } from "@/contracts";
import { inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { OfflineMap, type MapLine, type Pin } from "@/components/OfflineMap";
import { Empty, ErrorState, Loading } from "@/components/States";
import { AnimatedNumber, Illustrative, Segmented, Stars, SupplierBadge, SUPPLIER_COLOR, Tip, cn } from "@/components/ui";
import { WhyChips } from "@/components/WhyChips";

type View = "today" | "samesame";
const SPRING = { type: "tween", ease: [0.22, 1, 0.36, 1], duration: 0.55 } as const;

export default function HotelsPage() {
  const res = useApi<HotelSearch>("/api/hotels/search");
  if (res.status === "loading") return <Loading what="Searching 6 suppliers" />;
  if (res.status === "error") return <ErrorState error={res.error} onRetry={res.reload} />;
  if (!res.data.today.length) return <Empty title="No hotels for this search">Try widening the area or the star filter.</Empty>;
  return <Listing data={res.data} />;
}

function SearchSummary({ data }: { data: HotelSearch }) {
  const p = data.params;
  const d = new Date(p.checkin).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  return (
    <div className="flex flex-wrap items-center gap-2 text-[15px] text-ink-soft">
      {[`${p.city} · ${p.area}`, `${d} · ${p.nights} nights`, `${p.adults} adults${p.children ? ` + ${p.children}` : ""}`,
        p.star_min ? `${p.star_min}★ and up` : null, p.needs.length ? `Client wants ${p.needs.join(", ")}` : null,
        `Agent market: ${p.source_market === "IN" ? "India" : p.source_market}`].filter(Boolean).map((s) => (
        <span key={s} className="rounded-full border border-paper-line bg-paper px-3 py-1">{s}</span>
      ))}
    </div>
  );
}

function Listing({ data }: { data: HotelSearch }) {
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();
  const view: View = params.get("view") === "samesame" ? "samesame" : "today";
  const focusLookalike = params.get("focus") === "lookalike";
  const [active, setActive] = useState<string[]>([]);
  const [hover, setHover] = useState<string | null>(null);

  const setView = useCallback((v: View) => {
    const next = new URLSearchParams(params);
    next.set("view", v);
    if (v === "today") next.delete("focus");
    setParams(next, { replace: true });
  }, [params, setParams]);
  usePresenterAction(useCallback(() => setView(view === "today" ? "samesame" : "today"), [view, setView]));

  const pass = (c: HotelCard) => active.every((k) => c.dna_tags.includes(k));
  const cards = (view === "today" ? data.today : data.samesame).filter(pass);
  const looks = data.samesame.filter((c) => c.lookalike);

  useEffect(() => {
    if (view === "samesame" && focusLookalike && looks[0]) {
      const t = setTimeout(() => document.getElementById(`card-${looks[0].cluster_id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 650);
      return () => clearTimeout(t);
    }
  }, [view, focusLookalike, looks]);

  const pins = useMemo<Pin[]>(() => {
    const anchor: Pin = { id: "anchor", lat: data.params.area_lat, lng: data.params.area_lng, label: data.params.area.split(" ·")[0], tone: "anchor", permanent: true };
    const base = (view === "today" ? data.today : data.samesame).filter(pass).map((c) => ({
      id: c.cluster_id, lat: c.lat, lng: c.lng, label: view === "today" ? `${c.name} · ${c.supplier}` : `#${c.rank} ${c.name}`,
      tone: view === "samesame" && c.lookalike ? "danger" as const : "accent" as const,
      permanent: view === "samesame" && !!c.lookalike,
    }));
    return [anchor, ...base];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, view, active]);
  const lines = useMemo<MapLine[]>(() => {
    if (view !== "samesame" || looks.length < 2) return [];
    const [a, b] = looks;
    return [{ from: [a.lat, a.lng], to: [b.lat, b.lng], label: `${Math.round(a.lookalike!.distance_m)} m` }];
  }, [view, looks]);

  const c = data.counters;
  return (
    <div className="flex h-full min-h-0">
      <div className="min-w-0 flex-1 overflow-y-auto px-8 pb-16 pt-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Hotels in Bangkok</h1>
            <div className="mt-2"><SearchSummary data={data} /></div>
          </div>
          <Segmented value={view} onChange={setView}
            options={[{ value: "today", label: "Today" }, { value: "samesame", label: <span className="flex items-center gap-2"><Layers className="h-5 w-5" />SameSame</span> }]} />
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-paper-line bg-paper px-5 py-3">
          <div className="text-lg">
            {view === "today" ? (
              <><b className="tabular-nums">{c.raw_listings}</b> listings from 6 suppliers <span className="text-ink-mute">· sorted by sticker price</span></>
            ) : (
              <><b className="tabular-nums">{c.unique_hotels}</b> hotels · <span className="font-bold text-accent-700"><AnimatedNumber value={c.duplicates_collapsed} /> duplicates collapsed</span>
                <span className="text-ink-mute"> · ranked by True Price, promise and fit</span></>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {data.filters.map((f) => {
              const on = active.includes(f.key);
              const shown = view === "today" ? f.today_count : f.count;
              return (
                <Tip key={f.key} side="bottom" content={<>Variant DNA finds <b>{f.count}</b> listings with {f.label.toLowerCase()}.<br />
                  Keyword search on supplier text finds <b>{f.today_count}</b>.{f.today_count === 0 && " No supplier exposes it as text."}</>}>
                  <button onClick={() => setActive((a) => on ? a.filter((k) => k !== f.key) : [...a, f.key])}
                    className={cn("rounded-full border px-3 py-1.5 text-[15px] font-medium transition-colors",
                      on ? "border-accent-600 bg-accent-600 text-white" : "border-paper-line bg-paper text-ink-soft hover:border-accent-500")}>
                    {f.label} <span className={cn("ml-1 tabular-nums", on ? "text-white/80" : "text-ink-mute")}>{shown}</span>
                  </button>
                </Tip>
              );
            })}
          </div>
        </div>
        {view === "today" && active.length > 0 && (
          <div className="mt-2 text-sm text-ink-mute">Today's filter can only keyword-match supplier text ("BB NRF", "Incl. ABF" and "ROOM W/ ABF" never say "breakfast").</div>
        )}

        <LayoutGroup>
          {cards.length === 0 && <Empty title="Nothing matches these filters">Remove a filter to see more hotels.</Empty>}
          <div className={cn("mt-5 grid gap-4", view === "today" ? "grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3" : "grid-cols-1 2xl:grid-cols-2 gap-x-8 gap-y-6")}>
            {view === "today"
              ? cards.map((card) => (
                <motion.div key={card.card_id} layoutId={card.card_id} transition={SPRING}
                  onMouseEnter={() => setHover(card.cluster_id)} onMouseLeave={() => setHover(null)}
                  onClick={() => nav(`/hotels/${card.cluster_id}`)} className="cursor-pointer">
                  <TodayCard card={card} />
                </motion.div>))
              : cards.map((card) => (
                <Stack key={card.cluster_id} card={card} pulse={focusLookalike && !!card.lookalike}
                  onHover={setHover} onOpen={() => nav(`/hotels/${card.cluster_id}`)} />))}
          </div>
        </LayoutGroup>
      </div>

      <aside className="hidden w-[420px] shrink-0 border-l border-paper-line bg-paper p-4 lg:block">
        <div className="mb-2 flex items-center justify-between text-sm text-ink-mute">
          <span className="flex items-center gap-1"><MapPin className="h-4 w-4" />Offline map · no tile server</span>
          {view === "samesame" && looks.length > 0 && <span className="font-semibold text-danger-700">Red = look-alikes kept apart</span>}
        </div>
        <OfflineMap pins={pins} lines={lines} highlight={hover} fitPins className="h-[calc(100%-28px)] rounded-xl border border-paper-line" />
      </aside>
    </div>
  );
}

function TodayCard({ card }: { card: HotelCard }) {
  return (
    <div className="flex h-[112px] overflow-hidden rounded-xl border border-paper-line bg-paper shadow-sm transition-shadow hover:shadow-md">
      <Illustrative img={card.image} className="h-full w-[112px] shrink-0" label={false} />
      <div className="flex min-w-0 flex-1 flex-col justify-between p-3">
        <div className="min-w-0">
          <div className="truncate font-semibold leading-tight">{card.name}</div>
          <div className="mt-1 flex items-center gap-2 text-sm text-ink-mute"><Stars n={card.star} />{card.district}</div>
        </div>
        <div className="flex items-end justify-between">
          {card.supplier && <SupplierBadge name={card.supplier} small />}
          <div className="text-right"><div className="text-lg font-bold tabular-nums">{inr(card.from_price)}</div></div>
        </div>
      </div>
    </div>
  );
}

function Stack({ card, pulse, onHover, onOpen }: { card: HotelCard; pulse: boolean; onHover: (id: string | null) => void; onOpen: () => void }) {
  const [lead, ...rest] = card.member_ids;
  const look = card.lookalike;
  return (
    <div id={`card-${card.cluster_id}`} className="relative" onMouseEnter={() => onHover(card.cluster_id)} onMouseLeave={() => onHover(null)}>
      {rest.slice(0, 4).map((id, i) => (
        <motion.div key={id} layoutId={id} transition={SPRING} className="absolute rounded-xl border border-paper-line bg-paper shadow-sm"
          style={{ top: (rest.length > 4 ? 4 : rest.length) * 5 - i * 5 + 5, left: (rest.length > 4 ? 4 : rest.length) * 5 - i * 5 + 5, width: "100%", height: "100%", zIndex: 1 + i }} />
      ))}
      {rest.slice(4).map((id) => (
        <motion.div key={id} layoutId={id} transition={SPRING} className="absolute inset-0 rounded-xl bg-paper opacity-0" />
      ))}
      <motion.div layoutId={lead} transition={SPRING} onClick={onOpen}
        className={cn("relative z-10 flex cursor-pointer overflow-visible rounded-xl border bg-paper shadow-md transition-shadow hover:shadow-lg",
          look ? "border-danger-500" : "border-paper-line", pulse && "pulse-danger")}>
        <Illustrative img={card.image} className="w-[170px] shrink-0 rounded-l-xl" />
        <div className="min-w-0 flex-1 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink-mute">#{card.rank}</div>
              <div className="text-xl font-bold leading-tight">{card.name}</div>
              <div className="mt-1 flex items-center gap-2 text-sm text-ink-mute"><Stars n={card.star} />{card.district}</div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-sm text-ink-mute">from</div>
              <div className="text-2xl font-bold tabular-nums">{inr(card.from_price)}</div>
              {card.true_price_from != null && <div className="text-sm font-semibold text-accent-700">True Price {inr(card.true_price_from)}</div>}
            </div>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Tip content={<>{card.suppliers.join(" · ")}<br />One hotel, one card. Offers compared inside.</>}>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-ink px-2.5 py-1 text-sm font-semibold text-white">
                <Users className="h-3.5 w-3.5" />{card.suppliers.length} suppliers
                <span className="ml-1 flex -space-x-1">{card.suppliers.map((s) => <span key={s} className="h-2.5 w-2.5 rounded-full ring-1 ring-ink" style={{ background: SUPPLIER_COLOR[s] }} />)}</span>
              </span>
            </Tip>
            {look && (
              <span className="inline-flex items-center gap-1 rounded-full bg-danger-500 px-2.5 py-1 text-sm font-bold text-white">
                <AlertTriangle className="h-3.5 w-3.5" />Looks the same, isn't
              </span>
            )}
          </div>
          {look && (
            <div className="mt-2 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
              Kept apart from <b>{look.other_name}</b>: {look.reasons.map((r) => r.text).join(" · ")}
            </div>
          )}
          <WhyChips why={card.why} score={card.score} className="mt-2" />
        </div>
      </motion.div>
    </div>
  );
}
