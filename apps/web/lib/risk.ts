import type { Band } from "./types";

export const BANDS: Band[] = ["low", "moderate", "high", "very_high"];

export const BAND_COLOR: Record<Band, string> = {
  low: "#DCE8D2",
  moderate: "#F2B33D",
  high: "#E06A2C",
  very_high: "#9E2338",
};

// Text colour that stays readable on each band fill.
export const BAND_TEXT: Record<Band, string> = {
  low: "#25472A",
  moderate: "#4A3204",
  high: "#FFFFFF",
  very_high: "#FFFFFF",
};

// Map fill opacity encodes how sure the estimate is.
export const UNCERTAINTY_OPACITY = { low: 0.88, medium: 0.66, high: 0.42 } as const;

export function bandIndex(b: Band | null | undefined) {
  return b ? BANDS.indexOf(b) : -1;
}
