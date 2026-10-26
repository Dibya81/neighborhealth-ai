"use client";

import { useMemo } from "react";
import { Area, Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { nf } from "@/lib/format";
import type { Forecast } from "@/lib/types";

interface Row {
  week: string;
  cases?: number | null;
  /** cases in weeks that were filled in between bulletins, drawn lighter */
  filled?: number | null;
  median?: number;
  band50?: [number, number];
  band80?: [number, number];
  band95?: [number, number];
  rain?: number | null;
}

const FORECAST = "rgb(var(--lake))";
const AXIS = { fontSize: 12, fill: "rgb(var(--muted))" } as const;

function buildRows(f: Forecast, weeks: number): Row[] {
  const hist = f.history.slice(-weeks);
  const rows: Row[] = hist.map((h) => {
    const interpolated = (h as { quality?: string }).quality === "interpolated";
    return { week: h.week_end, cases: interpolated ? null : h.cases, filled: interpolated ? h.cases : null, rain: h.rain_mm ?? null };
  });
  const last = rows[rows.length - 1];
  if (last && (last.cases ?? last.filled) != null) {
    // join the forecast fan to the last observed week
    const v = (last.cases ?? last.filled) as number;
    last.median = v;
    last.band50 = last.band80 = last.band95 = [v, v];
  }
  for (const p of f.forecast) {
    rows.push({
      week: p.week_end,
      median: p.median,
      band50: p.lo50 != null && p.hi50 != null ? [p.lo50, p.hi50] : undefined,
      band80: p.lo80 != null && p.hi80 != null ? [p.lo80, p.hi80] : undefined,
      band95: p.lo95 != null && p.hi95 != null ? [p.lo95, p.hi95] : undefined,
    });
  }
  return rows;
}

const day = (v: string) => new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(new Date(v + "T00:00:00"));

function FanTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  const isForecast = r.cases == null && r.filled == null && r.median != null;
  return (
    <div className="min-w-[180px] rounded-lg border border-line-strong bg-surface px-3 py-2.5 text-xs shadow-float">
      <p className="font-medium">Week ending {day(r.week)}</p>
      {r.cases != null && <p className="num mt-1.5 text-sm">{nf(r.cases)} <span className="font-sans text-xs text-muted">reported cases</span></p>}
      {r.filled != null && <p className="mt-1.5 text-muted">About {nf(r.filled)} cases (estimated between bulletins)</p>}
      {isForecast && (
        <div className="mt-1.5 space-y-0.5">
          <p className="num text-sm">{nf(r.median)} <span className="font-sans text-xs text-muted">expected</span></p>
          {r.band80 && <p className="num text-muted">80% likely: {nf(r.band80[0])} to {nf(r.band80[1])}</p>}
          {r.band95 && <p className="num text-muted">95% likely: {nf(r.band95[0])} to {nf(r.band95[1])}</p>}
        </div>
      )}
      {r.rain != null && <p className="num mt-1.5 border-t border-line pt-1.5 text-muted">Rain: {nf(r.rain)} mm</p>}
    </div>
  );
}

export function ForecastFan({ forecast, weeks = 52, height = 300, showRain = true }: {
  forecast: Forecast; weeks?: number; height?: number; showRain?: boolean;
}) {
  const rows = useMemo(() => buildRows(forecast, weeks), [forecast, weeks]);
  const origin = forecast.origin_week;
  const tick = (v: string) => {
    const d = new Date(v + "T00:00:00");
    return d.getMonth() === 0 || v === rows[0]?.week
      ? new Intl.DateTimeFormat("en-IN", { month: "short", year: "2-digit" }).format(d)
      : new Intl.DateTimeFormat("en-IN", { month: "short" }).format(d);
  };
  const rainMax = Math.max(10, ...rows.map((r) => r.rain ?? 0));

  // Cap the axis at what people actually saw (plus the 80% range). The 95% band is clipped rather than
  // allowed to flatten the whole history.
  const seen = Math.max(1, ...rows.map((r) => Math.max(r.cases ?? 0, r.filled ?? 0)));
  const hi80 = Math.max(0, ...rows.map((r) => r.band80?.[1] ?? 0));
  const cap = Math.ceil((Math.max(seen, hi80) * 1.12) / 100) * 100;
  const clipped = rows.some((r) => (r.band95?.[1] ?? 0) > cap);

  return (
    <figure className="w-full" aria-label="Weekly reported dengue cases with forecast and rainfall">
      <div style={{ height }}>
        <ResponsiveContainer>
          <ComposedChart data={rows} syncId="fan" margin={{ top: 12, right: 8, bottom: 0, left: -8 }}>
            <CartesianGrid vertical={false} stroke="rgb(var(--line))" />
            <XAxis dataKey="week" tickFormatter={tick} minTickGap={42} tick={AXIS} axisLine={false} tickLine={false} hide={showRain} />
            <YAxis domain={[0, cap]} allowDataOverflow tickCount={5} tick={AXIS} axisLine={false} tickLine={false} width={48}
              tickFormatter={(v: number) => nf(v)} />
            <Tooltip content={<FanTooltip />} cursor={{ stroke: "rgb(var(--muted))", strokeDasharray: "3 3" }} />
            <Area dataKey="band95" stroke="none" fill={FORECAST} fillOpacity={0.1} isAnimationActive={false} connectNulls />
            <Area dataKey="band80" stroke="none" fill={FORECAST} fillOpacity={0.16} isAnimationActive={false} connectNulls />
            <Area dataKey="band50" stroke="none" fill={FORECAST} fillOpacity={0.26} isAnimationActive={false} connectNulls />
            <Line dataKey="filled" stroke="rgb(var(--muted))" strokeWidth={1.5} strokeDasharray="2 3" dot={false} isAnimationActive={false} connectNulls />
            <Line dataKey="cases" stroke="rgb(var(--ink))" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
            <Line dataKey="median" stroke={FORECAST} strokeWidth={2.25} strokeDasharray="5 4" dot={{ r: 3, fill: FORECAST, stroke: "rgb(var(--surface))", strokeWidth: 1.5 }} isAnimationActive={false} />
            <ReferenceLine x={origin} stroke="rgb(var(--muted))" strokeDasharray="2 3"
              label={{ value: "Data ends", position: "insideTopLeft", fontSize: 11, fill: "rgb(var(--muted))" }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {showRain && (
        <div style={{ height: 76 }}>
          <ResponsiveContainer>
            <ComposedChart data={rows} syncId="fan" margin={{ top: 2, right: 8, bottom: 0, left: -8 }}>
              <XAxis dataKey="week" tickFormatter={tick} minTickGap={42} tick={AXIS} axisLine={false} tickLine={false} />
              <YAxis domain={[0, rainMax]} tick={false} axisLine={false} tickLine={false} width={48}
                label={{ value: "Rain", angle: -90, position: "insideLeft", offset: 22, fontSize: 11, fill: "rgb(var(--muted))" }} />
              <Tooltip content={() => null} cursor={false} />
              <Bar dataKey="rain" fill="rgb(var(--lake))" fillOpacity={0.4} radius={[2, 2, 0, 0]} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
      <figcaption className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs text-muted">
        <span className="flex items-center gap-2"><i className="h-0.5 w-5 rounded bg-ink" />Reported cases</span>
        <span className="flex items-center gap-2"><i className="h-0 w-5 border-t-2 border-dashed border-lake" />Forecast</span>
        <span className="flex items-center gap-2"><i className="h-3 w-5 rounded-sm bg-lake/25" />Likely range (50, 80, 95%)</span>
        {showRain && <span className="flex items-center gap-2"><i className="h-3 w-2 rounded-sm bg-lake/40" />Weekly rain</span>}
        {clipped && <span>The 95% range runs above the top of the chart.</span>}
      </figcaption>
    </figure>
  );
}
