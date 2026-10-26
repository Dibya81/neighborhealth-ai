"use client";

import { useMemo } from "react";
import { Area, Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { nf, shortDate } from "@/lib/format";
import type { Forecast } from "@/lib/types";

interface Row {
  week: string;
  cases?: number | null;
  median?: number;
  band50?: [number, number];
  band80?: [number, number];
  band95?: [number, number];
  rain?: number | null;
}

function buildRows(f: Forecast, weeks: number): Row[] {
  const hist = f.history.slice(-weeks);
  const rows: Row[] = hist.map((h) => ({ week: h.week_end, cases: h.cases, rain: h.rain_mm ?? null }));
  const last = rows[rows.length - 1];
  if (last?.cases != null) {
    // join the forecast fan to the last observed week
    last.median = last.cases;
    last.band50 = last.band80 = last.band95 = [last.cases, last.cases];
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

function FanTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded border border-line bg-surface px-3 py-2 text-xs shadow-float">
      <p className="font-medium">Week ending {shortDate(r.week)}</p>
      {r.cases != null && <p className="tnum mt-1">Reported cases: <b>{nf(r.cases)}</b></p>}
      {r.cases == null && r.median != null && (
        <>
          <p className="tnum mt-1">Forecast: <b>{nf(r.median)}</b></p>
          {r.band80 && <p className="tnum text-muted">80% range: {nf(r.band80[0])}–{nf(r.band80[1])}</p>}
          {r.band95 && <p className="tnum text-muted">95% range: {nf(r.band95[0])}–{nf(r.band95[1])}</p>}
        </>
      )}
      {r.rain != null && <p className="tnum mt-1 text-muted">Rain that week: {nf(r.rain)} mm</p>}
    </div>
  );
}

export function ForecastFan({ forecast, weeks = 52, height = 300, showRain = true }: {
  forecast: Forecast; weeks?: number; height?: number; showRain?: boolean;
}) {
  const rows = useMemo(() => buildRows(forecast, weeks), [forecast, weeks]);
  const origin = forecast.origin_week;
  const tick = (v: string) => new Intl.DateTimeFormat("en-IN", { month: "short" }).format(new Date(v));
  const rainMax = Math.max(10, ...rows.map((r) => r.rain ?? 0));

  return (
    <figure className="w-full" aria-label="Weekly reported dengue cases with forecast and rainfall">
      <div style={{ height }}>
        <ResponsiveContainer>
          <ComposedChart data={rows} syncId="fan" margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid vertical={false} stroke="rgb(var(--line))" strokeDasharray="2 4" />
            <XAxis dataKey="week" tickFormatter={tick} minTickGap={36} tick={{ fontSize: 12, fill: "rgb(var(--muted))" }} axisLine={false} tickLine={false} hide={showRain} />
            <YAxis tick={{ fontSize: 12, fill: "rgb(var(--muted))" }} axisLine={false} tickLine={false} width={48} />
            <Tooltip content={<FanTooltip />} cursor={{ stroke: "rgb(var(--muted))", strokeDasharray: "3 3" }} />
            <Area dataKey="band95" stroke="none" fill="#F2B33D" fillOpacity={0.16} isAnimationActive={false} connectNulls />
            <Area dataKey="band80" stroke="none" fill="#F2B33D" fillOpacity={0.26} isAnimationActive={false} connectNulls />
            <Area dataKey="band50" stroke="none" fill="#E06A2C" fillOpacity={0.28} isAnimationActive={false} connectNulls />
            <Line dataKey="cases" stroke="rgb(var(--ink))" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
            <Line dataKey="median" stroke="#E06A2C" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 2.5, fill: "#E06A2C" }} isAnimationActive={false} />
            <ReferenceLine x={origin} stroke="rgb(var(--muted))" strokeDasharray="2 3"
              label={{ value: "now", position: "insideTopRight", fontSize: 11, fill: "rgb(var(--muted))" }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {showRain && (
        <div style={{ height: 72 }}>
          <ResponsiveContainer>
            <ComposedChart data={rows} syncId="fan" margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
              <XAxis dataKey="week" tickFormatter={tick} minTickGap={36} tick={{ fontSize: 12, fill: "rgb(var(--muted))" }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, rainMax]} reversed tick={false} axisLine={false} width={48} />
              <Tooltip content={() => null} cursor={false} />
              <Bar dataKey="rain" fill="#0E7C7B" fillOpacity={0.55} radius={[0, 0, 2, 2]} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
      <figcaption className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted">
        <span className="flex items-center gap-1.5"><i className="h-0.5 w-5 bg-ink" />Reported cases</span>
        <span className="flex items-center gap-1.5"><i className="h-0.5 w-5 border-t-2 border-dashed border-[#E06A2C]" />Forecast</span>
        <span className="flex items-center gap-1.5"><i className="h-3 w-5 rounded-sm bg-[#F2B33D]/40" />Likely range (50 / 80 / 95%)</span>
        {showRain && <span className="flex items-center gap-1.5"><i className="h-3 w-2 bg-lake/60" />Weekly rainfall, hanging below</span>}
      </figcaption>
    </figure>
  );
}
