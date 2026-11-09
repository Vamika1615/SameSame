import { ArrowRight, Boxes, ClipboardCheck, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { ApprovalItem, GapList, HotelSearch, RemixOverview, ReviewItem } from "@/contracts";
import { inr, useApi } from "@/lib/api";
import { CITY } from "@/lib/city";

/** One sentence on what Remix does, then three doors. */
export default function HomePage() {
  const remix = useApi<RemixOverview>("/api/remix");
  const gaps = useApi<GapList>("/api/remix/gaps");
  const hotels = useApi<HotelSearch>("/api/hotels/search");
  const appr = useApi<{ queue: ApprovalItem[] }>("/api/remix/approvals");
  const twins = useApi<ReviewItem[]>("/api/review/queue");
  const best = remix.status === "ready" ? remix.data.items.filter((i) => i.status === "ready").sort((a, b) => (b.agent_saving_inr ?? 0) - (a.agent_saving_inr ?? 0))[0] : null;
  const waiting = (appr.status === "ready" ? appr.data.queue.filter((i) => i.decision === null).length : 0) + (twins.status === "ready" ? twins.data.length : 0);

  return (
    <div className="mx-auto max-w-[1100px] px-8 pb-10 pt-16">
      <div className="text-sm font-medium text-sun-600">For TBO travel agents · {CITY}</div>
      <h1 className="mt-3 max-w-[820px] text-[52px] leading-[1.05] text-ink">
        Sell better trips, built from <span className="italic text-accent-700">parts suppliers already sell.</span>
      </h1>
      <p className="mt-5 max-w-[700px] text-lg leading-relaxed text-ink-soft">
        Suppliers sell the same tour and hotel many times over, under different names. Remix recognises what is really the same,
        then assembles TBO's own version from the most reliable parts: cheaper for the agent, with a margin for TBO.
      </p>

      {best && (
        <Link to="/remix" className="group mt-10 flex flex-wrap items-center gap-6 rounded-3xl border border-paper-line bg-paper p-6 shadow-card transition-shadow hover:shadow-lift">
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold uppercase tracking-wide text-ink-mute">Example</div>
            <div className="mt-1 text-xl font-semibold text-ink">{best.attraction.split(" (")[0]} · {best.name}</div>
            <div className="mt-1 text-ink-mute">Supplier package <span className="line-through">{inr(best.packaged_true_price ?? 0)}</span> → TBO Remix <b className="text-ink">{inr(best.agent_true_price ?? 0)}</b>, from {best.parts} parts by {best.suppliers?.length} suppliers</div>
          </div>
          <div className="flex gap-8">
            <Num label="Agent saves" value={`${((best.agent_saving ?? 0) * 100).toFixed(1)}%`} tone="text-ok-700" />
            <Num label="TBO keeps" value={`${((best.margin ?? 0) * 100).toFixed(1)}%`} tone="text-accent-700" />
          </div>
          <ArrowRight className="h-5 w-5 text-ink-mute transition-transform group-hover:translate-x-1" />
        </Link>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Door to="/remix" icon={<Sparkles className="h-5 w-5" />} title="Remix products"
          text="Rebuild supplier packages for less, and create products agents search for that nobody sells."
          stat={remix.status === "ready" && gaps.status === "ready" ? `${remix.data.counts.ready} packages beaten · ${gaps.data.counts.ready ?? 0} new products` : null} />
        <Door to="/hotels" icon={<Boxes className="h-5 w-5" />} title="Clean catalogue"
          text="See one hotel or tour instead of a page of duplicates, and drop in a supplier's rate sheet to map it."
          stat={hotels.status === "ready" ? `${hotels.data.counters.raw_listings} listings → ${hotels.data.counters.unique_hotels} real hotels` : null} />
        <Door to="/ops" icon={<ClipboardCheck className="h-5 w-5" />} title="Review"
          text="Approve Remixes before they are sold, and settle the matches the model wasn't sure about."
          stat={appr.status === "ready" && twins.status === "ready" ? `${waiting} waiting for a person` : null} />
      </div>

      <div className="mt-8 text-sm text-ink-mute">
        Want the evidence? <Link to="/suppliers" className="font-medium text-accent-700 hover:underline">Supplier reliability</Link> ·{" "}
        <Link to="/simulator" className="font-medium text-accent-700 hover:underline">Business case and matching quality</Link>
      </div>
    </div>
  );
}

function Door({ to, icon, title, text, stat }: { to: string; icon: ReactNode; title: string; text: string; stat: string | null }) {
  return (
    <Link to={to} className="group flex flex-col rounded-3xl border border-paper-line bg-paper p-6 shadow-card transition-shadow hover:shadow-lift">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-50 text-accent-700">{icon}</span>
      <div className="mt-4 flex items-center gap-2 text-lg font-semibold text-ink">{title}<ArrowRight className="h-4 w-4 text-ink-mute transition-transform group-hover:translate-x-1" /></div>
      <p className="mt-1 flex-1 text-[15px] leading-relaxed text-ink-mute">{text}</p>
      <div className="mt-4 min-h-[20px] text-sm font-medium text-ink-soft">{stat}</div>
    </Link>
  );
}

function Num({ label, value, tone }: { label: string; value: string; tone: string }) {
  return <div className="text-right"><div className={`font-display text-3xl font-semibold tabular-nums ${tone}`}>{value}</div><div className="text-xs text-ink-mute">{label}</div></div>;
}
