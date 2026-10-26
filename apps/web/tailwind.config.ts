import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "rgb(var(--paper) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        ink: "rgb(var(--ink) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
        lake: "rgb(var(--lake) / <alpha-value>)",
        "lake-soft": "rgb(var(--lake-soft) / <alpha-value>)",
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
        // Modular scale (1.25), Bringhurst-style: body 16, small 13, display sizes for numbers.
        xs: ["0.8125rem", { lineHeight: "1.25rem" }],
        sm: ["0.875rem", { lineHeight: "1.375rem" }],
        base: ["1rem", { lineHeight: "1.625rem" }],
        lg: ["1.25rem", { lineHeight: "1.875rem" }],
        xl: ["1.5625rem", { lineHeight: "2.125rem" }],
        "2xl": ["1.953rem", { lineHeight: "2.4rem" }],
        "3xl": ["2.441rem", { lineHeight: "2.8rem" }],
        "4xl": ["3.052rem", { lineHeight: "3.3rem" }],
      },
      borderRadius: { sm: "6px", DEFAULT: "10px", lg: "16px", xl: "22px" },
      boxShadow: {
        float: "0 1px 2px rgb(20 33 61 / 0.06), 0 12px 32px -12px rgb(20 33 61 / 0.22)",
      },
      maxWidth: { prose: "68ch" },
    },
  },
  plugins: [],
};
export default config;
