import { LayoutGroup, motion } from "framer-motion";
import { Layers, Star } from "lucide-react";
import { useCallback, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { ActivityListing, ActivitySearch, ActivityVariant, DnaKey, RemixOverview } from "@/contracts";
import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { Empty, ErrorState, Loading } from "@/components/States";
import { AnimatedNumber, Illustrative, Segmented, SupplierBadge, Tip, cn } from "@/components/ui";
import { WhyChips } from "@/components/WhyChips";
import { DEFAULT_QUERY, QUERIES } from "@/lib/city";
import { PageHeader } from "@/components/PageHeader";

const SEG_COLOR: Record<DnaKey, string> = {
  pickup: "bg-sky-100 text-accent-900", meals: "bg-sand-100 text-ink", duration: "bg-sun-50 text-sun-700",
  stops: "bg-ok-50 text-ok-700", access: "bg-danger-50 text-danger-700", option: "bg-accent-50 text-accent-700",
  cancel: "bg-paper-warm text-ink-soft", group: "bg-paper-warm text-ink-soft",
};
const SPRING = { type: "tween", ease: [0.22, 1, 0.36, 1], duration: 0.55 } as const;

export default function SightseeingPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? DEFAULT_QUERY;
  const view = params.get("view") === "today" ? "today" : "samesame";
  const res = useApi<ActivitySearch>(`/api/activities/search?q=${encodeURIComponent(q)}`);
  const set = useCallback((k: string, v: string) => { const n = new URLSearchParams(params); n.set(k, v); setParams(n, { replace: true }); }, [params, setParams]);
  usePresenterAction(useCallback(() => set("view", view === "today" ? "samesame" : "today"), [view, set]));

  return (
    <div className="mx-auto max-w-[1400px] px-8 pb-10 pt-8">
      <PageHeader title="Tours, grouped into what's really on sale"
        subtitle="Suppliers list the same tour many times with different words. Remix reads each listing and groups identical ones, keeping real differences (pickup, meals, time slot, cancellation) visible."
        right={<Segmented size="md" value={view} onChange={(v) => set("view", v)}
          options={[{ value: "samesame", label: "Grouped by product" }, { value: "today", label: "As suppliers list them" }]} />}>
        <div className="flex flex-wrap gap-1">
          {QUERIES.map((x) => (
            <button key={x.q} onClick={() => set("q", x.q)}
              className={cn("rounded-full px-4 py-1.5 text-sm font-medium transition-colors", q === x.q ? "bg-ink text-white" : "text-ink-soft hover:bg-paper")}>{x.label}</button>
          ))}
        </div>
      </PageHeader>
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
        <Tip content={<>{about.text} (Wikipedia, {about.title} · {about.license})</>} className="mt-3">
          <span className="cursor-help text-sm text-ink-mute underline decoration-dotted">About this attraction</span>
        </Tip>
      )}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="text-[15px] text-ink-soft">
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
                  className={cn("rounded-full border px-3 py-1.5 text-sm", on ? "border-accent-700 bg-accent-700 text-white" : "border-paper-line bg-paper text-ink-soft hover:border-accent-500")}>
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
              <motion.div key={l.listing_id} layoutId={l.listing_id} transition={SPRING} className="flex overflow-hidden rounded-2xl border border-paper-line bg-paper">
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
            <RemixCards attraction={data.groups[0]?.group_id} />
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
  return <span className="flex items-center gap-0.5 text-sm text-ink-mute"><Star className="h-3.5 w-3.5 fill-sun-500 text-sun-500" />{r.toFixed(1)}</span>;
}

function VariantRow({ v }: { v: ActivityVariant }) {
  return (
    <motion.div layout transition={SPRING} className="flex overflow-hidden rounded-2xl border border-paper-line bg-paper">
      <div className="relative hidden w-[200px] shrink-0 md:block">
        <Illustrative img={v.members.find((m) => m.image)?.image} className="h-full min-h-[200px] w-full" label={false} />
        <span className="absolute left-3 top-3 rounded-full bg-paper/95 px-2.5 py-0.5 text-sm font-semibold text-ink shadow-card">#{v.rank}</span>
      </div>
      <div className="min-w-0 flex-1 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[20px] font-semibold text-ink">{v.name}</div>
          <div className="flex items-center gap-1.5 text-sm text-ink-mute"><Layers className="h-4 w-4" />{v.members.length} identical listing{v.members.length === 1 ? "" : "s"} merged</div>
        </div>
        <div className="text-right">
          <div className="text-xs text-ink-mute">From</div>
          <div className="text-[20px] font-semibold tabular-nums leading-tight">{inr(v.price_from)}<span className="text-sm font-normal text-ink-mute"> pp</span></div>
          {v.true_price_from != null && <div className="mt-1 text-sm font-semibold text-sun-600">True Price {inr(v.true_price_from)} for 2</div>}
        </div>
      </div>

      <div className="mt-3 flex overflow-hidden rounded-2xl">
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
            className="flex items-center gap-2 rounded-full border border-paper-line px-3 py-1">
            <SupplierBadge name={m.supplier} small />
            <Tip content={m.title}><span className="max-w-[260px] truncate text-sm text-ink-soft">{m.title}</span></Tip>
            <b className="tabular-nums">{inr(m.price)}</b>
          </motion.div>
        ))}
      </div>
      <WhyChips why={v.why} score={v.score} className="mt-3" />
      </div>
    </motion.div>
  );
}

/** TBO's own Remix of this attraction, ranked above the packages when it passes every guardrail. */
function RemixCards({ attraction }: { attraction?: string }) {
  const o = useApi<RemixOverview>("/api/remix");
  if (o.status !== "ready" || !attraction) return null;
  const mine = o.data.items.filter((r) => r.attraction_id === attraction && r.status === "ready");
  return (
    <>
      {mine.map((r) => (
        <Link key={r.variant_id} to={`/remix?v=${r.variant_id}`}
          className="flex items-center gap-5 rounded-2xl border border-sun-500/60 bg-sun-50/40 p-5 hover:bg-sun-50">
          <span className="flex items-center gap-1.5 rounded-full bg-sun-500 px-2.5 py-0.5 text-xs font-semibold text-white"><Sparkles className="h-3.5 w-3.5" />TBO Remix</span>
          <div className="min-w-0 flex-1">
            <div className="text-[18px] font-semibold text-ink">{r.target_dna.pickup !== "No transfer" ? r.target_dna.pickup : r.target_dna.meals} · built from {r.parts} parts by {r.suppliers?.length} suppliers</div>
            <div className="text-sm text-ink-soft">The SAME product as the package, cheaper on True Price: agent saves {inr(r.agent_saving_inr ?? 0)} ({((r.agent_saving ?? 0) * 100).toFixed(1)}%), TBO keeps {((r.margin ?? 0) * 100).toFixed(1)}%.</div>
          </div>
          <div className="text-right"><div className="text-xs uppercase text-ink-mute">True Price for 2</div>
            <div className="text-xl font-semibold tabular-nums text-sun-600">{inr(r.agent_true_price ?? 0)}</div>
            <div className="text-sm text-ink-mute line-through">{inr(r.packaged_true_price ?? 0)} package</div></div>
        </Link>
      ))}
    </>
  );
}
