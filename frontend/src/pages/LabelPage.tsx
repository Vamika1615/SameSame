import { useCallback, useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { Empty, ErrorState, Loading } from "@/components/States";
import { SupplierBadge, cn } from "@/components/ui";

type Side = { id: string; supplier: string; title: string; fields: Record<string, string> };
type Pair = { pair_id: string; entity_type: string; left: Side; right: Side; definitions: Record<"S" | "V" | "D", string> };
type Next = { done: number; total: number; pair: Pair | null };
const KEYS = [["S", "SAME"], ["V", "VARIANT"], ["D", "DIFFERENT"]] as const;

/** Blind-set labelling for C: no model score, no generator label, just the two sides and the definitions. */
export default function LabelPage() {
  const [n, setN] = useState<Next | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { setN(await getJSON<Next>("/api/label/next")); setErr(null); } catch (e) { setErr((e as Error).message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const save = useCallback(async (label: string) => {
    if (!n?.pair || busy) return;
    if (n.pair.entity_type === "hotel" && label === "V") return;
    setBusy(true);
    try {
      const r = await fetch(`/api/label/${n.pair.pair_id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ label, labeller: "C" }) });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      setN(await r.json());
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }, [n, busy]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const k = e.key.toUpperCase();
      if (!e.metaKey && !e.ctrlKey && (k === "S" || k === "V" || k === "D")) save(k);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [save]);

  if (err) return <ErrorState error={err} onRetry={load} />;
  if (!n) return <Loading what="Loading the blind set" />;
  const p = n.pair;
  return (
    <div className="mx-auto max-w-[1300px] px-8 pb-20 pt-6">
      <h1 className="text-3xl font-bold tracking-tight">Blind-set labelling</h1>
      <p className="mt-1 text-ink-mute">For the team's independent check. You won't see the model's answer or the generator's label. Labels go to <code>data/blind/labels.jsonl</code>.</p>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-paper-warm"><div className="h-full bg-accent-500" style={{ width: `${(100 * n.done) / n.total}%` }} /></div>
      <div className="mt-1 text-sm text-ink-mute">{n.done} of {n.total} labelled</div>
      {!p ? <Empty title="All pairs labelled">Thanks. Metrics against your labels appear after the next build (METRICS.md).</Empty> : (
        <div className="mt-5">
          <span className="rounded-md bg-ink px-2 py-0.5 text-sm font-semibold uppercase text-white">{p.entity_type}</span>
          <span className="ml-3 font-mono text-sm text-ink-mute">{p.pair_id}</span>
          <div className="mt-3 grid grid-cols-2 gap-4">
            {[p.left, p.right].map((s) => (
              <div key={s.id} className="rounded-xl border border-paper-line bg-paper p-4">
                <SupplierBadge name={s.supplier} small />
                <div className="mt-1 text-xl font-bold">{s.title}</div>
                <dl className="mt-3 grid grid-cols-[120px_1fr] gap-y-1.5">
                  {Object.entries(s.fields).map(([k, v]) => <div key={k} className="contents"><dt className="text-ink-mute">{k}</dt><dd>{v}</dd></div>)}
                </dl>
              </div>
            ))}
          </div>
          <div className="mt-5 grid grid-cols-3 gap-3">
            {KEYS.map(([k, name]) => {
              const off = p.entity_type === "hotel" && k === "V";
              return (
                <button key={k} disabled={busy || off} onClick={() => save(k)}
                  className={cn("rounded-xl border-2 p-4 text-left transition-colors", off ? "border-paper-line opacity-40" : "border-accent-500 hover:bg-accent-50")}>
                  <div className="text-xl font-bold"><kbd className="mr-2 rounded bg-paper-warm px-2 font-mono">{k}</kbd>{name}</div>
                  <div className="mt-1 text-sm text-ink-soft">{p.definitions[k]}</div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
