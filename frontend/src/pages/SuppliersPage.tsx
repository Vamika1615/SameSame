import type { SupplierRow } from "@/contracts";
import { useApi } from "@/lib/api";
import { Empty, ErrorState, Loading } from "@/components/States";
import { PromiseMeter, SupplierBadge } from "@/components/ui";
import { PageHeader } from "@/components/PageHeader";

export default function SuppliersPage() {
  const res = useApi<SupplierRow[]>("/api/suppliers");
  if (res.status === "loading") return <Loading what="Scoring suppliers" />;
  if (res.status === "error") return <ErrorState error={res.error} onRetry={res.reload} />;
  if (!res.data.length) return <Empty title="No suppliers yet" />;
  return (
    <div className="mx-auto max-w-[1400px] px-8 pb-20 pt-8">
      <PageHeader title="Which suppliers keep their promise"
        subtitle="How often each supplier confirms a booking at the quoted price, 15–45 days out, learned from past booking attempts. A supplier with little history starts near the market average until it earns its own rate. Fictional suppliers, synthetic history." />
      <table className="mt-6 w-full overflow-hidden rounded-2xl border border-paper-line bg-paper">
        <thead className="text-left text-xs text-ink-mute">
          <tr className="border-b border-paper-line">
            <th className="px-4 py-3 font-medium">Supplier</th><th className="px-4 py-3 text-center font-medium">Hotels: confirmed</th><th className="px-4 py-3 text-center font-medium">Tours: confirmed</th>
            <th className="px-4 py-3 text-right font-medium">Booking attempts</th><th className="px-4 py-3 text-right font-medium">Listings that duplicate another</th><th className="px-4 py-3 text-right font-medium">Price spread</th>
          </tr>
        </thead>
        <tbody>
          {res.data.map((r) => (
            <tr key={r.supplier_id} className="border-b border-paper-line last:border-0">
              <td className="px-4 py-3"><SupplierBadge name={r.supplier} /></td>
              <td className="px-4 py-2 text-center"><PromiseMeter rate={r.honour_rate_hotel} n={r.hotel?.n ?? r.n_attempts} lo={r.hotel?.ci_low ?? r.honour_rate_hotel} hi={r.hotel?.ci_high ?? r.honour_rate_hotel} prior={r.hotel?.prior_weight} /></td>
              <td className="px-4 py-2 text-center"><PromiseMeter rate={r.honour_rate_activity} n={r.activity?.n ?? r.n_attempts} lo={r.activity?.ci_low ?? r.honour_rate_activity} hi={r.activity?.ci_high ?? r.honour_rate_activity} prior={r.activity?.prior_weight} /></td>
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
