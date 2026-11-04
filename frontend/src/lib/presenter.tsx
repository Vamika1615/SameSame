import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { DEFAULT_QUERY } from "@/lib/city";

/** The seven demo beats. Keys 1-7 jump straight to each with its state in the URL;
 *  ←/→ step; Space fires the beat's primary action; "." toggles the step indicator. */
export const BEATS = [
  { key: 1, path: "/hotels?view=today", title: "Today: duplicates everywhere", action: "Space → SameSame", owner: "C" },
  { key: 2, path: "/hotels?view=samesame&focus=lookalike", title: "Stacks + look-alike trap", action: "Space → back to Today", owner: "A" },
  { key: 3, path: "/hotels/demo?tp=0", title: "Offers + True Price flip", action: "Space → flip True Price", owner: "B" },
  { key: 4, path: "/hotels/demo?tp=1&book=1", title: "Book both + failover", action: "Space → Book both", owner: "B" },
  { key: 5, path: `/sightseeing?q=${encodeURIComponent(DEFAULT_QUERY)}&view=today`, title: "Sightseeing Variant DNA", action: "Space → group variants", owner: "A" },
  { key: 6, path: "/ops", title: "Ops queue: the catch", action: "S / V / D to label", owner: "A" },
  { key: 7, path: "/simulator", title: "Simulator + metrics", action: "Space → pessimistic preset", owner: "C" },
] as const;

const ACTION = "samesame:presenter-action";

/** Pages subscribe to Space presses for their beat's primary action. */
export function usePresenterAction(fn: () => void) {
  useEffect(() => {
    window.addEventListener(ACTION, fn);
    return () => window.removeEventListener(ACTION, fn);
  }, [fn]);
}

function currentBeat(pathname: string, search: string) {
  const here = pathname + search;
  return BEATS.find((b) => b.path === here) ?? BEATS.find((b) => b.path.split("?")[0] === pathname) ?? null;
}

export function Presenter() {
  const nav = useNavigate();
  const loc = useLocation();
  const [show, setShow] = useState(false);
  const beat = currentBeat(loc.pathname, loc.search);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable) && (t as HTMLInputElement).type !== "range") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const n = Number(e.key);
      if (n >= 1 && n <= BEATS.length) { nav(BEATS[n - 1].path); e.preventDefault(); return; }
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        const i = beat ? beat.key - 1 : -1;
        const j = e.key === "ArrowRight" ? Math.min(i + 1, BEATS.length - 1) : Math.max(i - 1, 0);
        nav(BEATS[j].path); e.preventDefault(); return;
      }
      if (e.key === " ") { window.dispatchEvent(new Event(ACTION)); e.preventDefault(); return; }
      if (e.key === ".") setShow((s) => !s);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [nav, beat]);

  return (
    <AnimatePresence>
      {show && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
          className="fixed bottom-3 right-3 z-[1000] rounded-lg bg-ink/85 px-3 py-2 text-xs text-white shadow-lg">
          <div className="flex gap-1">
            {BEATS.map((b) => <span key={b.key} className={`h-1.5 w-5 rounded-full ${beat?.key === b.key ? "bg-accent-500" : "bg-white/25"}`} />)}
          </div>
          <div className="mt-1.5 font-semibold">{beat ? `${beat.key}/7 · ${beat.title} · ${beat.owner}` : "off-script"}</div>
          {beat && <div className="text-white/70">{beat.action}</div>}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
