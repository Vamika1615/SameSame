import { BarChart3, Building2, ClipboardCheck, Ship, SlidersHorizontal } from "lucide-react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useApi } from "@/lib/api";
import { Presenter } from "@/lib/presenter";
import type { Meta } from "@/contracts";
import HotelsPage from "@/pages/HotelsPage";
import HotelDetailPage from "@/pages/HotelDetailPage";
import SightseeingPage from "@/pages/SightseeingPage";
import OpsPage from "@/pages/OpsPage";
import SimulatorPage from "@/pages/SimulatorPage";
import SuppliersPage from "@/pages/SuppliersPage";
import { Empty } from "@/components/States";

const NAV = [
  { to: "/hotels", label: "Hotels", icon: Building2 },
  { to: "/sightseeing", label: "Sightseeing", icon: Ship },
  { to: "/ops", label: "Ops Queue", icon: ClipboardCheck },
  { to: "/suppliers", label: "Supplier Report", icon: BarChart3 },
  { to: "/simulator", label: "Simulator", icon: SlidersHorizontal },
];

function ModeBadge() {
  const meta = useApi<Meta>("/api/meta");
  if (meta.status !== "ready") return null;
  const { llm, llm_model, data } = meta.data.mode;
  return (
    <div className="space-y-1.5 text-xs">
      <div className="rounded-md bg-warn-50 px-2 py-1 font-semibold uppercase tracking-wide text-warn-500">{data} data</div>
      <div className={`rounded-md px-2 py-1 ${llm ? "bg-accent-50 text-accent-700" : "bg-paper-warm text-ink-mute"}`}>
        {llm ? `LLM on · ${llm_model}` : "LLM off · rules + human queue"}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <div className="flex h-full">
      <aside className="flex w-56 shrink-0 flex-col border-r border-paper-line bg-paper px-4 py-6">
        <div className="px-2">
          <div className="text-2xl font-extrabold tracking-tight">Same<span className="text-accent-600">Same</span></div>
          <div className="mt-1 text-sm leading-snug text-ink-mute">Same same, but different.</div>
        </div>
        <nav className="mt-8 flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to}
              className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 font-medium transition-colors ${isActive ? "bg-accent-50 text-accent-700" : "text-ink-soft hover:bg-paper-warm"}`}>
              <Icon className="h-5 w-5" /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto space-y-4 px-2">
          <ModeBadge />
          <div className="text-xs leading-relaxed text-ink-mute">
            Built for TBO · Track 2<br />Suppliers are fictional, data synthetic, images illustrative.<br />Map data © OpenStreetMap contributors, ODbL
          </div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/hotels" replace />} />
          <Route path="/hotels" element={<HotelsPage />} />
          <Route path="/hotels/:id" element={<HotelDetailPage />} />
          <Route path="/sightseeing" element={<SightseeingPage />} />
          <Route path="/ops" element={<OpsPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="/simulator" element={<SimulatorPage />} />
          <Route path="*" element={<Empty title="Page not found" />} />
        </Routes>
      </main>
      <Presenter />
    </div>
  );
}
