"use client";

import { Bell, Camera, Map, MessageCircleQuestion, Moon, Sun, TrendingUp } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { useApp } from "@/components/providers";
import { Logo } from "@/components/shell/logo";
import { cn } from "@/lib/format";
import { LANG_NAMES, type TKey } from "@/lib/i18n";
import type { Lang } from "@/lib/types";

const NAV: { href: string; key: TKey; icon: React.ComponentType<{ className?: string }> }[] = [
  { href: "/map", key: "nav.map", icon: Map },
  { href: "/forecast", key: "nav.forecast", icon: TrendingUp },
  { href: "/report", key: "nav.report", icon: Camera },
  { href: "/alerts", key: "nav.alerts", icon: Bell },
  { href: "/assistant", key: "nav.assistant", icon: MessageCircleQuestion },
];

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const dark = mounted && resolvedTheme === "dark";
  return (
    <button onClick={() => setTheme(dark ? "light" : "dark")} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className="grid h-9 w-9 place-items-center rounded text-muted hover:bg-ink/5 hover:text-ink">
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}

function LangSwitch() {
  const { lang, setLang } = useApp();
  return (
    <label className="relative">
      <span className="sr-only">Language</span>
      <select value={lang} onChange={(e) => setLang(e.target.value as Lang)}
        className="h-9 cursor-pointer appearance-none rounded border border-line bg-surface pl-3 pr-7 text-sm">
        {(Object.keys(LANG_NAMES) as Lang[]).map((l) => <option key={l} value={l}>{LANG_NAMES[l]}</option>)}
      </select>
      <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-muted">▾</span>
    </label>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { t, user, signOut } = useApp();
  const isMap = pathname.startsWith("/map");
  const isOfficial = user && (user.role === "official" || user.role === "admin");

  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">Skip to content</a>
      <header className={cn("z-30 border-b border-line bg-paper/90 backdrop-blur", isMap ? "relative" : "sticky top-0")}>
        <div className="mx-auto flex h-14 max-w-[1240px] items-center gap-6 px-4 md:px-6">
          <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
            <Logo />
            <span>NeighborHealth</span>
          </Link>
          <nav aria-label="Main" className="hidden items-center gap-1 lg:flex">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} aria-current={pathname.startsWith(n.href) ? "page" : undefined}
                className={cn("rounded px-3 py-1.5 text-sm transition-colors",
                  pathname.startsWith(n.href) ? "bg-ink/[0.07] font-medium text-ink" : "text-muted hover:text-ink")}>
                {t(n.key)}
              </Link>
            ))}
            {isOfficial && (
              <Link href="/officials" aria-current={pathname.startsWith("/officials") ? "page" : undefined}
                className={cn("rounded px-3 py-1.5 text-sm", pathname.startsWith("/officials") ? "bg-ink/[0.07] font-medium" : "text-muted hover:text-ink")}>
                {t("nav.officials")}
              </Link>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-1.5">
            <Link href="/methodology" className="hidden px-2 text-sm text-muted hover:text-ink md:block">{t("nav.method")}</Link>
            <LangSwitch />
            <ThemeToggle />
            {user ? (
              <button onClick={signOut} className="hidden h-9 rounded px-3 text-sm text-muted hover:bg-ink/5 hover:text-ink sm:block">
                {t("nav.signout")}
              </button>
            ) : (
              <Link href={`/login?next=${encodeURIComponent(pathname)}`} className="h-9 rounded bg-ink px-3 text-sm font-medium leading-9 text-paper">
                {t("nav.signin")}
              </Link>
            )}
          </div>
        </div>
      </header>

      <main id="main" className={cn("flex-1", !isMap && "pb-24 lg:pb-0")}>{children}</main>

      {!isMap && (
        <footer className="hidden border-t border-line lg:block">
          <div className="mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-4 px-6 py-6 text-xs text-muted">
            <p>Data: Karnataka NVBDCP bulletins (via ICTS Bengaluru archive), NASA POWER, Census 2011, © OpenStreetMap contributors.</p>
            <p>Forecasts are estimates. In an emergency call 108.</p>
          </div>
        </footer>
      )}

      {/* Mobile tab bar */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-paper/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
        <ul className="mx-auto grid max-w-md grid-cols-5">
          {NAV.map((n) => {
            const active = pathname.startsWith(n.href);
            const Icon = n.icon;
            return (
              <li key={n.href}>
                <Link href={n.href} aria-current={active ? "page" : undefined}
                  className={cn("flex flex-col items-center gap-0.5 py-2 text-[11px]", active ? "text-lake" : "text-muted")}>
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
