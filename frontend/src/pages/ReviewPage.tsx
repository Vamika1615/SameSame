import { ArrowRight, UserRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { PendingItem, ReviewItem } from "@/contracts";
import { getJSON, useApi } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Empty, ErrorState, Loading } from "@/components/States";
import { Segmented } from "@/components/ui";
import { TwinQueue } from "@/pages/OpsPage";

/** Catalogue → Uncertain matches: everything Canon wouldn't decide on its own. */
export default function ReviewPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "listings" ? "listings" : "sheets";
  const [items, setItems] = useState<PendingItem[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const twins = useApi<ReviewItem[]>("/api/review/queue");
  const load = useCallback(async () => { try { setItems(await getJSON("/api/catalogue/pending")); } catch (e) { setErr((e as Error).message); } }, []);
  useEffect(() => { load(); }, [load]);
  const decide = async (it: PendingItem, value: string) => {
    await fetch(`/api/imports/${it.import_id}/decide`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sheet_id: it.sheet_id, kind: it.kind, value, room: it.room ?? null }) });
    load();
  };
  return (
    <div className="mx-auto max-w-[1400px] px-8 pb-16 pt-8">
      <PageHeader title="Uncertain matches"
        subtitle="Canon decides on its own only when it's sure. Everything else waits here for a person: a decision takes effect at once, and every one can be undone from its import."
        right={<Segmented size="md" value={tab} onChange={(t) => setParams({ tab: t }, { replace: true })}
          options={[{ value: "sheets", label: <>From imported sheets{items ? <span className="opacity-70"> · {items.length}</span> : null}</> },
                    { value: "listings", label: <>Between supplier listings{twins.status === "ready" ? <span className="opacity-70"> · {twins.data.length}</span> : null}</> }]} />} />
      {tab === "listings" ? <div className="mt-6"><TwinQueue embedded /></div> : (
        <div className="mt-6">
          {err && <ErrorState error={err} onRetry={load} />}
          {!items && !err && <Loading what="Collecting what waits for a person" />}
          {items && items.length === 0 && <Empty title="Nothing waiting">Every hotel and room in your imported sheets is resolved. <Link to="/import" className="text-accent-700 underline">Import another sheet</Link>.</Empty>}
          {items && items.length > 0 && (
            <ul className="space-y-3">
              {items.map((it) => (
                <li key={`${it.import_id}|${it.sheet_id}|${it.room ?? ""}`} className="rounded-2xl border border-paper-line bg-paper p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-xs text-ink-mute">{it.supplier} · {it.file} · {it.import_status === "applied" ? "in the catalogue" : "draft"}</div>
                      <div className="mt-1 text-[17px] font-semibold text-ink">
                        {it.kind === "hotel" ? <>Which hotel is <span className="font-mono">“{it.hotel_as_written}”</span>?</>
                          : <>Which room of {it.hotel} is <span className="font-mono">{it.code ? `${it.code} ` : ""}“{it.room}”</span>?</>}
                      </div>
                      <div className="text-sm text-ink-mute">{it.why}{it.kind === "hotel" && it.rates ? ` · ${it.rooms} rooms, ${it.rates} rates waiting on this` : ""}</div>
                    </div>
                    <Link to={`/import?id=${it.import_id}`} className="inline-flex items-center gap-1 text-xs font-semibold text-accent-700 hover:underline">Open the import<ArrowRight className="h-3.5 w-3.5" /></Link>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <UserRound className="h-4 w-4 text-warn-500" />
                    {it.kind === "hotel" ? (<>
                      {(it.candidates ?? []).map((c) => (
                        <button key={c.cluster_id} onClick={() => decide(it, c.cluster_id)} className="rounded-full border border-paper-line px-3 py-1 text-sm hover:border-accent-500">
                          {c.name}<span className="ml-1 text-xs text-ink-mute">{c.reasons[0]}</span></button>))}
                      <button onClick={() => decide(it, "new")} className="rounded-full border border-paper-line px-3 py-1 text-sm hover:border-accent-500">A new hotel</button>
                    </>) : (<>
                      {(it.options ?? []).map((o) => <button key={o.room_id} onClick={() => decide(it, o.room_id)} className="rounded-full border border-paper-line px-3 py-1 text-sm hover:border-accent-500">{o.name}</button>)}
                      <button onClick={() => decide(it, "new")} className="rounded-full border border-paper-line px-3 py-1 text-sm hover:border-accent-500">A room type they didn't have</button>
                    </>)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
