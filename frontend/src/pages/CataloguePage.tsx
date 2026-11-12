import { ArrowRight, FileSpreadsheet, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { CatalogueList } from "@/contracts";
import { useApi } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState, Loading } from "@/components/States";
import { Segmented, Stars, cn } from "@/components/ui";

/** Every hotel in the catalogue: from suppliers' feeds (past inventory) and from imported sheets. */
export default function CataloguePage() {
  const [params, setParams] = useSearchParams();
  const source = params.get("source") ?? "all";
  const [q, setQ] = useState(params.get("q") ?? "");
  const [debounced, setDebounced] = useState(q);
  useEffect(() => { const t = setTimeout(() => setDebounced(q), 200); return () => clearTimeout(t); }, [q]);
  const res = useApi<CatalogueList>(`/api/catalogue/hotels?${new URLSearchParams({ ...(debounced ? { q: debounced } : {}), ...(source !== "all" ? { source } : {}) })}`);
  const setSource = (s: string) => { const n = new URLSearchParams(params); if (s === "all") n.delete("source"); else n.set("source", s); setParams(n, { replace: true }); };
  const c = res.status === "ready" ? res.data.counts : null;
  return (
    <div className="mx-auto max-w-[1400px] px-8 pb-16 pt-8">
      <PageHeader title={c ? <>{(c.inventory + c.imported).toLocaleString("en-IN")} hotels in your catalogue</> : "Your catalogue"}
        subtitle={c ? <>{c.listings.toLocaleString("en-IN")} supplier listings consolidated into {c.inventory} hotels, plus {c.imported} added from imported sheets. {c.with_sheets} carry contracted rates from a sheet.</> : "Loading…"}
        right={<Link to="/import" className="inline-flex items-center gap-2 rounded-full bg-accent-700 px-4 py-2 text-sm font-semibold text-white hover:bg-accent-900"><FileSpreadsheet className="h-4 w-4" />Import a sheet</Link>} />
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <label className="flex min-w-[280px] flex-1 items-center gap-2 rounded-full border border-paper-line bg-paper px-4 py-2">
          <Search className="h-4 w-4 text-ink-mute" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search hotels by name" className="w-full bg-transparent text-[15px] outline-none" />
        </label>
        <Segmented size="md" value={source} onChange={setSource}
          options={[{ value: "all", label: "All" }, { value: "sheets", label: "With sheet rates" }, { value: "new", label: "Added from sheets" }]} />
      </div>
      {res.status === "loading" && <Loading what="Reading the catalogue" />}
      {res.status === "error" && <ErrorState error={res.error} onRetry={res.reload} />}
      {res.status === "ready" && (
        <div className="mt-4 overflow-hidden rounded-2xl border border-paper-line bg-paper">
          <table className="w-full text-[15px]">
            <thead className="bg-paper-warm/60 text-left text-xs text-ink-mute">
              <tr><th className="px-4 py-2.5 font-medium">Hotel</th><th className="px-4 font-medium">From supplier feeds</th><th className="px-4 font-medium">From imported sheets</th>
                <th className="px-4 text-right font-medium">Rooms</th><th className="px-4 text-right font-medium">Sheet rates</th><th className="w-8" /></tr>
            </thead>
            <tbody>
              {res.data.items.slice(0, 400).map((h) => (
                <tr key={h.id} className="group border-t border-paper-line hover:bg-paper-warm/40">
                  <td className="px-4 py-2.5">
                    <Link to={h.kind === "imported" ? `/catalogue/hotels/${h.id}` : `/hotels/${h.id}${h.sheets.length ? "?tab=sheets" : ""}`} className="font-medium text-ink group-hover:text-accent-700">{h.name}</Link>
                    <div className="flex items-center gap-2 text-xs text-ink-mute"><Stars n={h.star} />{h.kind === "imported" && <span className="rounded-full bg-sky-100 px-2 font-medium text-accent-700">new from a sheet</span>}</div>
                  </td>
                  <td className="px-4 text-sm text-ink-soft">{h.listings ? <>{h.listings} listings · {h.suppliers.length} suppliers</> : <span className="text-ink-mute">—</span>}</td>
                  <td className="px-4 text-sm">{h.sheets.length ? h.sheets.map((s) => <span key={s} className="mr-1 inline-block rounded-full border border-paper-line px-2 py-0.5 text-xs">{s}</span>) : <span className="text-ink-mute">—</span>}</td>
                  <td className="px-4 text-right tabular-nums text-ink-soft">{h.rooms}</td>
                  <td className={cn("px-4 text-right tabular-nums", h.rates ? "font-semibold text-ink" : "text-ink-mute")}>{h.rates ? h.rates.toLocaleString("en-IN") : "—"}</td>
                  <td className="pr-3"><ArrowRight className="h-4 w-4 text-ink-mute opacity-0 group-hover:opacity-100" /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {res.data.shown === 0 && <div className="px-4 py-6 text-ink-mute">No hotels match.</div>}
          {res.data.shown > 400 && <div className="border-t border-paper-line px-4 py-2 text-sm text-ink-mute">Showing 400 of {res.data.shown}. Search to narrow it down.</div>}
        </div>
      )}
    </div>
  );
}
