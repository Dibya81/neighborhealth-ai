"use client";

import { Layers } from "lucide-react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Legend, WardPanel } from "@/components/map/ward-panel";
import { useApp } from "@/components/providers";
import { WardSearch } from "@/components/ward-search";
import { BandPill, Notice, Segmented, Skeleton } from "@/components/ui/primitives";
import { track, useApi } from "@/lib/api";
import { cn, nf } from "@/lib/format";
import type { Hotspot, WardRisk } from "@/lib/types";

const RiskMap = dynamic(() => import("@/components/map/risk-map"), { ssr: false, loading: () => <Skeleton className="h-full w-full rounded-none" /> });

type Mode = "band" | "relative";

function MapScreen() {
  const { t, lang } = useApp();
  const params = useSearchParams();
  const router = useRouter();
  const [horizon, setHorizon] = useState(1);
  const [selected, setSelected] = useState<string | null>(params.get("ward"));
  const [showReports, setShowReports] = useState(false);
  const [showHotspots, setShowHotspots] = useState(true);
  const [layersOpen, setLayersOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("band");

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
  const weekStart = risk ? new Date(new Date(risk.week_end + "T00:00:00").getTime() - 6 * 86_400_000) : null;
  const weekText = weekStart ? new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "long", year: "numeric" }).format(weekStart) : "";
  const top = risk ? [...risk.wards].sort((a, b) => b.rate_per_100k - a.rate_per_100k).slice(0, 8) : [];

  const shading = (
    <div>
      <p className="mb-2 text-sm font-medium">Shade wards by</p>
      <Segmented<Mode> label="Shading" size="sm" value={mode} onChange={setMode}
        options={[{ value: "band", label: "Risk level" }, { value: "relative", label: "Compare wards" }]} />
    </div>
  );

  return (
    <div className="relative h-full">
      {city && (
        <RiskMap wards={risk?.wards} idKey={city.ward_id_key} selected={selected} onSelect={setSelected} mode={mode}
          reports={showReports ? reports?.reports : undefined} hotspots={showHotspots ? hs?.hotspots : undefined}
          center={[city.city.lat, city.city.lon]} />
      )}

      {/* Top controls */}
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex flex-wrap items-start gap-2 p-3 lg:pl-[444px]">
        <div className="pointer-events-auto w-full lg:hidden"><WardSearch /></div>
        <div className="pointer-events-auto max-w-full overflow-x-auto rounded-lg border border-line-strong bg-surface/95 p-0.5 shadow-float backdrop-blur">
          <Segmented label={t("map.week")} value={horizon} onChange={setHorizon} size="sm"
            options={[1, 2, 3, 4].map((h) => ({ value: h, label: h === 1 ? t("map.thisWeek") : t("map.inWeeks", { n: h }) }))} />
        </div>
        <div className="pointer-events-auto relative ml-auto">
          <button onClick={() => setLayersOpen((o) => !o)} aria-expanded={layersOpen}
            className="flex h-10 items-center gap-2 rounded-lg border border-line-strong bg-surface/95 px-3 text-sm font-medium shadow-float backdrop-blur transition-colors hover:border-ink/40">
            <Layers className="h-4 w-4" />{t("map.layers")}
          </button>
          {layersOpen && (
            <div className="absolute right-0 mt-2 w-64 space-y-4 rounded-lg border border-line-strong bg-surface p-4 text-sm shadow-float">
              <div className="lg:hidden">{shading}</div>
              <div className="space-y-2.5">
                <label className="flex items-center gap-2.5"><input type="checkbox" checked={showHotspots} onChange={(e) => setShowHotspots(e.target.checked)} className="h-4 w-4 accent-[rgb(var(--lake))]" />{t("map.hotspots")}</label>
                <label className="flex items-center gap-2.5"><input type="checkbox" checked={showReports} onChange={(e) => setShowReports(e.target.checked)} className="h-4 w-4 accent-[rgb(var(--lake))]" />{t("map.reports")}</label>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Desktop side panel */}
      <aside className="absolute bottom-4 left-4 top-4 z-20 hidden w-[412px] overflow-hidden rounded-lg border border-line-strong bg-surface shadow-float lg:block">
        {selected ? (
          <WardPanel wardId={selected} horizon={horizon} onClose={() => setSelected(null)} bandMax={bandMax} />
        ) : (
          <div className="scrollbar-thin h-full overflow-y-auto p-6">
            <h1 className="text-2xl font-semibold tracking-tight">{t("nav.map")}</h1>
            <p className="mt-2 text-sm text-muted">
              Estimated dengue risk for each ward in the week of {weekText ? weekText : "..."}. Choose a ward on the map or search for one.
            </p>
            <div className="mt-6"><WardSearch autoFocus /></div>
            <div className="mt-6">{shading}</div>
            {error && <div className="mt-6"><Notice tone="warn" title="Risk estimates aren't available">{error.message}</Notice></div>}
            {risk && (
              <div className="mt-8">
                <h2 className="text-sm font-semibold">Highest estimated risk</h2>
                <ol className="mt-2 divide-y divide-line border-y border-line">
                  {top.map((w, i) => (
                    <li key={w.ward_id}>
                      <button onClick={() => setSelected(w.ward_id)} className="flex w-full items-center gap-3 py-3 text-left text-sm transition-colors hover:text-lake">
                        <span className="num w-5 text-muted">{i + 1}</span>
                        <span className="min-w-0 flex-1 truncate">{w.ward_name}</span>
                        <BandPill band={w.band} lang={lang} />
                        <span className="num w-12 text-right text-muted">{nf(w.rate_per_100k, 1)}</span>
                      </button>
                    </li>
                  ))}
                </ol>
                <p className="mt-3 text-xs leading-relaxed text-muted">
                  Wards differ only a little, because each ward&apos;s number is the city forecast shared out by population and density. Use &ldquo;Compare wards&rdquo; to see the differences.
                </p>
              </div>
            )}
          </div>
        )}
      </aside>

      {/* Legend */}
      <div className={cn("absolute bottom-4 right-14 z-10 hidden md:block", selected && "lg:right-14")}><Legend bands={risk?.bands_per_100k ?? null} mode={mode} /></div>

      {/* Mobile bottom sheet */}
      {selected && (
        <div className="absolute inset-x-0 bottom-0 z-20 max-h-[72%] overflow-hidden rounded-t-xl border-t border-line-strong bg-surface shadow-float lg:hidden">
          <div className="mx-auto mt-2 h-1 w-10 rounded-full bg-ink/20" aria-hidden />
          <div className="h-[calc(66dvh-80px)]">
            <WardPanel wardId={selected} horizon={horizon} onClose={() => setSelected(null)} bandMax={bandMax} />
          </div>
        </div>
      )}
    </div>
  );
}

export default function MapPage() {
  return <Suspense fallback={<Skeleton className="h-full w-full rounded-none" />}><MapScreen /></Suspense>;
}
