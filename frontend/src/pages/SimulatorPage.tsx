import { useCallback, useEffect, useState } from "react";
import type { SimParams, SimResult } from "@/contracts";
import { inr } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { ErrorState, Loading } from "@/components/States";
import { cn } from "@/components/ui";
import { MatcherQuality } from "@/components/MatcherQuality";
import { PageHeader } from "@/components/PageHeader";

const DEFAULTS: SimParams = { sessions: 50000, price_sensitivity: 0.6, dup_abandon: 0.08, failure_scale: 1.0, seed: 7 };
// Pessimistic: agents ignore duplicates, chase sticker hard, suppliers fail half as often as profiled
const PESSIMISTIC: SimParams = { ...DEFAULTS, price_sensitivity: 0.9, dup_abandon: 0.02, failure_scale: 0.5 };

const SLIDERS: { key: keyof SimParams; label: string; min: number; max: number; step: number; fmt: (v: number) => string; help: string }[] = [
  { key: "price_sensitivity", label: "Agent price sensitivity", min: 0, max: 1, step: 0.05, fmt: (v) => v.toFixed(2), help: "How hard agents chase the lowest sticker" },
  { key: "dup_abandon", label: "Abandonment from duplicates", min: 0, max: 0.2, step: 0.01, fmt: (v) => `${(v * 100).toFixed(0)}%`, help: "Extra drop-off when a page is full of the same hotel" },
  { key: "failure_scale", label: "Supplier failure rates", min: 0.25, max: 2, step: 0.05, fmt: (v) => `${v.toFixed(2)}×`, help: "Multiplier on the profiled failure rates" },
];

export default function SimulatorPage() {
  const [p, setP] = useState<SimParams>(DEFAULTS);
  const [res, setRes] = useState<SimResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const preset = p.price_sensitivity === PESSIMISTIC.price_sensitivity && p.dup_abandon === PESSIMISTIC.dup_abandon && p.failure_scale === PESSIMISTIC.failure_scale;

  useEffect(() => {
    const t = setTimeout(async () => {
      try {
        const r = await fetch("/api/sim", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(p) });
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        setRes(await r.json()); setErr(null);
      } catch (e) { setErr((e as Error).message); }
    }, 120);
    return () => clearTimeout(t);
  }, [p]);
  usePresenterAction(useCallback(() => setP((cur) => (cur.failure_scale === PESSIMISTIC.failure_scale && cur.dup_abandon === PESSIMISTIC.dup_abandon ? DEFAULTS : PESSIMISTIC)), []));

  return (
    <div className="mx-auto max-w-[1400px] px-8 pb-20 pt-8">
      <PageHeader title="Does it hold up?"
        subtitle={<>A simulation of {p.sessions.toLocaleString("en-IN")} agent sessions, with assumptions you can change, then how accurately duplicates are found on data the model never trained on. Simulated, and labelled so.</>} />
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[360px_1fr]">
        <div className="h-fit rounded-2xl border border-paper-line bg-paper p-5">
          {SLIDERS.map((s) => (
            <label key={s.key} className="mb-5 block">
              <div className="flex justify-between text-sm font-medium"><span>{s.label}</span><span className="tabular-nums text-accent-700">{s.fmt(p[s.key] as number)}</span></div>
              <input type="range" min={s.min} max={s.max} step={s.step} value={p[s.key] as number}
                onChange={(e) => setP({ ...p, [s.key]: Number(e.target.value) })} className="mt-2 w-full accent-[#163a6b]" />
              <div className="text-sm text-ink-mute">{s.help}</div>
            </label>
          ))}
          <div className="flex gap-2">
            <button onClick={() => setP(PESSIMISTIC)} className={cn("flex-1 rounded-full border px-4 py-2 text-sm font-medium", preset ? "border-danger-500 bg-danger-50 text-danger-700" : "border-paper-line text-ink-soft hover:border-danger-500")}>Pessimistic assumptions</button>
            <button onClick={() => setP(DEFAULTS)} className="rounded-full px-4 py-2 text-sm font-medium text-ink-soft hover:bg-paper-warm">Reset</button>
          </div>
        </div>
        <div className="rounded-2xl border border-paper-line bg-paper p-6">
          {err && <ErrorState error={err} />}
          {!res && !err && <Loading what="Simulating sessions" />}
          {res && (
            <>
              {res.note && <div className="mb-4 rounded-lg bg-warn-50 px-3 py-2 text-sm font-semibold text-warn-500">{res.note}</div>}
              <div className="grid grid-cols-2 gap-6">
                <Big label="Confirmed bookings per search" value={`${res.lift_bookings_pct > 0 ? "+" : ""}${res.lift_bookings_pct.toFixed(1)}%`} good={res.lift_bookings_pct > 0} />
                <Big label="Failed-at-booking rate" value={`−${res.failed_reduction_pct.toFixed(1)}%`} good={res.failed_reduction_pct > 0} />
              </div>
              <div className="mt-6 space-y-4">
                {[["bookings_per_search", "Bookings per search", (v: number) => v.toFixed(3)], ["failed_at_booking", "Failed at booking", (v: number) => `${(v * 100).toFixed(1)}%`],
                  ["avg_true_cost", "Avg True Price paid", (v: number) => inr(v)]].map(([k, label, fmt]) => {
                  const key = k as "bookings_per_search" | "failed_at_booking" | "avg_true_cost";
                  const max = Math.max(...res.arms.map((a) => a[key]));
                  return (
                    <div key={key}>
                      <div className="mb-1 font-semibold">{label as string}</div>
                      {res.arms.map((a) => (
                        <div key={a.arm} className="mb-1 flex items-center gap-3">
                          <span className="w-24 text-sm text-ink-mute">{a.arm === "today" ? "Today" : "With Remix"}</span>
                          <div className="h-7 flex-1 rounded-full bg-paper-warm">
                            <div className={cn("h-7 rounded-full transition-all duration-500", a.arm === "today" ? "bg-sky-300" : "bg-accent-700")} style={{ width: `${(100 * a[key]) / max}%` }} />
                          </div>
                          <span className="w-24 text-right font-mono tabular-nums">{(fmt as (v: number) => string)(a[key])}</span>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
              {res.remix && (
                <div className="mt-6 rounded-2xl border border-sun-500/50 bg-sun-50/40 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-[16px] font-semibold text-ink">Remix, per 1,000 tour searches</div>
                    <span className="rounded-full bg-warn-50 px-2 py-0.5 text-xs font-bold uppercase text-warn-500">simulated</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-4">
                    <Small k="Searches a publishable Remix answers" v={`${(res.remix.matched_share * 100).toFixed(1)}%`} />
                    <Small k="Remix bookings" v={res.remix.bookings_per_1000_searches.toFixed(1)} />
                    <Small k="TBO margin" v={inr(res.remix.tbo_margin_per_1000_searches)} />
                    <Small k="Agents save" v={inr(res.remix.agent_saving_per_1000_searches)} />
                  </div>
                  <div className="mt-2 text-xs text-ink-mute">{res.remix.publishable_remixes} publishable Remixes{res.remix.pessimistic ? " under the pessimistic preset" : ""}; {inr(res.remix.avg_margin_per_booking)} average margin per Remix booking. {res.remix.note}</div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
      <div className="mt-6"><MatcherQuality /></div>
    </div>
  );
}

function Small({ k, v }: { k: string; v: string }) {
  return <div className="rounded-xl bg-paper px-3 py-2"><div className="text-[11px] uppercase text-ink-mute">{k}</div><div className="text-lg font-semibold tabular-nums">{v}</div></div>;
}

function Big({ label, value, good }: { label: string; value: string; good: boolean }) {
  return (
    <div>
      <div className={cn("font-display text-4xl font-semibold tabular-nums", good ? "text-accent-700" : "text-danger-700")}>{value}</div>
      <div className="mt-1 text-ink-mute">{label}</div>
    </div>
  );
}
