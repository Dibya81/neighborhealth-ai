"use client";

import { Bell, Camera, Clock, LogOut, Map, MessageCircleQuestion, Moon, Sun, TrendingUp } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { useApp } from "@/components/providers";
import { Logo } from "@/components/shell/logo";
import { cn } from "@/lib/format";
import { longDate, useFreshness } from "@/lib/freshness";
import { LANG_NAMES, type TKey } from "@/lib/i18n";
import type { Lang } from "@/lib/types";

const NAV: { href: string; key: TKey; icon: React.ComponentType<{ className?: string }> }[] = [
  { href: "/map", key: "nav.map", icon: Map },
  { href: "/forecast", key: "nav.forecast", icon: TrendingUp },
  { href: "/report", key: "nav.report", icon: Camera },
  { href: "/alerts", key: "nav.alerts", icon: Bell },
  { href: "/assistant", key: "nav.assistant", icon: MessageCircleQuestion },
];

function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const dark = mounted && resolvedTheme === "dark";
  return (
    <button onClick={() => setTheme(dark ? "light" : "dark")} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className={cn("grid h-10 w-10 place-items-center rounded text-muted transition-colors hover:bg-ink/[0.06] hover:text-ink", className)}>
      {dark ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
    </button>
  );
}

function LangSwitch() {
  const { lang, setLang } = useApp();
  return (
    <label className="relative">
      <span className="sr-only">Language</span>
      <select value={lang} onChange={(e) => setLang(e.target.value as Lang)}
        className="h-10 cursor-pointer appearance-none rounded border border-line-strong bg-surface pl-2.5 pr-7 text-sm transition-colors hover:border-ink/40 sm:pl-3 sm:pr-8">
        {(Object.keys(LANG_NAMES) as Lang[]).map((l) => <option key={l} value={l}>{LANG_NAMES[l]}</option>)}
      </select>
      <svg className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" viewBox="0 0 16 16" fill="none" aria-hidden>
        <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </label>
  );
}

/** Shown on every page while the forecast is built from old data. The single most important thing to say. */
function FreshnessBanner() {
  const { lang } = useApp();
  const f = useFreshness();
  if (!f.ready || !f.stale) return null;
  return (
    <div role="status" className="border-b border-warn-line bg-warn-bg text-warn-ink">
      <div className="mx-auto flex max-w-[1240px] items-start gap-3 px-4 py-2.5 text-sm md:items-center md:px-6">
        <Clock className="mt-0.5 h-4 w-4 shrink-0 md:mt-0" aria-hidden />
        <p className="min-w-0 flex-1 text-pretty">
          <strong className="font-semibold">Archived data, not a live forecast.</strong>{" "}
          {f.dataThrough
            ? <>Everything here is built from government bulletins up to {longDate(f.dataThrough, lang)}.</>
            : <>No forecast has been published yet.</>}
        </p>
        <Link href="/methodology#data" className="shrink-0 font-medium underline underline-offset-2 hover:no-underline">Why?</Link>
      </div>
    </div>
  );
}

function Footer() {
  const { t } = useApp();
  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto grid max-w-[1240px] gap-10 px-4 py-10 md:grid-cols-[1.4fr_1fr_1fr] md:px-6">
        <div className="max-w-sm">
          <div className="flex items-center gap-2.5 font-semibold tracking-tight"><Logo className="h-7 w-7" /> NeighborHealth</div>
          <p className="mt-3 text-sm text-muted">Dengue early warning for Bengaluru, built on government surveillance data. Estimates, not diagnoses.</p>
          <div className="mt-4 flex items-center gap-2 text-sm text-muted sm:hidden"><ThemeToggle className="border border-line-strong" /> Light or dark</div>
        </div>
        <nav aria-label="Footer" className="grid content-start gap-2 text-sm">
          {NAV.map((n) => <Link key={n.href} href={n.href} className="text-muted hover:text-ink">{t(n.key)}</Link>)}
          <Link href="/methodology" className="text-muted hover:text-ink">{t("nav.method")}</Link>
          <Link href="/privacy" className="text-muted hover:text-ink">Privacy notice</Link>
          <Link href="/terms" className="text-muted hover:text-ink">Terms of use</Link>
        </nav>
        <div className="text-sm">
          <p className="font-medium">If you feel seriously unwell</p>
          <p className="mt-2 text-muted">Severe stomach pain, repeated vomiting, bleeding or difficulty breathing: go to a hospital now or call <strong className="text-ink">108</strong>. Health helpline: <strong className="text-ink">104</strong>.</p>
        </div>
      </div>
      <div className="border-t border-line">
        <p className="mx-auto max-w-[1240px] px-4 py-4 text-xs text-muted md:px-6">
          Data: Karnataka NVBDCP bulletins via the ICTS Bengaluru archive, NASA POWER, Census of India 2011, © OpenStreetMap contributors.
        </p>
      </div>
    </footer>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { t, user, signOut } = useApp();
  const isMap = pathname.startsWith("/map");
  const isOfficial = user && (user.role === "official" || user.role === "admin");
  const links = isOfficial ? [...NAV, { href: "/officials", key: "nav.officials" as TKey, icon: Map }] : NAV;

  return (
    <div className={cn("flex flex-col", isMap ? "h-dvh" : "min-h-dvh")}>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">Skip to content</a>
      <header className={cn("z-30 border-b border-line bg-paper/90 backdrop-blur", isMap ? "relative" : "sticky top-0")}>
        <div className="mx-auto flex h-16 max-w-[1240px] items-center gap-3 px-4 sm:gap-8 md:px-6">
          <Link href="/" className="flex shrink-0 items-center gap-2 text-base font-semibold tracking-tight sm:gap-2.5 sm:text-[17px]">
            <Logo />
            <span>NeighborHealth</span>
          </Link>
          <nav aria-label="Main" className="hidden h-full items-stretch gap-1 lg:flex">
            {links.map((n) => {
              const active = pathname.startsWith(n.href);
              return (
                <Link key={n.href} href={n.href} aria-current={active ? "page" : undefined}
                  className={cn("relative flex items-center px-3 text-sm transition-colors",
                    active ? "font-medium text-ink" : "text-muted hover:text-ink")}>
                  {t(n.key)}
                  {active && <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-lake" aria-hidden />}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-1 sm:gap-1.5">
            <Link href="/methodology" className="hidden px-2 text-sm text-muted transition-colors hover:text-ink md:block">{t("nav.method")}</Link>
            <LangSwitch />
            <ThemeToggle className="hidden sm:grid" />
            {user ? (
              <button onClick={signOut} aria-label={t("nav.signout")}
                className="flex h-10 items-center gap-2 rounded px-2 text-sm text-muted transition-colors hover:bg-ink/[0.06] hover:text-ink sm:px-3">
                <LogOut className="h-[18px] w-[18px]" />
                <span className="hidden sm:inline">{t("nav.signout")}</span>
              </button>
            ) : (
              <Link href={`/login?next=${encodeURIComponent(pathname)}`}
                className="inline-flex h-10 shrink-0 items-center whitespace-nowrap rounded bg-ink px-3.5 text-sm font-medium text-paper transition-opacity hover:opacity-90 sm:px-4">
                {t("nav.signin")}
              </Link>
            )}
          </div>
        </div>
      </header>
      <FreshnessBanner />

      <main id="main" className={cn("flex-1", isMap ? "relative min-h-0 pb-[calc(56px+env(safe-area-inset-bottom))] lg:pb-0" : "pb-24 lg:pb-0")}>{children}</main>

      {!isMap && <Footer />}

      {/* Mobile tab bar */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-paper/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
        <ul className="mx-auto grid max-w-md grid-cols-5">
          {NAV.map((n) => {
            const active = pathname.startsWith(n.href);
            const Icon = n.icon;
            return (
              <li key={n.href}>
                <Link href={n.href} aria-current={active ? "page" : undefined}
                  className={cn("relative flex min-h-[56px] flex-col items-center justify-center gap-1 text-[11px] font-medium", active ? "text-lake" : "text-muted")}>
                  {active && <span className="absolute inset-x-4 top-0 h-0.5 rounded-full bg-lake" aria-hidden />}
                  <Icon className="h-5 w-5" />
                  <span className="max-w-[72px] truncate">{t(n.key)}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
