"use client";

import { useApi } from "@/lib/api";

/** A forecast older than this is shown as a demonstration, never as current. Mirrors the API's alert cut-off. */
export const STALE_AFTER_DAYS = 21;

interface ModelInfo { origin_week: string | null; generated_at: string | null }

export interface Freshness {
  ready: boolean;
  /** Last week of real observations behind the forecast (ISO date). */
  dataThrough: string | null;
  ageDays: number | null;
  stale: boolean;
}

export function useFreshness(): Freshness {
  const { data } = useApi<ModelInfo>("/v2/model");
  if (!data?.origin_week) return { ready: !!data, dataThrough: null, ageDays: null, stale: !!data };
  const ageDays = Math.floor((Date.now() - new Date(data.origin_week + "T00:00:00").getTime()) / 86_400_000);
  return { ready: true, dataThrough: data.origin_week, ageDays, stale: ageDays > STALE_AFTER_DAYS };
}

export function longDate(iso: string, lang = "en") {
  const locale = lang === "kn" ? "kn-IN" : lang === "hi" ? "hi-IN" : "en-IN";
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "long", year: "numeric" }).format(new Date(iso + "T00:00:00"));
}
