import { BadgePercent, CalendarRange, Info, Moon, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import type { Condition, SheetRate } from "@/contracts";
import { cn } from "@/components/ui";

const fmtDate = (d: string | null) => (d ? new Date(d + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "2-digit" }) : "");
const money = (n: number, cur: string | null) => `${cur === "USD" ? "$" : cur === "INR" ? "₹" : cur === "EUR" ? "€" : ""}${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const DAY_ORDER = ["Sun–Wed", "Mon–Thu", "Thu–Sat", "Fri–Sat"];

/** A supplier's rates rebuilt as a clean grid: one row per room, one column per season × weekdays × occupancy. */
export function RateGrid({ rates }: { rates: SheetRate[] }) {
  const plans = useMemo(() => [...new Set(rates.map((r) => r.plan))], [rates]);
  const sources = useMemo(() => [...new Set(rates.map((r) => r.source_file))], [rates]);
  const [plan, setPlan] = useState(plans[0]);
  const [source, setSource] = useState(sources[sources.length - 1]);
  const shown = rates.filter((r) => r.plan === (plans.includes(plan) ? plan : plans[0]) && r.source_file === (sources.includes(source) ? source : sources[0]));
  const currency = shown[0]?.currency ?? null;
  const cols = useMemo(() => {
    const m = new Map<string, { key: string; season: string; from: string | null; days: string | null; occ: string | null }>();
    for (const r of shown) {
      const key = `${r.season_from}|${r.season_to}|${r.days}|${r.occupancy}`;
      if (!m.has(key)) m.set(key, { key, season: r.season_from ? `${fmtDate(r.season_from)} – ${fmtDate(r.season_to)}` : (r.meal ?? "All dates"), from: r.season_from, days: r.days, occ: r.occupancy });
    }
    return [...m.values()].sort((a, b) => (a.from ?? "").localeCompare(b.from ?? "") || DAY_ORDER.indexOf(a.days ?? "") - DAY_ORDER.indexOf(b.days ?? "") || (a.occ ?? "").localeCompare(b.occ ?? ""));
  }, [shown]);
  const seasons = useMemo(() => {
    const out: { season: string; span: number }[] = [];
    for (const c of cols) {
      if (out.length && out[out.length - 1].season === c.season) out[out.length - 1].span++;
      else out.push({ season: c.season, span: 1 });
    }
    return out;
  }, [cols]);
  const rows = useMemo(() => {
    const m = new Map<string, { name: string; code: string | null; status: string; cells: Record<string, number> }>();
    for (const r of shown) {
      const k = r.room_id ?? `raw:${r.room}`;
      const row = m.get(k) ?? { name: r.room_name, code: r.code, status: r.room_status, cells: {} };
      row.cells[`${r.season_from}|${r.season_to}|${r.days}|${r.occupancy}`] = r.price;
      m.set(k, row);
    }
    return [...m.values()];
  }, [shown]);
  const showSub = cols.some((c) => c.days || c.occ);
  if (!rates.length) return <div className="text-sm text-ink-mute">No rates from supplier sheets yet.</div>;
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {plans.length > 1 && (
          <label className="flex items-center gap-2 text-ink-mute">Rate plan
            <select value={plan} onChange={(e) => setPlan(e.target.value)} className="rounded-lg border border-paper-line bg-paper px-2 py-1 text-ink">
              {plans.map((p) => <option key={p}>{p}</option>)}
            </select></label>
        )}
        {sources.length > 1 && (
          <label className="flex items-center gap-2 text-ink-mute">Sheet
            <select value={source} onChange={(e) => setSource(e.target.value)} className="max-w-[320px] rounded-lg border border-paper-line bg-paper px-2 py-1 text-ink">
              {sources.map((p) => <option key={p}>{p}</option>)}
            </select></label>
        )}
        <span className="text-ink-mute">{shown.length.toLocaleString("en-IN")} rates · {currency ?? "currency not stated"} · per room per night as the sheet states</span>
      </div>
      <div className="mt-3 overflow-x-auto rounded-xl border border-paper-line">
        <table className="w-max min-w-full text-sm tabular-nums">
          <thead className="bg-paper-warm/60 text-xs text-ink-mute">
            <tr>
              <th rowSpan={showSub ? 2 : 1} className="sticky left-0 z-10 bg-paper-warm px-3 py-2 text-left font-medium">Room</th>
              {seasons.map((s, i) => <th key={i} colSpan={s.span} className="border-l border-paper-line px-3 py-2 text-center font-medium">{s.season}</th>)}
            </tr>
            {showSub && <tr>{cols.map((c) => <th key={c.key} className="border-l border-paper-line px-2 pb-2 text-center font-normal">{[c.days, c.occ].filter(Boolean).join(" · ")}</th>)}</tr>}
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-paper-line">
                <td className="sticky left-0 z-10 bg-paper px-3 py-1.5">
                  <div className="font-medium text-ink">{r.name}</div>
                  <div className="text-xs text-ink-mute">{r.code && <span className="font-mono">{r.code}</span>}{r.status === "person" && <span className="ml-1 text-warn-500">room awaiting a person</span>}</div>
                </td>
                {cols.map((c) => <td key={c.key} className="border-l border-paper-line px-3 py-1.5 text-right">{r.cells[c.key] != null ? money(r.cells[c.key], currency) : <span className="text-ink-mute">—</span>}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** The sheet's footnotes, read into terms an agent can act on. */
export function Terms({ conditions }: { conditions: Condition[] }) {
  const items = conditions.filter((c) => c.kind !== "note");
  const notes = conditions.filter((c) => c.kind === "note");
  if (!conditions.length) return <div className="text-sm text-ink-mute">The sheet states no extra terms.</div>;
  return (
    <div>
      <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {items.map((c, i) => {
          const [Icon, title] = c.kind === "discount" ? [BadgePercent, `${c.percent}% off for ${c.max_nights ? `${c.min_nights}–${c.max_nights}` : `${c.min_nights}+`} nights`]
            : c.kind === "markup" ? [TrendingUp, `Mark up ${c.percent}% before selling`]
            : c.kind === "min_stay" ? [Moon, c.fee ? `${money(c.fee, "USD")} per room per night if the minimum stay isn't met` : "Minimum stay applies"]
            : c.kind === "booking_window" ? [CalendarRange, c.from ? `Book between ${fmtDate(c.from)} and ${fmtDate(c.to ?? null)}` : "Booking window"]
            : c.kind === "dynamic_dates" ? [CalendarRange, "Dynamic-rate dates (sheet rates don't apply)"]
            : [Info, "Rate basis"];
          return (
            <li key={i} className="flex gap-3 rounded-xl border border-paper-line px-3 py-2">
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-accent-700" />
              <div><div className="text-sm font-medium text-ink">{title}</div><div className="text-xs text-ink-mute">“{c.text}”{c.source_supplier ? ` · ${c.source_supplier}` : ""}</div></div>
            </li>
          );
        })}
      </ul>
      {notes.length > 0 && <details className="mt-2 text-sm text-ink-mute"><summary className="cursor-pointer">Other notes on the sheet ({notes.length})</summary>
        <ul className="mt-1 list-disc pl-5">{notes.map((n, i) => <li key={i}>{n.text}</li>)}</ul></details>}
    </div>
  );
}

export const LAYOUT_LABEL: Record<string, string> = { grid: "Price grid", flat: "One row per rate", rotated: "Rotated grid" };
export function StatusPill({ status }: { status: "draft" | "applied" | "removed" }) {
  return <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", status === "applied" ? "bg-ok-50 text-ok-700" : status === "draft" ? "bg-sky-100 text-accent-700" : "bg-sand-200 text-ink-mute")}>
    {status === "applied" ? "In catalogue" : status === "draft" ? "Draft" : "Removed"}</span>;
}
