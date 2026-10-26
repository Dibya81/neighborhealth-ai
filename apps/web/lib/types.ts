export type Band = "low" | "moderate" | "high" | "very_high";
export type Lang = "en" | "kn" | "hi";

export interface ForecastPoint {
  horizon: number;
  week_end: string;
  median: number;
  lo50?: number; hi50?: number;
  lo80?: number; hi80?: number;
  lo95?: number; hi95?: number;
}

export interface Factor {
  factor: string;
  label: string;
  effect_pct: number;
  effect_log: number;
  direction: "up" | "down";
  evidence: Record<string, number | null>;
}

export interface Forecast {
  generated_at: string;
  target: string;
  model: { version: string | null; type: string; explanations_from: string | null };
  origin_week: string;
  population_est: number | null;
  bands_per_100k: [number, Band][] | null;
  history: { week_end: string; cases: number | null; rain_mm?: number | null }[];
  forecast: ForecastPoint[];
  drivers: { method: string; baseline_cases: number; factors: Factor[] } | null;
  disclaimer: string;
}

export interface WardRisk {
  ward_id: string;
  ward_name: string;
  band: Band;
  rate_per_100k: number;
  rate_lo80: number;
  rate_hi80: number;
  expected_cases: number;
  cases_lo80: number;
  cases_hi80: number;
  p_high: number;
  uncertainty: "low" | "medium" | "high";
  population_est: number;
}

export interface WardDetail {
  ward_id: string;
  ward_name: string;
  population_est: number;
  relative_risk: number;
  horizons: (Omit<WardRisk, "ward_id" | "ward_name" | "population_est"> & { horizon: number; week_end: string })[];
  verified_reports: number;
  open_tasks: number;
  drivers: Forecast["drivers"];
  disclaimer: string;
}

export interface User { id: string; email: string; name?: string; role: "citizen" | "official" | "admin"; language: Lang; cohort?: string }

export interface Citation { n: number; title: string; org: string; url: string | null; page: number; quote: string }
export interface AssistantAnswer {
  answer: string;
  citations: Citation[];
  urgent: boolean;
  urgent_message?: string;
  refused_diagnosis: boolean;
  grounded?: boolean;
  nearby?: Clinic[];
}
export interface Clinic { id: string; name: string; lat: number; lon: number; kind: string; phone?: string; distance_m: number; emergency: boolean; address?: string }

export interface Hotspot { id: string; lat: number; lon: number; radius_m: number; reports: number; verified: number; ward_id: string | null; ward_name: string | null; latest: string; weight: number }

export interface Task {
  id: string; report_id: string | null; ward_id: string | null; lat: number; lon: number;
  kind: "inspection" | "fogging" | "source_reduction"; priority: 1 | 2 | 3;
  status: "open" | "assigned" | "in_progress" | "inspected" | "cleared" | "closed";
  team: string | null; route_id: string | null; notes: string | null; created_at: string; updated_at: string; completed_at: string | null;
}

export interface Subscription {
  id: string; label: "home" | "office" | "school" | "other"; lat: number; lon: number; radius_m: number;
  channels: ("whatsapp" | "sms" | "email")[]; language: Lang; quiet_start: string | null; quiet_end: string | null;
  threshold_band: Band; last_band: Band | null; active: boolean; created_at: string;
  wards: { ward_id: string; ward_name: string }[];
}
