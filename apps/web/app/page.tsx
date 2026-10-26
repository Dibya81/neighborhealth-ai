"use client";

import Link from "next/link";

import { ForecastFan } from "@/components/charts/forecast-fan";
import { useApp } from "@/components/providers";
import { WardSearch } from "@/components/ward-search";
import { Button, Notice, Skeleton } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { nf, weekLabel } from "@/lib/format";
import type { Forecast } from "@/lib/types";

function headline(f: Forecast): string {
  const lastObs = [...f.history].reverse().find((h) => h.cases != null)?.cases ?? 0;
  const next = f.forecast[0]?.median ?? 0;
  const change = lastObs > 0 ? (next - lastObs) / lastObs : 0;
  if (change > 0.15) return "Dengue cases in Bengaluru are likely to rise next week";
  if (change < -0.15) return "Dengue cases in Bengaluru are likely to ease next week";
  return "Dengue cases in Bengaluru are likely to stay about the same next week";
}

export default function Home() {
  const { t, lang } = useApp();
  const { data: f, error, isLoading, mutate } = useApi<Forecast>("/v2/forecast");
  const next = f?.forecast[0];

  return (
    <div className="mx-auto max-w-[1240px] px-4 pt-8 md:px-6 md:pt-14">
      <section className="grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-14">
        <div className="flex flex-col">
          <p className="text-sm font-medium text-lake">{t("home.title")}</p>
          {f ? (
            <h1 className="mt-3 text-balance font-display text-3xl font-semibold leading-tight tracking-tight md:text-4xl">
              {lang === "en" ? headline(f) : t("home.title")}
            </h1>
          ) : (
            <Skeleton className="mt-4 h-24 w-full" />
          )}
          <p className="mt-4 max-w-prose text-base text-muted">{t("home.lede")}</p>

          <div className="mt-8">
            <p className="mb-2 text-sm font-medium">{t("home.search")}</p>
            <WardSearch />
          </div>

          {next && (
            <dl className="mt-10 grid grid-cols-2 gap-6 border-t border-line pt-6">
              <div>
                <dt className="text-sm text-muted">{t("home.thisWeek")}</dt>
                <dd className="tnum mt-1 font-display text-4xl font-semibold">{nf(next.median)}</dd>
                <dd className="text-xs text-muted">{weekLabel(next.week_end, lang)}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted">{t("home.range")} (80%)</dt>
                <dd className="tnum mt-1 font-display text-4xl font-semibold text-muted">
                  {nf(next.lo80)}–{nf(next.hi80)}
                </dd>
                <dd className="text-xs text-muted">BBMP, reported cases</dd>
              </div>
            </dl>
          )}
        </div>

        <div className="lg:pt-8">
          {error ? (
            <Notice tone="warn" title="The forecast isn't available right now"
              action={<Button variant="secondary" size="sm" onClick={() => mutate()}>{t("common.retry")}</Button>}>
              {error.message}
            </Notice>
          ) : isLoading || !f ? (
            <Skeleton className="h-[400px] w-full" />
          ) : (
            <div className="rounded-lg border border-line bg-surface p-4 md:p-6">
              <ForecastFan forecast={f} weeks={52} height={300} />
              <p className="mt-4 max-w-prose text-sm text-muted">{t("home.rainNote")}</p>
            </div>
          )}
        </div>
      </section>

      <section className="mt-16 grid gap-10 border-t border-line py-12 md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-14">
        <div>
          <h2 className="font-display text-2xl font-semibold tracking-tight">{t("home.actionsTitle")}</h2>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/map"><Button size="lg">{t("home.openMap")}</Button></Link>
            <Link href="/alerts"><Button size="lg" variant="secondary">{t("home.getAlerts")}</Button></Link>
          </div>
        </div>
        <ul className="grid gap-x-10 gap-y-6 sm:grid-cols-2">
          {(["home.action1", "home.action2", "home.action3", "home.action4"] as const).map((k) => (
            <li key={k} className="border-l-2 border-[#F2B33D] pl-4 text-base">{t(k)}</li>
          ))}
        </ul>
      </section>

      {f && <p className="pb-10 text-xs text-muted">{f.disclaimer} Model: {f.model.type}, updated {new Date(f.generated_at).toLocaleDateString("en-IN")}.</p>}
    </div>
  );
}
