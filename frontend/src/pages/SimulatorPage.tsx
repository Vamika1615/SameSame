import { useCallback, useEffect, useState } from "react";
import type { SimParams, SimResult } from "@/contracts";
import { inr } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { ErrorState, Loading } from "@/components/States";
import { cn } from "@/components/ui";
import { MatcherQuality } from "@/components/MatcherQuality";

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
    <div className="mx-auto max-w-[1400px] px-8 pb-20 pt-6">
      <h1 className="text-3xl font-bold tracking-tight">Session simulator</h1>
      <p className="mt-1 text-ink-mute">{p.sessions.toLocaleString("en-IN")} simulated agent sessions: Today vs SameSame. The assumptions are yours to attack. Move them.</p>
      <div className="mt-5"><MatcherQuality /></div>
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[420px_1fr]">
        <div className="rounded-2xl border border-paper-line bg-paper p-5">
          {SLIDERS.map((s) => (
            <label key={s.key} className="mb-5 block">
              <div className="flex justify-between font-semibold"><span>{s.label}</span><span className="tabular-nums text-accent-700">{s.fmt(p[s.key] as number)}</span></div>
              <input type="range" min={s.min} max={s.max} step={s.step} value={p[s.key] as number}
                onChange={(e) => setP({ ...p, [s.key]: Number(e.target.value) })} className="mt-2 w-full accent-[#0b7a70]" />
              <div className="text-sm text-ink-mute">{s.help}</div>
            </label>
          ))}
          <div className="flex gap-2">
            <button onClick={() => setP(PESSIMISTIC)} className={cn("flex-1 rounded-xl border-2 px-4 py-2.5 font-bold", preset ? "border-danger-500 bg-danger-50 text-danger-700" : "border-danger-500 text-danger-700 hover:bg-danger-50")}>Pessimistic preset</button>
            <button onClick={() => setP(DEFAULTS)} className="rounded-xl border border-paper-line px-4 py-2.5 font-semibold text-ink-soft hover:bg-paper-warm">Reset</button>
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
                          <span className="w-24 text-sm text-ink-mute">{a.arm === "today" ? "Today" : "SameSame"}</span>
                          <div className="h-7 flex-1 rounded bg-paper-warm">
                            <div className={cn("h-7 rounded transition-all duration-500", a.arm === "today" ? "bg-slate-400" : "bg-accent-600")} style={{ width: `${(100 * a[key]) / max}%` }} />
                          </div>
                          <span className="w-24 text-right font-mono tabular-nums">{(fmt as (v: number) => string)(a[key])}</span>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Big({ label, value, good }: { label: string; value: string; good: boolean }) {
  return (
    <div>
      <div className={cn("text-5xl font-extrabold tabular-nums", good ? "text-accent-700" : "text-danger-700")}>{value}</div>
      <div className="mt-1 text-ink-mute">{label}</div>
    </div>
  );
}
