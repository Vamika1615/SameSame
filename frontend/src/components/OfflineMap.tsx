import L from "leaflet";
import { useEffect, useRef } from "react";
import { getJSON } from "@/lib/api";
import { MAP_CENTER, MAP_ZOOM } from "@/lib/city";

export interface Pin { id: string; lat: number; lng: number; label: string; tone?: "default" | "accent" | "danger" | "anchor"; permanent?: boolean }
export interface MapLine { from: [number, number]; to: [number, number]; label?: string }

const TONE = { default: "#475569", accent: "#0b7a70", danger: "#dc2626", anchor: "#0f172a" };
let basemapCache: Promise<GeoJSON.FeatureCollection> | null = null;

/** Leaflet with NO tile server: draws our saved OSM river / roads / districts. */
export function OfflineMap({ pins, lines = [], highlight, className, fitPins = false, onPinClick }:
  { pins: Pin[]; lines?: MapLine[]; highlight?: string | null; className?: string; fitPins?: boolean; onPinClick?: (id: string) => void }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const pinLayer = useRef<L.LayerGroup | null>(null);
  const clickRef = useRef(onPinClick);
  clickRef.current = onPinClick;

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { zoomControl: true, attributionControl: true, preferCanvas: true, zoomSnap: 0.25 }).setView(MAP_CENTER, MAP_ZOOM);
    m.attributionControl.setPrefix(false).addAttribution("© OpenStreetMap contributors, ODbL");
    map.current = m;
    m.createPane("pins").style.zIndex = "650";   // pins always above the async-loaded basemap
    pinLayer.current = L.layerGroup().addTo(m);
    basemapCache ??= getJSON<GeoJSON.FeatureCollection>("/api/basemap");
    basemapCache.then((gj) => {
      if (map.current !== m) return;   // this map instance was unmounted (StrictMode remount)
      L.geoJSON(gj, {
        style: (f) => {
          const layer = f?.properties?.layer;
          if (layer === "river") return { color: "#7cb4d9", weight: 8, opacity: 0.9 };
          if (layer === "district") return { color: "#94a3b8", weight: 1.2, dashArray: "4 4", opacity: 0.8 };
          return { color: "#ffffff", weight: f?.properties?.class === "motorway" ? 5 : 3, opacity: 1 };
        },
        interactive: false,
      }).addTo(m);
    }).catch(() => { /* pins still render on the plain background */ });
    return () => { m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const layer = pinLayer.current, m = map.current;
    if (!layer || !m) return;
    layer.clearLayers();
    for (const ln of lines) {
      L.polyline([ln.from, ln.to], { pane: "pins", color: "#dc2626", weight: 2.5, dashArray: "6 6" })
        .bindTooltip(ln.label ?? "", { permanent: !!ln.label, direction: "center", className: "map-line-label" }).addTo(layer);
    }
    const ordered = [...pins].sort((a, b) => Number(a.id === highlight) - Number(b.id === highlight));
    for (const p of ordered) {
      const hot = p.id === highlight;
      const mk = L.circleMarker([p.lat, p.lng], {
        pane: "pins", radius: p.tone === "anchor" ? 7 : hot || p.tone === "danger" ? 10 : 7, color: "#fff", weight: hot ? 3 : 2,
        fillColor: TONE[p.tone ?? "default"], fillOpacity: 1,
      }).bindTooltip(p.label, { permanent: !!p.permanent || hot, direction: "top", offset: [0, -8] });
      mk.on("click", () => clickRef.current?.(p.id));
      mk.addTo(layer);
    }
    if (fitPins && pins.length) m.fitBounds(L.latLngBounds(pins.map((p) => [p.lat, p.lng])), { padding: [40, 40], maxZoom: 16 });
  }, [pins, lines, highlight, fitPins]);

  return <div ref={el} className={className} />;
}
