import L from "leaflet";
import { useEffect, useRef } from "react";
import { getJSON } from "@/lib/api";

export interface Pin { id: string; lat: number; lng: number; label: string; tone?: "default" | "accent" | "danger" }

const TONE = { default: "#475569", accent: "#0b7a70", danger: "#dc2626" };
let basemapCache: Promise<GeoJSON.FeatureCollection> | null = null;

/** Leaflet with NO tile server: draws our saved OSM river / roads / districts. */
export function OfflineMap({ pins, className, fitPins = false }: { pins: Pin[]; className?: string; fitPins?: boolean }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const pinLayer = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { zoomControl: true, attributionControl: true, preferCanvas: true }).setView([13.745, 100.535], 12);
    m.attributionControl.setPrefix(false).addAttribution("© OpenStreetMap contributors, ODbL");
    map.current = m;
    m.createPane("pins").style.zIndex = "650";   // pins always above the async-loaded basemap
    pinLayer.current = L.layerGroup().addTo(m);
    basemapCache ??= getJSON<GeoJSON.FeatureCollection>("/api/basemap");
    basemapCache.then((gj) => {
      L.geoJSON(gj, {
        style: (f) => {
          const layer = f?.properties?.layer;
          if (layer === "river") return { color: "#7cb4d9", weight: 7, opacity: 0.9 };
          if (layer === "district") return { color: "#cbd5d1", weight: 1, dashArray: "3 4" };
          return { color: "#ffffff", weight: f?.properties?.class === "motorway" ? 4 : 2.5, opacity: 1 };
        },
        interactive: false,
      }).addTo(m);
    }).catch(() => { /* map still shows pins on a plain background */ });
    return () => { m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const layer = pinLayer.current, m = map.current;
    if (!layer || !m) return;
    layer.clearLayers();
    for (const p of pins) {
      L.circleMarker([p.lat, p.lng], { pane: "pins", radius: p.tone === "danger" ? 9 : 6, color: "#fff", weight: 2, fillColor: TONE[p.tone ?? "default"], fillOpacity: 1 })
        .bindTooltip(p.label).addTo(layer);
    }
    if (fitPins && pins.length) m.fitBounds(L.latLngBounds(pins.map((p) => [p.lat, p.lng])), { padding: [30, 30], maxZoom: 16 });
  }, [pins, fitPins]);

  return <div ref={el} className={className} />;
}
