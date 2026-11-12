import { ArrowRight, FileSpreadsheet, Layers, Sparkles, UserRound } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { CatalogueSummary, ReviewItem } from "@/contracts";
import { useApi } from "@/lib/api";

/** Canon in one sentence, the catalogue's state in four numbers, and where to start. */
export default function HomePage() {
  const s = useApi<CatalogueSummary>("/api/catalogue/summary");
  const twins = useApi<ReviewItem[]>("/api/review/queue");
  const d = s.status === "ready" ? s.data : null;
  const waiting = (d?.waiting ?? 0) + (twins.status === "ready" ? twins.data.length : 0);
  return (
    <div className="mx-auto max-w-[1100px] px-8 pb-12 pt-16">
      <div className="text-sm font-medium text-sun-600">For TBO's supply and catalogue teams</div>
      <h1 className="mt-3 max-w-[860px] text-[52px] leading-[1.05] text-ink">
        Every supplier sheet, <span className="italic text-accent-700">one clean catalogue.</span>
      </h1>
      <p className="mt-5 max-w-[720px] text-lg leading-relaxed text-ink-soft">
        Suppliers send rate sheets in every layout and name the same hotel a dozen ways. Canon reads each sheet, matches every hotel
        and room to what you already sell, keeps the differences that matter, and asks a person only when it isn't sure.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link to="/import" className="inline-flex items-center gap-2 rounded-full bg-accent-700 px-6 py-3 font-semibold text-white hover:bg-accent-900">
          <FileSpreadsheet className="h-5 w-5" />Import a supplier sheet</Link>
        <Link to="/catalogue" className="inline-flex items-center gap-2 rounded-full border border-paper-line bg-paper px-6 py-3 font-semibold text-ink-soft hover:border-accent-500">
          Browse the catalogue<ArrowRight className="h-4 w-4" /></Link>
      </div>

      <div className="mt-12 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Hotels in the catalogue" value={d ? (d.inventory_hotels + d.imported_hotels).toLocaleString("en-IN") : "…"} sub={d ? `${d.imported_hotels} added from sheets` : ""} />
        <Stat label="Supplier listings consolidated" value={d ? d.listings.toLocaleString("en-IN") : "…"} sub="duplicates merged into one hotel each" />
        <Stat label="Contracted rates from sheets" value={d ? d.sheet_rates.toLocaleString("en-IN") : "…"} sub={d ? `${d.imports.applied} sheet${d.imports.applied === 1 ? "" : "s"} imported` : ""} />
        <Stat label="Waiting for a person" value={d ? `${waiting}` : "…"} sub="uncertain matches" tone={waiting ? "text-warn-500" : "text-ok-700"} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Door to="/import" icon={<FileSpreadsheet className="h-5 w-5" />} title="1 · Import sheets"
          text="Price grids, one-row-per-rate sheets and multi-tab workbooks: hotels, room codes, seasons, weekday and occupancy prices, rate plans and footnote terms." />
        <Door to="/catalogue" icon={<Layers className="h-5 w-5" />} title="2 · One catalogue"
          text="Every hotel once, however many suppliers sell it: duplicates merged, look-alikes kept apart, rooms mapped, offers compared on what they really cost." />
        <Door to="/catalogue/review" icon={<UserRound className="h-5 w-5" />} title="3 · People decide the rest"
          text="Anything uncertain waits for a person. Every decision is logged and can be undone, and it teaches the next build." />
      </div>

      <Link to="/remix" className="group mt-8 flex items-center gap-4 rounded-2xl border border-paper-line bg-paper/60 px-5 py-4 transition-colors hover:bg-paper">
        <Sparkles className="h-5 w-5 shrink-0 text-sun-500" />
        <span className="flex-1 text-[15px] text-ink-soft"><b className="text-ink">What a clean catalogue makes possible: Bundles.</b> Once Canon knows which parts are truly the same, it can rebuild a supplier's tour package from other suppliers' parts, cheaper for the agent and still profitable for TBO.</span>
        <ArrowRight className="h-4 w-4 text-ink-mute transition-transform group-hover:translate-x-1" />
      </Link>
    </div>
  );
}

function Stat({ label, value, sub, tone = "text-ink" }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="rounded-2xl border border-paper-line bg-paper p-5">
      <div className={`font-display text-3xl font-semibold tabular-nums ${tone}`}>{value}</div>
      <div className="mt-1 text-sm font-medium text-ink">{label}</div>
      {sub && <div className="text-xs text-ink-mute">{sub}</div>}
    </div>
  );
}

function Door({ to, icon, title, text }: { to: string; icon: ReactNode; title: string; text: string }) {
  return (
    <Link to={to} className="group flex flex-col rounded-3xl border border-paper-line bg-paper p-6 shadow-card transition-shadow hover:shadow-lift">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-50 text-accent-700">{icon}</span>
      <div className="mt-4 flex items-center gap-2 text-lg font-semibold text-ink">{title}<ArrowRight className="h-4 w-4 text-ink-mute transition-transform group-hover:translate-x-1" /></div>
      <p className="mt-1 flex-1 text-[15px] leading-relaxed text-ink-mute">{text}</p>
    </Link>
  );
}
