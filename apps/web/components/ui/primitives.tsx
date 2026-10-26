"use client";

import { AlertTriangle, Info, OctagonAlert } from "lucide-react";
import { forwardRef } from "react";

import { bandLabel } from "@/lib/i18n";
import { BAND_COLOR, BAND_TEXT } from "@/lib/risk";
import { cn } from "@/lib/format";
import type { Band, Lang } from "@/lib/types";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded font-medium transition-[background-color,border-color,transform] duration-150",
        "active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" && "h-9 px-3 text-sm",
        size === "md" && "h-11 px-4 text-sm",
        size === "lg" && "h-12 px-5 text-base",
        variant === "primary" && "bg-lake text-white hover:bg-lake/90 dark:text-[#06222a]",
        variant === "secondary" && "border border-line-strong bg-surface text-ink hover:border-ink/40",
        variant === "ghost" && "text-ink hover:bg-ink/[0.06]",
        variant === "danger" && "bg-[#9E2338] text-white hover:bg-[#9E2338]/90",
        className,
      )}
      {...rest}
    >
      {loading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent" aria-hidden />}
      {children}
    </button>
  );
});

export function Field({ label, hint, error, children, htmlFor }: {
  label: string; hint?: string; error?: string; children: React.ReactNode; htmlFor?: string;
}) {
  return (
    <div className="space-y-2">
      <label htmlFor={htmlFor} className="block text-sm font-medium">{label}</label>
      {children}
      {error ? <p className="text-xs text-[#B42A42] dark:text-[#F08A9A]" role="alert">{error}</p> : hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

const control =
  "w-full rounded border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-muted/70 transition-colors " +
  "hover:border-ink/40 focus:border-lake focus:outline-none focus:ring-2 focus:ring-lake/20";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...rest }, ref) {
  return <input ref={ref} className={cn(control, "h-11", className)} {...rest} />;
});

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn(control, "min-h-[96px] py-2.5", props.className)} />;
}

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, children, ...rest }, ref) {
  return (
    <div className="relative">
      <select ref={ref} className={cn(control, "h-11 cursor-pointer appearance-none pr-9", className)} {...rest}>{children}</select>
      <svg className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" viewBox="0 0 16 16" fill="none" aria-hidden>
        <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
});

export function Segmented<T extends string | number>({ value, options, onChange, label, size = "md" }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string; size?: "sm" | "md";
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg bg-sunken p-1">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={String(o.value)}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={cn(
              "shrink-0 whitespace-nowrap rounded px-3 font-medium transition-colors",
              size === "sm" ? "h-8 text-xs" : "h-9 text-sm",
              active ? "bg-surface text-ink shadow-[0_1px_2px_rgb(14_26_43/0.12)] ring-1 ring-line-strong" : "text-muted hover:text-ink",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function BandPill({ band, lang, className }: { band: Band; lang: Lang; className?: string }) {
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold", className)}
      style={{ background: BAND_COLOR[band], color: BAND_TEXT[band] }}>
      {bandLabel(lang, band)}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-ink/[0.07]", className)} aria-hidden />;
}

const TONE = {
  info: { icon: Info, box: "border-line-strong bg-surface", icn: "text-lake" },
  warn: { icon: AlertTriangle, box: "border-warn-line bg-warn-bg text-warn-ink", icn: "text-warn-ink" },
  danger: { icon: OctagonAlert, box: "border-[#9E2338]/50 bg-[#9E2338]/[0.07]", icn: "text-[#B42A42] dark:text-[#F08A9A]" },
} as const;

export function Notice({ tone = "info", title, children, action }: {
  tone?: "info" | "warn" | "danger"; title: string; children?: React.ReactNode; action?: React.ReactNode;
}) {
  const T = TONE[tone];
  const Icon = T.icon;
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex gap-3 rounded-lg border p-4 text-sm", T.box)}>
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", T.icn)} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{title}</p>
        {children && <div className={cn("mt-1", tone === "warn" ? "text-warn-ink/90" : "text-muted")}>{children}</div>}
        {action && <div className="mt-3">{action}</div>}
      </div>
    </div>
  );
}

/** A bordered surface. Use sparingly: most grouping should be spacing and hairlines. */
export function Panel({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("rounded-lg border border-line bg-surface", className)}>{children}</div>;
}

export function Stat({ label, value, sub, className }: { label: string; value: React.ReactNode; sub?: React.ReactNode; className?: string }) {
  return (
    <div className={className}>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="num mt-1 text-4xl font-semibold leading-none">{value}</dd>
      {sub && <dd className="mt-1.5 text-xs text-muted">{sub}</dd>}
    </div>
  );
}

export function PageHeader({ title, lede, children }: { title: string; lede?: string; children?: React.ReactNode }) {
  return (
    <header className="mb-8 flex flex-col gap-5 md:mb-10 md:flex-row md:items-end md:justify-between">
      <div className="max-w-prose">
        <h1 className="text-balance text-3xl font-semibold tracking-tight md:text-4xl">{title}</h1>
        {lede && <p className="text-pretty mt-3 text-base text-muted">{lede}</p>}
      </div>
      {children}
    </header>
  );
}
