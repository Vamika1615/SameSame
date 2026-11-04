import type { ReactNode } from "react";
import { Skyline } from "@/components/Skyline";

/** The coastal header band every page opens with: eyebrow, serif title, one line of context, optional controls. */
export function PageHeader({ eyebrow, title, subtitle, right, children }:
  { eyebrow: string; title: ReactNode; subtitle?: ReactNode; right?: ReactNode; children?: ReactNode }) {
  return (
    <section className="hero-sky relative overflow-hidden rounded-4xl px-10 pb-7 pt-7">
      <Skyline className="pointer-events-none absolute bottom-0 right-0 h-[90%] w-[42%] opacity-25" />
      <div className="relative flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0 max-w-[900px]">
          <div className="text-xs font-semibold uppercase tracking-[0.22em] text-accent-700/80">{eyebrow}</div>
          <h1 className="mt-2 text-[40px] leading-[1.08] text-accent-700">{title}</h1>
          {subtitle && <div className="mt-2 text-[17px] text-ink-soft">{subtitle}</div>}
        </div>
        {right && <div className="relative">{right}</div>}
      </div>
      {children && <div className="relative mt-5">{children}</div>}
    </section>
  );
}
