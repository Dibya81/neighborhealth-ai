"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { FeatureCollection } from "geojson";
import type { MapLayerMouseEvent } from "maplibre-gl";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef, useState } from "react";
import MapGL, { AttributionControl, Layer, NavigationControl, Source, type MapRef } from "react-map-gl/maplibre";

import { BAND_COLOR, RELATIVE_RAMP, UNCERTAINTY_OPACITY } from "@/lib/risk";
import type { Hotspot, WardRisk } from "@/lib/types";

const STYLES = {
  light: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
};

export interface MapProps {
  wards: WardRisk[] | undefined;
  idKey: string;
  selected: string | null;
  onSelect: (wardId: string | null) => void;
  reports?: { id: string; lat: number; lon: number; status: string }[];
  hotspots?: Hotspot[];
  center: [number, number];
  /** "band": absolute risk bands. "relative": each ward against the rest of the city (quarters). */
  mode?: "band" | "relative";
}

export default function RiskMap({ wards, idKey, selected, onSelect, reports, hotspots, center, mode = "band" }: MapProps) {
  const { resolvedTheme } = useTheme();
  const mapRef = useRef<MapRef>(null);
  const [geo, setGeo] = useState<FeatureCollection | null>(null);
  const [hover, setHover] = useState<{ name: string; band: string; rate: string; x: number; y: number } | null>(null);
  const hoverId = useRef<string | number | null>(null);

  useEffect(() => {
    fetch("/data/wards.geojson").then((r) => r.json()).then(setGeo).catch(() => setGeo(null));
  }, []);

  const data = useMemo(() => {
    if (!geo) return null;
    const byId = new Map((wards ?? []).map((w) => [w.ward_id, w]));
    const rates = (wards ?? []).map((w) => w.rate_per_100k).sort((a, b) => a - b);
    const q = (p: number) => rates[Math.min(rates.length - 1, Math.floor(p * rates.length))] ?? 0;
    const [q1, q2, q3] = [q(0.25), q(0.5), q(0.75)];
    return {
      ...geo,
      features: geo.features.map((f) => {
        const id = String(f.properties?.[idKey]);
        const w = byId.get(id);
        return {
          ...f,
          properties: {
            ...f.properties,
            ward_id: id,
            name: w?.ward_name ?? f.properties?.KGISWardName ?? id,
            band: w?.band ?? "none",
            rate: w ? w.rate_per_100k : null,
            rel: !w ? -1 : w.rate_per_100k <= q1 ? 0 : w.rate_per_100k <= q2 ? 1 : w.rate_per_100k <= q3 ? 2 : 3,
            opacity: w ? UNCERTAINTY_OPACITY[w.uncertainty] : 0.15,
          },
        };
      }),
    } as FeatureCollection;
  }, [geo, wards, idKey]);

  // Fly to a selected ward (e.g. from search or a shared link).
  useEffect(() => {
    if (!selected || !data || !mapRef.current) return;
    const f = data.features.find((x) => x.properties?.ward_id === selected);
    if (!f || (f.geometry.type !== "Polygon" && f.geometry.type !== "MultiPolygon")) return;
    const coords = (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates).flat(2) as number[][];
    const xs = coords.map((c) => c[0]);
    const ys = coords.map((c) => c[1]);
    mapRef.current.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]],
      { padding: { top: 80, bottom: 80, left: window.innerWidth > 1024 ? 460 : 40, right: 40 }, maxZoom: 14, duration: 700 });
  }, [selected, data]);

  const reportsGeo = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: (reports ?? []).map((r) => ({ type: "Feature" as const, properties: { status: r.status }, geometry: { type: "Point" as const, coordinates: [r.lon, r.lat] } })),
  }), [reports]);

  const hotspotsGeo = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: (hotspots ?? []).map((h) => ({ type: "Feature" as const, properties: { reports: h.reports }, geometry: { type: "Point" as const, coordinates: [h.lon, h.lat] } })),
  }), [hotspots]);

  const onMove = (e: MapLayerMouseEvent) => {
    const map = mapRef.current?.getMap();
    const f = e.features?.[0];
    if (!map) return;
    if (hoverId.current != null) map.setFeatureState({ source: "wards", id: hoverId.current }, { hover: false });
    if (f && f.id != null) {
      hoverId.current = f.id;
      map.setFeatureState({ source: "wards", id: f.id }, { hover: true });
      const r = f.properties?.rate;
      setHover({ name: String(f.properties?.name), band: String(f.properties?.band), rate: r != null && r !== "null" ? Number(r).toFixed(1) : "", x: e.point.x, y: e.point.y });
    } else {
      hoverId.current = null;
      setHover(null);
    }
  };

  return (
    <div className="relative h-full w-full">
      <MapGL
        ref={mapRef}
        initialViewState={{ longitude: center[1], latitude: center[0], zoom: 10.6 }}
        mapStyle={resolvedTheme === "dark" ? STYLES.dark : STYLES.light}
        interactiveLayerIds={["ward-fill"]}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        onClick={(e) => onSelect((e.features?.[0]?.properties?.ward_id as string) ?? null)}
        cursor={hover ? "pointer" : "grab"}
        attributionControl={false}
        style={{ width: "100%", height: "100%" }}
      >
        <NavigationControl position="bottom-right" showCompass={false} />
        <AttributionControl compact position="bottom-left" />
        {data && (
          <Source id="wards" type="geojson" data={data} promoteId="ward_id">
            <Layer id="ward-fill" type="fill" paint={{
              "fill-color": mode === "relative"
                ? ["match", ["get", "rel"], 0, RELATIVE_RAMP[0], 1, RELATIVE_RAMP[1], 2, RELATIVE_RAMP[2], 3, RELATIVE_RAMP[3], "#9AA5B1"]
                : ["match", ["get", "band"],
                    "low", BAND_COLOR.low, "moderate", BAND_COLOR.moderate, "high", BAND_COLOR.high, "very_high", BAND_COLOR.very_high, "#9AA5B1"],
              "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.95, ["get", "opacity"]],
            }} />
            <Layer id="ward-line" type="line" paint={{ "line-color": resolvedTheme === "dark" ? "#0B121E" : "#FFFFFF", "line-width": 0.7, "line-opacity": 0.9 }} />
            <Layer id="ward-selected" type="line" filter={["==", ["get", "ward_id"], selected ?? ""]}
              paint={{ "line-color": resolvedTheme === "dark" ? "#E8EDF3" : "#0E1A2B", "line-width": 2.75 }} />
          </Source>
        )}
        {hotspots && hotspots.length > 0 && (
          <Source id="hotspots" type="geojson" data={hotspotsGeo}>
            <Layer id="hotspot-halo" type="circle" paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 10, 15, 40],
              "circle-color": "#9E2338", "circle-opacity": 0.12, "circle-stroke-color": "#9E2338", "circle-stroke-width": 1.5,
            }} />
          </Source>
        )}
        {reports && reports.length > 0 && (
          <Source id="reports" type="geojson" data={reportsGeo}>
            <Layer id="report-dots" type="circle" paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 2.5, 15, 6],
              "circle-color": ["match", ["get", "status"], "verified", "#0B6B68", "#52607A"],
              "circle-stroke-color": "#FFFFFF", "circle-stroke-width": 1,
            }} />
          </Source>
        )}
      </MapGL>
      {hover && (
        <div className="pointer-events-none absolute z-10 rounded-lg bg-ink px-3 py-2 text-xs text-paper shadow-float"
          style={{ left: hover.x + 14, top: hover.y + 14 }}>
          <p className="font-semibold">{hover.name}</p>
          {hover.rate && <p className="num mt-0.5 opacity-80">{hover.rate} per 100,000 a week</p>}
        </div>
      )}
    </div>
  );
}
