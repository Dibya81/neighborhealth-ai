export const nf = (n: number | null | undefined, digits = 0) =>
  n == null || Number.isNaN(n) ? "n/a" : n.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });

export function weekLabel(iso: string, lang = "en") {
  const d = new Date(iso + "T00:00:00");
  const start = new Date(d);
  start.setDate(d.getDate() - 6);
  const locale = lang === "kn" ? "kn-IN" : lang === "hi" ? "hi-IN" : "en-IN";
  const f = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" });
  return `${f.format(start)} to ${f.format(d)}`;
}

export function shortDate(iso: string) {
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" }).format(new Date(iso));
}

export function timeAgo(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

export function cn(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}
