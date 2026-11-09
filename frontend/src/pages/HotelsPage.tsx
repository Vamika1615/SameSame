import { LayoutGroup, motion } from "framer-motion";
import { AlertTriangle, Check, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { HotelCard, HotelSearch } from "@/contracts";
import { inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { OfflineMap, type MapLine, type Pin } from "@/components/OfflineMap";
import { Empty, ErrorState, Loading } from "@/components/States";
import { AnimatedNumber, Illustrative, Segmented, Stars, SupplierAvatars, SupplierBadge, Tip, cn, metres } from "@/components/ui";
import { PageHeader } from "@/components/PageHeader";
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
  return <>{p.area} · {d} · {p.nights} nights · {p.adults} adults{p.children ? ` + ${p.children}` : ""}{p.star_min ? ` · ${p.star_min}★ and up` : ""}{p.needs.length ? ` · client wants ${p.needs.join(", ")}` : ""}</>;
}

function FilterChips({ data, view, active, toggle }: { data: HotelSearch; view: View; active: string[]; toggle: (k: string) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {data.filters.map((f) => {
        const on = active.includes(f.key);
        return (
          <Tip key={f.key} side="bottom" content={<>Read from the listings: <b>{f.count}</b> have {f.label.toLowerCase()}.<br />A keyword search of supplier text finds only <b>{f.today_count}</b>.</>}>
            <button onClick={() => toggle(f.key)} className={cn("flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors",
              on ? "border-accent-700 bg-accent-700 text-white" : "border-paper-line bg-paper text-ink-soft hover:border-accent-500")}>
              {on && <Check className="h-3.5 w-3.5" />}{f.label}<span className={cn("tabular-nums", on ? "text-white/75" : "text-ink-mute")}>{view === "today" ? f.today_count : f.count}</span>
            </button>
          </Tip>
        );
      })}
    </div>
  );
}

function LookalikeAlert({ looks }: { looks: HotelCard[] }) {
  const [a] = looks;
  if (!a?.lookalike) return null;
  return (
    <button onClick={() => document.getElementById(`card-${a.cluster_id}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}
      className="w-full rounded-2xl border border-danger-500/30 bg-danger-50 p-4 text-left transition-shadow hover:shadow-card">
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
  const view: View = params.get("view") === "today" ? "today" : "samesame";
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
  const toggle = (k: string) => setActive((a) => a.includes(k) ? a.filter((x) => x !== k) : [...a, k]);
  return (
    <div className="mx-auto max-w-[1400px] px-8 pb-10 pt-8">
      <PageHeader title={view === "samesame" ? <>{c.unique_hotels} hotels <span className="text-ink-mute">from {c.raw_listings} supplier listings</span></> : <>{c.raw_listings} listings, as suppliers send them</>}
        subtitle={<SearchSummary data={data} />}
        right={<Segmented size="md" value={view} onChange={setView}
          options={[{ value: "samesame", label: "One card per hotel" }, { value: "today", label: "As suppliers list them" }]} />} />
      <div className="mt-4"><FilterChips data={data} view={view} active={active} toggle={toggle} /></div>
      {view === "today" && active.length > 0 && <div className="mt-2 text-sm text-sun-700">Suppliers write "BB NRF" or "Incl. ABF", never "breakfast", so a keyword filter misses most of them.</div>}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="min-w-0">
          <div className="mb-3 text-sm text-ink-mute">{view === "today" ? "Sorted by listed price." : <><b className="text-ink-soft"><AnimatedNumber value={c.duplicates_collapsed} /></b> duplicates merged · ranked by True Price, reliability and fit · hover <i>why</i> on a card</>}</div>
          <LayoutGroup>
            {cards.length === 0 && <Empty title="Nothing matches these filters">Remove a filter to see more hotels.</Empty>}
            <div className={cn("grid gap-4", view === "today" ? "grid-cols-1 2xl:grid-cols-2" : "grid-cols-1 gap-y-5")}>
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
          <div className="sticky top-[132px] space-y-4">
            {view === "samesame" && <LookalikeAlert looks={looks} />}
            <div className="overflow-hidden rounded-2xl border border-paper-line bg-paper">
              <OfflineMap pins={pins} lines={lines} highlight={hover} fitPins className="h-[calc(100vh-320px)] min-h-[380px]" />
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
        <motion.div key={id} layoutId={id} transition={SPRING} className="absolute rounded-2xl border border-paper-line bg-sand-100 shadow-sm"
          style={{ top: (rest.length > 4 ? 4 : rest.length) * 5 - i * 5 + 5, left: (rest.length > 4 ? 4 : rest.length) * 5 - i * 5 + 5, width: "100%", height: "100%", zIndex: 1 + i }} />
      ))}
      {rest.slice(4).map((id) => (
        <motion.div key={id} layoutId={id} transition={SPRING} className="absolute inset-0 rounded-3xl bg-paper opacity-0" />
      ))}
      <motion.div layoutId={lead} transition={SPRING} onClick={onOpen}
        className={cn("relative z-10 flex cursor-pointer overflow-visible rounded-2xl border bg-paper shadow-card transition-shadow hover:shadow-lift",
          look ? "border-danger-500/60" : "border-paper-line", pulse && "pulse-danger")}>
        <div className="relative w-[200px] shrink-0">
          <Illustrative img={card.image} className="h-full min-h-[170px] w-full rounded-l-2xl" label={false} />
          <span className="absolute left-3 top-3 rounded-full bg-paper/95 px-2.5 py-0.5 text-sm font-semibold text-ink shadow-card">#{card.rank}</span>
        </div>
        <div className="min-w-0 flex-1 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="text-[20px] font-semibold leading-tight text-ink">{card.name}</div>
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
              <div className="text-[20px] font-semibold tabular-nums leading-tight">{inr(card.from_price)}</div>
              {card.true_price_from != null && (<>
                <div className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-ink-mute">True Price from</div>
                <div className="text-[20px] font-semibold tabular-nums leading-tight text-sun-600">{inr(card.true_price_from)}</div>
              </>)}
            </div>
          </div>
          {look && (
            <div className="mt-3 rounded-2xl bg-danger-50 px-3.5 py-2.5 text-sm text-danger-700">
              Kept apart from <b>{look.other_name}</b>: {look.reasons.map((r) => r.text).join(" · ")}
            </div>
          )}
          <WhyChips why={card.why} score={card.score} className="mt-3" />
        </div>
      </motion.div>
    </div>
  );
}
