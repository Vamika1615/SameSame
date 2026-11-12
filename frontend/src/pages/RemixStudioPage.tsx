import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, ArrowRight, BarChart3, Bus, Car, Check, CheckCircle2, ChevronDown, Dice5, Loader2, RefreshCw, ShieldCheck, SlidersHorizontal, Ticket, Utensils, X, XCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { ApprovalItem, Meta, RemixBooking, RemixLeg, RemixOverview, RemixPart, RemixResult, RemixSettings, RemixStats, RemixSummary } from "@/contracts";
import { getJSON, inr, useApi } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { PageHeader } from "@/components/PageHeader";
import { Disclosure, Drawer } from "@/components/Disclosure";
import { ErrorState, Loading } from "@/components/States";
import { SupplierBadge, Tip, cn } from "@/components/ui";

export const SUP: Record<string, string> = { kestrel: "Kestrel", mynah: "Mynah", heron: "Heron", bulbul: "Bulbul", hornbill: "Hornbill", sunbird: "Sunbird" };
const ZONES = [["deira", "Deira"], ["bur-dubai", "Bur Dubai"], ["downtown", "Downtown"], ["marina", "Dubai Marina"], ["palm", "Palm Jumeirah"], ["dxb", "DXB Airport"]];
const LEG_ICON = { ticket: Ticket, out: Car, back: Car, lunch: Utensils } as const;
const LEG_LABEL = { ticket: "Entry ticket", out: "Transfer out", back: "Transfer back", lunch: "Lunch voucher" } as const;
const DNA_LABEL: Record<string, string> = { pickup: "Pickup", meals: "Meals", access: "Access", stops: "Stops", option: "Option", slot: "Slot", cancel: "Cancellation" };
export const pct = (x?: number | null, d = 1) => (x == null ? "—" : `${(x * 100).toFixed(d)}%`);
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
  const [rulesOpen, setRulesOpen] = useState(false);
  const q = qs(knobs);
  const overview = useApi<RemixOverview>(`/api/remix?${q}`);
  const detail = useApi<RemixResult>(v ? `/api/remix/${v}?${q}` : null);
  const showTp = params.get("tp") === "1";
  const pick = (id: string) => { const n = new URLSearchParams(params); n.set("v", id); n.delete("tp"); n.delete("book"); setParams(n, { replace: true }); };
  const toggleTp = useCallback(() => { const n = new URLSearchParams(params); n.set("tp", showTp ? "0" : "1"); setParams(n, { replace: true }); }, [params, setParams, showTp]);
  const bookBeat = params.get("book") === "1";
  usePresenterAction(useCallback(() => { if (!bookBeat) toggleTp(); }, [bookBeat, toggleTp]));
  const changed = JSON.stringify(knobs) !== JSON.stringify(DEFAULT_KNOBS);

  return (
    <div className="mx-auto max-w-[1400px] px-8 pb-10 pt-8">
      <PageHeader title="Rebuild supplier packages for less"
        subtitle="Each tour package is rebuilt from the same parts other suppliers sell separately. A bundle is offered only when it is the same experience, cheaper for the agent, and leaves TBO a margin."
        right={<button onClick={() => setRulesOpen(true)} className="relative flex items-center gap-2 rounded-full border border-paper-line bg-paper px-4 py-2 text-sm font-medium text-ink-soft hover:border-accent-500">
          <SlidersHorizontal className="h-4 w-4" />Publish rules{changed && <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-sun-500" />}</button>} />
      <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside>{overview.status === "ready" ? <ProductList o={overview.data} active={v} onPick={pick} /> : <Loading what="Loading products" />}</aside>
        <div className="min-w-0">
          {(detail.status === "loading" || !v) && <Loading what="Assembling parts" />}
          {detail.status === "error" && <ErrorState error={detail.error} onRetry={detail.reload} />}
          {detail.status === "ready" && <RemixView r={detail.data} showTp={showTp} onToggleTp={toggleTp} bookBeat={bookBeat}
            seed={meta.status === "ready" ? (meta.data.demo.remix_seed as number) : 1} seedNote={meta.status === "ready" ? (meta.data.demo.remix_seed_note as string) : ""}
            isDemo={v === demo} />}
        </div>
      </div>
      <Drawer open={rulesOpen} onClose={() => setRulesOpen(false)} title="Publish rules">
        <Guardrails knobs={knobs} setKnobs={setKnobs} r={detail.status === "ready" ? detail.data : null} />
      </Drawer>
    </div>
  );
}

const short = (a: string) => a.split(" (")[0].split(",")[0].split(":")[0];
const variantLabel = (it: { target_dna: Record<string, string> }) =>
  it.target_dna.pickup && it.target_dna.pickup !== "No transfer" ? it.target_dna.pickup.replace(" hotel pickup", " pickup") : `with ${it.target_dna.meals?.toLowerCase()}`;

/** Ready products first; the rest are one click away, never hidden. */
function ProductList({ o, active, onPick }: { o: RemixOverview; active: string | null; onPick: (id: string) => void }) {
  const ready = o.items.filter((i) => i.status === "ready").sort((a, b) => (b.agent_saving_inr ?? 0) - (a.agent_saving_inr ?? 0));
  const rest = o.items.filter((i) => i.status === "blocked" || i.status === "not_remixable")
    .sort((a, b) => Number(a.status !== "blocked") - Number(b.status !== "blocked") || (b.gap ?? -1e9) - (a.gap ?? -1e9));
  const [showRest, setShowRest] = useState(rest.some((i) => i.variant_id === active));
  const c = o.counts;
  const row = (it: RemixSummary) => (
    <li key={it.variant_id}>
      <button onClick={() => onPick(it.variant_id)} className={cn("flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors",
        active === it.variant_id ? "bg-accent-700 text-white" : "hover:bg-paper")}>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[15px] font-medium">{short(it.attraction)}</span>
          <span className={cn("block truncate text-sm", active === it.variant_id ? "text-white/75" : "text-ink-mute")}>{variantLabel(it)}</span>
        </span>
        {it.status === "ready"
          ? <span className={cn("text-sm font-semibold tabular-nums", active === it.variant_id ? "text-white" : "text-ok-700")}>−{pct(it.agent_saving, 0)}</span>
          : <span className={cn("text-xs", active === it.variant_id ? "text-white/75" : "text-ink-mute")}>{(it.gap ?? 0) <= 0 && it.status === "blocked" ? "package cheaper" : it.status === "blocked" ? "blocked" : "can't build"}</span>}
      </button>
    </li>
  );
  return (
    <div className="lg:sticky lg:top-[132px]">
      <div className="px-3 text-xs font-semibold uppercase tracking-wide text-ink-mute">Ready to sell · {ready.length}</div>
      <ul className="mt-2 space-y-0.5">{ready.map(row)}</ul>
      <button onClick={() => setShowRest(!showRest)} className="mt-4 flex w-full items-center justify-between px-3 text-xs font-semibold uppercase tracking-wide text-ink-mute hover:text-ink">
        Not offered · {rest.length}<ChevronDown className={cn("h-4 w-4 transition-transform", showRest && "rotate-180")} />
      </button>
      {showRest && <ul className="mt-2 max-h-[420px] space-y-0.5 overflow-auto">{rest.map(row)}</ul>}
      <p className="mt-5 px-3 text-xs leading-relaxed text-ink-mute">
        Of {c.multi_part} packages with more than one part, {c.remix_exists} can be rebuilt identically, {c.cheaper} cheaper, and {c.ready} pass every rule.
        In {c.package_wins} the supplier's package is cheaper, and we say so.
      </p>
    </div>
  );
}

function RemixView({ r, showTp, onToggleTp, bookBeat, seed, seedNote, isDemo }:
  { r: RemixResult; showTp: boolean; onToggleTp: () => void; bookBeat: boolean; seed: number; seedNote: string; isDemo: boolean }) {
  const pkg = r.packaged;
  const appr = useApi<{ queue: ApprovalItem[] }>("/api/remix/approvals");
  const decision = appr.status === "ready" ? appr.data.queue.find((i) => i.variant_id === r.variant_id)?.decision : undefined;
  const [bookTick, setBookTick] = useState(0);
  const status = r.status === "ready"
    ? { cls: "bg-ok-50 text-ok-700", text: decision === "approve" ? "Ready · approved and on sale" : decision === "reject" ? "Ready · rejected in Review" : "Ready · waiting for approval in Review" }
    : (r.gap ?? 1) <= 0 ? { cls: "bg-sand-100 text-ink-soft", text: "The supplier's package is cheaper" }
      : { cls: "bg-danger-50 text-danger-700", text: r.status === "blocked" ? "Not offered: it breaks a publish rule" : "Can't be rebuilt from parts" };
  const priced = !!(r.parts && pkg && r.sell != null);
  return (
    <div className="space-y-4">
      <div>
        <span className={cn("rounded-full px-3 py-1 text-xs font-semibold", status.cls)}>{status.text}</span>
        <h2 className="mt-3 text-[34px] leading-tight text-ink">{short(r.attraction)}</h2>
        <div className="text-lg text-ink-mute">{r.name}</div>
      </div>

      {priced ? (
        <section className="rounded-3xl border border-paper-line bg-paper p-6 shadow-card">
          <div className="grid grid-cols-1 items-center gap-6 md:grid-cols-[1fr_auto_1fr]">
            <div>
              <div className="text-sm text-ink-mute">{SUP[pkg!.supplier_id]}'s package</div>
              <div className="font-display text-[34px] font-semibold tabular-nums text-ink-mute line-through decoration-1">{inr(pkg!.true_price)}</div>
              <div className="text-sm text-ink-mute">listed at {inr(pkg!.price)} for 2</div>
            </div>
            <ArrowRight className="hidden h-6 w-6 text-ink-mute md:block" />
            <div>
              <div className="text-sm font-medium text-sun-600">TBO bundle · {r.parts!.length} parts, {r.suppliers?.length} suppliers</div>
              <div className="font-display text-[34px] font-semibold tabular-nums text-ink">{inr(r.agent_true_price!.total)}</div>
              <div className="text-sm text-ink-mute">sold to the agent at {inr(r.sell!)} for 2</div>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-3 gap-3 border-t border-paper-line pt-5">
            <Metric label="Agent saves" value={inr(r.agent_saving_inr!)} sub={pct(r.agent_saving)} tone={r.agent_saving! > 0 ? "text-ok-700" : "text-danger-700"} />
            <Metric label="TBO keeps" value={inr(r.margin_inr!)} sub={`${pct(r.margin)} margin`} tone={r.margin! > 0 ? "text-accent-700" : "text-danger-700"} />
            <Metric label="Books first time" value={pct(r.promise)} sub={`cancel: ${r.cancel}`} />
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button onClick={() => setBookTick((t) => t + 1)} className="rounded-full bg-accent-700 px-6 py-2.5 font-semibold text-white hover:bg-accent-900">Book bundle</button>
            <button onClick={onToggleTp} className="rounded-full px-4 py-2.5 text-sm font-medium text-ink-soft hover:bg-paper-warm">{showTp ? "Hide" : "How is this priced?"}</button>
            <Tip content="True Price = the listed price plus what its risks are expected to cost: cancellation, price changes and failed bookings. Prices compare on True Price, never on sticker alone.">
              <span className="cursor-help text-xs text-ink-mute underline decoration-dotted">Prices shown are True Prices</span>
            </Tip>
          </div>
          {r.status !== "ready" && <div className="mt-4 rounded-xl bg-paper-warm px-4 py-3 text-sm text-ink-soft">{r.reasons.join("; ")}.</div>}
        </section>
      ) : (
        <section className="rounded-3xl border border-paper-line bg-paper p-6 text-ink-soft shadow-card">
          {r.parts ? r.reasons.join("; ") : `No combination of resellable parts is the same experience. ${r.reasons.join("; ")}.`}
          {pkg && <div className="mt-2 text-sm text-ink-mute">Best package: {SUP[pkg.supplier_id]}, True Price {inr(pkg.true_price)}.</div>}
        </section>
      )}

      {r.parts && (
        <section className="rounded-3xl border border-paper-line bg-paper p-6">
          <h3 className="text-[16px] font-semibold text-ink">What's in the bundle</h3>
          <ul className="mt-3 divide-y divide-paper-line">{r.parts.map((p) => <PartRow key={p.leg} p={p} />)}</ul>
          {r.timeline && <Timeline r={r} />}
        </section>
      )}

      {r.parts && <Disclosure title="Is it really the same experience?" hint="Compared field by field with the package. Anything the package doesn't state is checked by a person.">
        <SameCheck r={r} />
      </Disclosure>}
      {priced && <Disclosure title="How it's priced" hint="Every term behind both True Prices, with its assumption." open={showTp}>
        <PriceBreakdown r={r} />
      </Disclosure>}
      {priced && <BookRemix r={r} active={bookBeat} trigger={bookTick} demoSeed={isDemo ? seed : 1} seedNote={isDemo ? seedNote : "Seed 1, the first tried."} />}
    </div>
  );
}

function Metric({ label, value, sub, tone = "text-ink" }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div>
      <div className="text-xs text-ink-mute">{label}</div>
      <div className={cn("text-2xl font-semibold tabular-nums", tone)}>{value}</div>
      {sub && <div className="truncate text-xs text-ink-mute">{sub}</div>}
    </div>
  );
}

export function DnaStrip({ dna }: { dna: Record<string, string> }) {
  const keys = Object.keys(DNA_LABEL).filter((k) => dna[k]);
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {keys.map((k) => <span key={k} className="rounded-lg bg-sky-100 px-2.5 py-1 text-sm"><span className="text-[10px] font-bold uppercase text-ink-mute">{DNA_LABEL[k]} </span>{dna[k]}</span>)}
    </div>
  );
}

export function PartRow({ p }: { p: RemixPart }) {
  const Icon = p.mode === "shared" ? Bus : LEG_ICON[p.leg];
  return (
    <li className="flex items-center gap-4 py-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sky-100 text-accent-700"><Icon className="h-4 w-4" /></span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[15px] text-ink" title={p.title}>{LEG_LABEL[p.leg]} <span className="text-ink-mute">· {hhmm(p.start)}–{hhmm(p.end)}</span></div>
        <div className="truncate text-sm text-ink-mute" title={p.title}>{p.title}</div>
      </div>
      <SupplierBadge name={SUP[p.supplier_id]} small />
      <Tip content={<>Books first time {pct(p.p_secure)} (incl. {p.twins.length} identical backup{p.twins.length === 1 ? "" : "s"} from other suppliers) · {p.cancel}</>}>
        <span className="w-14 cursor-help text-right text-sm tabular-nums text-ink-mute">{pct(p.p_secure, 0)}</span>
      </Tip>
      <div className="w-24 text-right font-semibold tabular-nums">{inr(p.price)}</div>
    </li>
  );
}

export function Timeline({ r }: { r: RemixResult }) {
  const parts = r.parts!;
  const lo = Math.min(...parts.map((p) => p.start)), hi = Math.max(...parts.map((p) => p.end));
  const x = (m: number) => `${((m - lo) / (hi - lo)) * 100}%`;
  return (
    <div className="mt-4">
      <div className="relative h-2 rounded-full bg-paper-warm">
        {parts.map((p) => (
          <span key={p.leg} title={`${LEG_LABEL[p.leg]} ${hhmm(p.start)}–${hhmm(p.end)} · ${SUP[p.supplier_id]}`}
            className={cn("absolute top-0 h-2 rounded-full", p.leg === "ticket" ? "bg-sun-500" : p.leg === "lunch" ? "bg-ok-500" : "bg-accent-700/70")}
            style={{ left: x(p.start), width: `calc(${x(p.end)} - ${x(p.start)})` }} />
        ))}
      </div>
      <div className="mt-2 flex justify-between text-xs text-ink-mute"><span>Pickup {hhmm(lo)}</span><span>{r.timeline!.door_to_door_h} h door to door · arrives {r.timeline!.slack_min} min before the slot</span><span>Back {hhmm(hi)}</span></div>
    </div>
  );
}

export function SameCheck({ r }: { r: RemixResult }) {
  const keys = Object.keys(DNA_LABEL).filter((k) => r.target_dna[k] != null || r.assembled_dna?.[k] != null);
  return (
    <table className="w-full text-[15px]">
      <thead><tr className="text-left text-xs text-ink-mute"><th className="pb-2 font-medium" /><th className="pb-2 font-medium">{r.packaged ? "Package" : "Agents asked for"}</th><th className="pb-2 font-medium">Remix</th><th /></tr></thead>
      <tbody>
        {keys.map((k) => {
          const unv = r.unverified?.includes(k);
          return (
            <tr key={k} className="border-t border-paper-line">
              <td className="py-2 pr-4 text-ink-mute">{DNA_LABEL[k]}</td>
              <td className="py-2 pr-4">{r.target_dna[k] ?? <span className="text-ink-mute">not stated</span>}</td>
              <td className="py-2 pr-4">{r.assembled_dna?.[k] ?? "—"}</td>
              <td className="py-2 text-right">{unv
                ? <span className="inline-flex items-center gap-1 text-xs font-medium text-warn-500"><AlertTriangle className="h-3.5 w-3.5" />a person checks</span>
                : <Check className="ml-auto h-4 w-4 text-ok-500" />}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function PriceBreakdown({ r }: { r: RemixResult }) {
  const pkg = r.packaged!;
  const partsRisk = r.parts!.reduce((t, p) => t + p.tbo_cost - p.price, 0);
  return (
    <div className="grid grid-cols-1 gap-6 text-sm lg:grid-cols-2">
      <div>
        <div className="font-semibold">Package from {SUP[pkg.supplier_id]}: the agent's True Price</div>
        <table className="mt-2 w-full"><tbody>{pkg.terms.terms.map((t) => <tr key={t.key} className="border-t border-paper-line"><td className="py-1.5">{t.label}<div className="text-xs text-ink-mute">{t.assumption}</div></td><td className="text-right tabular-nums">{inr(t.amount)}</td></tr>)}
          <tr className="border-t-2 border-ink/20 font-semibold"><td className="py-1.5">True Price</td><td className="text-right tabular-nums">{inr(pkg.true_price)}</td></tr></tbody></table>
      </div>
      <div>
        <div className="font-semibold">Remix: what TBO expects to pay</div>
        <table className="mt-2 w-full"><tbody>
          {r.parts!.map((p) => <tr key={p.leg} className="border-t border-paper-line"><td className="py-1.5">{LEG_LABEL[p.leg]} · {SUP[p.supplier_id]}<div className="text-xs text-ink-mute">price + its own price-change and failure risk</div></td><td className="text-right tabular-nums">{inr(p.tbo_cost)}</td></tr>)}
          <tr className="border-t border-paper-line"><td className="py-1.5">Assembly risk<div className="text-xs text-ink-mute">{r.assembly_risk!.assumption}</div></td><td className="text-right tabular-nums">{inr(r.assembly_risk!.amount)}</td></tr>
          <tr className="border-t-2 border-ink/20 font-semibold"><td className="py-1.5">TBO's expected cost <span className="font-normal text-ink-mute">(risk in parts {inr(partsRisk)})</span></td><td className="text-right tabular-nums">{inr(r.tbo_cost!)}</td></tr>
          <tr className="border-t border-paper-line"><td className="py-1.5">Agent's True Price: sells at {inr(r.sell!)} + cancellation risk under "{r.cancel}"</td><td className="text-right tabular-nums">{inr(r.agent_true_price!.total)}</td></tr>
        </tbody></table>
        <div className="mt-2 text-xs text-ink-mute">The gap between the package and TBO's cost is split: {pct(r.settings.agent_share, 0)} to the agent, the rest to TBO (Publish rules).</div>
      </div>
    </div>
  );
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
    <div>
      <p className="text-sm text-ink-mute">Set by the product team and applied to every Remix. Change one and every product is re-checked.</p>
      <div className="mt-5 space-y-5">
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
        <ul className="mt-6 space-y-1.5 border-t border-paper-line pt-4">
          <li className="text-xs font-semibold uppercase tracking-wide text-ink-mute">This product</li>
          {checks.map((c) => <li key={c.k} className="flex items-center gap-2 text-sm">{c.ok ? <CheckCircle2 className="h-4 w-4 text-ok-500" /> : <XCircle className="h-4 w-4 text-danger-500" />}
            <span className="flex-1">{c.k}</span><b className="tabular-nums">{c.v}</b></li>)}
          {r?.unverified && r.unverified.length > 0 && <li className="flex items-center gap-2 text-sm"><AlertTriangle className="h-4 w-4 text-warn-500" />Needs approval: package silent on {r.unverified.join(", ")}</li>}
        </ul>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Book Remix
const OUTCOME: Record<string, { label: string; c: string }> = {
  clean: { label: "Confirmed first time", c: "bg-ok-500" }, paid_rise: { label: "Paid a price rise", c: "bg-warn-500" },
  failover: { label: "Part failed over to a SAME twin", c: "bg-accent-500" }, compensated: { label: "Unwound, package bought instead", c: "bg-sun-500" },
  failed: { label: "Failed", c: "bg-danger-500" },
};

export function BookRemix({ r, active, demoSeed, seedNote, withStats = true, trigger = 0 }:
  { r: RemixResult; active: boolean; demoSeed: number; seedNote: string; withStats?: boolean; trigger?: number }) {
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
  useEffect(() => { if (trigger > 0) run(demoSeed); }, [trigger]); // eslint-disable-line react-hooks/exhaustive-deps
  const allSteps = res ? [...res.legs.flatMap((l) => l.steps), ...(res.compensation?.steps ?? [])] : [];
  const done = res && allSteps.every((s) => s.t_ms <= clock);
  const legsInOrder = useMemo(() => res?.legs ?? [], [res]);

  return (
    <section ref={ref} className={cn("scroll-mt-36 rounded-2xl border bg-paper p-5", active || res ? "border-accent-500" : "border-paper-line")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-[640px]">
          <h3 className="text-[16px] font-semibold text-ink">Booking it, live (sandbox)</h3>
          <p className="text-sm text-ink-mute">The riskiest part is booked first. If a part fails, an identical part from another supplier takes over; if none is left, TBO cancels and buys the package so the client still travels.</p>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          <button onClick={() => run(demoSeed)} className="rounded-full bg-accent-700 px-4 py-2 text-sm font-semibold text-white hover:bg-accent-900">{res ? "Book again" : "Book bundle"}</button>
          <button onClick={() => run(Math.floor(Math.random() * 1e6))} className="flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-medium text-ink-soft hover:bg-paper-warm"><Dice5 className="h-4 w-4" />Fresh seed</button>
          {withStats && <button onClick={async () => setStats(await getJSON<RemixStats>(`/api/remix/book/stats?variant_id=${r.variant_id}&runs=1000`))}
            className="flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-medium text-ink-soft hover:bg-paper-warm"><BarChart3 className="h-4 w-4" />Run 1,000×</button>}
        </div>
      </div>
      {res && <div className="mt-1 text-xs text-ink-mute">Scenario seed <span className="font-mono">{seed}</span>. {seed === demoSeed ? seedNote : "A fresh random draw."} Outcomes come from the behaviour model.</div>}
      {err && <div className="mt-3 rounded-lg bg-danger-50 p-3 text-danger-700">{err}</div>}
      <AnimatePresence>
        {done && res && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className={cn("mt-3 flex items-center gap-3 rounded-xl px-4 py-2.5 text-[15px] font-semibold text-white", OUTCOME[res.outcome].c)}>
            <ShieldCheck className="h-5 w-5 shrink-0" />{res.summary}
          </motion.div>
        )}
      </AnimatePresence>
      {res && <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {legsInOrder.map((l) => <LegCard key={l.leg} l={l} clock={clock} />)}
      </div>}
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
    <div className={cn("rounded-xl border p-3", finished ? (l.status === "confirmed" ? "border-ok-500" : "border-danger-500") : "border-paper-line")}>
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
