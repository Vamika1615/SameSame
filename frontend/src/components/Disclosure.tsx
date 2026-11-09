import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { cn } from "@/components/ui";

/** A titled section that stays closed until you want the detail. */
export function Disclosure({ title, hint, open: forced, children, className }:
  { title: ReactNode; hint?: ReactNode; open?: boolean; children: ReactNode; className?: string }) {
  const [open, setOpen] = useState(!!forced);
  useEffect(() => { if (forced !== undefined) setOpen(forced); }, [forced]);
  return (
    <section className={cn("rounded-2xl border border-paper-line bg-paper", className)}>
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-3 px-5 py-4 text-left">
        <span className="flex-1">
          <span className="block text-[16px] font-semibold text-ink">{title}</span>
          {hint && <span className="block text-sm text-ink-mute">{hint}</span>}
        </span>
        <ChevronDown className={cn("h-5 w-5 shrink-0 text-ink-mute transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }} className="overflow-hidden">
            <div className="border-t border-paper-line px-5 pb-5 pt-4">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

/** A side panel for settings that most people never need to touch. */
export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="fixed inset-0 z-50 bg-ink/20" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside className="fixed inset-y-0 right-0 z-50 w-[380px] max-w-full overflow-y-auto bg-paper p-6 shadow-lift"
            initial={{ x: 400 }} animate={{ x: 0 }} exit={{ x: 400 }} transition={{ type: "tween", duration: 0.22 }}>
            <div className="flex items-center justify-between">
              <h2 className="text-xl text-ink">{title}</h2>
              <button onClick={onClose} className="rounded-full px-3 py-1 text-sm text-ink-mute hover:bg-paper-warm">Close</button>
            </div>
            <div className="mt-4">{children}</div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
