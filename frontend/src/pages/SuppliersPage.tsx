import type { SupplierRow } from "@/contracts";
import { useApi } from "@/lib/api";
import { Empty, ErrorState, Loading } from "@/components/States";
import { PromiseMeter, SupplierBadge } from "@/components/ui";

export default function SuppliersPage() {
  const res = useApi<SupplierRow[]>("/api/suppliers");
  if (res.status === "loading") return <Loading what="Scoring suppliers" />;
  if (res.status === "error") return <ErrorState error={res.error} onRetry={res.reload} />;
  if (!res.data.length) return <Empty title="No suppliers yet" />;
  return (
    <div className="mx-auto max-w-[1200px] px-8 pb-20 pt-6">
      <h1 className="text-3xl font-bold tracking-tight">Supplier report card</h1>
      <p className="mt-1 text-ink-mute">Honour rate at 15-45 days lead, from booking attempts. Fictional suppliers, synthetic logs.</p>
      <table className="mt-6 w-full overflow-hidden rounded-2xl border border-paper-line bg-paper">
        <thead className="text-left text-sm uppercase tracking-wide text-ink-mute">
          <tr className="border-b border-paper-line">
            <th className="px-4 py-3">Supplier</th><th className="px-4 py-3 text-center">Hotels</th><th className="px-4 py-3 text-center">Activities</th>
            <th className="px-4 py-3 text-right">Attempts</th><th className="px-4 py-3 text-right">Duplicate share</th><th className="px-4 py-3 text-right">Price spread</th>
          </tr>
        </thead>
        <tbody>
          {res.data.map((r) => (
            <tr key={r.supplier_id} className="border-b border-paper-line last:border-0">
              <td className="px-4 py-3"><SupplierBadge name={r.supplier} /></td>
              <td className="px-4 py-2 text-center"><PromiseMeter rate={r.honour_rate_hotel} n={r.hotel?.n ?? r.n_attempts} lo={r.hotel?.ci_low ?? r.honour_rate_hotel} hi={r.hotel?.ci_high ?? r.honour_rate_hotel} /></td>
              <td className="px-4 py-2 text-center"><PromiseMeter rate={r.honour_rate_activity} n={r.activity?.n ?? r.n_attempts} lo={r.activity?.ci_low ?? r.honour_rate_activity} hi={r.activity?.ci_high ?? r.honour_rate_activity} /></td>
              <td className="px-4 py-3 text-right tabular-nums">{r.n_attempts.toLocaleString("en-IN")}</td>
              <td className="px-4 py-3 text-right tabular-nums">{Math.round(r.duplicate_share * 100)}%</td>
              <td className="px-4 py-3 text-right tabular-nums">±{r.price_spread_pct.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
