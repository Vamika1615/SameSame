import { ArrowRight, Check, ChevronDown, Download, FileSpreadsheet, Loader2, RefreshCw, Repeat2, RotateCcw, Trash2, Undo2, Upload, UserRound } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { ImportHotel, ImportMeta, ImportRoom, ImportSample, ImportView } from "@/contracts";
import { getJSON } from "@/lib/api";
import { usePresenterAction } from "@/lib/presenter";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState, Loading } from "@/components/States";
import { LAYOUT_LABEL, StatusPill, Terms } from "@/components/RateGrid";
import { Tip, cn } from "@/components/ui";

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail ?? `${r.status} ${r.statusText}`);
  return body as T;
}
const post = <T,>(url: string, json?: unknown) => call<T>(url, { method: "POST", headers: json ? { "Content-Type": "application/json" } : undefined, body: json ? JSON.stringify(json) : undefined });
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const money = (n: number | null, cur: string | null) => n == null ? "—" : `${cur === "USD" ? "$" : cur === "INR" ? "₹" : ""}${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

/** The heart of Canon: a supplier's rate sheet in, a clean catalogue out. */
export default function ImportPage() {
  const [params, setParams] = useSearchParams();
  const [list, setList] = useState<{ imports: ImportMeta[]; samples: ImportSample[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const selected = params.get("id") ?? list?.imports[0]?.id ?? null;
  const select = useCallback((id: string) => { const n = new URLSearchParams(params); n.set("id", id); setParams(n, { replace: true }); }, [params, setParams]);
  const refresh = useCallback(async () => { try { setList(await getJSON("/api/imports")); } catch (e) { setErr((e as Error).message); } }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const run = useCallback(async (p: Promise<{ created: boolean; import: ImportView }>) => {
    setBusy(true); setErr(null);
    try { const r = await p; await refresh(); select(r.import.meta.id); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }, [refresh, select]);
  const upload = (f: File, supplier: string) => { const fd = new FormData(); fd.append("file", f); if (supplier) fd.append("supplier", supplier); run(call("/api/imports", { method: "POST", body: fd })); };
  const sample = useCallback((name: string) => run(post(`/api/imports/samples/${name}`)), [run]);
  usePresenterAction(useCallback(() => sample("plover"), [sample]));

  return (
    <div className="mx-auto max-w-[1400px] px-8 pb-16 pt-8">
      <PageHeader title="Import supplier sheets"
        subtitle="Drop in a supplier's rate sheet, whatever its layout. Canon reads every hotel, room, season and rate, matches them to your catalogue, and asks a person only when it isn't sure." />
      <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-6 lg:sticky lg:top-[132px] lg:self-start">
          <UploadBox busy={busy} onUpload={upload} />
          {list && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-ink-mute">No sheet handy? Try a sample</div>
              <div className="mt-2 space-y-2">
                {list.samples.map((s) => (
                  <div key={s.name} className="rounded-xl border border-paper-line bg-paper p-3">
                    <button onClick={() => sample(s.name)} disabled={busy} className="flex w-full items-center justify-between text-left text-sm font-semibold text-accent-700 hover:underline disabled:opacity-50">
                      {s.supplier}'s sheet<ArrowRight className="h-4 w-4" /></button>
                    <div className="text-xs text-ink-mute">{s.description}. Synthetic. {Object.entries(s.files).map(([f, u]) => <a key={f} href={u} className="ml-1 underline">{f.toUpperCase()}</a>)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          <ImportList list={list?.imports ?? null} selected={selected} onSelect={select} />
        </aside>
        <div className="min-w-0">
          {err && <div className="mb-4 rounded-xl border border-danger-500/30 bg-danger-50 px-4 py-3 text-sm text-danger-700">{err}</div>}
          {busy && <div className="mb-4 flex items-center gap-2 text-ink-mute"><Loader2 className="h-4 w-4 animate-spin" />Reading the sheet and matching every hotel and room against the catalogue…</div>}
          {selected ? <ImportDetail key={selected} id={selected} onChange={refresh} /> : list && <Welcome />}
        </div>
      </div>
    </div>
  );
}

function UploadBox({ busy, onUpload }: { busy: boolean; onUpload: (f: File, supplier: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [supplier, setSupplier] = useState("");
  return (
    <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) onUpload(f, supplier); }}
      className={cn("rounded-2xl border-2 border-dashed bg-paper p-5 transition-colors", drag ? "border-sun-500 bg-sun-50" : "border-paper-line")}>
      <FileSpreadsheet className="h-8 w-8 text-accent-500" />
      <div className="mt-2 font-semibold">Drop a rate sheet here</div>
      <div className="text-sm text-ink-mute">CSV or Excel. Price grids, one-row-per-rate sheets and multi-tab workbooks all work.</div>
      <input value={supplier} onChange={(e) => setSupplier(e.target.value)} placeholder="Supplier name (optional)"
        className="mt-3 w-full rounded-lg border border-paper-line bg-paper px-3 py-1.5 text-sm" />
      <input ref={input} type="file" accept=".csv,.xlsx,.xlsm,.txt" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f, supplier); e.target.value = ""; }} />
      <button onClick={() => input.current?.click()} disabled={busy}
        className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-full bg-accent-700 px-4 py-2 text-sm font-semibold text-white hover:bg-accent-900 disabled:opacity-60">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}Choose a file</button>
    </div>
  );
}

function ImportList({ list, selected, onSelect }: { list: ImportMeta[] | null; selected: string | null; onSelect: (id: string) => void }) {
  if (!list) return <Loading what="Loading imports" />;
  if (!list.length) return null;
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-ink-mute">Imports · {list.length}</div>
      <ul className="mt-2 space-y-0.5">
        {list.map((m) => (
          <li key={m.id}>
            <button onClick={() => onSelect(m.id)} className={cn("w-full rounded-xl px-3 py-2 text-left transition-colors", selected === m.id ? "bg-accent-700 text-white" : "hover:bg-paper")}>
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-[15px] font-medium">{m.supplier}</span>
                {selected !== m.id && <StatusPill status={m.status} />}
              </div>
              <div className={cn("truncate text-xs", selected === m.id ? "text-white/75" : "text-ink-mute")}>{m.file}</div>
              <div className={cn("text-xs", selected === m.id ? "text-white/75" : "text-ink-mute")}>{when(m.uploaded_at)} · {m.summary.names} hotels · {(m.summary.rates ?? 0).toLocaleString("en-IN")} rates</div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Welcome() {
  return (
    <div className="rounded-3xl border border-paper-line bg-paper p-8">
      <h2 className="text-2xl text-ink">How it works</h2>
      <ol className="mt-4 space-y-3 text-[15px] text-ink-soft">
        <li><b className="text-ink">1. Drop in a sheet.</b> Canon finds the hotels, rooms, room codes, seasons, weekday and occupancy prices, rate plans (one per tab) and the terms in the footnotes.</li>
        <li><b className="text-ink">2. Check what it matched.</b> Each hotel is matched to your catalogue, to a hotel an earlier sheet added, or marked new. Each room maps to that hotel's rooms. Anything uncertain is left for a person.</li>
        <li><b className="text-ink">3. Add it to the catalogue.</b> Rates appear on the hotel's page. Remove the import any time to take them back out.</li>
      </ol>
    </div>
  );
}

function ImportDetail({ id, onChange }: { id: string; onChange: () => void }) {
  const [v, setV] = useState<ImportView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "person" | "new" | "matched">("all");
  const load = useCallback(async () => { try { setV(await getJSON(`/api/imports/${id}`)); } catch (e) { setErr((e as Error).message); } }, [id]);
  useEffect(() => { load(); }, [load]);
  const act = async (action: string) => {
    setBusy(action);
    try { setV(await post(`/api/imports/${id}/${action}`)); onChange(); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };
  const decide = async (body: { sheet_id: string; kind: "hotel" | "room"; value: string; room?: string }) => {
    try { setV(await post(`/api/imports/${id}/decide`, body)); } catch (e) { setErr((e as Error).message); }
  };
  const undo = async (audit: string) => { await post(`/api/imports/decisions/undo/${audit}`); load(); };
  if (err) return <ErrorState error={err} onRetry={load} />;
  if (!v) return <Loading what="Opening the import" />;
  const m = v.meta, s = v.summary, p = v.progress;
  const needs = (h: ImportHotel) => h.final === null || h.rooms.some((r) => r.status === "person");
  const shown = v.hotels.filter((h) => filter === "all" || (filter === "person" && needs(h)) || (filter === "new" && h.final?.kind === "new")
    || (filter === "matched" && h.final && h.final.kind !== "new"));
  return (
    <div className="space-y-5">
      <section className="rounded-3xl border border-paper-line bg-paper p-6 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2"><StatusPill status={m.status} /><span className="text-xs text-ink-mute">uploaded {when(m.uploaded_at)}{m.applied_at && m.status === "applied" ? ` · added ${when(m.applied_at)}` : ""}</span></div>
            <h2 className="mt-2 truncate text-[28px] leading-tight text-ink">{m.supplier}</h2>
            <div className="truncate text-sm text-ink-mute">{m.file}</div>
          </div>
          <div className="flex flex-wrap items-center gap-1">
            {m.status === "draft" && <button onClick={() => act("apply")} disabled={!!busy} className="flex items-center gap-2 rounded-full bg-accent-700 px-5 py-2 font-semibold text-white hover:bg-accent-900 disabled:opacity-60">
              {busy === "apply" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}Add to catalogue</button>}
            {m.status === "applied" && <button onClick={() => act("remove")} disabled={!!busy} className="flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-medium text-ink-soft hover:bg-paper-warm"><Trash2 className="h-4 w-4" />Remove from catalogue</button>}
            {m.status === "removed" && <button onClick={() => act("restore")} disabled={!!busy} className="flex items-center gap-1.5 rounded-full border border-paper-line px-3 py-2 text-sm font-medium text-ink-soft hover:border-accent-500"><RotateCcw className="h-4 w-4" />Restore as draft</button>}
            <Tip content="Read the stored file again against today's catalogue (after a rebuild, or after other sheets were added)">
              <button onClick={() => act("recheck")} disabled={!!busy} className="flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-medium text-ink-soft hover:bg-paper-warm">
                <RefreshCw className={cn("h-4 w-4", busy === "recheck" && "animate-spin")} />Re-check</button></Tip>
            <a href={`/api/imports/${id}/source`} className="flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-medium text-ink-soft hover:bg-paper-warm"><Download className="h-4 w-4" />Original</a>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <span className="rounded-full bg-sky-100 px-2.5 py-1 font-medium text-accent-700">{LAYOUT_LABEL[v.layout] ?? v.layout}</span>
          <span className="rounded-full bg-sky-100 px-2.5 py-1 font-medium text-accent-700">{v.currency ?? "currency not stated"}</span>
          {v.tabs.filter((t) => t.layout).map((t) => <span key={t.tab} className="rounded-full border border-paper-line px-2.5 py-1 text-ink-soft">tab “{t.tab}”{t.rates ? ` · ${t.rates.toLocaleString("en-IN")} rates` : ""}</span>)}
        </div>
        {v.warnings.length > 0 && <ul className="mt-3 space-y-1 rounded-xl bg-warn-50 px-4 py-2 text-sm text-warn-500">{v.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
        <div className="mt-5 grid grid-cols-2 gap-4 border-t border-paper-line pt-5 md:grid-cols-4">
          <Num label="Rates read" value={s.rates.toLocaleString("en-IN")} />
          <Num label="Hotels" value={`${s.names}`} sub={`${s.matched} matched · ${s.new} new · ${s.review} for a person`} />
          <Num label="Rooms" value={`${s.room_names}`} sub={`${s.rooms_mapped} mapped · ${s.rooms_new} new · ${s.rooms_person} for a person`} />
          <Num label="Still waiting" value={`${p.waiting}`} sub={p.waiting ? "decide below, or in Uncertain matches" : "nothing left to decide"} tone={p.waiting ? "text-warn-500" : "text-ok-700"} />
        </div>
        {v.check && <div className="mt-4 rounded-xl bg-ok-50 px-4 py-2.5 text-sm text-ok-700">
          Checked against this synthetic sample's answer key: {v.check.hotels.matched_right}/{v.check.hotels.matched_right + v.check.hotels.matched_wrong} automatic hotel matches and {v.check.rooms.mapped_right}/{v.check.rooms.mapped_right + v.check.rooms.mapped_wrong} automatic room mappings are right.</div>}
        {m.status === "draft" && <div className="mt-4 text-sm text-ink-mute">This is a draft: nothing is in the catalogue yet. Check the matches below, then <b className="text-ink">Add to catalogue</b>. Hotels still waiting for a person are added once decided.</div>}
      </section>

      <div className="flex flex-wrap items-center gap-2">
        {([["all", "All hotels", v.hotels.length], ["person", "Needs a person", v.hotels.filter(needs).length], ["matched", "Matched", v.hotels.filter((h) => h.final && h.final.kind !== "new").length],
           ["new", "New to the catalogue", v.hotels.filter((h) => h.final?.kind === "new").length]] as const).map(([k, l, n]) => (
          <button key={k} onClick={() => setFilter(k)} className={cn("rounded-full border px-3.5 py-1.5 text-sm", filter === k ? "border-accent-700 bg-accent-700 text-white" : "border-paper-line bg-paper text-ink-soft hover:border-accent-500")}>
            {l} <span className="opacity-70">{n}</span></button>))}
      </div>
      <ul className="space-y-3">
        {shown.map((h) => <HotelRow key={h.sheet_id} h={h} currency={v.currency} applied={m.status === "applied"} onDecide={decide} onUndo={undo} />)}
        {!shown.length && <li className="rounded-2xl bg-paper px-5 py-6 text-ink-mute">Nothing here.</li>}
      </ul>
    </div>
  );
}

function Num({ label, value, sub, tone = "text-ink" }: { label: string; value: string; sub?: string; tone?: string }) {
  return <div><div className="text-xs text-ink-mute">{label}</div><div className={cn("text-2xl font-semibold tabular-nums", tone)}>{value}</div>{sub && <div className="text-xs text-ink-mute">{sub}</div>}</div>;
}

function HotelRow({ h, currency, applied, onDecide, onUndo }: { h: ImportHotel; currency: string | null; applied: boolean;
  onDecide: (b: { sheet_id: string; kind: "hotel" | "room"; value: string; room?: string }) => void; onUndo: (audit: string) => void }) {
  const waiting = h.final === null || h.rooms.some((r) => r.status === "person");
  const [open, setOpen] = useState(waiting);
  const top = h.candidates[0];
  const pill = h.final === null ? ["Needs a person", "bg-warn-50 text-warn-500"] : h.by_person ? ["Decided", "bg-ok-50 text-ok-700"]
    : h.final.kind === "new" ? ["New hotel", "bg-sky-100 text-accent-700"] : ["Matched", "bg-ok-50 text-ok-700"];
  const link = h.final && applied ? (h.final.kind === "inventory" ? `/hotels/${h.final.id}?tab=sheets` : h.final.id ? `/catalogue/hotels/${h.final.id}` : null) : null;
  return (
    <li className="rounded-2xl border border-paper-line bg-paper">
      <button onClick={() => setOpen(!open)} className="grid w-full grid-cols-[minmax(0,1fr)_24px_minmax(0,1.2fr)_auto] items-center gap-4 px-5 py-3.5 text-left">
        <div className="min-w-0">
          <div className="truncate font-mono text-[15px] font-semibold">{h.name}</div>
          <div className="truncate text-xs text-ink-mute">{h.rooms.length} rooms · {h.rooms.reduce((t, r) => t + r.rate_count, 0)} rates{h.rate_plans.length > 1 ? ` · ${h.rate_plans.length} rate plans` : ""}{h.lat == null ? " · no location in the sheet" : ""}</div>
        </div>
        <ArrowRight className="h-5 w-5 text-ink-mute" />
        <div className="min-w-0">
          <div className="truncate text-[17px] font-semibold text-accent-700">
            {h.final ? (h.final.kind === "new" ? <>New hotel: {h.final.name}</> : h.final.name) : <>{top?.name ?? "?"}<span className="text-ink-mute">?</span></>}
          </div>
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {(h.final?.kind === "new" ? [] : top?.reasons ?? []).slice(0, 3).map((x, i) => <span key={i} className={cn("rounded-full px-2 py-0.5 text-xs", x.includes(" read as ") ? "bg-sun-100 font-semibold text-sun-700" : "bg-sky-50 text-ink-soft")}>{x}</span>)}
            {top?.kind === "imported" && h.final?.kind !== "new" && <span className="rounded-full bg-sand-200 px-2 py-0.5 text-xs font-medium text-ink-soft">added by an earlier sheet</span>}
            {h.also_as && <span className="inline-flex items-center gap-1 rounded-full bg-sand-200 px-2 py-0.5 text-xs font-semibold text-ink-soft"><Repeat2 className="h-3 w-3" />also in this sheet as “{h.also_as.join("”, “")}”</span>}
            {h.name_from_file && <span className="rounded-full bg-warn-50 px-2 py-0.5 text-xs text-warn-500">name taken from the file</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn("rounded-full px-3 py-1 text-xs font-semibold", pill[1])}>{pill[0]}</span>
          <ChevronDown className={cn("h-5 w-5 text-ink-mute transition-transform", open && "rotate-180")} />
        </div>
      </button>
      {open && (
        <div className="border-t border-paper-line px-5 pb-5 pt-3">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-ink-soft">
            <span>{h.why}{h.address && <span className="text-ink-mute"> · {h.address}</span>}</span>
            <span className="flex items-center gap-3">
              {h.by_person && h.audit_id && <button onClick={() => onUndo(h.audit_id!)} className="inline-flex items-center gap-1 text-xs font-medium text-ink-mute hover:text-ink"><Undo2 className="h-3.5 w-3.5" />Undo decision</button>}
              {link && <Link to={link} className="inline-flex items-center gap-1 text-xs font-semibold text-accent-700 hover:underline">Open in catalogue<ArrowRight className="h-3.5 w-3.5" /></Link>}
            </span>
          </div>
          {h.final === null && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <UserRound className="h-4 w-4 text-warn-500" /><span className="text-sm font-semibold">Which hotel is this?</span>
              {h.candidates.map((c) => (
                <button key={c.cluster_id} onClick={() => onDecide({ sheet_id: h.sheet_id, kind: "hotel", value: c.cluster_id })}
                  className="rounded-full border border-paper-line px-3 py-1 text-sm hover:border-accent-500">{c.name}<span className="ml-1 text-xs text-ink-mute">{c.kind === "imported" ? "from a sheet" : c.p != null ? `p ${c.p.toFixed(2)}` : ""}</span></button>))}
              <button onClick={() => onDecide({ sheet_id: h.sheet_id, kind: "hotel", value: "new" })} className="rounded-full border border-paper-line px-3 py-1 text-sm hover:border-accent-500">A new hotel</button>
            </div>
          )}
          <table className="mt-3 w-full text-[15px]">
            <thead><tr className="text-left text-xs text-ink-mute"><th className="py-1 font-medium">Room as written</th><th className="font-medium">In the catalogue</th><th className="font-medium">Why</th><th className="text-right font-medium">Rates</th></tr></thead>
            <tbody>{h.rooms.map((r) => <RoomRow key={r.raw} r={r} h={h} currency={currency} onDecide={onDecide} onUndo={onUndo} />)}</tbody>
          </table>
          {h.conditions.length > 0 && <div className="mt-4"><div className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-mute">Terms on the sheet</div><Terms conditions={h.conditions} /></div>}
        </div>
      )}
    </li>
  );
}

function RoomRow({ r, h, currency, onDecide, onUndo }: { r: ImportRoom; h: ImportHotel; currency: string | null;
  onDecide: (b: { sheet_id: string; kind: "hotel" | "room"; value: string; room?: string }) => void; onUndo: (audit: string) => void }) {
  const canPick = r.status === "person" && h.final !== null && h.options.length > 0;
  return (
    <tr className="border-t border-paper-line/70 align-top">
      <td className="py-1.5 pr-3 text-sm">{r.code && <span className="mr-1.5 rounded bg-sky-100 px-1.5 font-mono text-xs text-accent-700">{r.code}</span>}<span className="font-mono">{r.raw}</span></td>
      <td className="py-1.5 pr-3 text-sm">
        {r.status === "mapped" ? <span className="font-semibold text-ok-700">{r.room}</span>
          : r.status === "new" ? <span className="text-accent-700">New room</span>
          : canPick ? (
            <select value="" onChange={(e) => onDecide({ sheet_id: h.sheet_id, kind: "room", value: e.target.value, room: r.raw })}
              className="max-w-[260px] rounded-lg border border-warn-500 bg-warn-50 px-2 py-1 text-sm">
              <option value="">Pick the room…</option>
              {h.options.map((o) => <option key={o.room_id} value={o.room_id}>{o.name}</option>)}
              <option value="new">A room type they didn't have</option>
            </select>)
          : <span className="text-warn-500">waits for the hotel decision</span>}
      </td>
      <td className="py-1.5 pr-3 text-sm text-ink-soft">{r.why}{r.decided && r.audit_id && <button onClick={() => onUndo(r.audit_id!)} className="ml-2 text-xs text-ink-mute hover:text-ink">undo</button>}</td>
      <td className="whitespace-nowrap py-1.5 text-right text-sm tabular-nums text-ink-soft">{r.rate_count ? <>{r.rate_count} · from {money(r.price_from, currency)}</> : "—"}</td>
    </tr>
  );
}
