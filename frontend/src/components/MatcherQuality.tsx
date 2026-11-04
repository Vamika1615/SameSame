import { useApi } from "@/lib/api";
import { Tip } from "@/components/ui";

type PR = { precision: number | null; recall: number | null; n?: number; true_pairs?: number; false_merges?: number };
type Metrics = {
  generated_at: string;
  blind: { pairs: number; human_labelled: number; stale: number; by_type: Record<string, { pairs: number; vs_generator: PR; human_labelled: number; vs_human: PR }> };
  hotels: { all: PR; held_out: PR; listings: number; clusters: number; hotels: number };
  hard_negatives: { pairs: number; wrongly_merged: number; held_out_pairs: number };
  routing: { review_share: number; llm_share: number | null; human_share: number | null; llm_mode: string; to_review: number; auto_merged: number;
    thresholds: { auto_merge: number; gray_low: number } };
};

const pct = (x: number | null | undefined) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);

/** Blind-set precision / recall per entity type, straight from data/build/metrics.json (rebuilt every build). */
export function MatcherQuality() {
  const m = useApi<Metrics>("/api/metrics");
  if (m.status !== "ready") return null;
  const d = m.data;
  return (
    <section className="rounded-3xl border border-paper-line bg-paper shadow-card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[26px] font-semibold text-accent-700">Twin Finder on the held-out set</h2>
        <span className="text-sm text-ink-mute">
          {d.blind.pairs} frozen pairs from brand families the model never trained on · {d.blind.human_labelled} hand-labelled so far
        </span>
      </div>
      <table className="mt-3 w-full text-left text-[15px]">
        <thead className="text-sm uppercase text-ink-mute">
          <tr><th className="py-1">Entity</th><th>Pairs</th><th>Precision</th><th>Recall</th><th>vs human labels</th></tr>
        </thead>
        <tbody className="tabular-nums">
          {Object.entries(d.blind.by_type).map(([k, v]) => (
            <tr key={k} className="border-t border-paper-line">
              <td className="py-1.5 font-semibold capitalize">{k}</td>
              <td>{v.pairs}</td>
              <td className="font-bold">{pct(v.vs_generator.precision)}</td>
              <td>{pct(v.vs_generator.recall)}</td>
              <td className="text-ink-mute">{v.human_labelled ? `${pct(v.vs_human.precision)} / ${pct(v.vs_human.recall)} (n=${v.human_labelled})` : "not labelled yet"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 grid grid-cols-1 gap-2 text-sm text-ink-soft md:grid-cols-3">
        <div>Whole catalogue: {d.hotels.listings} listings → {d.hotels.clusters} hotels, precision {pct(d.hotels.all.precision)}, recall {pct(d.hotels.all.recall)}</div>
        <div>Real look-alike pairs wrongly merged: <b>{d.hard_negatives.wrongly_merged} of {d.hard_negatives.pairs}</b> (scored out-of-fold; {d.hard_negatives.held_out_pairs} fully held out)</div>
        <Tip content={<>Auto-merge at p ≥ {d.routing.thresholds.auto_merge}; review from p ≥ {d.routing.thresholds.gray_low}. LLM {d.routing.llm_mode}.</>}>
          <div className="cursor-help">To human review: {pct(d.routing.human_share)} of likely pairs · to LLM: {pct(d.routing.llm_share)}</div>
        </Tip>
      </div>
      <p className="mt-2 text-xs text-ink-mute">Labels are the generator's, and we saw these totals while still building M3, so this is held-out, not blind. We wrote both generator and matcher: read it as an upper bound. The independent check is the hand-labelled column. Caveats in METRICS.md.</p>
    </section>
  );
}
