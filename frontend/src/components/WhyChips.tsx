import { Info } from "lucide-react";
import type { ScoreTerm, WhyChip } from "@/contracts";
import { Tip, cn } from "./ui";

const KIND: Record<WhyChip["kind"], string> = {
  price: "bg-sun-50 text-sun-700 border-sun-100",
  promise: "bg-ok-50 text-ok-700 border-ok-50",
  relevance: "bg-sky-100 text-accent-700 border-sky-200",
  popularity: "bg-sand-100 text-ink-soft border-sand-200",
  content: "bg-paper-warm text-ink-soft border-paper-line",
  warning: "bg-danger-50 text-danger-700 border-danger-50",
};

export function ScoreBreakdown({ score }: { score: ScoreTerm[] }) {
  const total = score.reduce((s, t) => s + t.contribution, 0);
  return (
    <div className="min-w-[340px]">
      <div className="mb-1 font-semibold">Why ranked here: transparent score</div>
      <table className="w-full text-xs">
        <tbody>
          {[...score].sort((a, b) => b.contribution - a.contribution).map((t) => (
            <tr key={t.feature} className="border-t border-white/10">
              <td className="py-0.5 pr-2">{t.label}<div className="text-white/60">{t.detail}</div></td>
              <td className="whitespace-nowrap py-0.5 text-right font-mono text-white/70">{t.weight.toFixed(2)} × {t.value.toFixed(2)}</td>
              <td className="py-0.5 pl-2 text-right font-mono">{t.contribution.toFixed(3)}</td>
            </tr>
          ))}
          <tr className="border-t border-white/30 font-semibold"><td>Total</td><td /><td className="text-right font-mono">{total.toFixed(3)}</td></tr>
        </tbody>
      </table>
      <div className="mt-1 text-white/60">Weights are fixed and set by people, not learned from clicks.</div>
    </div>
  );
}

export function WhyChips({ why, score, className }: { why: WhyChip[]; score: ScoreTerm[]; className?: string }) {
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      {why.map((w) => (
        <span key={w.label} className={cn("rounded-full border px-2.5 py-0.5 text-[13px] font-medium", KIND[w.kind])}>{w.label}</span>
      ))}
      {score.length > 0 && (
        <Tip content={<ScoreBreakdown score={score} />}>
          <span className="inline-flex cursor-help items-center gap-1 text-[13px] text-ink-mute"><Info className="h-3.5 w-3.5" />why</span>
        </Tip>
      )}
    </div>
  );
}
