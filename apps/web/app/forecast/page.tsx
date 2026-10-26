"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { ForecastFan } from "@/components/charts/forecast-fan";
import { useApp } from "@/components/providers";
import { Notice, PageHeader, Panel, Segmented, Skeleton } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { cn, nf, weekLabel } from "@/lib/format";
import { longDate, useFreshness } from "@/lib/freshness";
import type { Forecast } from "@/lib/types";

interface BacktestRow { model: string; horizon: number; mae: number; wis?: number; coverage80?: number; skill_vs_seasonal_naive?: number; n: number }
interface ModelInfo {
  model: { version: string | null; type: string };
  backtest: BacktestRow[];
  drift: { overall: string; significant: string[] };
}

const MODEL_NAMES: Record<string, string> = {
  persistence: "Same as this week",
  seasonal_naive: "Same week last year",
  sarima: "Time series (ARIMA with seasons)",
  glm_poisson: "Poisson regression",
  gbm: "Gradient boosting",
  ensemble: "Ensemble of three",
};

const pct = (v: number) => `${v > 0 ? "+" : ""}${Math.round(v * 100)}%`;

/** A plain-language verdict computed from the published backtest, so it can never drift from the table below it. */
function verdict(rows: BacktestRow[], model: string): { good: number[]; bad: number[] } | null {
  const mine = rows.filter((r) => r.model === model && r.skill_vs_seasonal_naive != null);
  if (!mine.length) return null;
  return {
    good: mine.filter((r) => (r.skill_vs_seasonal_naive ?? 0) > 0.02).map((r) => r.horizon).sort(),
    bad: mine.filter((r) => (r.skill_vs_seasonal_naive ?? 0) <= 0.02).map((r) => r.horizon).sort(),
  };
}

const listWeeks = (hs: number[]) => (hs.length === 1 ? `${hs[0]} week` : hs.length === 2 ? `${hs[0]} and ${hs[1]} weeks` : `${hs.slice(0, -1).join(", ")} and ${hs[hs.length - 1]} weeks`);

export default function ForecastPage() {
  const { lang } = useApp();
  const fresh = useFreshness();
  const { data: f, error } = useApi<Forecast>("/v2/forecast");
  const { data: m } = useApi<ModelInfo>("/v2/model");
  const [span, setSpan] = useState(104);
  const [h, setH] = useState(1);

  const table = useMemo(() => {
    if (!m) return [];
    return m.backtest.filter((r) => r.horizon === h).sort((a, b) => (a.wis ?? a.mae) - (b.wis ?? b.mae));
  }, [m, h]);
  const v = m ? verdict(m.backtest, m.model.type) : null;

  return (
    <div className="mx-auto max-w-[1240px] px-4 py-10 md:px-6 md:py-14">
      <PageHeader title="City forecast"
        lede={fresh.stale && fresh.dataThrough
          ? `Weekly reported dengue cases for BBMP, as the forecast stood on ${longDate(fresh.dataThrough, lang)}, with how well it has done in the past.`
          : "Weekly reported dengue cases for BBMP, the next four weeks, and how well this forecast has done in the past."}>
        <Segmented label="Time span" value={span} onChange={setSpan} options={[{ value: 52, label: "1 year" }, { value: 104, label: "2 years" }, { value: 156, label: "3 years" }]} />
      </PageHeader>

      {error && <Notice tone="warn" title="The forecast isn't available right now">{error.message}</Notice>}
      {!f && !error && <Skeleton className="h-[480px]" />}
      {f && (
        <>
          <Panel className="p-4 md:p-6"><ForecastFan forecast={f} weeks={span} height={340} /></Panel>

          <section className="mt-16 grid gap-12 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-16">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">Next four weeks</h2>
              <div className="mt-5 overflow-x-auto">
                <table className="w-full min-w-[440px] text-sm">
                  <caption className="sr-only">Forecast of weekly reported cases with prediction ranges</caption>
                  <thead className="text-left text-muted">
                    <tr className="border-b border-line-strong">
                      <th className="py-2.5 font-medium">Week</th>
                      <th className="py-2.5 text-right font-medium">Expected</th>
                      <th className="py-2.5 text-right font-medium">Likely (80%)</th>
                      <th className="py-2.5 text-right font-medium">Possible (95%)</th>
                    </tr>
                  </thead>
                  <tbody className="num">
                    {f.forecast.map((p) => (
                      <tr key={p.horizon} className="border-b border-line">
                        <td className="py-3.5 font-sans">{weekLabel(p.week_end, lang)}</td>
                        <td className="py-3.5 text-right text-base font-semibold">{nf(p.median)}</td>
                        <td className="py-3.5 text-right text-muted">{nf(p.lo80)} to {nf(p.hi80)}</td>
                        <td className="py-3.5 text-right text-muted">{nf(p.lo95)} to {nf(p.hi95)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-4 max-w-prose text-sm text-muted">An 80% range means that in past tests, the real number landed inside ranges like this about 80% of the time. Wide ranges are normal: this is an honest statement of how little can be known in advance.</p>
            </div>

            {f.drivers && (
              <div>
                <h2 className="text-2xl font-semibold tracking-tight">What is driving next week</h2>
                <p className="mt-2 text-sm text-muted">Each factor&apos;s push on the forecast, compared with a typical week ({f.drivers.method}).</p>
                <ul className="mt-6 space-y-5">
                  {f.drivers.factors.map((d) => (
                    <li key={d.factor}>
                      <div className="flex items-baseline justify-between gap-4 text-sm">
                        <span>{d.label}</span>
                        <span className={cn("num font-semibold", d.direction === "up" ? "text-ink" : "text-lake")}>{d.effect_pct > 0 ? "+" : ""}{nf(d.effect_pct, 0)}%</span>
                      </div>
                      <div className="mt-2 h-1.5 rounded-full bg-ink/[0.07]">
                        <div className={cn("h-full rounded-full", d.direction === "up" ? "bg-ink" : "bg-lake")} style={{ width: `${Math.min(100, Math.abs(d.effect_pct))}%` }} />
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
        <section className="mt-20 border-t border-line pt-12">
          <div className="max-w-prose">
            <h2 className="text-2xl font-semibold tracking-tight">How much can you trust it?</h2>
            {v && (
              <p className="mt-3 text-lg">
                {v.good.length > 0
                  ? <>It has beaten the simple baseline <strong className="font-semibold">{listWeeks(v.good)} ahead</strong>{v.bad.length > 0 && <>, but not {listWeeks(v.bad)} ahead</>}.</>
                  : <>It has <strong className="font-semibold">not beaten</strong> the simple baseline at any horizon in past tests.</>}
              </p>
            )}
            <p className="mt-3 text-muted">Every method was re-run week by week on past data, using only what was known at the time, and judged only on weeks with real bulletins. &ldquo;Skill&rdquo; compares its error with repeating the same week last year: above 0% is better.</p>
          </div>

          <div className="mt-8"><Segmented label="Forecast horizon" value={h} onChange={setH} size="sm" options={[1, 2, 3, 4].map((x) => ({ value: x, label: `${x} week${x > 1 ? "s" : ""} ahead` }))} /></div>
          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-muted">
                <tr className="border-b border-line-strong">
                  <th className="py-2.5 font-medium">Method</th>
                  <th className="py-2.5 text-right font-medium">Typical error (cases)</th>
                  <th className="py-2.5 text-right font-medium">Interval score</th>
                  <th className="py-2.5 text-right font-medium">80% range hit rate</th>
                  <th className="py-2.5 text-right font-medium">Skill</th>
                </tr>
              </thead>
              <tbody className="num">
                {table.map((r) => {
                  const inUse = r.model === m.model.type;
                  const skill = r.skill_vs_seasonal_naive;
                  return (
                    <tr key={r.model} className={cn("border-b border-line", inUse && "bg-lake-soft/70")}>
                      <td className="py-3 font-sans">{MODEL_NAMES[r.model] ?? r.model}{inUse && <span className="ml-2 text-xs font-semibold text-lake">in use</span>}</td>
                      <td className="py-3 text-right">{nf(r.mae, 0)}</td>
                      <td className="py-3 text-right">{r.wis != null ? nf(r.wis, 0) : "n/a"}</td>
                      <td className="py-3 text-right">{r.coverage80 != null ? `${Math.round(r.coverage80 * 100)}%` : "n/a"}</td>
                      <td className={cn("py-3 text-right font-semibold", skill == null ? "text-muted" : skill > 0.02 ? "text-lake" : skill < -0.02 ? "text-[#B42A42] dark:text-[#F08A9A]" : "text-muted")}>
                        {skill != null ? pct(skill) : "n/a"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-5 max-w-prose text-sm text-muted">
            Data drift: {m.drift.overall === "ok" ? "recent weeks look like the data the model learned from." : `recent data differs in ${m.drift.significant.join(", ")}, so take extra care with this forecast.`}{" "}
            <Link href="/methodology" className="font-medium text-lake underline underline-offset-2 hover:no-underline">Read how it works</Link>.
          </p>
        </section>
      )}
    </div>
  );
}
