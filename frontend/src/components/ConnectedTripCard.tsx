import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, BedDouble, CheckCircle2, Dice5, PlaneLanding, PlaneTakeoff, ShieldCheck, Sparkles, XCircle } from "lucide-react";
import { forwardRef, useCallback, useState } from "react";
import type { ConnectedTrip, Meta, TripBooking } from "@/contracts";
import { inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { PromiseMeter, SupplierBadge, cn } from "@/components/ui";
import { SUP, pct } from "@/pages/RemixStudioPage";

/** Hotel + DXB airport cars + a sightseeing Remix, sold as one product with one Promise and one cancellation rule. */
export const ConnectedTripCard = forwardRef<HTMLElement, { active: boolean }>(function ConnectedTripCard({ active }, ref) {
  const [minPromise, setMinPromise] = useState<number | null>(null);
  const t = useApi<ConnectedTrip>(`/api/trip${minPromise != null ? `?min_promise=${minPromise}` : ""}`);
  const meta = useApi<Meta>("/api/meta");
  const seed = meta.status === "ready" ? meta.data.demo.trip_seed ?? 1 : 1;
  const [res, setRes] = useState<TripBooking | null>(null);
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (s: number) => {
    setBusy(true); setRes(null);
    try {
      const r = await fetch("/api/trip/book", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ seed: s }) });
      setRes(await r.json());
    } finally { setBusy(false); }
  }, []);
  usePresenterAction(useCallback(() => { if (active) run(seed); }, [active, run, seed]));
  if (t.status !== "ready") return null;
  const d = t.data;
  if (!d.hotel) return null;
  const ok = d.status === "ready";
  const rows = [
    { icon: PlaneLanding, label: "Airport arrival", what: d.arrival.title, sup: d.arrival.supplier_id, price: d.arrival.price, p: d.arrival.p_secure },
    { icon: BedDouble, label: `Hotel · ${d.hotel.nights} nights`, what: `${d.hotel.name} · ${d.hotel.offer.board} · ${d.hotel.offer.cancel_text}`, sup: d.hotel.offer.supplier_id, price: d.hotel.offer.price, p: d.hotel.p_secure },
    { icon: Sparkles, label: "Activity · TBO Remix", what: `${d.activity.attraction} · ${d.activity.name}`, sup: null, price: d.activity.sticker ?? 0, p: d.activity.promise ?? 0 },
    { icon: PlaneTakeoff, label: "Airport departure", what: d.departure.title, sup: d.departure.supplier_id, price: d.departure.price, p: d.departure.p_secure },
  ];
  return (
    <section ref={ref} className={cn("relative mt-8 scroll-mt-20 rounded-3xl border-2 bg-paper p-6 shadow-card", active ? "border-accent-700" : ok ? "border-sun-500" : "border-paper-line")}>
      <span className="absolute -top-3 left-6 flex items-center gap-1.5 rounded-full bg-sun-500 px-3 py-1 text-xs font-bold uppercase tracking-wide text-white shadow-card"><Sparkles className="h-3.5 w-3.5" />Connected Trip Remix</span>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-[28px] font-semibold text-accent-700">Hotel, airport cars and the best tour Remix, as one product</h2>
          <p className="text-ink-soft">One price, one Promise, one cancellation rule. TBO runs the failover for every part.</p>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase text-ink-mute">One price for 2</div>
          <div className="font-display text-3xl font-semibold tabular-nums">{inr(d.sell)}</div>
          <div className="text-sm font-semibold text-sun-600">True Price {inr(d.agent_true_price.total)} · booked separately {inr(d.separate.total)}</div>
        </div>
      </div>
      <div className={cn("mt-3 flex items-center gap-2 rounded-xl px-4 py-2 font-semibold", ok ? "bg-ok-50 text-ok-700" : "bg-danger-50 text-danger-700")}>
        {ok ? <ShieldCheck className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
        {ok ? "Passes every guardrail" : `Blocked: ${d.reasons.join("; ")}. Four independent parts multiply; the guardrail holds.`}
      </div>
      <ul className="mt-4 space-y-2">
        {rows.map((r) => (
          <li key={r.label} className="flex items-center gap-3 rounded-2xl border border-paper-line px-3 py-2">
            <r.icon className="h-5 w-5 shrink-0 text-accent-700" />
            <div className="min-w-0 flex-1"><div className="text-[11px] font-semibold uppercase tracking-wide text-ink-mute">{r.label}</div><div className="truncate" title={r.what}>{r.what}</div></div>
            {r.sup ? <SupplierBadge name={SUP[r.sup] ?? r.sup} small /> : <span className="text-xs text-ink-mute">{d.activity.suppliers?.length} suppliers</span>}
            <div className="w-24 text-right font-semibold tabular-nums">{inr(r.price)}</div>
            <PromiseMeter rate={r.p} n={0} lo={r.p} hi={r.p} size={46} />
          </li>
        ))}
      </ul>
      <div className="mt-4 grid grid-cols-1 gap-3 text-sm md:grid-cols-4">
        <Box k="Booked separately today" v={inr(d.separate.total)} sub={`hotel ${inr(d.separate.hotel)} + cars ${inr(d.separate.cars)} + 2 extra bookings ${inr(d.separate.friction)} + tour package ${inr(d.separate.activity)}`} />
        <Box k="Agent saves" v={`${inr(d.agent_saving_inr)} · ${pct(d.agent_saving)}`} />
        <Box k="TBO keeps" v={`${inr(d.margin_inr)} · ${pct(d.margin)}`} />
        <Box k="Trip Promise" v={pct(d.promise)} sub="every part secured, incl. SAME-twin failover (independence assumed)" />
      </div>
      <div className="mt-3 rounded-2xl bg-paper-warm px-4 py-3 text-sm">
        <b>Cancellation:</b> {d.cancellation.summary}
        <span className="text-ink-mute"> Parts: {d.cancellation.rules.map((r) => `${r.part}: ${r.rule}`).join(" · ")}.</span>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button onClick={() => run(seed)} disabled={busy} className="rounded-xl bg-accent-700 px-6 py-3 text-lg font-bold text-white shadow hover:bg-accent-900 disabled:opacity-50">Book the trip (sandbox)</button>
        <button onClick={() => run(Math.floor(Math.random() * 1e6))} className="flex items-center gap-1.5 rounded-xl border border-paper-line px-4 py-3 font-semibold text-ink-soft hover:bg-paper-warm"><Dice5 className="h-5 w-5" />Fresh seed</button>
        <label className="flex items-center gap-2 text-sm text-ink-soft">Promise guardrail
          <input type="range" min={0.85} max={0.99} step={0.01} value={minPromise ?? d.settings.min_promise} onChange={(e) => setMinPromise(Number(e.target.value))} className="accent-[#163a6b]" />
          <b className="tabular-nums">{pct(minPromise ?? d.settings.min_promise, 0)}</b></label>
        <span className="text-xs text-ink-mute">Seed {seed} is the first that shows a part failing over (chosen to show it).</span>
      </div>
      <AnimatePresence>
        {res && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} className="mt-4">
            <div className={cn("rounded-xl px-5 py-3 font-bold text-white", res.outcome === "failed" ? "bg-danger-500" : res.outcome === "failover" ? "bg-accent-500" : "bg-ok-500")}>{res.summary}</div>
            <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-4">
              {res.legs.map((l) => (
                <div key={l.leg} className={cn("rounded-xl border px-3 py-2 text-sm", l.status === "confirmed" ? "border-ok-500" : "border-danger-500")}>
                  <div className="flex items-center gap-1.5 font-semibold">{l.status === "confirmed" ? <CheckCircle2 className="h-4 w-4 text-ok-500" /> : <XCircle className="h-4 w-4 text-danger-500" />}{l.label}</div>
                  <div className="text-ink-soft">{l.summary}</div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
});

function Box({ k, v, sub }: { k: string; v: string; sub?: string }) {
  return <div className="rounded-2xl bg-paper-warm px-4 py-2"><div className="text-xs uppercase text-ink-mute">{k}</div><div className="font-semibold tabular-nums">{v}</div>{sub && <div className="text-xs text-ink-mute">{sub}</div>}</div>;
}
