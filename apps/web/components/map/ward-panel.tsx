"use client";

import { ArrowDownRight, ArrowUpRight, Bell, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useApp } from "@/components/providers";
import { BandPill, Button, Skeleton } from "@/components/ui/primitives";
import { api, track, useApi } from "@/lib/api";
import { cn, nf, weekLabel } from "@/lib/format";
import { BAND_COLOR, BANDS } from "@/lib/risk";
import type { TKey } from "@/lib/i18n";
import type { WardDetail } from "@/lib/types";

function RangeBar({ value, lo, hi, max }: { value: number; lo: number; hi: number; max: number }) {
  const pct = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  return (
    <div className="relative mt-3 h-2.5 rounded-full bg-ink/[0.07]" aria-hidden>
      <div className="absolute inset-y-0 rounded-full bg-[#F2B33D]/55" style={{ left: pct(lo), width: `calc(${pct(hi)} - ${pct(lo)})` }} />
      <div className="absolute -top-1 h-[18px] w-[3px] rounded bg-ink" style={{ left: `calc(${pct(value)} - 1px)` }} />
    </div>
  );
}

export function WardPanel({ wardId, horizon, onClose, bandMax }: { wardId: string; horizon: number; onClose: () => void; bandMax: number }) {
  const { t, lang } = useApp();
  const { data, error } = useApi<WardDetail>(`/v2/wards/${encodeURIComponent(wardId)}`);
  const [explain, setExplain] = useState<{ text: string; method: string } | null>(null);
  const [explaining, setExplaining] = useState(false);

  const h = data?.horizons.find((x) => x.horizon === horizon) ?? data?.horizons[0];

  const askExplain = async () => {
    setExplaining(true);
    try {
      const r = await api<{ text: string; method: string }>(`/v2/wards/${encodeURIComponent(wardId)}/explain?horizon=${horizon}&lang=${lang}`);
      setExplain(r);
      track("ward_opened", { ward_id: wardId, source: "explain" });
    } catch (e) {
      setExplain({ text: (e as Error).message, method: "error" });
    } finally {
      setExplaining(false);
    }
  };

  return (
    <section aria-label="Ward details" className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 border-b border-line px-5 pb-4 pt-5">
        <div>
          {data ? <h2 className="font-display text-2xl font-semibold leading-tight tracking-tight">{data.ward_name}</h2> : <Skeleton className="h-7 w-48" />}
          {h && <p className="mt-1 text-sm text-muted">{weekLabel(h.week_end, lang)} · {t("common.estimate")}</p>}
        </div>
        <button onClick={onClose} aria-label={t("common.close")} className="grid h-8 w-8 place-items-center rounded text-muted hover:bg-ink/5 hover:text-ink">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="scrollbar-thin flex-1 space-y-7 overflow-y-auto px-5 py-5">
        {error && <p className="text-sm text-muted">{error.message}</p>}
        {!data && !error && <><Skeleton className="h-20" /><Skeleton className="h-32" /></>}
        {data && h && (
          <>
            <div>
              <div className="flex items-center gap-3">
                <BandPill band={h.band} lang={lang} className="px-3 py-1 text-sm" />
                <span className="text-sm text-muted">{t(`unc.${h.uncertainty}` as TKey)}</span>
              </div>
              <p className="mt-5 text-sm text-muted">{t("ward.estimate")}</p>
              <p className="tnum mt-1 font-display text-4xl font-semibold">{nf(h.rate_per_100k, 1)}</p>
              <RangeBar value={h.rate_per_100k} lo={h.rate_lo80} hi={h.rate_hi80} max={Math.max(bandMax, h.rate_hi80 * 1.1)} />
              <p className="tnum mt-2 text-xs text-muted">80% range {nf(h.rate_lo80, 1)}–{nf(h.rate_hi80, 1)} · about {nf(h.expected_cases, 0)} cases ({nf(h.cases_lo80, 0)}–{nf(h.cases_hi80, 0)}) in ~{nf(data.population_est / 1000, 0)}k people</p>
              <p className="mt-3 text-sm">{t("ward.chanceHigh")}: <b className="tnum">{Math.round(h.p_high * 100)}%</b></p>
            </div>

            <div>
              <h3 className="text-sm font-medium">Next four weeks</h3>
              <ol className="mt-3 grid grid-cols-4 gap-1.5">
                {data.horizons.map((x) => (
                  <li key={x.horizon} className={cn("rounded px-2 py-2 text-center", x.horizon === horizon && "ring-2 ring-ink/70")}
                    style={{ background: BAND_COLOR[x.band] + (x.uncertainty === "high" ? "88" : "") }}>
                    <span className={cn("block text-[11px] font-medium", (x.band === "high" || x.band === "very_high") ? "text-white" : "text-ink")}>
                      {x.horizon === 1 ? t("map.thisWeek") : t("map.inWeeks", { n: x.horizon })}
                    </span>
                    <span className={cn("tnum block text-sm font-semibold", (x.band === "high" || x.band === "very_high") ? "text-white" : "text-ink")}>
                      {nf(x.rate_per_100k, 1)}
                    </span>
                  </li>
                ))}
              </ol>
            </div>

            {data.drivers && data.drivers.factors.length > 0 && (
              <div>
                <h3 className="text-sm font-medium">{t("ward.why")}</h3>
                <p className="mt-1 text-xs text-muted">What moves the city-wide forecast this week ({data.drivers.method}).</p>
                <ul className="mt-3 space-y-2.5">
                  {data.drivers.factors.map((f) => {
                    const width = Math.min(100, Math.abs(f.effect_pct));
                    return (
                      <li key={f.factor}>
                        <div className="flex items-center justify-between text-sm">
                          <span className="flex items-center gap-1.5">
                            {f.direction === "up" ? <ArrowUpRight className="h-4 w-4 text-[#E06A2C]" /> : <ArrowDownRight className="h-4 w-4 text-lake" />}
                            {f.label}
                          </span>
                          <span className="tnum text-muted">{f.effect_pct > 0 ? "+" : ""}{nf(f.effect_pct, 0)}%</span>
                        </div>
                        <div className="mt-1 h-1.5 rounded-full bg-ink/[0.06]">
                          <div className={cn("h-full rounded-full", f.direction === "up" ? "bg-[#E06A2C]" : "bg-lake")} style={{ width: `${width}%` }} />
                        </div>
                      </li>
                    );
                  })}
                </ul>
                <div className="mt-4">
                  {explain ? (
                    <p className="rounded border border-line bg-paper p-3 text-sm leading-relaxed">{explain.text}
                      <span className="mt-2 block text-[11px] text-muted">Written only from the numbers above ({explain.method}).</span></p>
                  ) : (
                    <Button variant="secondary" size="sm" onClick={askExplain} loading={explaining}>
                      <Sparkles className="h-4 w-4" />{t("ward.explain")}
                    </Button>
                  )}
                </div>
              </div>
            )}

            <dl className="grid grid-cols-2 gap-4 border-t border-line pt-5 text-sm">
              <div><dt className="text-muted">{t("ward.reports")}</dt><dd className="tnum mt-0.5 text-lg font-semibold">{data.verified_reports}</dd></div>
              <div><dt className="text-muted">{t("ward.tasks")}</dt><dd className="tnum mt-0.5 text-lg font-semibold">{data.open_tasks}</dd></div>
            </dl>

            <p className="text-xs leading-relaxed text-muted">{t("ward.estimateNote")}</p>
          </>
        )}
      </div>

      <div className="border-t border-line p-4">
        <Link href={`/alerts?ward=${encodeURIComponent(wardId)}`} className="block">
          <Button className="w-full" size="lg"><Bell className="h-4 w-4" />{t("ward.alertMe")}</Button>
        </Link>
      </div>
    </section>
  );
}

export function Legend({ bands }: { bands: [number, string][] | null }) {
  const { t, lang } = useApp();
  return (
    <div className="rounded border border-line bg-surface/95 p-3 text-xs shadow-float backdrop-blur">
      <p className="font-medium">{t("map.legend")}</p>
      <ul className="mt-2 space-y-1">
        {BANDS.map((b, i) => (
          <li key={b} className="flex items-center gap-2">
            <i className="h-3 w-5 rounded-sm" style={{ background: BAND_COLOR[b] }} />
            <span>{t(`band.${b}` as TKey)}</span>
            {bands?.[i] && <span className="tnum ml-auto pl-3 text-muted">≥ {nf(bands[i][0], 1)}</span>}
          </li>
        ))}
      </ul>
      <p className="mt-2 max-w-[180px] text-muted">{t("map.legendNote")}</p>
      <p className="mt-1 text-muted">{lang === "en" ? "Weekly cases per 100k." : ""}</p>
    </div>
  );
}
