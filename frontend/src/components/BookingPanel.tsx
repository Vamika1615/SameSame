import { AnimatePresence, motion } from "framer-motion";
import { BarChart3, CheckCircle2, Dice5, Loader2, RefreshCw, ShieldCheck, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { BookResponse, BookStats, BookingResult, BookingStep, Meta, Offer } from "@/contracts";
import { getJSON, inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { SupplierBadge, cn } from "./ui";

const FAMILIES = ["Shah family", "Patel family"];
// Labels come from the offer's own ranks, so they stay true whatever the data says
const why = (o: Offer, i: number) => i === 0
  ? `booked on sticker · ${o.sticker_rank === 1 ? "cheapest" : `#${o.sticker_rank} cheapest`}, True Price #${o.true_rank}`
  : `booked on True Price · #${o.true_rank}, sticker #${o.sticker_rank}`;

export function BookingPanel({ offers, active }: { offers: Offer[]; active: boolean }) {
  const meta = useApi<Meta>("/api/meta");
  const basket = meta.status === "ready" ? meta.data.demo.book_offers ?? [] : [];
  const demoSeed = meta.status === "ready" ? meta.data.demo.book_seed ?? 1 : 1;
  const chosen = basket.map((id) => offers.find((o) => o.offer_id === id)).filter(Boolean) as Offer[];
  const [seed, setSeed] = useState<number | null>(null);
  const [resp, setResp] = useState<BookResponse | null>(null);
  const [clock, setClock] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [stats, setStats] = useState<BookStats | null>(null);
  const timer = useRef<number>();
  const panel = useRef<HTMLElement>(null);

  const run = useCallback(async (s: number) => {
    setErr(null); setResp(null); setClock(0); setSeed(s);
    panel.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    try {
      const r = await fetch("/api/book", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ offer_ids: basket, seed: s }) });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const data: BookResponse = await r.json();
      setResp(data);
      const t0 = performance.now();
      const end = Math.max(...data.results.flatMap((x) => x.steps.map((st) => st.t_ms))) + 200;
      window.clearInterval(timer.current);
      timer.current = window.setInterval(() => {
        const t = performance.now() - t0;
        setClock(t);
        if (t > end) window.clearInterval(timer.current);
      }, 50);
    } catch (e) { setErr((e as Error).message); }
  }, [basket]);
  useEffect(() => () => window.clearInterval(timer.current), []);
  usePresenterAction(useCallback(() => { if (active) run(demoSeed); }, [active, run, demoSeed]));

  const loadStats = async () => setStats(await getJSON<BookStats>(`/api/book/stats?offer_ids=${basket.join(",")}&runs=1000`));
  const done = resp && resp.results.every((r) => r.steps.every((s) => s.t_ms <= clock));
  const failover = done ? resp!.results.find((r) => r.via_failover && r.status === "confirmed") : undefined;

  return (
    <section ref={panel} className={cn("mt-6 scroll-mt-36 rounded-2xl border bg-paper p-5", active ? "border-accent-500" : "border-paper-line")}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-[16px] font-semibold text-ink">Try booking the top two offers (sandbox)</h3>
          <p className="max-w-[640px] text-sm text-ink-mute">Outcomes follow each supplier's record at this lead time. If a booking fails, it moves only to the identical room from another supplier, never a different one.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => run(demoSeed)} disabled={!chosen.length}
            className="rounded-full bg-accent-700 px-4 py-2 text-sm font-semibold text-white hover:bg-accent-900 disabled:opacity-50">Book both</button>
          <button onClick={() => run(Math.floor(Math.random() * 1e6))} title="Rerun with a fresh random seed"
            className="flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-medium text-ink-soft hover:bg-paper-warm"><Dice5 className="h-4 w-4" />Fresh seed</button>
          <button onClick={loadStats} className="flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-medium text-ink-soft hover:bg-paper-warm"><BarChart3 className="h-4 w-4" />Run 1,000×</button>
        </div>
      </div>
      <div className="mt-2 text-sm text-ink-mute">
        Scenario seed <b className="font-mono text-ink-soft">{seed ?? demoSeed}</b>. {meta.status === "ready" && meta.data.demo.book_seed_note}
      </div>
      {err && <div className="mt-3 rounded-lg bg-danger-50 p-3 text-danger-700">Booking sandbox error: {err}</div>}

      <AnimatePresence>
        {failover && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="mt-4 flex items-center gap-3 rounded-xl bg-ok-500 px-4 py-2.5 text-[15px] font-semibold text-white">
            <ShieldCheck className="h-6 w-6" />
            Rebooked SAME twin via {failover.final_supplier}, confirmed at {inr(failover.final_price ?? 0)}. The client never saw the failure.
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {chosen.map((o, i) => (
          <BookingCard key={o.offer_id} family={`${FAMILIES[i] ?? "Booking"} · ${why(o, i)}`} offer={o} result={resp?.results.find((r) => r.offer_id === o.offer_id)} clock={clock} />
        ))}
      </div>

      {stats && (
        <div className="mt-5 rounded-xl bg-paper-warm p-4">
          <div className="font-semibold">Same basket, seeds 1 to {stats.runs.toLocaleString("en-IN")}</div>
          <div className="mt-2 space-y-2">
            {stats.per_offer.map((p) => {
              const o = offers.find((x) => x.offer_id === p.offer_id);
              const seg = [
                { k: "Confirmed first time", v: p.confirmed_first_time, c: "bg-ok-500" },
                { k: "Paid a price rise", v: p.paid_price_rise, c: "bg-warn-500" },
                { k: "Saved by failover", v: p.via_failover, c: "bg-accent-500" },
                { k: "Failed", v: p.failed, c: "bg-danger-500" },
              ];
              return (
                <div key={p.offer_id} className="flex items-center gap-3">
                  <div className="w-28 shrink-0">{o && <SupplierBadge name={o.supplier} small />}</div>
                  <div className="flex h-6 flex-1 overflow-hidden rounded">
                    {seg.map((s) => s.v > 0 && <div key={s.k} className={s.c} style={{ width: `${(100 * s.v) / stats.runs}%` }} title={`${s.k}: ${s.v}`} />)}
                  </div>
                  <div className="w-[380px] shrink-0 text-sm text-ink-soft">
                    {seg.filter((s) => s.v > 0).map((s) => `${s.k.toLowerCase()} ${((100 * s.v) / stats.runs).toFixed(1)}%`).join(" · ")}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

const ICON: Partial<Record<BookingStep["event"], JSX.Element>> = {
  confirmed: <CheckCircle2 className="h-5 w-5 text-ok-500" />, failed: <XCircle className="h-5 w-5 text-danger-500" />,
  price_changed: <XCircle className="h-5 w-5 text-warn-500" />, sold_out: <XCircle className="h-5 w-5 text-danger-500" />,
  error: <XCircle className="h-5 w-5 text-danger-500" />, failover: <RefreshCw className="h-5 w-5 text-accent-600" />,
  request: <Loader2 className="h-5 w-5 animate-spin text-ink-mute" />,
};

function BookingCard({ family, offer, result, clock }: { family: string; offer: Offer; result?: BookingResult; clock: number }) {
  const steps = result?.steps.filter((s) => s.t_ms <= clock) ?? [];
  const finished = result && steps.length === result.steps.length;
  return (
    <div className={cn("rounded-xl border p-4", finished ? (result!.status === "confirmed" ? "border-ok-500" : "border-danger-500") : "border-paper-line")}>
      <div className="text-sm font-semibold uppercase tracking-wide text-ink-mute">{family}</div>
      <div className="mt-1 flex items-center justify-between gap-2">
        <span className="flex items-center gap-2"><SupplierBadge name={offer.supplier} /><span className="text-ink-soft">{offer.board} · {offer.cancel_text}</span></span>
        <span className="text-right"><span className="text-xl font-bold tabular-nums">{inr(offer.price)}</span>
          <span className="block text-sm text-accent-700">True Price {inr(offer.true_price.total)}</span></span>
      </div>
      <ol className="mt-3 min-h-[140px] space-y-1.5">
        {!result && <li className="text-ink-mute">Waiting for "Book both"…</li>}
        <AnimatePresence initial={false}>
          {steps.map((s, i) => (
            <motion.li key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} className="flex items-center gap-2">
              {s.event === "request" && i < steps.length - 1 ? <span className="h-5 w-5" /> : ICON[s.event]}
              <span className={cn(s.event === "confirmed" && "font-semibold text-ok-700", s.event === "failover" && "font-semibold text-accent-700")}>{s.detail}</span>
              {s.price != null && s.event !== "request" && <span className="ml-auto tabular-nums text-ink-mute">{inr(s.price)}</span>}
            </motion.li>
          ))}
        </AnimatePresence>
      </ol>
      {finished && (
        <div className={cn("mt-2 rounded-lg px-3 py-2 font-bold", result!.status === "confirmed" ? "bg-ok-50 text-ok-700" : "bg-danger-50 text-danger-700")}>
          {result!.status === "confirmed"
            ? `Confirmed${result!.via_failover ? ` via ${result!.final_supplier} (SAME twin)` : " first time"} · ${inr(result!.final_price ?? 0)}`
            : "Failed: no SAME twin left; the agent decides"}
        </div>
      )}
    </div>
  );
}
