import { Info } from "lucide-react";
import { Link, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useApi } from "@/lib/api";
import { Presenter } from "@/lib/presenter";
import type { Meta } from "@/contracts";
import { Tip, cn } from "@/components/ui";
import HomePage from "@/pages/HomePage";
import HotelsPage from "@/pages/HotelsPage";
import HotelDetailPage from "@/pages/HotelDetailPage";
import SightseeingPage from "@/pages/SightseeingPage";
import { ApprovalsPage } from "@/pages/OpsPage";
import SimulatorPage from "@/pages/SimulatorPage";
import SuppliersPage from "@/pages/SuppliersPage";
import LabelPage from "@/pages/LabelPage";
import RemixStudioPage from "@/pages/RemixStudioPage";
import GapsPage from "@/pages/GapsPage";
import ImportPage from "@/pages/ImportPage";
import CataloguePage from "@/pages/CataloguePage";
import CatalogueHotelPage from "@/pages/CatalogueHotelPage";
import ReviewPage from "@/pages/ReviewPage";
import { Empty } from "@/components/States";

/** Three sections. The catalogue is the product; Bundles is what a clean catalogue makes possible. */
export const SECTIONS = [
  { key: "catalogue", label: "Catalogue", home: "/import", tabs: [
    { to: "/import", label: "Import sheets" },
    { to: "/catalogue", label: "All hotels", end: true },
    { to: "/hotels", label: "Agent search" },
    { to: "/sightseeing", label: "Tours" },
    { to: "/catalogue/review", label: "Uncertain matches" },
  ] },
  { key: "insights", label: "Insights", home: "/suppliers", tabs: [
    { to: "/suppliers", label: "Supplier reliability" },
    { to: "/simulator", label: "Business case" },
  ] },
  { key: "bundles", label: "Bundles", home: "/remix", tabs: [
    { to: "/remix", label: "Rebuild packages", end: true },
    { to: "/remix/gaps", label: "New products" },
    { to: "/bundles/approvals", label: "Approvals" },
  ] },
] as const;

function sectionOf(path: string) {
  if (path.startsWith("/remix") || path.startsWith("/bundles")) return "bundles";
  if (["/import", "/catalogue", "/hotels", "/sightseeing", "/sheets", "/label"].some((p) => path.startsWith(p))) return "catalogue";
  if (path.startsWith("/suppliers") || path.startsWith("/simulator")) return "insights";
  return null;
}

/** Old addresses keep working. */
function OpsRedirect() {
  const loc = useLocation();
  return <Navigate to={loc.search.includes("tab=twin") ? "/catalogue/review?tab=listings" : "/bundles/approvals"} replace />;
}

/** Canon's mark: many lines folded into one. */
export function CanonMark({ className = "h-7 w-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect x="3" y="6" width="11" height="3" rx="1.5" fill="#e07b2e" opacity=".55" />
      <rect x="3" y="14.5" width="11" height="3" rx="1.5" fill="#e07b2e" opacity=".75" />
      <rect x="3" y="23" width="11" height="3" rx="1.5" fill="#e07b2e" />
      <path d="M15 7.5 C21 7.5 20 16 25 16 M15 16 H25 M15 24.5 C21 24.5 20 16 25 16" stroke="#163a6b" strokeWidth="1.8" fill="none" strokeLinecap="round" />
      <circle cx="26.5" cy="16" r="3" fill="#163a6b" />
    </svg>
  );
}

/** A small sun: the old brand mark (kept for the bundle pages' accents). */
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
    if (p === "/catalogue" && loc.pathname.startsWith("/catalogue/hotels")) return true;
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
            <NavLink to="/" className="flex items-center gap-2" title="Canon: one clean catalogue from every supplier sheet">
              <CanonMark className="h-6 w-6" />
              <span className="font-display text-[22px] font-semibold leading-none tracking-tight text-accent-700">Canon</span>
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
          <Route path="/import" element={<ImportPage />} />
          <Route path="/catalogue" element={<CataloguePage />} />
          <Route path="/catalogue/hotels/:id" element={<CatalogueHotelPage />} />
          <Route path="/catalogue/review" element={<ReviewPage />} />
          <Route path="/hotels" element={<HotelsPage />} />
          <Route path="/hotels/:id" element={<HotelDetailPage />} />
          <Route path="/sightseeing" element={<SightseeingPage />} />
          <Route path="/remix" element={<RemixStudioPage />} />
          <Route path="/remix/gaps" element={<GapsPage />} />
          <Route path="/bundles/approvals" element={<ApprovalsPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="/simulator" element={<SimulatorPage />} />
          <Route path="/label" element={<LabelPage />} />
          <Route path="/sheets" element={<Navigate to="/import" replace />} />
          <Route path="/ops" element={<OpsRedirect />} />
          <Route path="*" element={<Empty title="Page not found" />} />
        </Routes>
        <footer className="mx-auto max-w-[1400px] px-8 pb-8 pt-10 text-xs text-ink-mute">
          Canon · built for TBO · Track 2. Catalogue suppliers are fictional and their data synthetic; sheets you import stay on this machine. Photos: Wikimedia Commons (credited on hover). Map data © OpenStreetMap contributors, ODbL.
        </footer>
      </main>
      <Presenter />
    </div>
  );
}
