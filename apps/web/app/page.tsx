"use client";

import { ArrowRight, Bell, Camera, Map, MessageCircleQuestion } from "lucide-react";
import Link from "next/link";

import { ForecastFan } from "@/components/charts/forecast-fan";
import { useApp } from "@/components/providers";
import { Button, Notice, Panel, Skeleton } from "@/components/ui/primitives";
import { WardSearch } from "@/components/ward-search";
import { useApi } from "@/lib/api";
import { cn, nf, weekLabel } from "@/lib/format";
import { longDate, useFreshness } from "@/lib/freshness";
import type { Forecast } from "@/lib/types";

/** Compare the next forecast with the median of the last four observed weeks. A median shrugs off one odd week. */
function trend(f: Forecast) {
  const recent = f.history.map((h) => h.cases).filter((c): c is number => c != null).slice(-4).sort((a, b) => a - b);
  const baseline = recent.length ? (recent[Math.floor((recent.length - 1) / 2)] + recent[Math.ceil((recent.length - 1) / 2)]) / 2 : 0;
  const next = f.forecast[0]?.median ?? 0;
  const change = baseline > 0 ? (next - baseline) / baseline : 0;
  return { baseline, next, change, verdict: change > 0.2 ? "rise" : change < -0.2 ? "ease" : "hold" } as const;
}

const monthYear = (iso: string) => new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" }).format(new Date(iso + "T00:00:00"));

const SERVICES = [
  { href: "/map", icon: Map, title: "Risk map", body: "See estimated risk for every ward, with how sure we are." },
  { href: "/report", icon: Camera, title: "Report a spot", body: "Send a photo of standing water so the health team can check it." },
  { href: "/alerts", icon: Bell, title: "Alerts", body: "Get a message when risk rises around your home, office or school." },
  { href: "/assistant", icon: MessageCircleQuestion, title: "Ask about dengue", body: "Answers from WHO and Government of India guidelines, with sources." },
];

export default function Home() {
  const { t, lang } = useApp();
  const fresh = useFreshness();
  const { data: f, error, isLoading, mutate } = useApi<Forecast>("/v2/forecast");
  const next = f?.forecast[0];
  const tr = f ? trend(f) : null;

  const headline = !f || !tr
    ? null
    : lang !== "en"
      ? t("home.title")
      : fresh.stale && fresh.dataThrough
        ? `Dengue in Bengaluru, ${monthYear(fresh.dataThrough)}`
        : tr.verdict === "rise" ? "Dengue cases in Bengaluru are likely to rise next week"
          : tr.verdict === "ease" ? "Dengue cases in Bengaluru are likely to ease next week"
            : "Dengue cases in Bengaluru are likely to stay about the same next week";

  return (
    <div className="mx-auto max-w-[1240px] px-4 md:px-6">
      <section className="grid gap-10 pb-14 pt-10 md:pb-20 md:pt-16 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
        <div className="flex flex-col justify-center">
          {headline ? (
            <h1 className="text-balance text-4xl font-semibold leading-[1.08] tracking-tight md:text-5xl">{headline}</h1>
          ) : (
            <Skeleton className="h-28 w-full" />
          )}
          <p className="text-pretty mt-5 max-w-prose text-lg text-muted">{t("home.lede")}</p>

          <div className="mt-8">
            <p className="mb-2 text-sm font-medium">{t("home.search")}</p>
            <WardSearch />
          </div>
          <p className="mt-4 text-sm text-muted">
            Or <Link href="/map" className="font-medium text-lake underline underline-offset-2 hover:no-underline">browse the whole city on the map</Link>.
          </p>
        </div>

        <div>
          {error ? (
            <Notice tone="warn" title="The forecast isn't available right now"
              action={<Button variant="secondary" size="sm" onClick={() => mutate()}>{t("common.retry")}</Button>}>
              {error.message}
            </Notice>
          ) : isLoading || !f || !next || !tr ? (
            <Skeleton className="h-[460px] w-full" />
          ) : (
            <Panel>
              <dl className="grid grid-cols-2 border-b border-line sm:grid-cols-3">
                <div className="border-r border-line p-4 md:p-5">
                  <dt className="text-xs text-muted md:text-sm">Expected next week</dt>
                  <dd className="num mt-1.5 text-3xl font-semibold leading-none md:text-4xl">{nf(next.median)}</dd>
                  <dd className="mt-1.5 text-xs text-muted">Week of {weekLabel(next.week_end, lang).split(" to ")[0]}</dd>
                </div>
                <div className="p-4 sm:border-r sm:border-line md:p-5">
                  <dt className="text-xs text-muted md:text-sm">Likely range (80%)</dt>
                  <dd className="num mt-1.5 text-3xl font-semibold leading-none text-muted md:text-4xl">{nf(next.lo80)} to {nf(next.hi80)}</dd>
                  <dd className="mt-1.5 text-xs text-muted">Reported cases, all of BBMP</dd>
                </div>
                <div className="col-span-2 border-t border-line p-4 sm:col-span-1 sm:border-t-0 md:p-5">
                  <dt className="text-xs text-muted md:text-sm">Vs recent weeks</dt>
                  <dd className={cn("num mt-1.5 text-3xl font-semibold leading-none md:text-4xl")}>
                    {tr.change > 0 ? "+" : ""}{Math.round(tr.change * 100)}%
                  </dd>
                  <dd className="mt-1.5 text-xs text-muted">Against the last 4 weeks</dd>
                </div>
              </dl>
              <div className="p-4 md:p-6">
                <ForecastFan forecast={f} weeks={52} height={280} />
              </div>
            </Panel>
          )}
        </div>
      </section>

      <section className="grid gap-10 border-t border-line py-14 md:py-20 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
        <div className="lg:sticky lg:top-24 lg:self-start">
          <h2 className="text-balance text-2xl font-semibold tracking-tight md:text-3xl">{t("home.actionsTitle")}</h2>
          <p className="mt-3 max-w-prose text-muted">{t("home.rainNote")}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/map"><Button size="lg">{t("home.openMap")}</Button></Link>
            <Link href="/alerts"><Button size="lg" variant="secondary">{t("home.getAlerts")}</Button></Link>
          </div>
        </div>
        <ol className="divide-y divide-line border-y border-line">
          {(["home.action1", "home.action2", "home.action3", "home.action4"] as const).map((k, i) => (
            <li key={k} className="flex gap-5 py-5">
              <span className="num w-6 shrink-0 pt-0.5 text-lg font-semibold text-lake">{i + 1}</span>
              <p className="text-pretty text-base">{t(k)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-t border-line py-14 md:py-20">
        <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">What you can do here</h2>
        <ul className="mt-8 grid border-t border-line md:grid-cols-2 md:gap-x-12">
          {SERVICES.map((s) => (
            <li key={s.href} className="border-b border-line">
              <Link href={s.href} className="group flex items-start gap-4 py-6">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded bg-lake-soft text-lake"><s.icon className="h-5 w-5" /></span>
                <span className="min-w-0 flex-1">
                  <span className="block text-base font-semibold">{s.title}</span>
                  <span className="mt-1 block text-sm text-muted">{s.body}</span>
                </span>
                <ArrowRight className="mt-1 h-5 w-5 shrink-0 text-muted transition-transform group-hover:translate-x-1 group-hover:text-lake" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      </section>

      {f && (
        <p className="pb-12 text-xs text-muted">
          {f.disclaimer} Model: {f.model.type}. Data through {longDate(f.origin_week, lang)}.
        </p>
      )}
    </div>
  );
}
