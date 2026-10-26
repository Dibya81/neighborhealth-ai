"use client";

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
        "inline-flex select-none items-center justify-center gap-2 rounded font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-55",
        size === "sm" && "h-8 px-3 text-sm",
        size === "md" && "h-10 px-4 text-sm",
        size === "lg" && "h-12 px-5 text-base",
        variant === "primary" && "bg-lake text-white hover:bg-lake/90",
        variant === "secondary" && "border border-line bg-surface text-ink hover:border-ink/30",
        variant === "ghost" && "text-ink hover:bg-ink/5",
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
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium">{label}</label>
      {children}
      {error ? <p className="text-xs text-[#9E2338]" role="alert">{error}</p> : hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...rest }, ref) {
  return (
    <input
      ref={ref}
      className={cn("h-10 w-full rounded border border-line bg-surface px-3 text-sm placeholder:text-muted/80 focus:border-lake focus:outline-none", className)}
      {...rest}
    />
  );
});

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn("min-h-[88px] w-full rounded border border-line bg-surface px-3 py-2 text-sm placeholder:text-muted/80 focus:border-lake focus:outline-none", props.className)} />;
}

export function Segmented<T extends string | number>({ value, options, onChange, label, size = "md" }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string; size?: "sm" | "md";
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded border border-line bg-surface p-0.5">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={String(o.value)}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={cn(
              "rounded-sm px-3 font-medium transition-colors",
              size === "sm" ? "h-7 text-xs" : "h-8 text-sm",
              active ? "bg-ink text-paper" : "text-muted hover:text-ink",
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
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold", className)}
      style={{ background: BAND_COLOR[band], color: BAND_TEXT[band] }}>
      {bandLabel(lang, band)}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-ink/[0.06]", className)} aria-hidden />;
}

export function Notice({ tone = "info", title, children, action }: {
  tone?: "info" | "warn" | "danger"; title: string; children?: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn(
      "rounded border p-4 text-sm",
      tone === "info" && "border-line bg-surface",
      tone === "warn" && "border-[#F2B33D]/60 bg-[#F2B33D]/10",
      tone === "danger" && "border-[#9E2338]/50 bg-[#9E2338]/[0.07]",
    )}>
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 text-muted">{children}</div>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function PageHeader({ title, lede, children }: { title: string; lede?: string; children?: React.ReactNode }) {
  return (
    <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="max-w-prose">
        <h1 className="text-balance font-display text-3xl font-semibold tracking-tight md:text-4xl">{title}</h1>
        {lede && <p className="mt-3 text-base text-muted">{lede}</p>}
      </div>
      {children}
    </header>
  );
}
