"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { FeatureCollection } from "geojson";
import type { MapLayerMouseEvent } from "maplibre-gl";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef, useState } from "react";
import MapGL, { Layer, NavigationControl, Source, type MapRef } from "react-map-gl/maplibre";

import { BAND_COLOR, UNCERTAINTY_OPACITY } from "@/lib/risk";
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
}

export default function RiskMap({ wards, idKey, selected, onSelect, reports, hotspots, center }: MapProps) {
  const { resolvedTheme } = useTheme();
  const mapRef = useRef<MapRef>(null);
  const [geo, setGeo] = useState<FeatureCollection | null>(null);
  const [hover, setHover] = useState<{ name: string; x: number; y: number } | null>(null);
  const hoverId = useRef<string | number | null>(null);

  useEffect(() => {
    fetch("/data/wards.geojson").then((r) => r.json()).then(setGeo).catch(() => setGeo(null));
  }, []);

  const data = useMemo(() => {
    if (!geo) return null;
    const byId = new Map((wards ?? []).map((w) => [w.ward_id, w]));
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
      setHover({ name: String(f.properties?.name), x: e.point.x, y: e.point.y });
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
        attributionControl={{ compact: true }}
        style={{ width: "100%", height: "100%" }}
      >
        <NavigationControl position="bottom-right" showCompass={false} />
        {data && (
          <Source id="wards" type="geojson" data={data} promoteId="ward_id">
            <Layer id="ward-fill" type="fill" paint={{
              "fill-color": ["match", ["get", "band"],
                "low", BAND_COLOR.low, "moderate", BAND_COLOR.moderate, "high", BAND_COLOR.high, "very_high", BAND_COLOR.very_high, "#9AA5B1"],
              "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.95, ["get", "opacity"]],
            }} />
            <Layer id="ward-line" type="line" paint={{ "line-color": resolvedTheme === "dark" ? "#0D1626" : "#FFFFFF", "line-width": 0.7, "line-opacity": 0.9 }} />
            <Layer id="ward-selected" type="line" filter={["==", ["get", "ward_id"], selected ?? ""]}
              paint={{ "line-color": resolvedTheme === "dark" ? "#E9EFF5" : "#14213D", "line-width": 2.5 }} />
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
              "circle-color": ["match", ["get", "status"], "verified", "#0E7C7B", "#5A6880"],
              "circle-stroke-color": "#FFFFFF", "circle-stroke-width": 1,
            }} />
          </Source>
        )}
      </MapGL>
      {hover && (
        <div className="pointer-events-none absolute z-10 rounded bg-ink px-2 py-1 text-xs text-paper"
          style={{ left: hover.x + 12, top: hover.y + 12 }}>
          {hover.name}
        </div>
      )}
    </div>
  );
}
