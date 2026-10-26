"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useTheme } from "next-themes";
import MapGL, { Layer, Marker, NavigationControl, Source } from "react-map-gl/maplibre";

export interface RoutePlan {
  route_id: string;
  method: string;
  depot: { lat: number; lon: number };
  routes: { team: number; total_minutes: number; travel_minutes: number; stops: { stop_id: string; label: string | null; lat: number; lon: number; priority: number; eta_min: number }[] }[];
  dropped: string[];
  total_minutes: number;
  naive_single_route_minutes: number;
}

export const TEAM_COLORS = ["#0E7C7B", "#E06A2C", "#5B4BDB", "#9E2338", "#2E7D32", "#B7791F"];

export default function RouteMap({ plan, tasks }: { plan: RoutePlan | null; tasks: { id: string; lat: number; lon: number }[] }) {
  const { resolvedTheme } = useTheme();
  const center = plan?.depot ?? { lat: 12.9716, lon: 77.5946 };
  const lines = {
    type: "FeatureCollection" as const,
    features: (plan?.routes ?? []).map((r) => ({
      type: "Feature" as const,
      properties: { color: TEAM_COLORS[(r.team - 1) % TEAM_COLORS.length] },
      geometry: { type: "LineString" as const, coordinates: [[plan!.depot.lon, plan!.depot.lat], ...r.stops.map((s) => [s.lon, s.lat]), [plan!.depot.lon, plan!.depot.lat]] },
    })),
  };
  return (
    <MapGL initialViewState={{ latitude: center.lat, longitude: center.lon, zoom: 11 }}
      mapStyle={resolvedTheme === "dark" ? "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json" : "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"}
      attributionControl={{ compact: true }} style={{ width: "100%", height: "100%" }}>
      <NavigationControl position="bottom-right" showCompass={false} />
      <Source id="routes" type="geojson" data={lines}>
        <Layer id="route-lines" type="line" paint={{ "line-color": ["get", "color"], "line-width": 3, "line-opacity": 0.85 }} layout={{ "line-join": "round", "line-cap": "round" }} />
      </Source>
      {!plan && tasks.map((t) => (
        <Marker key={t.id} latitude={t.lat} longitude={t.lon}><span className="block h-2.5 w-2.5 rounded-full border border-white bg-ink" /></Marker>
      ))}
      {plan?.routes.map((r) => r.stops.map((s, i) => (
        <Marker key={s.stop_id} latitude={s.lat} longitude={s.lon}>
          <span className="grid h-5 w-5 place-items-center rounded-full border-2 border-white text-[10px] font-semibold text-white"
            style={{ background: TEAM_COLORS[(r.team - 1) % TEAM_COLORS.length] }}>{i + 1}</span>
        </Marker>
      )))}
      {plan && (
        <Marker latitude={plan.depot.lat} longitude={plan.depot.lon}>
          <span className="rounded bg-ink px-1.5 py-0.5 text-[10px] font-semibold text-paper">Depot</span>
        </Marker>
      )}
    </MapGL>
  );
}
