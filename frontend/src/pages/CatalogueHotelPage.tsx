import { ArrowLeft } from "lucide-react";
import { Link, Navigate, useParams } from "react-router-dom";
import type { CatalogueHotel } from "@/contracts";
import { useApi } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState, Loading } from "@/components/States";
import { RateGrid, Terms } from "@/components/RateGrid";
import { Stars } from "@/components/ui";

/** A hotel that imported sheets added to the catalogue: its rooms, its rates as a clean grid, and its terms. */
export default function CatalogueHotelPage() {
  const { id } = useParams();
  const res = useApi<CatalogueHotel>(`/api/catalogue/hotels/${id}`);
  if (res.status === "loading") return <Loading what="Opening the hotel" />;
  if (res.status === "error") return <ErrorState error={res.error} onRetry={res.reload} />;
  const h = res.data;
  if (h.kind === "inventory") return <Navigate to={`/hotels/${h.id}?tab=sheets`} replace />;
  return (
    <div className="mx-auto max-w-[1400px] px-8 pb-16 pt-6">
      <Link to="/catalogue?source=new" className="inline-flex items-center gap-1 text-sm text-ink-mute hover:text-ink"><ArrowLeft className="h-4 w-4" />All hotels</Link>
      <div className="mt-3">
        <PageHeader title={h.name}
          subtitle={<span className="flex flex-wrap items-center gap-2"><Stars n={h.star} />{h.address ?? "No address in the sheets yet"} · added to the catalogue from {h.sources.length} sheet{h.sources.length === 1 ? "" : "s"}</span>} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {h.sources.map((s) => (
          <Link key={s.import_id + s.as_written} to={`/import?id=${s.import_id}`} className="rounded-full border border-paper-line bg-paper px-3 py-1 text-sm text-ink-soft hover:border-accent-500">
            <b className="text-ink">{s.supplier}</b> · {s.file}{s.as_written !== h.name ? ` · as “${s.as_written}”` : ""}</Link>
        ))}
      </div>
      <section className="mt-6 rounded-2xl border border-paper-line bg-paper p-5">
        <h2 className="text-xl text-ink">Rates</h2>
        <div className="mt-3"><RateGrid rates={h.rates} /></div>
      </section>
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-paper-line bg-paper p-5">
          <h2 className="text-xl text-ink">Rooms · {h.rooms.length}</h2>
          <table className="mt-3 w-full text-sm">
            <thead><tr className="text-left text-xs text-ink-mute"><th className="py-1 font-medium">Code</th><th className="font-medium">Room</th><th className="font-medium">Extra guests and occupancy</th></tr></thead>
            <tbody>{h.rooms.map((r) => (
              <tr key={r.id} className="border-t border-paper-line align-top">
                <td className="py-1.5 pr-3 font-mono text-xs text-accent-700">{r.code ?? "—"}</td>
                <td className="py-1.5 pr-3 font-medium text-ink">{r.name}</td>
                <td className="py-1.5 text-xs text-ink-mute">{Object.entries(r.extras ?? {}).slice(0, 4).map(([k, v]) => `${k}: ${v}`).join(" · ") || "—"}</td>
              </tr>))}</tbody>
          </table>
        </section>
        <section className="rounded-2xl border border-paper-line bg-paper p-5">
          <h2 className="text-xl text-ink">Terms</h2>
          <div className="mt-3"><Terms conditions={h.conditions} /></div>
        </section>
      </div>
    </div>
  );
}
