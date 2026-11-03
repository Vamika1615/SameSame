import { useMemo } from "react";
import { useApi } from "@/lib/api";
import { OfflineMap, type Pin } from "@/components/OfflineMap";
import { ErrorState, Loading } from "@/components/States";

type BaseHotels = { source: string; hotels: { osm_id: string; name: string; lat: number; lng: number }[] };

/** M0: base truth on the offline map. M1 replaces this with the listing page. */
export default function HotelsPage() {
  const res = useApi<BaseHotels>("/api/base/hotels");
  const pins = useMemo<Pin[]>(
    () => (res.status === "ready" ? res.data.hotels.map((h) => ({ id: h.osm_id, lat: h.lat, lng: h.lng, label: h.name })) : []),
    [res],
  );
  if (res.status === "loading") return <Loading what="Loading Bangkok base truth" />;
  if (res.status === "error") return <ErrorState error={res.error} onRetry={res.reload} />;
  return (
    <div className="flex h-full flex-col p-8">
      <h1 className="text-3xl font-bold">Hotels · Bangkok</h1>
      <p className="mt-1 text-ink-mute">
        Base truth: {res.data.hotels.length.toLocaleString("en-IN")} hotels from the OpenStreetMap snapshot. Offline basemap, no tile server.
      </p>
      <OfflineMap pins={pins} className="mt-6 min-h-[500px] flex-1 rounded-xl border border-paper-line" />
    </div>
  );
}
