import { ArrowRight, ChevronDown, Search } from "lucide-react";
import { useCallback, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { GapList, RemixResult } from "@/contracts";
import { inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { PageHeader } from "@/components/PageHeader";
import { Disclosure } from "@/components/Disclosure";
import { ErrorState, Loading } from "@/components/States";
import { cn } from "@/components/ui";
import { BookRemix, PartRow, SameCheck, Timeline, pct } from "@/pages/RemixStudioPage";

const short = (a: string) => a.split(" (")[0].split(",")[0];

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
  return (
    <div className="mx-auto max-w-[1400px] px-8 pb-10 pt-8">
      <PageHeader title="New products agents ask for"
        subtitle="Agents search for combinations that no supplier sells as one product, like a ticket with a private pickup. Canon builds them from parts, priced against what the agent does today: book each piece separately." />
      <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-[300px_minmax(0,1fr)]">
        <GapList items={items} active={sel?.variant_id ?? null} onPick={pick} total={res.data.counts.gaps} />
        {sel && <GapView r={sel} />}
      </div>
    </div>
  );
}

function GapList({ items, active, onPick, total }: { items: RemixResult[]; active: string | null; onPick: (id: string) => void; total: number }) {
  const ready = items.filter((r) => r.status === "ready");
  const rest = items.filter((r) => r.status !== "ready");
  const [showRest, setShowRest] = useState(rest.some((r) => r.variant_id === active));
  const row = (r: RemixResult) => (
    <li key={r.variant_id}>
      <button onClick={() => onPick(r.variant_id)} className={cn("flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors",
        active === r.variant_id ? "bg-accent-700 text-white" : "hover:bg-paper")}>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[15px] font-medium">{short(r.attraction)}</span>
          <span className={cn("block truncate text-sm", active === r.variant_id ? "text-white/75" : "text-ink-mute")}>{r.name}</span>
        </span>
        <span className={cn("flex items-center gap-1 text-xs tabular-nums", active === r.variant_id ? "text-white/80" : "text-ink-mute")}><Search className="h-3 w-3" />{r.demand}</span>
      </button>
    </li>
  );
  return (
    <aside className="lg:sticky lg:top-[132px] lg:self-start">
      <div className="px-3 text-xs font-semibold uppercase tracking-wide text-ink-mute">Ready to sell · {ready.length}</div>
      <ul className="mt-2 max-h-[520px] space-y-0.5 overflow-auto">{ready.map(row)}</ul>
      <button onClick={() => setShowRest(!showRest)} className="mt-4 flex w-full items-center justify-between px-3 text-xs font-semibold uppercase tracking-wide text-ink-mute hover:text-ink">
        Not offered · {rest.length}<ChevronDown className={cn("h-4 w-4 transition-transform", showRest && "rotate-180")} />
      </button>
      {showRest && <ul className="mt-2 max-h-[420px] space-y-0.5 overflow-auto">{rest.map(row)}</ul>}
      <p className="mt-5 px-3 text-xs leading-relaxed text-ink-mute">{total} combinations searched for in the last 90 days that nobody sells. The number is how many searches asked for it. Searches are synthetic.</p>
    </aside>
  );
}

function GapView({ r }: { r: RemixResult }) {
  const ok = r.status === "ready";
  return (
    <div className="min-w-0 space-y-4">
      <div>
        <span className={cn("rounded-full px-3 py-1 text-xs font-semibold", ok ? "bg-ok-50 text-ok-700" : "bg-danger-50 text-danger-700")}>
          {ok ? "New product · waiting for approval in Review" : r.status === "blocked" ? "Not offered: it breaks a publish rule" : "Can't be built from parts"}</span>
        <h2 className="mt-3 text-[34px] leading-tight text-ink">{short(r.attraction)}</h2>
        <div className="text-lg text-ink-mute">{r.name} · asked for in {r.demand} searches, sold by no supplier</div>
      </div>
      {r.diy && r.sell != null ? (
        <section className="rounded-3xl border border-paper-line bg-paper p-6 shadow-card">
          <div className="grid grid-cols-1 items-center gap-6 md:grid-cols-[1fr_auto_1fr]">
            <div>
              <div className="text-sm text-ink-mute">The agent books each piece today</div>
              <div className="font-display text-[34px] font-semibold tabular-nums text-ink-mute line-through decoration-1">{inr(r.diy.total)}</div>
              <div className="text-sm text-ink-mute">ticket + two cars + two extra bookings to manage</div>
            </div>
            <ArrowRight className="hidden h-6 w-6 text-ink-mute md:block" />
            <div>
              <div className="text-sm font-medium text-sun-600">TBO bundle · one booking</div>
              <div className="font-display text-[34px] font-semibold tabular-nums text-ink">{inr(r.agent_true_price!.total)}</div>
              <div className="text-sm text-ink-mute">sold to the agent at {inr(r.sell)} for 2</div>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-3 gap-3 border-t border-paper-line pt-5">
            <M label="Agent saves" value={inr(r.agent_saving_inr ?? 0)} sub={pct(r.agent_saving)} tone="text-ok-700" />
            <M label="TBO keeps" value={inr(r.margin_inr ?? 0)} sub={`${pct(r.margin)} margin`} tone="text-accent-700" />
            <M label="Books first time" value={pct(r.promise)} sub={`cancel: ${r.cancel}`} />
          </div>
          {!ok && <div className="mt-4 rounded-xl bg-paper-warm px-4 py-3 text-sm text-ink-soft">{r.reasons.join("; ")}.</div>}
        </section>
      ) : (
        <section className="rounded-3xl border border-paper-line bg-paper p-6 text-ink-soft shadow-card">{r.reasons.join("; ")}.</section>
      )}
      {r.parts && (
        <section className="rounded-3xl border border-paper-line bg-paper p-6">
          <h3 className="text-[16px] font-semibold text-ink">What's in it</h3>
          <ul className="mt-3 divide-y divide-paper-line">{r.parts.map((p) => <PartRow key={p.leg} p={p} />)}</ul>
          {r.timeline && <Timeline r={r} />}
        </section>
      )}
      {r.parts && <Disclosure title="Is it exactly what agents asked for?" hint="Field by field against the search. No packaged product is the same, so this is new."><SameCheck r={r} /></Disclosure>}
      {r.parts && ok && <BookRemix r={r} active={false} demoSeed={1} seedNote="Seed 1, the first tried." withStats={false} />}
    </div>
  );
}

function M({ label, value, sub, tone = "text-ink" }: { label: string; value: string; sub?: string; tone?: string }) {
  return <div><div className="text-xs text-ink-mute">{label}</div><div className={cn("text-2xl font-semibold tabular-nums", tone)}>{value}</div>{sub && <div className="truncate text-xs text-ink-mute">{sub}</div>}</div>;
}
