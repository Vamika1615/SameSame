import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/** The eight demo beats. Keys 1-8 jump straight to each with its state in the URL;
 *  ←/→ step; Space fires the beat's primary action; "." toggles the step indicator. */
const BURJ = encodeURIComponent("burj khalifa");
export const BEATS = [
  { key: 1, path: `/sightseeing?q=${BURJ}&view=today`, title: "The problem: one experience, many packages", action: "Space → Variant DNA", owner: "A" },
  { key: 2, path: "/remix", title: "Remix Studio: package vs Remix", action: "Space → show the arithmetic", owner: "B" },
  { key: 3, path: "/remix?tp=1", title: "True Price proof + TBO margin", action: "Space → hide arithmetic", owner: "B" },
  { key: 4, path: "/remix?book=1", title: "Book Remix live: a part fails over", action: "Space → Book Remix", owner: "B" },
  { key: 5, path: "/remix/gaps", title: "Gap Remix: nobody sells this", action: "Space → next gap", owner: "C" },
  { key: 6, path: "/hotels/demo?trip=1", title: "Connected Trip: hotel + transfer + tour", action: "Space → book the trip", owner: "C" },
  { key: 7, path: "/ops?tab=remix", title: "Trust: approvals + held-out metrics", action: "A / R to approve or reject", owner: "A" },
  { key: 8, path: "/simulator", title: "Business case", action: "Space → pessimistic preset", owner: "C" },
] as const;

const ACTION = "remix:presenter-action";

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
          <div className="mt-1.5 font-semibold">{beat ? `${beat.key}/${BEATS.length} · ${beat.title} · ${beat.owner}` : "off-script"}</div>
          {beat && <div className="text-white/70">{beat.action}</div>}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
