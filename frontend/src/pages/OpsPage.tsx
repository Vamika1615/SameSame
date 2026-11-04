import { AnimatePresence, motion } from "framer-motion";
import { Flame, ShieldAlert, Undo2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { ReviewAck, ReviewItem, ReviewSide } from "@/contracts";
import { getJSON } from "@/lib/api";
import { Empty, ErrorState, Loading } from "@/components/States";
import { Illustrative, SupplierBadge, cn } from "@/components/ui";

type Audit = { audit_id: string; pair_id: string; label: string; reviewer: string; truth: string; correct: boolean; undone?: boolean };
const LABEL = { S: "SAME", V: "VARIANT", D: "DIFFERENT" } as const;
const ROUTE = { gray_zone: "Gray zone: below the auto-merge bar", llm_unsure: "LLM unsure", constraint_block: "Blocked by a never-merge rule" };

export default function OpsPage() {
  const [queue, setQueue] = useState<ReviewItem[] | null>(null);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [ack, setAck] = useState<(ReviewAck & { label: keyof typeof LABEL; item: ReviewItem }) | null>(null);
  const [streak, setStreak] = useState(0);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [q, a] = await Promise.all([getJSON<ReviewItem[]>("/api/review/queue"), getJSON<Audit[]>("/api/review/audit")]);
      setQueue(q); setAudit(a); setErr(null);
    } catch (e) { setErr((e as Error).message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const current = queue?.[0];
  const label = useCallback(async (l: keyof typeof LABEL) => {
    if (!current || busy || ack) return;
    setBusy(true);
    try {
      const r = await fetch(`/api/review/${current.pair_id}/label`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ label: l, reviewer: "ops" }) });
      const a: ReviewAck = await r.json();
      setAck({ ...a, label: l, item: current }); setStreak(a.streak);
      setAudit(await getJSON<Audit[]>("/api/review/audit"));
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }, [current, busy, ack]);
  const next = useCallback(async () => { setAck(null); await load(); }, [load]);
  const undo = useCallback(async () => {
    const last = audit.find((a) => !a.undone);
    if (!last) return;
    await fetch(`/api/review/undo/${last.audit_id}`, { method: "POST" });
    setAck(null); await load();
  }, [audit, load]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toUpperCase();
      if (ack && (k === "ENTER" || k === "S" || k === "V" || k === "D" || k === " ")) { e.preventDefault(); next(); return; }
      if (k === "S" || k === "V" || k === "D") label(k);
      if (k === "U") undo();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [label, next, undo, ack]);

  if (err) return <ErrorState error={err} onRetry={load} />;
  if (!queue) return <Loading what="Loading the review queue" />;
  const item = ack?.item ?? current;

  return (
    <div className="mx-auto grid max-w-[1600px] grid-cols-1 gap-6 px-8 pb-20 pt-6 xl:grid-cols-[1fr_340px]">
      <div>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Spot the Twin</h1>
            <p className="mt-1 text-ink-mute">Pairs the Twin Finder wasn't sure enough to merge, or that a never-merge rule blocked. Nothing here was auto-merged. <a href="/label" className="underline">Blind-set labelling →</a></p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1.5 font-bold text-amber-700"><Flame className="h-5 w-5" />streak {streak}</div>
            <div className="rounded-full bg-paper px-3 py-1.5 font-semibold text-ink-soft">{queue.length} in queue</div>
          </div>
        </div>

        {!item ? (
          <Empty title="Queue is empty">Every uncertain pair has a human label. Press U to undo the last one.</Empty>
        ) : (
          <div className="mt-5">
            <div className="flex flex-wrap items-center gap-3 rounded-xl border border-paper-line bg-paper px-4 py-3">
              <span className="rounded-md bg-ink px-2 py-0.5 text-sm font-semibold uppercase text-white">{item.entity_type}</span>
              <span className="text-lg">Model says <b>{item.model_relation}</b> at <b className="tabular-nums">{item.model_p.toFixed(2)}</b></span>
              <span className="text-ink-mute">· {ROUTE[item.routed_by]}</span>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <Side s={item.left} other={item.right} />
              <Side s={item.right} other={item.left} />
            </div>
            <ul className="mt-3 space-y-1 text-[15px] text-ink-soft">{item.reasons.map((r) => <li key={r}>• {r}</li>)}</ul>

            <AnimatePresence mode="wait">
              {ack ? (
                <motion.div key="ack" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  className={cn("mt-5 rounded-xl p-5", !ack.model_was_right ? "bg-danger-50" : "bg-ok-50")}>
                  <div className="text-xl font-bold">
                    You said {LABEL[ack.label]} · generator label {ack.truth}
                    {LABEL[ack.label] === ack.truth ? " ✓" : " ✗"}
                  </div>
                  {!ack.model_was_right && (
                    <div className="mt-1 flex items-center gap-2 text-lg font-semibold text-danger-700">
                      <ShieldAlert className="h-5 w-5" />Model error caught: it leaned {item.model_relation} (p {item.model_p.toFixed(2)}). Precision-first routing stopped a wrong merge, so no wrong booking.
                    </div>
                  )}
                  <div className="mt-2 text-sm text-ink-mute">Label {ack.audit_id} saved: the next build trains on it and treats it as a must-link / cannot-link · reversible (U) · any label key or Enter for the next pair.</div>
                </motion.div>
              ) : (
                <motion.div key="keys" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-5 grid grid-cols-3 gap-3">
                  {(["S", "V", "D"] as const).map((k) => (
                    <button key={k} onClick={() => label(k)} disabled={busy}
                      className={cn("rounded-xl border-2 py-4 text-xl font-bold transition-colors",
                        k === "S" ? "border-ok-500 text-ok-700 hover:bg-ok-50" : k === "V" ? "border-amber-500 text-amber-700 hover:bg-amber-50" : "border-danger-500 text-danger-700 hover:bg-danger-50")}>
                      <kbd className="mr-2 rounded bg-paper-warm px-2 font-mono">{k}</kbd>{LABEL[k]}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      <aside className="rounded-2xl border border-paper-line bg-paper p-4">
        <div className="flex items-center justify-between">
          <h2 className="font-bold">Audit log</h2>
          <button onClick={undo} className="flex items-center gap-1 text-sm font-semibold text-ink-soft hover:text-ink"><Undo2 className="h-4 w-4" />Undo (U)</button>
        </div>
        {audit.length === 0 && <div className="mt-3 text-sm text-ink-mute">No labels yet.</div>}
        <ul className="mt-3 space-y-2 text-sm">
          {audit.map((a) => (
            <li key={a.audit_id} className={cn("rounded-lg border border-paper-line px-3 py-2", a.undone && "opacity-40 line-through")}>
              <div className="flex justify-between"><span className="font-mono">{a.audit_id}</span><span>{a.pair_id}</span></div>
              <div className="text-ink-mute">{a.reviewer} labelled {LABEL[a.label as keyof typeof LABEL]} · generator {a.truth}</div>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

function Side({ s, other }: { s: ReviewSide; other: ReviewSide }) {
  return (
    <div className="rounded-xl border border-paper-line bg-paper p-4">
      <div className="flex items-start gap-3">
        {s.image && <Illustrative img={s.image} className="h-20 w-28 shrink-0 rounded-lg" label={false} />}
        <div className="min-w-0">
          <SupplierBadge name={s.supplier} small />
          <div className="mt-1 text-xl font-bold leading-tight">{s.title}</div>
        </div>
      </div>
      <dl className="mt-3 grid grid-cols-[110px_1fr] gap-y-1.5">
        {Object.entries(s.fields).map(([k, v]) => {
          const diff = other.fields[k] !== undefined && other.fields[k] !== v;
          return (
            <div key={k} className="contents">
              <dt className="text-ink-mute">{k}</dt>
              <dd className={cn("font-medium", diff && "rounded bg-amber-100 px-1")}>{v}</dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}
