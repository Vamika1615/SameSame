import { useApi } from "@/lib/api";
import { Tip } from "@/components/ui";

type PR = { precision: number | null; recall: number | null; n?: number; true_pairs?: number; false_merges?: number };
type Metrics = {
  generated_at: string;
  blind: { pairs: number; human_labelled: number; stale: number; by_type: Record<string, { pairs: number; vs_generator: PR; human_labelled: number; vs_human: PR }> };
  hotels: { all: PR; held_out: PR; listings: number; clusters: number; hotels: number };
  hard_negatives: { pairs: number; wrongly_merged: number };
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
    <section className="rounded-2xl border border-paper-line bg-paper p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-bold">Twin Finder on the blind set</h2>
        <span className="text-sm text-ink-mute">
          {d.blind.pairs} frozen pairs from held-out families · {d.blind.human_labelled} human-labelled so far · rebuilt {d.generated_at.replace("T", " ")}
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
        <div>Real look-alike pairs wrongly merged: <b>{d.hard_negatives.wrongly_merged} of {d.hard_negatives.pairs}</b></div>
        <Tip content={<>Auto-merge at p ≥ {d.routing.thresholds.auto_merge}; review from p ≥ {d.routing.thresholds.gray_low}. LLM {d.routing.llm_mode}.</>}>
          <div className="cursor-help">To human review: {pct(d.routing.human_share)} of likely pairs · to LLM: {pct(d.routing.llm_share)}</div>
        </Tip>
      </div>
      <p className="mt-2 text-xs text-ink-mute">Labels are the generator's; we wrote both generator and matcher, so read these as an upper bound. Caveats in METRICS.md.</p>
    </section>
  );
}
