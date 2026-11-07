import { Search, Sparkles } from "lucide-react";
import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import type { GapList, RemixResult } from "@/contracts";
import { inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { CITY } from "@/lib/city";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState, Loading } from "@/components/States";
import { cn } from "@/components/ui";
import { BookRemix, PartRow, SameCheck, Timeline, pct } from "@/pages/RemixStudioPage";

/** Products agents search for that no supplier sells as one product, assembled from parts. */
export default function GapsPage() {
  const res = useApi<GapList>("/api/remix/gaps");
  const [params, setParams] = useSearchParams();
  const ready = res.status === "ready" ? res.data.items.filter((r) => r.status === "ready") : [];
  const g = params.get("g") ?? (res.status === "ready" ? res.data.demo : null);
  const pick = useCallback((id: string) => { const n = new URLSearchParams(params); n.set("g", id); setParams(n, { replace: true }); }, [params, setParams]);
  usePresenterAction(useCallback(() => {
    if (!ready.length) return;
    const i = ready.findIndex((r) => r.variant_id === g);
    pick(ready[(i + 1) % ready.length].variant_id);
  }, [ready, g, pick]));
  if (res.status === "loading") return <Loading what="Reading agents' searches" />;
  if (res.status === "error") return <ErrorState error={res.error} onRetry={res.reload} />;
  const items = res.data.items;
  const sel = items.find((r) => r.variant_id === g) ?? ready[0];
  const c = res.data.counts;
  return (
    <div className="mx-auto max-w-[1560px] px-8 pb-10 pt-6">
      <PageHeader eyebrow={`Gap finder · ${CITY}`} title={<>Products agents want <span className="italic">that nobody sells.</span></>}
        subtitle="Agents' searches ask for combinations no supplier packages. Remix builds them from parts, with the same SAME rule and the same guardrails, priced against what the agent does today: buy the ticket and book the cars themselves."
        right={<div className="rounded-2xl bg-paper/90 px-5 py-3 text-sm shadow-card"><b className="text-lg">{c.gaps}</b> searched-for gaps · <b className="text-lg text-sun-600">{c.ready ?? 0}</b> pass every guardrail
          <div className="text-xs text-ink-mute">{c.blocked ?? 0} blocked, {c.not_remixable ?? 0} can't be assembled. Searches are synthetic (DATA.md).</div></div>} />
      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-[400px_minmax(0,1fr)]">
        <ul className="max-h-[1100px] space-y-2 overflow-auto pr-1">
          {items.map((r) => (
            <li key={r.variant_id}>
              <button onClick={() => pick(r.variant_id)} className={cn("w-full rounded-2xl border px-4 py-3 text-left shadow-card transition-colors",
                sel?.variant_id === r.variant_id ? "border-accent-700 bg-accent-700 text-white" : "border-paper-line bg-paper hover:border-accent-500", r.status !== "ready" && sel?.variant_id !== r.variant_id && "opacity-70")}>
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-semibold">{r.attraction.split(" (")[0].split(",")[0]}</span>
                  <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold uppercase", r.status === "ready" ? "bg-sun-500 text-white" : "bg-sand-200 text-ink-soft")}>
                    {r.status === "ready" ? "new product" : r.status === "blocked" ? "blocked" : "can't build"}</span>
                </div>
                <div className="mt-0.5 truncate text-sm opacity-80">{r.name}</div>
                <div className="mt-1 flex items-center gap-1.5 text-xs opacity-80"><Search className="h-3.5 w-3.5" />{r.demand} searches in 90 days · 0 packages</div>
              </button>
            </li>
          ))}
        </ul>
        {sel && <GapView r={sel} />}
      </div>
    </div>
  );
}

function GapView({ r }: { r: RemixResult }) {
  return (
    <div className="min-w-0">
      <section className={cn("relative rounded-3xl border-2 bg-paper p-6 shadow-card", r.status === "ready" ? "border-sun-500" : "border-paper-line")}>
        <span className={cn("absolute -top-3 left-6 flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide shadow-card",
          r.status === "ready" ? "bg-sun-500 text-white" : "bg-sand-200 text-ink-soft")}><Sparkles className="h-3.5 w-3.5" />New product: nobody sells this</span>
        <h2 className="mt-1 text-[30px] font-semibold leading-tight text-accent-700">{r.attraction}</h2>
        <div className="text-lg text-ink-soft">{r.name}</div>
        <div className="mt-2 text-sm text-ink-mute">Asked for in <b className="text-ink">{r.demand}</b> agent searches in the last 90 days. No supplier sells it as one product.</div>
        <div className={cn("mt-3 rounded-xl px-4 py-2 text-[15px] font-semibold", r.status === "ready" ? "bg-ok-50 text-ok-700" : "bg-danger-50 text-danger-700")}>{r.reasons.join("; ")}</div>
        {r.parts && (
          <>
            <ul className="mt-4 space-y-2">{r.parts.map((p) => <PartRow key={p.leg} p={p} />)}</ul>
            <Timeline r={r} />
            <SameCheck r={r} />
          </>
        )}
      </section>
      {r.diy && r.sell != null && (
        <section className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="rounded-3xl border border-paper-line bg-paper p-5 shadow-card">
            <div className="text-xs uppercase text-ink-mute">What the agent does today</div>
            <div className="font-display text-3xl font-semibold tabular-nums">{inr(r.diy.total)}</div>
            <div className="mt-1 text-sm text-ink-soft">Ticket {inr(r.diy.ticket)} ({r.diy.ticket_from}) + two transfers booked separately {inr(r.diy.transfers)} (True Price: the agent carries their risk) + {inr(r.diy.friction)} for two extra bookings to manage</div>
          </div>
          <div className="rounded-3xl border-2 border-sun-500 bg-paper p-5 shadow-card">
            <div className="text-xs uppercase text-ink-mute">TBO Remix, one product</div>
            <div className="font-display text-3xl font-semibold tabular-nums text-sun-600">{inr(r.agent_true_price!.total)}</div>
            <div className="mt-1 text-sm text-ink-soft">Sell {inr(r.sell)} + cancellation risk under "{r.cancel}". One booking, one Promise ({pct(r.promise)}), TBO runs the failover.</div>
          </div>
          <div className="rounded-3xl border border-paper-line bg-paper p-5 shadow-card">
            <div className="text-xs uppercase text-ink-mute">Split</div>
            <div className="text-lg font-semibold">Agent saves {inr(r.agent_saving_inr ?? 0)} ({pct(r.agent_saving)})</div>
            <div className="text-lg font-semibold">TBO keeps {inr(r.margin_inr ?? 0)} ({pct(r.margin)})</div>
            <div className="mt-1 text-sm text-ink-mute">Same guardrails as every Remix; published only after approval in Ops.</div>
          </div>
        </section>
      )}
      {r.parts && r.status === "ready" && <BookRemix r={r} active={false} demoSeed={1} seedNote="Seed 1, the first tried." withStats={false} />}
    </div>
  );
}
