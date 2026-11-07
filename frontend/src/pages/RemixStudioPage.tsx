import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, BarChart3, Bus, Car, Check, CheckCircle2, Dice5, Loader2, Package, RefreshCw, ShieldCheck, Sparkles, Ticket, Utensils, X, XCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Meta, RemixBooking, RemixLeg, RemixOverview, RemixPart, RemixResult, RemixSettings, RemixStats, RemixSummary } from "@/contracts";
import { getJSON, inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { CITY } from "@/lib/city";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState, Loading } from "@/components/States";
import { PromiseMeter, SupplierBadge, Tip, cn } from "@/components/ui";

const SUP: Record<string, string> = { kestrel: "Kestrel", mynah: "Mynah", heron: "Heron", bulbul: "Bulbul", hornbill: "Hornbill", sunbird: "Sunbird" };
const ZONES = [["deira", "Deira"], ["bur-dubai", "Bur Dubai"], ["downtown", "Downtown"], ["marina", "Dubai Marina"], ["palm", "Palm Jumeirah"], ["dxb", "DXB Airport"]];
const LEG_ICON = { ticket: Ticket, out: Car, back: Car, lunch: Utensils } as const;
const LEG_LABEL = { ticket: "Entry ticket", out: "Transfer out", back: "Transfer back", lunch: "Lunch voucher" } as const;
const DNA_LABEL: Record<string, string> = { pickup: "Pickup", meals: "Meals", access: "Access", stops: "Stops", option: "Option", slot: "Slot", cancel: "Cancellation" };
const pct = (x?: number | null, d = 1) => (x == null ? "—" : `${(x * 100).toFixed(d)}%`);
const hhmm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

type Knobs = Pick<RemixSettings, "zone" | "agent_share" | "min_saving" | "min_margin" | "min_promise" | "buffer_min"> & { preset: "" | "pessimistic" };
const DEFAULT_KNOBS: Knobs = { zone: "deira", agent_share: 0.5, min_saving: 0.03, min_margin: 0.04, min_promise: 0.95, buffer_min: 20, preset: "" };
const qs = (k: Knobs) => new URLSearchParams(Object.entries(k).filter(([, v]) => v !== "").map(([a, b]) => [a, String(b)])).toString();

export default function RemixStudioPage() {
  const [params, setParams] = useSearchParams();
  const meta = useApi<Meta>("/api/meta");
  const demo = meta.status === "ready" ? (meta.data.demo.remix_variant as string) : null;
  const v = params.get("v") ?? demo;
  const [knobs, setKnobs] = useState<Knobs>(DEFAULT_KNOBS);
  const q = qs(knobs);
  const overview = useApi<RemixOverview>(`/api/remix?${q}`);
  const detail = useApi<RemixResult>(v ? `/api/remix/${v}?${q}` : null);
  const showTp = params.get("tp") === "1";
  const pick = (id: string) => { const n = new URLSearchParams(params); n.set("v", id); setParams(n, { replace: true }); };
  const toggleTp = useCallback(() => { const n = new URLSearchParams(params); n.set("tp", showTp ? "0" : "1"); setParams(n, { replace: true }); }, [params, setParams, showTp]);
  const bookBeat = params.get("book") === "1";
  usePresenterAction(useCallback(() => { if (!bookBeat) toggleTp(); }, [bookBeat, toggleTp]));

  return (
    <div className="mx-auto max-w-[1560px] px-8 pb-10 pt-6">
      <PageHeader eyebrow={`Remix Studio · ${CITY}`} title={<>Remix makes <span className="italic">new products</span> from parts suppliers already sell.</>}
        subtitle="Every supplier's tour, split into parts. TBO's own version is built from the cheapest reliable ones, and only when it is the SAME experience, cheaper on True Price, with a margin left for TBO."
        right={overview.status === "ready" ? <Funnel o={overview.data} /> : undefined}>
        {overview.status === "ready" && <Picker items={overview.data.items} active={v} onPick={pick} />}
      </PageHeader>
      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          {(detail.status === "loading" || !v) && <Loading what="Assembling parts" />}
          {detail.status === "error" && <ErrorState error={detail.error} onRetry={detail.reload} />}
          {detail.status === "ready" && <RemixView r={detail.data} showTp={showTp} onToggleTp={toggleTp} bookBeat={bookBeat}
            seed={meta.status === "ready" ? (meta.data.demo.remix_seed as number) : 1} seedNote={meta.status === "ready" ? (meta.data.demo.remix_seed_note as string) : ""}
            isDemo={v === demo} />}
        </div>
        <Guardrails knobs={knobs} setKnobs={setKnobs} r={detail.status === "ready" ? detail.data : null} />
      </div>
    </div>
  );
}

function Funnel({ o }: { o: RemixOverview }) {
  const c = o.counts;
  const rows = [["multi-part packages", c.multi_part], ["SAME Remix exists", c.remix_exists], ["cheaper on True Price", c.cheaper], ["passes every guardrail", c.ready]] as const;
  return (
    <div className="rounded-2xl bg-paper/90 px-5 py-3 shadow-card">
      {rows.map(([k, n], i) => (
        <div key={k} className="flex items-center gap-3 text-sm">
          <div className="h-2 rounded-full bg-accent-700" style={{ width: `${Math.max(6, (n / c.multi_part) * 140)}px`, opacity: 0.35 + i * 0.2 }} />
          <b className="w-6 tabular-nums">{n}</b><span className="text-ink-soft">{k}</span>
        </div>
      ))}
      <div className="mt-1 text-xs text-ink-mute">{c.package_wins} where the package is cheaper, shown, not hidden</div>
    </div>
  );
}

const STATUS: Record<string, { label: string; cls: string }> = {
  ready: { label: "TBO Remix", cls: "bg-sun-500 text-white" },
  blocked: { label: "blocked", cls: "bg-sand-200 text-ink-soft" },
  not_remixable: { label: "not remixable", cls: "bg-paper-warm text-ink-mute" },
};

function Picker({ items, active, onPick }: { items: RemixSummary[]; active: string | null; onPick: (id: string) => void }) {
  const order = { ready: 0, blocked: 1, not_remixable: 2, single_part: 3 };
  const sorted = [...items].sort((a, b) => order[a.status] - order[b.status] || (b.agent_saving_inr ?? -1e9) - (a.agent_saving_inr ?? -1e9));
  return (
    <div className="flex max-h-[132px] flex-wrap gap-2 overflow-auto pr-2">
      {sorted.map((it) => (
        <button key={it.variant_id} onClick={() => onPick(it.variant_id)}
          className={cn("flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm shadow-card transition-colors",
            active === it.variant_id ? "border-accent-700 bg-accent-700 text-white" : "border-paper-line bg-paper text-ink-soft hover:border-accent-500")}>
          <span className="max-w-[220px] truncate font-semibold">{it.attraction.split(" (")[0].split(",")[0].split(":")[0]}</span>
          <span className="max-w-[160px] truncate opacity-80">{it.target_dna.pickup !== "No transfer" ? it.target_dna.pickup.replace(" hotel pickup", " pickup") : it.target_dna.meals}</span>
          <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-bold uppercase", STATUS[it.status]?.cls)}>
            {it.status === "blocked" && (it.gap ?? 0) <= 0 ? "package wins" : STATUS[it.status]?.label}
          </span>
        </button>
      ))}
    </div>
  );
}

function RemixView({ r, showTp, onToggleTp, bookBeat, seed, seedNote, isDemo }:
  { r: RemixResult; showTp: boolean; onToggleTp: () => void; bookBeat: boolean; seed: number; seedNote: string; isDemo: boolean }) {
  const pkg = r.packaged;
  const verdict = r.status === "ready"
    ? { cls: "bg-ok-50 text-ok-700 border-ok-500", icon: <ShieldCheck className="h-5 w-5" />, text: r.reasons[0] }
    : (r.gap ?? 1) <= 0
      ? { cls: "bg-sand-100 text-ink border-sand-200", icon: <Package className="h-5 w-5" />, text: `Package wins: ${r.reasons.join("; ")}. Remix never pretends otherwise.` }
      : { cls: "bg-danger-50 text-danger-700 border-danger-50", icon: <AlertTriangle className="h-5 w-5" />, text: `${r.status === "blocked" ? "Blocked" : "Not remixable"}: ${r.reasons.join("; ")}` };
  return (
    <>
      <div className={cn("flex items-center gap-3 rounded-2xl border px-5 py-3 text-[15px] font-semibold", verdict.cls)}>{verdict.icon}{verdict.text}</div>
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="rounded-3xl border border-paper-line bg-paper p-5 shadow-card">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-mute">Packaged by suppliers today</div>
          <h2 className="mt-1 text-[26px] font-semibold leading-tight text-accent-700">{r.attraction}</h2>
          <div className="text-ink-soft">{r.name}</div>
          <DnaStrip dna={r.target_dna} />
          {pkg ? (
            <div className="mt-4 rounded-2xl bg-paper-warm p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2"><SupplierBadge name={SUP[pkg.supplier_id]} /><span className="text-sm text-ink-mute">best package on True Price</span></span>
                <PromiseMeter rate={pkg.p_secure} n={0} lo={pkg.p_secure} hi={pkg.p_secure} size={56} />
              </div>
              <div className="mt-1 line-clamp-1 text-sm text-ink-soft">{pkg.title}</div>
              <div className="mt-2 flex items-end justify-between">
                <div><div className="text-xs uppercase text-ink-mute">Sticker, 2 adults</div><div className="font-display text-2xl font-semibold tabular-nums">{inr(pkg.price)}</div></div>
                <div className="text-right"><div className="text-xs uppercase text-ink-mute">True Price</div><div className="font-display text-2xl font-semibold tabular-nums text-sun-600">{inr(pkg.true_price)}</div></div>
              </div>
            </div>
          ) : <div className="mt-4 text-ink-mute">No supplier sells this as one product.</div>}
        </section>

        <section className={cn("relative rounded-3xl border-2 bg-paper p-5 shadow-card", r.status === "ready" ? "border-sun-500" : "border-paper-line")}>
          <span className={cn("absolute -top-3 left-5 flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide shadow-card",
            r.status === "ready" ? "bg-sun-500 text-white" : "bg-sand-200 text-ink-soft")}><Sparkles className="h-3.5 w-3.5" />TBO Remix</span>
          {r.parts ? (
            <>
              <div className="mt-1 flex items-start justify-between gap-3">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-mute">Recipe · {r.parts.length} parts from {r.suppliers?.length} suppliers</div>
                  <div className="text-sm text-ink-soft">Cancellation: <b>{r.cancel}</b> (strictest part) · Remix Promise <b>{pct(r.promise)}</b></div>
                </div>
                {r.sell != null && <div className="text-right"><div className="text-xs uppercase text-ink-mute">Sell to agent</div>
                  <div className="font-display text-2xl font-semibold tabular-nums">{inr(r.sell)}</div>
                  <div className="text-sm font-semibold text-sun-600">True Price {inr(r.agent_true_price!.total)}</div></div>}
              </div>
              <ul className="mt-3 space-y-2">{r.parts.map((p) => <PartRow key={p.leg} p={p} />)}</ul>
              {r.timeline && <Timeline r={r} />}
              <SameCheck r={r} />
            </>
          ) : <div className="mt-3 text-ink-mute">No assembly of bundleable parts is the SAME product. {r.reasons.join("; ")}.</div>}
        </section>
      </div>
      {r.parts && pkg && r.sell != null && <TruePriceProof r={r} open={showTp} onToggle={onToggleTp} />}
      {r.parts && pkg && <BookRemix r={r} active={bookBeat} demoSeed={isDemo ? seed : 1} seedNote={isDemo ? seedNote : "Seed 1, first tried."} />}
    </>
  );
}

function DnaStrip({ dna }: { dna: Record<string, string> }) {
  const keys = Object.keys(DNA_LABEL).filter((k) => dna[k]);
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {keys.map((k) => <span key={k} className="rounded-lg bg-sky-100 px-2.5 py-1 text-sm"><span className="text-[10px] font-bold uppercase text-ink-mute">{DNA_LABEL[k]} </span>{dna[k]}</span>)}
    </div>
  );
}

function PartRow({ p }: { p: RemixPart }) {
  const Icon = LEG_ICON[p.leg];
  return (
    <li className="flex items-center gap-3 rounded-2xl border border-paper-line px-3 py-2">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sky-100 text-accent-700">{p.mode === "shared" ? <Bus className="h-4 w-4" /> : <Icon className="h-4 w-4" />}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-ink-mute">{LEG_LABEL[p.leg]} · {hhmm(p.start)}–{hhmm(p.end)}</div>
        <div className="truncate text-[15px]" title={p.title}>{p.title}</div>
        <div className="text-xs text-ink-mute">{p.twins.length} SAME twin{p.twins.length === 1 ? "" : "s"} for failover · {p.cancel}{p.vehicle && p.mode === "private" ? ` · ${p.vehicle}` : ""}</div>
      </div>
      <SupplierBadge name={SUP[p.supplier_id]} small />
      <div className="w-[86px] text-right font-semibold tabular-nums">{inr(p.price)}</div>
      <PromiseMeter rate={p.p_secure} n={p.promise.n} lo={p.promise.ci_low} hi={p.promise.ci_high} prior={p.promise.prior_weight} size={48} />
    </li>
  );
}

function Timeline({ r }: { r: RemixResult }) {
  const parts = r.parts!;
  const lo = Math.min(...parts.map((p) => p.start)), hi = Math.max(...parts.map((p) => p.end));
  const x = (m: number) => `${((m - lo) / (hi - lo)) * 100}%`;
  return (
    <div className="mt-4">
      <div className="flex justify-between text-xs text-ink-mute"><span>Pickup {hhmm(lo)}</span><span>door to door {r.timeline!.door_to_door_h} h · {r.timeline!.slack_min} min slack before the slot</span><span>Back {hhmm(hi)}</span></div>
      <div className="relative mt-1 h-8 rounded-full bg-paper-warm">
        {parts.map((p) => (
          <span key={p.leg} title={`${LEG_LABEL[p.leg]} ${hhmm(p.start)}–${hhmm(p.end)} · ${SUP[p.supplier_id]}`}
            className={cn("absolute top-1 h-6 rounded-full", p.leg === "ticket" ? "bg-sun-500" : p.leg === "lunch" ? "bg-ok-500" : "bg-accent-700/70")}
            style={{ left: x(p.start), width: `calc(${x(p.end)} - ${x(p.start)})` }} />
        ))}
      </div>
    </div>
  );
}

function SameCheck({ r }: { r: RemixResult }) {
  const keys = Object.keys(DNA_LABEL).filter((k) => r.target_dna[k] != null || r.assembled_dna?.[k] != null);
  return (
    <div className="mt-4 flex flex-wrap gap-1.5">
      {keys.map((k) => {
        const unv = r.unverified?.includes(k);
        return (
          <Tip key={k} content={unv ? <>The package doesn't state {DNA_LABEL[k].toLowerCase()}; the Remix's is {r.assembled_dna?.[k]}. A person confirms it before publishing.</>
            : <>Package: {r.target_dna[k]} · Remix: {r.assembled_dna?.[k]}</>}>
            <span className={cn("flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold", unv ? "bg-warn-50 text-warn-500" : "bg-ok-50 text-ok-700")}>
              {unv ? <AlertTriangle className="h-3 w-3" /> : <Check className="h-3 w-3" />}{DNA_LABEL[k]}
            </span>
          </Tip>
        );
      })}
      <span className="text-xs text-ink-mute">SAME by Variant DNA, never VARIANT</span>
    </div>
  );
}

function TruePriceProof({ r, open, onToggle }: { r: RemixResult; open: boolean; onToggle: () => void }) {
  const pkg = r.packaged!;
  const bars = [
    { k: "Best package, True Price", v: pkg.true_price, c: "bg-sand-200" },
    { k: "Remix, agent's True Price", v: r.agent_true_price!.total, c: "bg-sun-500" },
    { k: "TBO's expected cost", v: r.tbo_cost!, c: "bg-accent-700" },
  ];
  const max = Math.max(...bars.map((b) => b.v));
  const partsRisk = r.parts!.reduce((s, p) => s + p.tbo_cost - p.price, 0);
  return (
    <section className="mt-4 rounded-3xl border border-paper-line bg-paper p-5 shadow-card">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-[26px] font-semibold text-accent-700">Cheaper on True Price, not just sticker</h2>
        <button onClick={onToggle} className="rounded-full border border-paper-line px-4 py-1.5 text-sm font-semibold text-ink-soft hover:bg-paper-warm">{open ? "Hide" : "Show"} the arithmetic</button>
      </div>
      <div className="mt-3 space-y-2">
        {bars.map((b) => (
          <div key={b.k} className="flex items-center gap-3">
            <div className="w-56 shrink-0 text-sm text-ink-soft">{b.k}</div>
            <motion.div className={cn("h-7 rounded-full", b.c)} initial={{ width: 0 }} animate={{ width: `${(b.v / max) * 100}%` }} transition={{ duration: 0.6 }} />
            <div className="w-24 shrink-0 text-right font-semibold tabular-nums">{inr(b.v)}</div>
          </div>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-1 gap-3 text-[15px] md:grid-cols-3">
        <Stat label="Agent saves" value={`${inr(r.agent_saving_inr!)} · ${pct(r.agent_saving)}`} tone={r.agent_saving! > 0 ? "ok" : "bad"} />
        <Stat label="TBO keeps" value={`${inr(r.margin_inr!)} · ${pct(r.margin)} margin`} tone={r.margin! > 0 ? "ok" : "bad"} />
        <Stat label="Split of the gap" value={`${pct(r.settings.agent_share, 0)} to the agent, ${pct(1 - r.settings.agent_share, 0)} to TBO`} />
      </div>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <div className="mt-4 grid grid-cols-1 gap-4 text-sm lg:grid-cols-2">
              <div>
                <div className="font-semibold">Best package: {SUP[pkg.supplier_id]}</div>
                <table className="mt-1 w-full">{pkg.terms.terms.map((t) => <tr key={t.key} className="border-t border-paper-line"><td className="py-1">{t.label}<div className="text-xs text-ink-mute">{t.assumption}</div></td><td className="text-right tabular-nums">{inr(t.amount)}</td></tr>)}
                  <tr className="border-t-2 border-ink/30 font-semibold"><td className="py-1">True Price</td><td className="text-right tabular-nums">{inr(pkg.true_price)}</td></tr></table>
              </div>
              <div>
                <div className="font-semibold">Remix: what TBO expects to pay</div>
                <table className="mt-1 w-full">
                  {r.parts!.map((p) => <tr key={p.leg} className="border-t border-paper-line"><td className="py-1">{LEG_LABEL[p.leg]} · {SUP[p.supplier_id]}<div className="text-xs text-ink-mute">sticker + price-change and failover risk from its own Promise</div></td><td className="text-right tabular-nums">{inr(p.tbo_cost)}</td></tr>)}
                  <tr className="border-t border-paper-line"><td className="py-1">Assembly risk<div className="text-xs text-ink-mute">{r.assembly_risk!.assumption}</div></td><td className="text-right tabular-nums">{inr(r.assembly_risk!.amount)}</td></tr>
                  <tr className="border-t-2 border-ink/30 font-semibold"><td className="py-1">TBO's expected cost (risk in parts: {inr(partsRisk)})</td><td className="text-right tabular-nums">{inr(r.tbo_cost!)}</td></tr>
                  <tr className="border-t border-paper-line"><td className="py-1">Agent's True Price = sell {inr(r.sell!)} + cancellation risk under "{r.cancel}". TBO carries the rest.</td><td className="text-right tabular-nums">{inr(r.agent_true_price!.total)}</td></tr>
                </table>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "ok" | "bad" }) {
  return <div className="rounded-2xl bg-paper-warm px-4 py-2"><div className="text-xs uppercase text-ink-mute">{label}</div>
    <div className={cn("font-semibold", tone === "ok" && "text-ok-700", tone === "bad" && "text-danger-700")}>{value}</div></div>;
}

function Guardrails({ knobs, setKnobs, r }: { knobs: Knobs; setKnobs: (k: Knobs) => void; r: RemixResult | null }) {
  const [draft, setDraft] = useState(knobs);
  useEffect(() => { const t = setTimeout(() => setKnobs(draft), 350); return () => clearTimeout(t); }, [draft, setKnobs]);
  const slider = (key: keyof Knobs, label: string, min: number, max: number, step: number, fmt: (v: number) => string) => (
    <label className="block">
      <div className="flex justify-between text-sm"><span className="text-ink-soft">{label}</span><b className="tabular-nums">{fmt(draft[key] as number)}</b></div>
      <input type="range" min={min} max={max} step={step} value={draft[key] as number} onChange={(e) => setDraft({ ...draft, [key]: Number(e.target.value) })} className="w-full accent-[#163a6b]" />
    </label>
  );
  const checks = r && r.sell != null ? [
    { k: `Agent saves ≥ ${pct(r.settings.min_saving, 0)}`, ok: (r.agent_saving ?? 0) >= r.settings.min_saving, v: pct(r.agent_saving) },
    { k: `TBO margin ≥ ${pct(r.settings.min_margin, 0)}`, ok: (r.margin ?? 0) >= r.settings.min_margin, v: pct(r.margin) },
    { k: `Remix Promise ≥ ${pct(r.settings.min_promise, 0)}`, ok: (r.promise ?? 0) >= r.settings.min_promise, v: pct(r.promise) },
    { k: `Slack ≥ ${r.settings.buffer_min} min`, ok: (r.timeline?.slack_min ?? 0) >= r.settings.buffer_min, v: `${r.timeline?.slack_min} min` },
  ] : [];
  return (
    <aside className="h-fit rounded-3xl border border-paper-line bg-paper p-5 shadow-card xl:sticky xl:top-[84px]">
      <h3 className="font-display text-xl font-semibold text-accent-700">Publish guardrails</h3>
      <p className="text-xs text-ink-mute">Set by the product team, applied to every Remix. Change one and every verdict is recomputed.</p>
      <div className="mt-3 space-y-3">
        <label className="block text-sm"><span className="text-ink-soft">Client stays in</span>
          <select value={draft.zone} onChange={(e) => setDraft({ ...draft, zone: e.target.value })} className="mt-1 w-full rounded-lg border border-paper-line bg-paper px-2 py-1.5">
            {ZONES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select></label>
        {slider("agent_share", "Agent's share of the gap", 0, 1, 0.05, (v) => pct(v, 0))}
        {slider("min_saving", "Minimum agent saving", 0, 0.15, 0.01, (v) => pct(v, 0))}
        {slider("min_margin", "Minimum TBO margin", 0, 0.15, 0.01, (v) => pct(v, 0))}
        {slider("min_promise", "Minimum Remix Promise", 0.8, 0.99, 0.01, (v) => pct(v, 0))}
        {slider("buffer_min", "Arrive before the slot (min)", 0, 45, 5, (v) => `${v}`)}
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.preset === "pessimistic"}
          onChange={(e) => setDraft({ ...draft, preset: e.target.checked ? "pessimistic" : "" })} />Pessimistic: transfers +30%, parts fail 1.5× as often</label>
        <button onClick={() => setDraft(DEFAULT_KNOBS)} className="text-sm font-semibold text-accent-700 underline">Reset to defaults</button>
      </div>
      {checks.length > 0 && (
        <ul className="mt-4 space-y-1.5 border-t border-paper-line pt-3">
          {checks.map((c) => <li key={c.k} className="flex items-center gap-2 text-sm">{c.ok ? <CheckCircle2 className="h-4 w-4 text-ok-500" /> : <XCircle className="h-4 w-4 text-danger-500" />}
            <span className="flex-1">{c.k}</span><b className="tabular-nums">{c.v}</b></li>)}
          {r?.unverified && r.unverified.length > 0 && <li className="flex items-center gap-2 text-sm"><AlertTriangle className="h-4 w-4 text-warn-500" />Needs approval: package silent on {r.unverified.join(", ")}</li>}
        </ul>
      )}
    </aside>
  );
}

// ------------------------------------------------------------------ Book Remix
const OUTCOME: Record<string, { label: string; c: string }> = {
  clean: { label: "Confirmed first time", c: "bg-ok-500" }, paid_rise: { label: "Paid a price rise", c: "bg-warn-500" },
  failover: { label: "Part failed over to a SAME twin", c: "bg-accent-500" }, compensated: { label: "Unwound, package bought instead", c: "bg-sun-500" },
  failed: { label: "Failed", c: "bg-danger-500" },
};

function BookRemix({ r, active, demoSeed, seedNote }: { r: RemixResult; active: boolean; demoSeed: number; seedNote: string }) {
  const [res, setRes] = useState<RemixBooking | null>(null);
  const [clock, setClock] = useState(0);
  const [seed, setSeed] = useState(demoSeed);
  const [stats, setStats] = useState<RemixStats | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const timer = useRef<number>();
  const ref = useRef<HTMLElement>(null);
  useEffect(() => { setRes(null); setStats(null); setSeed(demoSeed); }, [r.variant_id, demoSeed]);
  const run = useCallback(async (s: number) => {
    setErr(null); setRes(null); setClock(0); setSeed(s);
    ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    try {
      const resp = await fetch("/api/remix/book", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ variant_id: r.variant_id, seed: s }) });
      if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
      const data: RemixBooking = await resp.json();
      setRes(data);
      const all = [...data.legs.flatMap((l) => l.steps), ...(data.compensation?.steps ?? [])];
      const end = Math.max(...all.map((x) => x.t_ms)) + 300, t0 = performance.now();
      window.clearInterval(timer.current);
      timer.current = window.setInterval(() => { const t = performance.now() - t0; setClock(t); if (t > end) window.clearInterval(timer.current); }, 50);
    } catch (e) { setErr((e as Error).message); }
  }, [r.variant_id]);
  useEffect(() => () => window.clearInterval(timer.current), []);
  usePresenterAction(useCallback(() => { if (active) run(demoSeed); }, [active, run, demoSeed]));
  const allSteps = res ? [...res.legs.flatMap((l) => l.steps), ...(res.compensation?.steps ?? [])] : [];
  const done = res && allSteps.every((s) => s.t_ms <= clock);
  const legsInOrder = useMemo(() => res?.legs ?? [], [res]);

  return (
    <section ref={ref} className={cn("mt-4 scroll-mt-20 rounded-3xl border-2 bg-paper p-5 shadow-card", active ? "border-accent-700" : "border-paper-line")}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-[26px] font-semibold text-accent-700">Book the Remix</h2>
          <p className="text-sm text-ink-mute">Riskiest part first. A failed part fails over to a SAME twin of that part only; if none is left, TBO unwinds and buys the package. Outcomes are drawn from the behaviour model.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => run(demoSeed)} className="rounded-xl bg-accent-700 px-6 py-3 text-lg font-bold text-white shadow hover:bg-accent-900">Book Remix</button>
          <button onClick={() => run(Math.floor(Math.random() * 1e6))} className="flex items-center gap-1.5 rounded-xl border border-paper-line px-4 py-3 font-semibold text-ink-soft hover:bg-paper-warm"><Dice5 className="h-5 w-5" />Fresh seed</button>
          <button onClick={async () => setStats(await getJSON<RemixStats>(`/api/remix/book/stats?variant_id=${r.variant_id}&runs=1000`))}
            className="flex items-center gap-1.5 rounded-xl border border-paper-line px-4 py-3 font-semibold text-ink-soft hover:bg-paper-warm"><BarChart3 className="h-5 w-5" />Run 1,000×</button>
        </div>
      </div>
      <div className="mt-1 text-sm text-ink-mute">Scenario seed <b className="font-mono text-ink-soft">{seed}</b>. {seed === demoSeed ? seedNote : "A fresh random draw."}</div>
      {err && <div className="mt-3 rounded-lg bg-danger-50 p-3 text-danger-700">{err}</div>}
      <AnimatePresence>
        {done && res && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className={cn("mt-3 flex items-center gap-3 rounded-xl px-5 py-3 text-[17px] font-bold text-white", OUTCOME[res.outcome].c)}>
            <ShieldCheck className="h-6 w-6 shrink-0" />{res.summary}
          </motion.div>
        )}
      </AnimatePresence>
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {(legsInOrder.length ? legsInOrder : r.parts!.map((p) => ({ leg: p.leg, label: LEG_LABEL[p.leg], planned_supplier: SUP[p.supplier_id], steps: [] as RemixLeg["steps"] } as unknown as RemixLeg)))
          .map((l) => <LegCard key={l.leg} l={l} clock={clock} />)}
      </div>
      {res?.compensation && (
        <div className="mt-3 rounded-2xl bg-sun-50 p-4">
          <div className="font-semibold">Compensation</div>
          <ol className="mt-1 space-y-1 text-sm">{res.compensation.steps.filter((s) => s.t_ms <= clock).map((s, i) => <li key={i}>{s.detail}</li>)}</ol>
        </div>
      )}
      {stats && (
        <div className="mt-4 rounded-2xl bg-paper-warm p-4">
          <div className="font-semibold">Seeds 1 to {stats.runs.toLocaleString("en-IN")}: Remix vs the best package, same draws</div>
          {(["remix", "package"] as const).map((k) => (
            <div key={k} className="mt-2 flex items-center gap-3">
              <div className="w-20 shrink-0 text-sm font-semibold capitalize">{k}</div>
              <div className="flex h-6 flex-1 overflow-hidden rounded-full">
                {Object.entries(stats[k]).map(([o, n]) => n > 0 && <div key={o} className={OUTCOME[o].c} style={{ width: `${(100 * n) / stats.runs}%` }} title={`${OUTCOME[o].label}: ${n}`} />)}
              </div>
              <div className="w-[420px] shrink-0 text-xs text-ink-soft">{Object.entries(stats[k]).filter(([, n]) => n > 0).map(([o, n]) => `${OUTCOME[o].label.toLowerCase()} ${((100 * n) / stats.runs).toFixed(1)}%`).join(" · ")}</div>
            </div>
          ))}
          <div className="mt-2 text-sm text-ink-soft">Average paid: Remix {inr(stats.remix_avg_paid)} (TBO, to suppliers) · package {inr(stats.package_avg_paid)} (agent, to the packager).</div>
        </div>
      )}
    </section>
  );
}

function LegCard({ l, clock }: { l: RemixLeg; clock: number }) {
  const steps = l.steps.filter((s) => s.t_ms <= clock);
  const finished = l.steps.length > 0 && steps.length === l.steps.length;
  const Icon = LEG_ICON[l.leg as keyof typeof LEG_ICON] ?? Ticket;
  return (
    <div className={cn("rounded-2xl border p-3", finished ? (l.status === "confirmed" ? "border-ok-500" : "border-danger-500") : "border-paper-line")}>
      <div className="flex items-center gap-2 font-semibold"><Icon className="h-4 w-4 text-accent-700" />{l.label}<span className="ml-auto"><SupplierBadge name={l.planned_supplier} small /></span></div>
      <ol className="mt-2 min-h-[64px] space-y-1 text-sm">
        {l.steps.length === 0 && <li className="text-ink-mute">Waiting…</li>}
        {steps.map((s, i) => (
          <li key={i} className="flex items-center gap-1.5">
            {s.event === "confirmed" ? <CheckCircle2 className="h-4 w-4 text-ok-500" /> : s.event === "failover" ? <RefreshCw className="h-4 w-4 text-accent-600" />
              : s.event === "request" ? (i === steps.length - 1 && !finished ? <Loader2 className="h-4 w-4 animate-spin text-ink-mute" /> : <span className="h-4 w-4" />) : <XCircle className="h-4 w-4 text-danger-500" />}
            <span className={cn(s.event === "failover" && "font-semibold text-accent-700")}>{s.detail}</span>
          </li>
        ))}
      </ol>
      {finished && <div className={cn("mt-1 rounded-lg px-2 py-1 text-sm font-bold", l.status === "confirmed" ? "bg-ok-50 text-ok-700" : "bg-danger-50 text-danger-700")}>
        {l.status === "confirmed" ? `${l.via_failover ? `SAME twin via ${l.final_supplier}` : "Confirmed"} · ${inr(l.final_price ?? 0)}` : <span className="flex items-center gap-1"><X className="h-4 w-4" />No SAME twin left</span>}</div>}
    </div>
  );
}
