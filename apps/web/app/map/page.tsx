"use client";

import { Layers } from "lucide-react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Legend, WardPanel } from "@/components/map/ward-panel";
import { useApp } from "@/components/providers";
import { WardSearch } from "@/components/ward-search";
import { Notice, Segmented, Skeleton } from "@/components/ui/primitives";
import { track, useApi } from "@/lib/api";
import { cn } from "@/lib/format";
import type { Hotspot, WardRisk } from "@/lib/types";

const RiskMap = dynamic(() => import("@/components/map/risk-map"), { ssr: false, loading: () => <Skeleton className="h-full w-full rounded-none" /> });

function MapScreen() {
  const { t } = useApp();
  const params = useSearchParams();
  const router = useRouter();
  const [horizon, setHorizon] = useState(1);
  const [selected, setSelected] = useState<string | null>(params.get("ward"));
  const [showReports, setShowReports] = useState(false);
  const [showHotspots, setShowHotspots] = useState(true);
  const [layersOpen, setLayersOpen] = useState(false);

  const { data: city } = useApi<{ city: { lat: number; lon: number }; ward_id_key: string }>("/v2/city");
  const { data: risk, error } = useApi<{ wards: WardRisk[]; bands_per_100k: [number, string][] | null; week_end: string }>(`/v2/wards/risk?horizon=${horizon}`);
  const { data: reports } = useApi<{ reports: { id: string; lat: number; lon: number; status: string }[] }>(showReports ? "/v2/reports/public" : null);
  const { data: hs } = useApi<{ hotspots: Hotspot[] }>(showHotspots ? "/v2/hotspots" : null);

  useEffect(() => {
    const url = selected ? `/map?ward=${encodeURIComponent(selected)}` : "/map";
    router.replace(url, { scroll: false });
    if (selected) track("ward_opened", { ward_id: selected, horizon });
  }, [selected]); // eslint-disable-line react-hooks/exhaustive-deps

  const bandMax = risk?.bands_per_100k?.[3]?.[0] ? risk.bands_per_100k[3][0] * 1.6 : 20;

  return (
    <div className="relative h-[calc(100dvh-56px-64px)] lg:h-[calc(100dvh-56px)]">
      {city && (
        <RiskMap wards={risk?.wards} idKey={city.ward_id_key} selected={selected} onSelect={setSelected}
          reports={showReports ? reports?.reports : undefined} hotspots={showHotspots ? hs?.hotspots : undefined}
          center={[city.city.lat, city.city.lon]} />
      )}

      {/* Top controls */}
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex flex-wrap items-start gap-3 p-3 lg:pl-[440px]">
        <div className="pointer-events-auto w-full max-w-sm lg:hidden"><WardSearch /></div>
        <div className="pointer-events-auto rounded border border-line bg-surface/95 p-1 shadow-float backdrop-blur">
          <Segmented label={t("map.week")} value={horizon} onChange={setHorizon} size="sm"
            options={[1, 2, 3, 4].map((h) => ({ value: h, label: h === 1 ? t("map.thisWeek") : t("map.inWeeks", { n: h }) }))} />
        </div>
        <div className="pointer-events-auto relative ml-auto">
          <button onClick={() => setLayersOpen((o) => !o)} aria-expanded={layersOpen}
            className="flex h-10 items-center gap-2 rounded border border-line bg-surface/95 px-3 text-sm shadow-float backdrop-blur">
            <Layers className="h-4 w-4" />{t("map.layers")}
          </button>
          {layersOpen && (
            <div className="absolute right-0 mt-2 w-56 space-y-2 rounded border border-line bg-surface p-3 text-sm shadow-float">
              <label className="flex items-center gap-2"><input type="checkbox" checked={showHotspots} onChange={(e) => setShowHotspots(e.target.checked)} className="accent-[#0E7C7B]" />{t("map.hotspots")}</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={showReports} onChange={(e) => setShowReports(e.target.checked)} className="accent-[#0E7C7B]" />{t("map.reports")}</label>
            </div>
          )}
        </div>
      </div>

      {/* Desktop side panel */}
      <aside className="absolute bottom-3 left-3 top-3 z-20 hidden w-[416px] overflow-hidden rounded-lg border border-line bg-surface shadow-float lg:block">
        {selected ? (
          <WardPanel wardId={selected} horizon={horizon} onClose={() => setSelected(null)} bandMax={bandMax} />
        ) : (
          <div className="p-5">
            <h1 className="font-display text-2xl font-semibold tracking-tight">{t("nav.map")}</h1>
            <p className="mt-2 text-sm text-muted">Estimated dengue risk by ward for {risk ? new Date(risk.week_end).toLocaleDateString("en-IN", { day: "numeric", month: "long" }) : "…"}. Pick a ward on the map or search.</p>
            <div className="mt-5"><WardSearch autoFocus /></div>
            {error && <div className="mt-5"><Notice tone="warn" title="Risk estimates aren't available">{error.message}</Notice></div>}
            {risk && (
              <div className="mt-8">
                <h2 className="text-sm font-medium">Highest estimated risk</h2>
                <ol className="mt-3 divide-y divide-line">
                  {[...risk.wards].sort((a, b) => b.rate_per_100k - a.rate_per_100k).slice(0, 8).map((w) => (
                    <li key={w.ward_id}>
                      <button onClick={() => setSelected(w.ward_id)} className="flex w-full items-center justify-between py-2.5 text-left text-sm hover:text-lake">
                        <span>{w.ward_name}</span>
                        <span className="tnum text-muted">{w.rate_per_100k.toFixed(1)} <span className="text-xs">/100k</span></span>
                      </button>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        )}
      </aside>

      {/* Legend */}
      <div className="absolute bottom-3 right-14 z-10 hidden md:block"><Legend bands={risk?.bands_per_100k ?? null} /></div>

      {/* Mobile bottom sheet */}
      {selected && (
        <div className={cn("absolute inset-x-0 bottom-0 z-20 max-h-[70%] overflow-hidden rounded-t-xl border-t border-line bg-surface shadow-float lg:hidden")}>
          <div className="mx-auto mt-2 h-1 w-10 rounded-full bg-ink/20" aria-hidden />
          <div className="h-[calc(70dvh-80px)]">
            <WardPanel wardId={selected} horizon={horizon} onClose={() => setSelected(null)} bandMax={bandMax} />
          </div>
        </div>
      )}
    </div>
  );
}

export default function MapPage() {
  return <Suspense fallback={<Skeleton className="h-[calc(100dvh-56px)] w-full rounded-none" />}><MapScreen /></Suspense>;
}
