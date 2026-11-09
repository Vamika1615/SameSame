import { Info } from "lucide-react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useApi } from "@/lib/api";
import { Presenter } from "@/lib/presenter";
import type { Meta } from "@/contracts";
import { Tip, cn } from "@/components/ui";
import HomePage from "@/pages/HomePage";
import HotelsPage from "@/pages/HotelsPage";
import HotelDetailPage from "@/pages/HotelDetailPage";
import SightseeingPage from "@/pages/SightseeingPage";
import OpsPage from "@/pages/OpsPage";
import SimulatorPage from "@/pages/SimulatorPage";
import SuppliersPage from "@/pages/SuppliersPage";
import LabelPage from "@/pages/LabelPage";
import RemixStudioPage from "@/pages/RemixStudioPage";
import GapsPage from "@/pages/GapsPage";
import SheetsPage from "@/pages/SheetsPage";
import { Empty } from "@/components/States";

/** Four sections. Each groups the pages that answer one job; the sub-tabs are the pages. */
export const SECTIONS = [
  { key: "remix", label: "Remix", home: "/remix", tabs: [
    { to: "/remix", label: "Rebuild packages", end: true },
    { to: "/remix/gaps", label: "New products" },
  ] },
  { key: "catalogue", label: "Catalogue", home: "/hotels", tabs: [
    { to: "/hotels", label: "Hotels" },
    { to: "/sightseeing", label: "Tours" },
    { to: "/sheets", label: "Supplier sheets" },
  ] },
  { key: "review", label: "Review", home: "/ops", tabs: [
    { to: "/ops?tab=remix", label: "Remix approvals" },
    { to: "/ops?tab=twin", label: "Uncertain matches" },
  ] },
  { key: "insights", label: "Insights", home: "/suppliers", tabs: [
    { to: "/suppliers", label: "Supplier reliability" },
    { to: "/simulator", label: "Business case" },
  ] },
] as const;

function sectionOf(path: string) {
  if (path.startsWith("/remix")) return "remix";
  if (path.startsWith("/hotels") || path.startsWith("/sightseeing") || path.startsWith("/sheets")) return "catalogue";
  if (path.startsWith("/ops") || path.startsWith("/label")) return "review";
  if (path.startsWith("/suppliers") || path.startsWith("/simulator")) return "insights";
  return null;
}

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

/** One quiet badge instead of three: the details are one hover away. */
function DataBadge() {
  const meta = useApi<Meta>("/api/meta");
  if (meta.status !== "ready") return null;
  const m = meta.data;
  return (
    <Tip side="bottom" className="ml-auto" content={<div className="space-y-1">
      <div><b>{m.city} · prices in {m.currency}</b></div>
      {Object.entries(m.sources ?? {}).map(([k, v]) => <div key={k}><b className="capitalize">{k.replace("_", " ")}:</b> {v}</div>)}
      <div><b>LLM:</b> {m.mode.llm ? `on (${m.mode.llm_model})` : "off. Rules decide; anything uncertain goes to a person."}</div>
    </div>}>
      <span className="flex cursor-help items-center gap-1.5 rounded-full border border-paper-line px-3 py-1 text-xs font-medium text-ink-mute">
        <Info className="h-3.5 w-3.5" />{m.city} · synthetic suppliers
      </span>
    </Tip>
  );
}

function SubNav({ section }: { section: string }) {
  const loc = useLocation();
  const s = SECTIONS.find((x) => x.key === section);
  if (!s) return null;
  const here = loc.pathname + loc.search;
  const isActive = (to: string, end?: boolean) => {
    const [p, q] = to.split("?");
    if (q) return loc.pathname === p && (here.includes(q) || (q === "tab=remix" && !loc.search.includes("tab=")));
    return end ? loc.pathname === p : loc.pathname === p || loc.pathname.startsWith(p + "/");
  };
  return (
    <div className="border-b border-paper-line bg-paper">
      <div className="mx-auto flex max-w-[1400px] gap-6 px-8">
        {s.tabs.map((t) => (
          <Link key={t.to} to={t.to} className={cn("relative py-3 text-sm font-medium transition-colors",
            isActive(t.to, "end" in t ? t.end : false) ? "text-accent-700" : "text-ink-mute hover:text-ink")}>
            {t.label}
            {isActive(t.to, "end" in t ? t.end : false) && <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-accent-700" />}
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const loc = useLocation();
  const section = sectionOf(loc.pathname);
  return (
    <div className="flex h-full flex-col">
      <header className="sticky top-0 z-40 bg-paper/90 backdrop-blur-md">
        <div className="border-b border-paper-line">
          <div className="mx-auto flex h-16 max-w-[1400px] items-center gap-10 px-8">
            <NavLink to="/" className="flex items-center gap-2" title="Remix: new products from parts suppliers already sell">
              <SunMark className="h-6 w-6" />
              <span className="font-display text-[22px] font-semibold leading-none tracking-tight text-accent-700">Re<span className="italic text-sun-500">mix</span></span>
            </NavLink>
            <nav className="flex h-full items-stretch gap-1">
              {SECTIONS.map((s) => (
                <Link key={s.key} to={s.home} className={cn("relative flex items-center px-3 text-[15px] font-medium transition-colors",
                  section === s.key ? "text-ink" : "text-ink-mute hover:text-ink")}>
                  {s.label}
                  {section === s.key && <span className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-sun-500" />}
                </Link>
              ))}
            </nav>
            <DataBadge />
          </div>
        </div>
        {section && <SubNav section={section} />}
      </header>
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/remix" element={<RemixStudioPage />} />
          <Route path="/remix/gaps" element={<GapsPage />} />
          <Route path="/hotels" element={<HotelsPage />} />
          <Route path="/hotels/:id" element={<HotelDetailPage />} />
          <Route path="/sheets" element={<SheetsPage />} />
          <Route path="/sightseeing" element={<SightseeingPage />} />
          <Route path="/ops" element={<OpsPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="/simulator" element={<SimulatorPage />} />
          <Route path="/label" element={<LabelPage />} />
          <Route path="*" element={<Empty title="Page not found" />} />
        </Routes>
        <footer className="mx-auto max-w-[1400px] px-8 pb-8 pt-10 text-xs text-ink-mute">
          Remix · built for TBO · Track 2. Fictional suppliers, synthetic data. Photos: Wikimedia Commons (credited on hover). Map data © OpenStreetMap contributors, ODbL.
        </footer>
      </main>
      <Presenter />
    </div>
  );
}
