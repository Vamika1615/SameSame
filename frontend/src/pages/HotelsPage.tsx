import { LayoutGroup, motion } from "framer-motion";
import { AlertTriangle, CalendarDays, Check, ChevronRight, Coffee, Globe2, Layers, MapPin, Search, Star, UserRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { HotelCard, HotelSearch } from "@/contracts";
import { inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { OfflineMap, type MapLine, type Pin } from "@/components/OfflineMap";
import { Empty, ErrorState, Loading } from "@/components/States";
import { AnimatedNumber, Illustrative, Segmented, Stars, SupplierAvatars, SupplierBadge, SUPPLIER_COLOR, Tip, cn, metres } from "@/components/ui";
import { Skyline } from "@/components/Skyline";
import { WhyChips } from "@/components/WhyChips";
import { CITY } from "@/lib/city";

type View = "today" | "samesame";
const SPRING = { type: "tween", ease: [0.22, 1, 0.36, 1], duration: 0.55 } as const;

export default function HotelsPage() {
  const res = useApi<HotelSearch>("/api/hotels/search");
  if (res.status === "loading") return <Loading what="Searching 6 suppliers" />;
  if (res.status === "error") return <ErrorState error={res.error} onRetry={res.reload} />;
  if (!res.data.today.length) return <Empty title="No hotels for this search">Try widening the area or the star filter.</Empty>;
  return <Listing data={res.data} />;
}

function HeroSearch({ data, onSearch }: { data: HotelSearch; onSearch: () => void }) {
  const p = data.params;
  const d = new Date(p.checkin).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  const seg = "flex items-center gap-2.5 px-4 py-1";
  return (
    <section className="hero-sky relative overflow-hidden rounded-4xl px-12 pb-8 pt-8">
      <Skyline className="pointer-events-none absolute bottom-0 right-0 h-[82%] w-[58%] opacity-60" />
      <div className="relative max-w-[720px]">
        <div className="text-xs font-semibold uppercase tracking-[0.22em] text-accent-700/80">Hotels · {p.city}</div>
        <h1 className="mt-2 text-[46px] leading-[1.05] text-accent-700">Find the same hotel <span className="italic">across suppliers.</span></h1>
        <p className="mt-3 text-lg text-ink-soft">One hotel, one card. The real price, from the supplier that keeps its promise.</p>
        <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-paper/70 px-3 py-1 text-[13px] font-medium text-ink-soft backdrop-blur">
          <Globe2 className="h-4 w-4 text-sun-500" />Agent in Surat · source market {p.source_market === "IN" ? "India" : p.source_market}
        </div>
      </div>
      <div className="relative mt-6 flex w-fit max-w-full flex-wrap items-center gap-y-2 divide-x divide-paper-line rounded-full bg-paper py-2.5 pl-3 pr-2.5 shadow-lift">
        <div className={seg}><MapPin className="h-5 w-5 text-sun-500" /><div><div className="text-[11px] font-semibold uppercase tracking-wide text-ink-mute">Where</div><div className="font-semibold">{p.city} · {p.area}</div></div></div>
        <div className={seg}><CalendarDays className="h-5 w-5 text-sun-500" /><div><div className="text-[11px] font-semibold uppercase tracking-wide text-ink-mute">When</div><div className="font-semibold">{d} · {p.nights} nights</div></div></div>
        <div className={seg}><UserRound className="h-5 w-5 text-sun-500" /><div><div className="text-[11px] font-semibold uppercase tracking-wide text-ink-mute">Guests</div><div className="font-semibold">{p.adults} adults{p.children ? ` + ${p.children}` : ""}</div></div></div>
        <div className={seg}><Star className="h-5 w-5 text-sun-500" /><div><div className="text-[11px] font-semibold uppercase tracking-wide text-ink-mute">Stars</div><div className="font-semibold">{p.star_min ? `${p.star_min}★ and up` : "Any"}</div></div></div>
        {p.needs.length > 0 && <div className={seg}><Coffee className="h-5 w-5 text-sun-500" /><div><div className="text-[11px] font-semibold uppercase tracking-wide text-ink-mute">Client wants</div><div className="font-semibold capitalize">{p.needs.join(", ")}</div></div></div>}
        <div className="ml-auto !border-l-0 pl-2">
          <Tip side="bottom" content="Group the duplicates (same as the SameSame toggle)">
            <button onClick={onSearch} aria-label="Group duplicates" className="flex h-12 w-12 items-center justify-center rounded-full bg-sun-500 text-white shadow-card transition-colors hover:bg-sun-600">
              <Search className="h-5 w-5" />
            </button>
          </Tip>
        </div>
      </div>
    </section>
  );
}

function DnaFilters({ data, view, active, toggle }: { data: HotelSearch; view: View; active: string[]; toggle: (k: string) => void }) {
  return (
    <div className="rounded-3xl border border-paper-line bg-paper p-5 shadow-card">
      <h2 className="text-xl text-accent-700">DNA filters</h2>
      <p className="mt-1 text-[13px] leading-snug text-ink-mute">Structured truth vs what a keyword search on supplier text finds.</p>
      <div className="mt-4 space-y-1">
        {data.filters.map((f) => {
          const on = active.includes(f.key);
          return (
            <button key={f.key} onClick={() => toggle(f.key)}
              className={cn("flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition-colors", on ? "bg-sky-100" : "hover:bg-paper-warm")}>
              <span className={cn("flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 transition-colors", on ? "border-accent-700 bg-accent-700 text-white" : "border-sky-300")}>
                {on && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
              </span>
              <span className="flex-1 font-medium">{f.label}</span>
              <Tip side="bottom" content={<>Variant DNA finds <b>{f.count}</b> listings with {f.label.toLowerCase()}.<br />Keyword search on supplier text finds <b>{f.today_count}</b>.</>}>
                <span className="text-[13px] tabular-nums text-ink-mute">
                  <b className={view === "samesame" ? "text-accent-700" : "text-ink-soft"}>{f.count}</b> vs {f.today_count}
                </span>
              </Tip>
            </button>
          );
        })}
      </div>
      {view === "today" && active.length > 0 && (
        <div className="mt-3 rounded-xl bg-sun-50 px-3 py-2 text-[13px] leading-snug text-sun-700">Today's filter can only keyword-match supplier text: "BB NRF" and "Incl. ABF" never say "breakfast".</div>
      )}
    </div>
  );
}

function AboutData() {
  return (
    <div className="rounded-3xl border border-paper-line bg-paper p-5 shadow-card">
      <div className="flex items-center gap-2"><Layers className="h-5 w-5 text-sun-500" /><h2 className="text-xl text-accent-700">About the data</h2></div>
      <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">
        Six fictional suppliers selling real {CITY} hotels from OpenStreetMap. Hotel groups come from LightGBM matching plus
        constrained clustering, scored by a model that never saw that hotel's labels. Rank is a transparent weighted score: hover <b>why</b> on any card.
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {Object.keys(SUPPLIER_COLOR).map((s) => <SupplierBadge key={s} name={s} small />)}
      </div>
    </div>
  );
}

function LookalikeAlert({ looks }: { looks: HotelCard[] }) {
  const [a] = looks;
  if (!a?.lookalike) return null;
  return (
    <button onClick={() => document.getElementById(`card-${a.cluster_id}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}
      className="w-full rounded-3xl border border-danger-500/30 bg-danger-50 p-4 text-left shadow-card transition-shadow hover:shadow-lift">
      <div className="flex items-center gap-2 font-semibold text-danger-700"><AlertTriangle className="h-5 w-5" />Looks the same, isn't</div>
      <div className="mt-1.5 text-[15px] font-semibold text-ink">{a.name} <span className="font-normal text-ink-mute">vs</span> {a.lookalike.other_name}</div>
      <div className="mt-1 flex items-center justify-between text-[13px] text-ink-soft">
        <span>{Math.round(a.lookalike.distance_m)} m apart · different phone & street</span><ChevronRight className="h-4 w-4" />
      </div>
    </button>
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
  const anchor: [number, number] = [data.params.area_lat, data.params.area_lng];

  useEffect(() => {
    if (view === "samesame" && focusLookalike && looks[0]) {
      const t = setTimeout(() => document.getElementById(`card-${looks[0].cluster_id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 650);
      return () => clearTimeout(t);
    }
  }, [view, focusLookalike, looks]);

  const pins = useMemo<Pin[]>(() => {
    const a: Pin = { id: "anchor", lat: data.params.area_lat, lng: data.params.area_lng, label: data.params.area.split(" ·")[0], tone: "anchor", permanent: true };
    const base = (view === "today" ? data.today : data.samesame).filter(pass).map((c) => ({
      id: c.cluster_id, lat: c.lat, lng: c.lng, label: view === "today" ? `${c.name} · ${c.supplier}` : `#${c.rank} ${c.name}`,
      tone: view === "samesame" && c.lookalike ? "danger" as const : "accent" as const,
      permanent: view === "samesame" && !!c.lookalike,
    }));
    return [a, ...base];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, view, active]);
  const lines = useMemo<MapLine[]>(() => {
    if (view !== "samesame" || looks.length < 2) return [];
    const [a, b] = looks;
    return [{ from: [a.lat, a.lng], to: [b.lat, b.lng], label: `${Math.round(a.lookalike!.distance_m)} m` }];
  }, [view, looks]);

  const c = data.counters;
  return (
    <div className="mx-auto max-w-[1760px] px-8 pb-10 pt-6">
      <HeroSearch data={data} onSearch={() => setView("samesame")} />

      <div className="mt-7 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_380px] xl:grid-cols-[280px_minmax(0,1fr)_400px]">
        <aside className="hidden space-y-5 xl:block">
          <div className="sticky top-[88px] space-y-5">
            <DnaFilters data={data} view={view} active={active} toggle={(k) => setActive((a) => a.includes(k) ? a.filter((x) => x !== k) : [...a, k])} />
            <AboutData />
          </div>
        </aside>

        <div className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Segmented value={view} onChange={setView}
              options={[{ value: "today", label: <span>Today <span className="font-normal opacity-75">({c.raw_listings} listings)</span></span> },
                        { value: "samesame", label: <span className="flex items-center gap-2"><Layers className="h-5 w-5" />SameSame <span className="font-normal opacity-75">({c.unique_hotels} hotels)</span></span> }]} />
            <div className="text-[15px] text-ink-soft">
              {view === "today" ? <>{c.raw_listings} listings from 6 suppliers · <span className="text-ink-mute">sorted by sticker price</span></> : (
                <><span className="font-display text-xl font-semibold text-sun-600"><AnimatedNumber value={c.duplicates_collapsed} /></span> duplicates collapsed
                  <span className="text-ink-mute"> · ranked by True Price, promise and fit</span></>
              )}
            </div>
          </div>
          <div className="mt-3 xl:hidden"><DnaFilters data={data} view={view} active={active} toggle={(k) => setActive((a) => a.includes(k) ? a.filter((x) => x !== k) : [...a, k])} /></div>

          <LayoutGroup>
            {cards.length === 0 && <Empty title="Nothing matches these filters">Remove a filter to see more hotels.</Empty>}
            <div className={cn("mt-5 grid gap-4", view === "today" ? "grid-cols-1 2xl:grid-cols-2" : "grid-cols-1 gap-y-6")}>
              {view === "today"
                ? cards.map((card) => (
                  <motion.div key={card.card_id} layoutId={card.card_id} transition={SPRING}
                    onMouseEnter={() => setHover(card.cluster_id)} onMouseLeave={() => setHover(null)}
                    onClick={() => nav(`/hotels/${card.cluster_id}`)} className="cursor-pointer">
                    <TodayCard card={card} />
                  </motion.div>))
                : cards.map((card) => (
                  <Stack key={card.cluster_id} card={card} pulse={focusLookalike && !!card.lookalike} metresAway={metres(anchor, [card.lat, card.lng])}
                    onHover={setHover} onOpen={() => nav(`/hotels/${card.cluster_id}`)} />))}
            </div>
          </LayoutGroup>
        </div>

        <aside className="hidden lg:block">
          <div className="sticky top-[88px] space-y-4">
            {view === "samesame" && <LookalikeAlert looks={looks} />}
            <div className="overflow-hidden rounded-3xl border border-paper-line bg-paper shadow-card">
              <div className="flex items-center justify-between px-4 py-2.5 text-[13px] text-ink-mute">
                <span className="flex items-center gap-1.5"><MapPin className="h-4 w-4 text-sun-500" />Offline map · no tile server</span>
                {view === "samesame" && looks.length > 0 && <span className="font-semibold text-danger-700">Red = kept apart</span>}
              </div>
              <OfflineMap pins={pins} lines={lines} highlight={hover} fitPins className="h-[calc(100vh-260px)] min-h-[420px]" />
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function TodayCard({ card }: { card: HotelCard }) {
  return (
    <div className="flex h-[118px] overflow-hidden rounded-2xl border border-paper-line bg-paper shadow-card transition-shadow hover:shadow-lift">
      <Illustrative img={card.image} className="h-full w-[124px] shrink-0" label={false} />
      <div className="flex min-w-0 flex-1 flex-col justify-between p-3.5">
        <div className="min-w-0">
          <div className="truncate font-semibold leading-tight">{card.name}</div>
          <div className="mt-1 flex items-center gap-2 text-sm text-ink-mute"><Stars n={card.star} />{card.district}</div>
        </div>
        <div className="flex items-end justify-between">
          {card.supplier && <SupplierBadge name={card.supplier} small />}
          <div className="font-display text-xl font-semibold tabular-nums text-accent-700">{inr(card.from_price)}</div>
        </div>
      </div>
    </div>
  );
}

function Stack({ card, pulse, metresAway, onHover, onOpen }: { card: HotelCard; pulse: boolean; metresAway: number; onHover: (id: string | null) => void; onOpen: () => void }) {
  const [lead, ...rest] = card.member_ids;
  const look = card.lookalike;
  return (
    <div id={`card-${card.cluster_id}`} className="relative" onMouseEnter={() => onHover(card.cluster_id)} onMouseLeave={() => onHover(null)}>
      {rest.slice(0, 4).map((id, i) => (
        <motion.div key={id} layoutId={id} transition={SPRING} className="absolute rounded-3xl border border-paper-line bg-sand-100 shadow-sm"
          style={{ top: (rest.length > 4 ? 4 : rest.length) * 5 - i * 5 + 5, left: (rest.length > 4 ? 4 : rest.length) * 5 - i * 5 + 5, width: "100%", height: "100%", zIndex: 1 + i }} />
      ))}
      {rest.slice(4).map((id) => (
        <motion.div key={id} layoutId={id} transition={SPRING} className="absolute inset-0 rounded-3xl bg-paper opacity-0" />
      ))}
      <motion.div layoutId={lead} transition={SPRING} onClick={onOpen}
        className={cn("relative z-10 flex cursor-pointer overflow-visible rounded-3xl border bg-paper shadow-card transition-shadow hover:shadow-lift",
          look ? "border-danger-500/60" : "border-paper-line", pulse && "pulse-danger")}>
        <div className="relative w-[240px] shrink-0">
          <Illustrative img={card.image} className="h-full min-h-[200px] w-full rounded-l-3xl" />
          <span className="absolute left-3 top-3 rounded-full bg-paper/95 px-3 py-1 font-display text-lg font-semibold text-accent-700 shadow-card">#{card.rank}</span>
        </div>
        <div className="min-w-0 flex-1 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="font-display text-[26px] font-semibold leading-tight text-accent-700">{card.name}</div>
              <div className="mt-1.5 flex flex-wrap items-center gap-x-2 text-sm text-ink-mute">
                <Stars n={card.star} /><span>·</span><span>{Math.round(metresAway).toLocaleString("en-IN")} m</span><span>·</span><span>{card.district}</span>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <SupplierAvatars names={card.suppliers} />
                {look && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-danger-500 px-2.5 py-1 text-[13px] font-bold text-white">
                    <AlertTriangle className="h-3.5 w-3.5" />Looks the same, isn't
                  </span>
                )}
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-mute">From</div>
              <div className="font-display text-[26px] font-semibold tabular-nums leading-tight">{inr(card.from_price)}</div>
              {card.true_price_from != null && (<>
                <div className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-ink-mute">True Price from</div>
                <div className="font-display text-[26px] font-semibold tabular-nums leading-tight text-sun-600">{inr(card.true_price_from)}</div>
              </>)}
            </div>
          </div>
          {look && (
            <div className="mt-3 rounded-2xl bg-danger-50 px-3.5 py-2.5 text-sm text-danger-700">
              Kept apart from <b>{look.other_name}</b>: {look.reasons.map((r) => r.text).join(" · ")}
            </div>
          )}
          <div className="mt-3 border-t border-paper-line pt-3">
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-mute">Why ranked here</div>
            <WhyChips why={card.why} score={card.score} />
          </div>
        </div>
      </motion.div>
    </div>
  );
}
