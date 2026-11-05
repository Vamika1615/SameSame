import { AnimatePresence, motion } from "framer-motion";
import { Star } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { ImageRef } from "@/contracts";

export const cn = (...xs: (string | false | null | undefined)[]) => xs.filter(Boolean).join(" ");

export const SUPPLIER_COLOR: Record<string, string> = {
  Kestrel: "#d9732a", Mynah: "#2a5590", Heron: "#7a5aa6", Bulbul: "#c49a2c", Hornbill: "#3b8a8c", Sunbird: "#c2577a",
};

export function SupplierBadge({ name, small }: { name: string; small?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border border-paper-line bg-paper font-medium text-ink-soft", small ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm")}>
      <span className="h-2 w-2 rounded-full" style={{ background: SUPPLIER_COLOR[name] ?? "#64748b" }} />
      {name}
    </span>
  );
}

export function Stars({ n }: { n: number | null }) {
  if (!n) return null;
  return (
    <span className="inline-flex items-center gap-0.5 text-sun-500" aria-label={`${n} stars`}>
      {Array.from({ length: Math.floor(n) }).map((_, i) => <Star key={i} className="h-3.5 w-3.5 fill-current" />)}
      {n % 1 ? <span className="text-xs text-ink-mute">½</span> : null}
    </span>
  );
}

export function Segmented<T extends string>({ value, options, onChange, size = "lg" }:
  { value: T; options: { value: T; label: ReactNode }[]; onChange: (v: T) => void; size?: "md" | "lg" }) {
  return (
    <div className="relative inline-flex rounded-full border border-sky-200 bg-sky-100/80 p-1">
      {options.map((o) => (
        <button key={o.value} onClick={() => onChange(o.value)}
          className={cn("relative z-10 rounded-full font-semibold transition-colors", size === "lg" ? "px-6 py-2.5 text-[17px]" : "px-4 py-1.5",
            value === o.value ? "text-white" : "text-ink-soft hover:text-ink")}>
          {value === o.value && (
            <motion.span layoutId={`seg-${options.map((x) => x.value).join("-")}`} className="absolute inset-0 -z-10 rounded-full bg-accent-700 shadow-card"
              transition={{ type: "spring", stiffness: 500, damping: 40 }} />
          )}
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Hover tooltip; content can be rich. Pure CSS so it never lags on stage. */
export function Tip({ children, content, side = "top", className }: { children: ReactNode; content: ReactNode; side?: "top" | "bottom"; className?: string }) {
  return (
    <span className={cn("group/tip relative inline-flex", className)}>
      {children}
      <span className={cn("pointer-events-none absolute left-1/2 z-50 w-max max-w-sm -translate-x-1/2 rounded-xl bg-accent-900 px-3 py-2 text-left text-sm font-normal leading-snug text-white opacity-0 shadow-xl transition-opacity duration-150 group-hover/tip:opacity-100",
        side === "top" ? "bottom-full mb-2" : "top-full mt-2")}>
        {content}
      </span>
    </span>
  );
}

export function Illustrative({ img, className, label = true }: { img: ImageRef | null | undefined; className?: string; label?: boolean }) {
  return (
    <div className={cn("relative overflow-hidden bg-paper-line", className)}>
      {img && <img src={img.url} alt="" className="h-full w-full object-cover" draggable={false} />}
      {label && img && (
        <span title={img.credit ?? undefined}
          className="absolute bottom-1 left-1 max-w-[95%] truncate rounded bg-black/55 px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-white">
          {img.kind === "photo" ? "PHOTO" : img.kind === "stock" ? "STOCK PHOTO · NOT THIS EXACT PLACE" : "ILLUSTRATIVE"}
          {img.credit && img.kind !== "generated" ? <span className="normal-case opacity-80"> · {img.credit}</span> : null}
        </span>
      )}
    </div>
  );
}

/** Counts towards a value in ~500 ms. */
export function AnimatedNumber({ value, format = (n: number) => Math.round(n).toLocaleString("en-IN") }: { value: number; format?: (n: number) => string }) {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    const start = performance.now(), a = from.current, dur = 500;
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / dur), e = 1 - Math.pow(1 - k, 3);
      setShown(a + (value - a) * e);
      if (k < 1) raf = requestAnimationFrame(tick); else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <span className="tabular-nums">{format(shown)}</span>;
}

/** Airport departure-board flip: each character tile flips independently. */
export function FlipBoard({ text, className, tone = "dark" }: { text: string; className?: string; tone?: "dark" | "accent" }) {
  return (
    <span className={cn("inline-flex gap-[2px] font-mono font-bold", className)} aria-label={text}>
      {text.split("").map((ch, i) => (
        <span key={i} className={cn("relative inline-flex h-[1.5em] min-w-[0.78em] items-center justify-center overflow-hidden rounded-[3px] text-white",
          tone === "dark" ? "bg-ink" : "bg-accent-700")} style={{ perspective: 200 }}>
          <span className="absolute inset-x-0 top-1/2 h-px bg-black/40" />
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.span key={ch + i} className="inline-block" initial={{ rotateX: -90, opacity: 0 }} animate={{ rotateX: 0, opacity: 1 }}
              exit={{ rotateX: 90, opacity: 0 }} transition={{ duration: 0.18, delay: i * 0.025 }}>
              {ch === " " ? " " : ch}
            </motion.span>
          </AnimatePresence>
        </span>
      ))}
    </span>
  );
}

/** Semicircle gauge for a supplier's honour rate at this lead time. */
export function PromiseMeter({ rate, n, lo, hi, prior, size = 64 }: { rate: number; n: number; lo: number; hi: number; prior?: number; size?: number }) {
  const color = rate >= 0.9 ? "#2f9461" : rate >= 0.8 ? "#e07b2e" : "#d23c2f";
  const r = size / 2 - 5, cx = size / 2, cy = size / 2;
  const arc = (p: number) => {
    const a = Math.PI * (1 - p);
    return `${cx + r * Math.cos(a)} ${cy - r * Math.sin(a)}`;
  };
  return (
    <Tip content={<>Honoured {(rate * 100).toFixed(0)}% at this lead time<br />95% credible interval {(lo * 100).toFixed(0)}-{(hi * 100).toFixed(0)}% · n = {n.toLocaleString("en-IN")} attempts{prior != null && <><br />{Math.round(prior * 100)}% of the estimate borrowed from this supplier's other lead times and the market</>}</>}>
      <span className="inline-flex flex-col items-center">
        <svg width={size} height={size / 2 + 4} viewBox={`0 0 ${size} ${size / 2 + 4}`}>
          <path d={`M ${arc(0)} A ${r} ${r} 0 0 1 ${arc(1)}`} stroke="#e7dcc9" strokeWidth="7" fill="none" strokeLinecap="round" />
          <motion.path d={`M ${arc(0)} A ${r} ${r} 0 0 1 ${arc(1)}`} stroke={color} strokeWidth="7" fill="none" strokeLinecap="round"
            initial={{ pathLength: 0 }} animate={{ pathLength: rate }} transition={{ duration: 0.5 }} />
        </svg>
        <span className="-mt-1 text-sm font-bold tabular-nums" style={{ color }}>{Math.round(rate * 100)}%</span>
      </span>
    </Tip>
  );
}

export function DataBadge({ kind }: { kind: "mock" | "synthetic" | "real" | string }) {
  if (kind === "real") return null;
  return <span className="rounded-md bg-warn-50 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-warn-500">{kind} data</span>;
}

/** Overlapping supplier initials: who sells this hotel. */
export function SupplierAvatars({ names, max = 4 }: { names: string[]; max?: number }) {
  return (
    <Tip content={<>{names.join(" · ")}<br />One hotel, one card. Offers compared inside.</>}>
      <span className="inline-flex items-center">
        <span className="flex -space-x-1.5">
          {names.slice(0, max).map((s) => (
            <span key={s} className="flex h-7 w-7 items-center justify-center rounded-full text-[12px] font-bold ring-2 ring-paper"
              style={{ background: `${SUPPLIER_COLOR[s] ?? "#76829a"}22`, color: SUPPLIER_COLOR[s] ?? "#76829a" }}>{s[0]}</span>
          ))}
        </span>
        {names.length > max && <span className="ml-1.5 text-xs font-semibold text-ink-mute">+{names.length - max}</span>}
      </span>
    </Tip>
  );
}

/** Metres between two points (for "320 m from the Metro"). */
export function metres(a: [number, number], b: [number, number]) {
  const r = 6371000, p1 = (a[0] * Math.PI) / 180, p2 = (b[0] * Math.PI) / 180;
  const h = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin((((b[1] - a[1]) * Math.PI) / 180) / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}
