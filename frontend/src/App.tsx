import { BarChart3, Building2, ClipboardCheck, Ship, SlidersHorizontal, Sparkles } from "lucide-react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useApi } from "@/lib/api";
import { Presenter } from "@/lib/presenter";
import type { Meta } from "@/contracts";
import { Tip } from "@/components/ui";
import HotelsPage from "@/pages/HotelsPage";
import HotelDetailPage from "@/pages/HotelDetailPage";
import SightseeingPage from "@/pages/SightseeingPage";
import OpsPage from "@/pages/OpsPage";
import SimulatorPage from "@/pages/SimulatorPage";
import SuppliersPage from "@/pages/SuppliersPage";
import LabelPage from "@/pages/LabelPage";
import RemixStudioPage from "@/pages/RemixStudioPage";
import GapsPage from "@/pages/GapsPage";
import { Empty } from "@/components/States";

const NAV = [
  { to: "/remix", label: "Remix Studio", icon: Sparkles },
  { to: "/remix/gaps", label: "Gap Finder", icon: Ship },
  { to: "/sightseeing", label: "Sightseeing", icon: Ship },
  { to: "/hotels", label: "Hotels", icon: Building2 },
  { to: "/ops", label: "Ops Queue", icon: ClipboardCheck },
  { to: "/suppliers", label: "Suppliers", icon: BarChart3 },
  { to: "/simulator", label: "Simulator", icon: SlidersHorizontal },
];

/** A small sun: the brand mark. */
export function SunMark({ className = "h-7 w-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <circle cx="16" cy="16" r="6" fill="#e07b2e" />
      {Array.from({ length: 12 }).map((_, i) => {
        const a = (i * Math.PI) / 6, r1 = 9.5, r2 = i % 2 ? 12.5 : 14.5;
        return <line key={i} x1={16 + r1 * Math.cos(a)} y1={16 + r1 * Math.sin(a)} x2={16 + r2 * Math.cos(a)} y2={16 + r2 * Math.sin(a)}
          stroke="#e07b2e" strokeWidth="1.6" strokeLinecap="round" />;
      })}
    </svg>
  );
}

function ModeBadge() {
  const meta = useApi<Meta>("/api/meta");
  if (meta.status !== "ready") return null;
  const { llm, llm_model, data } = meta.data.mode;
  return (
    <div className="flex items-center gap-2 text-xs font-semibold">
      <span className="rounded-full border border-paper-line bg-paper px-3 py-1.5 text-ink-soft">{meta.data.city} · {meta.data.currency}</span>
      <Tip side="bottom" content={<ul className="space-y-1">{Object.entries(meta.data.sources ?? {}).map(([k, v]) => <li key={k}><b>{k.replace("_", " ")}:</b> {v}</li>)}</ul>}>
        <span className="cursor-help rounded-full bg-sand-200 px-3 py-1.5 uppercase tracking-wide text-ink-soft">{data} data</span>
      </Tip>
      <span className={`rounded-full px-3 py-1.5 ${llm ? "bg-accent-50 text-accent-700" : "bg-sky-100 text-ink-soft"}`}>
        {llm ? `LLM on · ${llm_model}` : "LLM off · rules + human queue"}
      </span>
    </div>
  );
}

export default function App() {
  return (
    <div className="flex h-full flex-col">
      <header className="sticky top-0 z-40 border-b border-paper-line/80 bg-paper/85 backdrop-blur-md">
        <div className="mx-auto flex h-[68px] max-w-[1760px] items-center gap-10 px-8">
          <NavLink to="/remix" className="flex items-center gap-2.5" title="Remix makes new products from parts suppliers already sell.">
            <SunMark />
            <span className="font-display text-[26px] font-semibold leading-none tracking-tight text-accent-700">
              Re<span className="italic text-sun-500">mix</span>
            </span>
          </NavLink>
          <nav className="flex h-full items-stretch gap-1">
            {NAV.map(({ to, label }) => (
              <NavLink key={to} to={to} end={to === "/remix"}
                className={({ isActive }) => `relative flex items-center px-4 text-[15px] font-semibold transition-colors ${isActive ? "text-accent-700" : "text-ink-mute hover:text-ink"}`}>
                {({ isActive }) => (<>{label}{isActive && <span className="absolute inset-x-4 bottom-0 h-[3px] rounded-t-full bg-sun-500" />}</>)}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto"><ModeBadge /></div>
        </div>
      </header>
      <main className="min-w-0 flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/remix" replace />} />
          <Route path="/remix" element={<RemixStudioPage />} />
          <Route path="/remix/gaps" element={<GapsPage />} />
          <Route path="/hotels" element={<HotelsPage />} />
          <Route path="/hotels/:id" element={<HotelDetailPage />} />
          <Route path="/sightseeing" element={<SightseeingPage />} />
          <Route path="/ops" element={<OpsPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="/simulator" element={<SimulatorPage />} />
          <Route path="/label" element={<LabelPage />} />
          <Route path="*" element={<Empty title="Page not found" />} />
        </Routes>
        <footer className="mx-auto max-w-[1760px] px-8 pb-8 pt-4 text-xs leading-relaxed text-ink-mute">
          <span className="font-semibold text-ink-soft">Remix · built for TBO · Track 2.</span> Remix makes new products from parts suppliers already sell. Suppliers are fictional and their data synthetic.
          Photos from Wikimedia Commons (credited on hover); stock photos are labelled. Map data © OpenStreetMap contributors, ODbL.
        </footer>
      </main>
      <Presenter />
    </div>
  );
}
