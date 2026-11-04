import { LayoutGroup, motion } from "framer-motion";
import { Dna, Layers, Star } from "lucide-react";
import { useCallback, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { ActivityListing, ActivitySearch, ActivityVariant, DnaKey } from "@/contracts";
import { inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { Empty, ErrorState, Loading } from "@/components/States";
import { AnimatedNumber, Illustrative, Segmented, SupplierBadge, Tip, cn } from "@/components/ui";
import { WhyChips } from "@/components/WhyChips";

const QUERIES = [{ q: "floating market", label: "Floating Market" }, { q: "grand palace", label: "Grand Palace" }, { q: "skywalk", label: "Rooftop SkyWalk" }];
const SEG_COLOR: Record<DnaKey, string> = {
  pickup: "bg-sky-100 text-sky-900", meals: "bg-amber-100 text-amber-900", duration: "bg-violet-100 text-violet-900",
  stops: "bg-emerald-100 text-emerald-900", access: "bg-rose-100 text-rose-900", option: "bg-indigo-100 text-indigo-900",
  cancel: "bg-slate-100 text-slate-800", group: "bg-slate-100 text-slate-800",
};
const SPRING = { type: "tween", ease: [0.22, 1, 0.36, 1], duration: 0.55 } as const;

export default function SightseeingPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "floating market";
  const view = params.get("view") === "samesame" ? "samesame" : "today";
  const res = useApi<ActivitySearch>(`/api/activities/search?q=${encodeURIComponent(q)}`);
  const set = useCallback((k: string, v: string) => { const n = new URLSearchParams(params); n.set(k, v); setParams(n, { replace: true }); }, [params, setParams]);
  usePresenterAction(useCallback(() => set("view", view === "today" ? "samesame" : "today"), [view, set]));

  return (
    <div className="mx-auto max-w-[1500px] px-8 pb-20 pt-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Sightseeing in Bangkok</h1>
          <div className="mt-3 flex gap-2">
            {QUERIES.map((x) => (
              <button key={x.q} onClick={() => set("q", x.q)}
                className={cn("rounded-full border px-4 py-1.5 font-medium", q === x.q ? "border-ink bg-ink text-white" : "border-paper-line bg-paper text-ink-soft hover:border-ink-mute")}>{x.label}</button>
            ))}
          </div>
        </div>
        <Segmented value={view} onChange={(v) => set("view", v)}
          options={[{ value: "today", label: "Today" }, { value: "samesame", label: <span className="flex items-center gap-2"><Dna className="h-5 w-5" />Variant DNA</span> }]} />
      </div>
      {res.status === "loading" && <Loading what="Reading supplier tour text" />}
      {res.status === "error" && <ErrorState error={res.error} onRetry={res.reload} />}
      {res.status === "ready" && (res.data.raw_count === 0 ? <Empty title="No tours found" /> : <Results data={res.data} view={view} />)}
    </div>
  );
}

function Results({ data, view }: { data: ActivitySearch; view: "today" | "samesame" }) {
  const [active, setActive] = useState<string[]>([]);
  const variants = data.groups.flatMap((g) => g.variants);
  const visibleVariants = variants.filter((v) => active.every((k) => v.dna_tags.includes(k)));
  const visibleToday = data.today.filter((l) => active.every((k) => l.dna_tags.includes(k)));
  const filters = data.filters.filter((f) => f.count > 0 || f.today_count > 0);
  const about = data.groups[0]?.description;
  return (
    <>
      {about?.text && (
        <p className="mt-4 max-w-[1100px] text-[15px] leading-relaxed text-ink-soft">
          {about.text} <span className="text-xs text-ink-mute">(Wikipedia, <a className="underline" href={about.source} target="_blank" rel="noreferrer">{about.title}</a> · {about.license})</span>
        </p>
      )}
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-paper-line bg-paper px-5 py-3">
        <div className="text-lg">
          {view === "today"
            ? <><b>{data.raw_count}</b> "{data.query}" listings from 6 suppliers <span className="text-ink-mute">· which are the same?</span></>
            : <><b>{data.raw_count}</b> listings → <b className="text-accent-700"><AnimatedNumber value={variants.length} /> variants</b> of one product <span className="text-ink-mute">· SAME twins grouped, differences kept</span></>}
        </div>
        <div className="flex flex-wrap gap-2">
          {filters.map((f) => {
            const on = active.includes(f.key);
            return (
              <Tip key={f.key} side="bottom" content={<>Variant DNA: <b>{f.count}</b> of {data.raw_count} listings really have {f.label.toLowerCase()}.<br />Keyword search on supplier text finds <b>{f.today_count}</b>.</>}>
                <button onClick={() => setActive((a) => on ? a.filter((k) => k !== f.key) : [...a, f.key])}
                  className={cn("rounded-full border px-3 py-1.5 text-[15px] font-medium", on ? "border-accent-600 bg-accent-600 text-white" : "border-paper-line bg-paper text-ink-soft hover:border-accent-500")}>
                  {f.label} <span className={cn("ml-1 tabular-nums", on ? "text-white/80" : "text-ink-mute")}>{view === "today" ? f.today_count : f.count}</span>
                </button>
              </Tip>
            );
          })}
        </div>
      </div>

      <LayoutGroup>
        {view === "today" ? (
          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {visibleToday.length === 0 && <Empty title="Keyword search found nothing">Supplier text says "PVT car ex-hotel" or "collection from your hotel", not "pickup".</Empty>}
            {visibleToday.map((l) => (
              <motion.div key={l.listing_id} layoutId={l.listing_id} transition={SPRING} className="flex overflow-hidden rounded-xl border border-paper-line bg-paper shadow-sm">
                <Illustrative img={l.image} className="w-[104px] shrink-0" label={false} />
                <div className="min-w-0 flex-1 p-3">
                  <div className="line-clamp-2 font-semibold leading-snug">{l.title}</div>
                  <div className="mt-2 flex items-center justify-between">
                    <SupplierBadge name={l.supplier} small />
                    <span className="flex items-center gap-2"><Rating r={l.rating} /><b className="tabular-nums">{inr(l.price)}</b></span>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        ) : (
          <div className="mt-5 space-y-5">
            {visibleVariants.length === 0 && <Empty title="No variant has all of these">Remove a filter.</Empty>}
            {visibleVariants.map((v) => <VariantRow key={v.variant_id} v={v} />)}
          </div>
        )}
      </LayoutGroup>
      <p className="mt-6 text-sm text-ink-mute">Prices per person; True Price for 2 adults including hotel pickup if missing. Supplier data is synthetic; images are illustrative.</p>
    </>
  );
}

function Rating({ r }: { r?: number | null }) {
  if (!r) return null;
  return <span className="flex items-center gap-0.5 text-sm text-ink-mute"><Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />{r.toFixed(1)}</span>;
}

function VariantRow({ v }: { v: ActivityVariant }) {
  return (
    <motion.div layout transition={SPRING} className="rounded-2xl border border-paper-line bg-paper p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-ink-mute"><Layers className="h-4 w-4" />#{v.rank} · {v.members.length} SAME listings</div>
          <div className="text-2xl font-bold">{v.name}</div>
        </div>
        <div className="text-right">
          <div className="text-sm text-ink-mute">from</div>
          <div className="text-2xl font-bold tabular-nums">{inr(v.price_from)}<span className="text-base font-normal text-ink-mute"> pp</span></div>
          {v.true_price_from != null && <div className="text-sm font-semibold text-accent-700">True Price {inr(v.true_price_from)} for 2</div>}
        </div>
      </div>

      <div className="mt-3 flex overflow-hidden rounded-xl">
        {v.dna.map((s) => (
          <Tip key={s.key} content={s.differs ? <>{s.label} differs between variants: this is what you are choosing.</> : <>{s.label} is identical across all variants.</>}>
            <div className={cn("flex min-w-0 flex-1 flex-col justify-center border-r-2 border-paper px-3 py-2 last:border-0", SEG_COLOR[s.key],
              s.differs ? "dna-glow relative z-10" : "opacity-55")}>
              <div className="text-[11px] font-bold uppercase tracking-wider opacity-70">{s.label}</div>
              <div className={cn("truncate text-[15px] leading-tight", s.differs && "font-bold")}>{s.value}</div>
            </div>
          </Tip>
        ))}
      </div>
      {v.diff_sentence && <div className="mt-2 text-[15px] text-ink-soft">{v.diff_sentence} <span className="text-xs text-ink-mute">({v.diff_source === "llm" ? "LLM" : "template"})</span></div>}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {v.members.map((m: ActivityListing) => (
          <motion.div key={m.listing_id} layoutId={m.listing_id} transition={SPRING}
            className="flex items-center gap-2 rounded-lg border border-paper-line bg-paper-warm px-2.5 py-1.5">
            <SupplierBadge name={m.supplier} small />
            <Tip content={m.title}><span className="max-w-[260px] truncate text-sm text-ink-soft">{m.title}</span></Tip>
            <b className="tabular-nums">{inr(m.price)}</b>
          </motion.div>
        ))}
      </div>
      <WhyChips why={v.why} score={v.score} className="mt-3" />
    </motion.div>
  );
}
