import type { ReactNode } from "react";

/** A quiet page header: one title, one line of context, optional actions on the right.
 *  (The section and sub-tab already say where you are, so there is no eyebrow or banner.) */
export function PageHeader({ title, subtitle, right, children }:
  { eyebrow?: string; title: ReactNode; subtitle?: ReactNode; right?: ReactNode; children?: ReactNode }) {
  return (
    <section className="pb-2 pt-2">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 max-w-[820px]">
          <h1 className="text-[30px] leading-tight text-ink">{title}</h1>
          {subtitle && <div className="mt-1.5 text-[16px] leading-relaxed text-ink-mute">{subtitle}</div>}
        </div>
        {right && <div className="shrink-0">{right}</div>}
      </div>
      {children && <div className="mt-4">{children}</div>}
    </section>
  );
}
