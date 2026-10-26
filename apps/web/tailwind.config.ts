import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "rgb(var(--paper) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        sunken: "rgb(var(--sunken) / <alpha-value>)",
        ink: "rgb(var(--ink) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
        "line-strong": "rgb(var(--line-strong) / <alpha-value>)",
        lake: "rgb(var(--lake) / <alpha-value>)",
        "lake-soft": "rgb(var(--lake-soft) / <alpha-value>)",
        warn: {
          bg: "rgb(var(--warn-bg) / <alpha-value>)",
          line: "rgb(var(--warn-line) / <alpha-value>)",
          ink: "rgb(var(--warn-ink) / <alpha-value>)",
        },
        // Reserved for data. Never used as decoration.
        risk: {
          low: "#DCE8D2",
          moderate: "#F2B33D",
          high: "#E06A2C",
          very_high: "#9E2338",
        },
      },
      fontFamily: {
        sans: ["var(--font-plex)", "var(--font-plex-kn)", "var(--font-plex-hi)", "system-ui", "sans-serif"],
        display: ["var(--font-plex-condensed)", "var(--font-plex)", "system-ui", "sans-serif"],
      },
      fontSize: {
        xs: ["0.8125rem", { lineHeight: "1.25rem" }],
        sm: ["0.9375rem", { lineHeight: "1.5rem" }],
        base: ["1rem", { lineHeight: "1.65rem" }],
        lg: ["1.1875rem", { lineHeight: "1.85rem" }],
        xl: ["1.4375rem", { lineHeight: "2rem" }],
        "2xl": ["1.75rem", { lineHeight: "2.2rem" }],
        "3xl": ["2.125rem", { lineHeight: "2.5rem" }],
        "4xl": ["2.75rem", { lineHeight: "3rem" }],
        "5xl": ["3.5rem", { lineHeight: "3.75rem" }],
      },
      // One radius system: 8px for controls, 12px for panels. Nothing else.
      borderRadius: { sm: "6px", DEFAULT: "8px", md: "8px", lg: "12px", xl: "12px", "2xl": "12px" },
      boxShadow: {
        float: "0 1px 2px rgb(14 26 43 / 0.06), 0 10px 28px -12px rgb(14 26 43 / 0.22)",
      },
      maxWidth: { prose: "64ch" },
    },
  },
  plugins: [],
};
export default config;
