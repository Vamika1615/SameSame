import { AlertTriangle, Check, Sparkles, Undo2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { ApprovalDecision, ApprovalItem } from "@/contracts";
import { getJSON, inr } from "@/lib/api";
import { ErrorState, Loading } from "@/components/States";
import { MatcherQuality } from "@/components/MatcherQuality";
import { SupplierBadge, cn } from "@/components/ui";
import { SUP, pct } from "@/pages/RemixStudioPage";

const LEG = { ticket: "Ticket", out: "Out", back: "Back", lunch: "Lunch" } as const;

/** The product team approves every Remix before it is published. Decisions are logged, snapshot what was approved, and can be undone. */
export function RemixApprovals() {
  const [data, setData] = useState<{ queue: ApprovalItem[]; history: ApprovalDecision[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setData(await getJSON("/api/remix/approvals")); setErr(null); } catch (e) { setErr((e as Error).message); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const decide = useCallback(async (id: string, decision: "approve" | "reject") => {
    await fetch(`/api/remix/approvals/${encodeURIComponent(id)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision }) });
    load();
  }, [load]);
  const undo = useCallback(async (audit: string) => { await fetch(`/api/remix/approvals/undo/${audit}`, { method: "POST" }); load(); }, [load]);
  const pending = data?.queue.filter((i) => i.decision === null) ?? [];
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || !pending.length) return;
      const k = e.key.toUpperCase();
      if (k === "A") decide(pending[0].variant_id, "approve");
      if (k === "R") decide(pending[0].variant_id, "reject");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pending, decide]);

  if (err) return <ErrorState error={err} onRetry={load} />;
  if (!data) return <Loading what="Loading Remix approvals" />;
  const order = [...data.queue].sort((a, b) => Number(a.decision !== null) - Number(b.decision !== null));
  return (
    <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-3">
        <div className="text-sm text-ink-mute">{pending.length} awaiting a decision · {data.queue.filter((i) => i.decision === "approve").length} published · press <kbd className="rounded bg-paper-warm px-1.5 font-mono">A</kbd> / <kbd className="rounded bg-paper-warm px-1.5 font-mono">R</kbd> for the top one</div>
        {order.map((i) => <Card key={i.variant_id} i={i} onDecide={decide} />)}
        <MatcherQuality />
      </div>
      <aside className="h-fit rounded-3xl border border-paper-line bg-paper p-5 shadow-card">
        <h3 className="font-display text-xl font-semibold text-accent-700">Decision log</h3>
        <p className="text-xs text-ink-mute">Append-only. Each decision keeps a snapshot of the recipe and numbers approved; if a rebuild changes them, the Remix comes back to the queue.</p>
        <ul className="mt-3 space-y-2 text-sm">
          {data.history.length === 0 && <li className="text-ink-mute">No decisions yet.</li>}
          {data.history.slice(0, 12).map((h) => (
            <li key={h.audit_id} className={cn("flex items-center gap-2", h.undone && "line-through opacity-50")}>
              {h.decision === "approve" ? <Check className="h-4 w-4 text-ok-500" /> : <X className="h-4 w-4 text-danger-500" />}
              <span className="min-w-0 flex-1 truncate">{h.variant_id}</span>
              <span className="text-xs text-ink-mute">{h.ts.slice(11, 16)}</span>
              {!h.undone && <button onClick={() => undo(h.audit_id)} title="Undo" className="text-ink-mute hover:text-ink"><Undo2 className="h-4 w-4" /></button>}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

function Card({ i, onDecide }: { i: ApprovalItem; onDecide: (id: string, d: "approve" | "reject") => void }) {
  const r = i.remix;
  const isGap = !r.packaged;
  return (
    <div className={cn("rounded-3xl border bg-paper p-5 shadow-card", i.decision === "approve" ? "border-ok-500" : i.decision === "reject" ? "border-danger-500 opacity-70" : "border-paper-line")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-ink-mute">
            <Sparkles className="h-3.5 w-3.5 text-sun-500" />{isGap ? `Gap Remix · ${r.demand} searches, nobody sells it` : "Remix of a packaged product"}
            {i.stale && <span className="rounded-full bg-warn-50 px-2 text-warn-500">numbers changed since the last decision</span>}
          </div>
          <div className="font-display text-[22px] font-semibold text-accent-700">{r.attraction}</div>
          <div className="text-ink-soft">{r.name}</div>
        </div>
        <div className="flex gap-2">
          {i.decision === null ? (
            <>
              <button onClick={() => onDecide(r.variant_id, "approve")} className="flex items-center gap-1.5 rounded-xl bg-ok-500 px-4 py-2 font-bold text-white hover:bg-ok-700"><Check className="h-4 w-4" />Approve</button>
              <button onClick={() => onDecide(r.variant_id, "reject")} className="flex items-center gap-1.5 rounded-xl border border-paper-line px-4 py-2 font-semibold text-ink-soft hover:bg-paper-warm"><X className="h-4 w-4" />Reject</button>
            </>
          ) : <span className={cn("rounded-full px-3 py-1 text-sm font-bold uppercase", i.decision === "approve" ? "bg-ok-50 text-ok-700" : "bg-danger-50 text-danger-700")}>{i.decision === "approve" ? "Published" : "Rejected"}</span>}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {r.parts?.map((p) => (
          <span key={p.leg} className="flex items-center gap-1.5 rounded-full border border-paper-line bg-paper-warm px-3 py-1 text-sm">
            <b>{LEG[p.leg]}</b><SupplierBadge name={SUP[p.supplier_id]} small /><span className="tabular-nums">{inr(p.price)}</span>
            <span className="text-xs text-ink-mute">{pct(p.p_secure)}</span>
          </span>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-sm md:grid-cols-5">
        <Fact k="Sell to agent" v={inr(r.sell ?? 0)} />
        <Fact k="TBO margin" v={`${pct(r.margin)} · ${inr(r.margin_inr ?? 0)}`} />
        <Fact k={isGap ? "Agent saves vs DIY" : "Agent saves"} v={`${pct(r.agent_saving)}`} />
        <Fact k="Remix Promise" v={pct(r.promise)} />
        <Fact k="Cancellation" v={r.cancel ?? "—"} />
      </div>
      {r.unverified && r.unverified.length > 0 && (
        <div className="mt-2 flex items-center gap-2 rounded-xl bg-warn-50 px-3 py-2 text-sm text-warn-500"><AlertTriangle className="h-4 w-4" />
          Check before approving: the package doesn't state {r.unverified.join(", ")}; the Remix's is {r.unverified.map((k) => r.assembled_dna?.[k]).join(", ")}.</div>
      )}
    </div>
  );
}

function Fact({ k, v }: { k: string; v: string }) {
  return <div className="rounded-xl bg-paper-warm px-3 py-1.5"><div className="text-[11px] uppercase text-ink-mute">{k}</div><div className="font-semibold tabular-nums">{v}</div></div>;
}
