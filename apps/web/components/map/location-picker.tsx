"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { LocateFixed } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import MapGL, { AttributionControl, Marker, NavigationControl } from "react-map-gl/maplibre";
import { toast } from "sonner";

import { Button } from "@/components/ui/primitives";
import { api } from "@/lib/api";

export interface PickedLocation { lat: number; lon: number; ward_id: string | null; ward_name: string | null }

export default function LocationPicker({ value, onChange, center = [12.9716, 77.5946], height = 260, autoLocate = false }: {
  value: PickedLocation | null; onChange: (v: PickedLocation) => void; center?: [number, number]; height?: number; autoLocate?: boolean;
}) {
  const { resolvedTheme } = useTheme();
  const [busy, setBusy] = useState(false);

  const set = async (lat: number, lon: number) => {
    try {
      const r = await api<{ ward_id: string | null; ward_name: string | null }>(`/v2/locate?lat=${lat}&lon=${lon}`);
      onChange({ lat, lon, ...r });
    } catch {
      onChange({ lat, lon, ward_id: null, ward_name: null });
    }
  };

  const locate = () => {
    if (!navigator.geolocation) return toast.error("Location isn't available in this browser. Tap the map instead.");
    setBusy(true);
    navigator.geolocation.getCurrentPosition(
      (p) => { set(p.coords.latitude, p.coords.longitude).finally(() => setBusy(false)); },
      () => { setBusy(false); toast.error("Location permission was denied. Tap the map to choose the spot."); },
      { enableHighAccuracy: true, timeout: 12000 },
    );
  };

  useEffect(() => { if (autoLocate && !value) locate(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-2">
      <div className="overflow-hidden rounded-lg border border-line-strong" style={{ height }}>
        <MapGL
          initialViewState={{ latitude: value?.lat ?? center[0], longitude: value?.lon ?? center[1], zoom: value ? 15 : 11 }}
          mapStyle={resolvedTheme === "dark" ? "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json" : "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"}
          onClick={(e) => set(e.lngLat.lat, e.lngLat.lng)}
          cursor="crosshair"
          attributionControl={false}
          style={{ width: "100%", height: "100%" }}
        >
          <NavigationControl position="bottom-right" showCompass={false} />
          <AttributionControl compact position="bottom-left" />
          {value && (
            <Marker latitude={value.lat} longitude={value.lon} anchor="bottom" draggable onDragEnd={(e) => set(e.lngLat.lat, e.lngLat.lng)}>
              <svg width="28" height="36" viewBox="0 0 28 36" aria-hidden><path d="M14 0C6.3 0 0 6.1 0 13.6 0 23.8 14 36 14 36s14-12.2 14-22.4C28 6.1 21.7 0 14 0Z" fill="#0B6B68" /><circle cx="14" cy="13.5" r="5" fill="#FFFFFF" /></svg>
            </Marker>
          )}
        </MapGL>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted" aria-live="polite">
          {value ? (value.ward_name ? <>Ward: <span className="font-medium text-ink">{value.ward_name}</span>. Drag the pin to adjust.</> : "This spot is outside the BBMP wards.") : "Tap the map or use your location. You can drag the pin afterwards."}
        </p>
        <Button type="button" variant="secondary" size="sm" onClick={locate} loading={busy}><LocateFixed className="h-4 w-4" />Use my location</Button>
      </div>
    </div>
  );
}
