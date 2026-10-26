"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { ForecastFan } from "@/components/charts/forecast-fan";
import { useApp } from "@/components/providers";
import { Notice, PageHeader, Segmented, Skeleton } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { cn, nf, weekLabel } from "@/lib/format";
import type { Forecast } from "@/lib/types";

interface ModelInfo {
  model: { version: string | null; type: string };
  backtest: { model: string; horizon: number; mae: number; wis?: number; coverage80?: number; skill_vs_seasonal_naive?: number; n: number }[];
  drift: { overall: string; significant: string[] };
}

const MODEL_NAMES: Record<string, string> = {
  persistence: "Same as this week",
  seasonal_naive: "Same week last year",
  sarima: "Time-series (ARIMA + seasonality)",
  glm_poisson: "Poisson regression",
  gbm: "Gradient boosting",
  ensemble: "Ensemble",
};

export default function ForecastPage() {
  const { lang } = useApp();
  const { data: f, error } = useApi<Forecast>("/v2/forecast");
  const { data: m } = useApi<ModelInfo>("/v2/model");
  const [span, setSpan] = useState(104);
  const [h, setH] = useState(1);

  const table = useMemo(() => {
    if (!m) return [];
    return m.backtest.filter((r) => r.horizon === h).sort((a, b) => (a.wis ?? a.mae) - (b.wis ?? b.mae));
  }, [m, h]);

  return (
    <div className="mx-auto max-w-[1240px] px-4 py-8 md:px-6 md:py-12">
      <PageHeader title="City forecast" lede="Weekly reported dengue cases for BBMP, the next four weeks, and how well this forecast has done in the past.">
        <Segmented label="Time span" value={span} onChange={setSpan} options={[{ value: 52, label: "1 year" }, { value: 104, label: "2 years" }, { value: 156, label: "3 years" }]} />
      </PageHeader>

      {error && <Notice tone="warn" title="The forecast isn't available right now">{error.message}</Notice>}
      {!f && !error && <Skeleton className="h-[420px]" />}
      {f && (
        <>
          <div className="rounded-lg border border-line bg-surface p-4 md:p-6"><ForecastFan forecast={f} weeks={span} height={340} /></div>

          <section className="mt-12 grid gap-10 lg:grid-cols-2">
            <div>
              <h2 className="font-display text-2xl font-semibold tracking-tight">Next four weeks</h2>
              <table className="mt-4 w-full text-sm">
                <caption className="sr-only">Forecast of weekly reported cases with prediction intervals</caption>
                <thead className="text-left text-muted">
                  <tr className="border-b border-line"><th className="py-2 font-normal">Week</th><th className="py-2 text-right font-normal">Expected</th><th className="py-2 text-right font-normal">50% range</th><th className="py-2 text-right font-normal">95% range</th></tr>
                </thead>
                <tbody className="tnum">
                  {f.forecast.map((p) => (
                    <tr key={p.horizon} className="border-b border-line/70">
                      <td className="py-3">{weekLabel(p.week_end, lang)}</td>
                      <td className="py-3 text-right font-semibold">{nf(p.median)}</td>
                      <td className="py-3 text-right text-muted">{nf(p.lo50)}–{nf(p.hi50)}</td>
                      <td className="py-3 text-right text-muted">{nf(p.lo95)}–{nf(p.hi95)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-xs text-muted">A 95% range means: in past backtests, the real number fell inside ranges like this about 95% of the time.</p>
            </div>

            {f.drivers && (
              <div>
                <h2 className="font-display text-2xl font-semibold tracking-tight">What&apos;s driving next week</h2>
                <p className="mt-1 text-sm text-muted">Each factor&apos;s push on the forecast compared with a typical week ({f.drivers.method}).</p>
                <ul className="mt-5 space-y-4">
                  {f.drivers.factors.map((d) => (
                    <li key={d.factor} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1.5">
                      <span className="text-sm">{d.label}</span>
                      <span className={cn("tnum text-sm font-medium", d.direction === "up" ? "text-[#E06A2C]" : "text-lake")}>{d.effect_pct > 0 ? "+" : ""}{nf(d.effect_pct, 0)}%</span>
                      <div className="col-span-2 h-2 rounded-full bg-ink/[0.06]">
                        <div className={cn("h-full rounded-full", d.direction === "up" ? "bg-[#E06A2C]" : "bg-lake")} style={{ width: `${Math.min(100, Math.abs(d.effect_pct))}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        </>
      )}

      {m && (
        <section className="mt-14 border-t border-line pt-10">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div className="max-w-prose">
              <h2 className="font-display text-2xl font-semibold tracking-tight">How accurate has this been?</h2>
              <p className="mt-2 text-sm text-muted">Every model was re-run week by week on past data, only using what was known at the time. Skill compares its error with simply repeating the same week last year: above 0% means better.</p>
            </div>
            <Segmented label="Forecast horizon" value={h} onChange={setH} size="sm" options={[1, 2, 3, 4].map((x) => ({ value: x, label: `${x} wk` }))} />
          </div>
          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-muted">
                <tr className="border-b border-line">
                  <th className="py-2 font-normal">Method</th><th className="py-2 text-right font-normal">Avg. error (cases)</th>
                  <th className="py-2 text-right font-normal">Interval score</th><th className="py-2 text-right font-normal">80% range hit rate</th>
                  <th className="py-2 text-right font-normal">Skill</th>
                </tr>
              </thead>
              <tbody className="tnum">
                {table.map((r) => (
                  <tr key={r.model} className={cn("border-b border-line/70", r.model === m.model.type && "bg-lake-soft/60")}>
                    <td className="py-2.5">{MODEL_NAMES[r.model] ?? r.model}{r.model === m.model.type && <span className="ml-2 text-xs font-medium text-lake">in use</span>}</td>
                    <td className="py-2.5 text-right">{nf(r.mae, 1)}</td>
                    <td className="py-2.5 text-right">{r.wis != null ? nf(r.wis, 1) : "–"}</td>
                    <td className="py-2.5 text-right">{r.coverage80 != null ? `${Math.round(r.coverage80 * 100)}%` : "–"}</td>
                    <td className={cn("py-2.5 text-right font-medium", (r.skill_vs_seasonal_naive ?? 0) > 0 ? "text-lake" : "text-[#9E2338]")}>
                      {r.skill_vs_seasonal_naive != null ? `${r.skill_vs_seasonal_naive > 0 ? "+" : ""}${Math.round(r.skill_vs_seasonal_naive * 100)}%` : "–"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-sm text-muted">
            Data drift: {m.drift.overall === "ok" ? "recent weeks look like the training data." : `recent data differs in ${m.drift.significant.join(", ")}, so treat this week's forecast with extra care.`}{" "}
            <Link href="/methodology" className="text-lake underline-offset-2 hover:underline">Read how it works</Link>
          </p>
        </section>
      )}
    </div>
  );
}
