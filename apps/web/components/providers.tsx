"use client";

import { ThemeProvider } from "next-themes";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Toaster } from "sonner";

import { api, getToken, setToken } from "@/lib/api";
import { translate, type TKey } from "@/lib/i18n";
import type { Lang, User } from "@/lib/types";

interface AppState {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: TKey, vars?: Record<string, string | number>) => string;
  user: User | null;
  authReady: boolean;
  signIn: (token: string, user: User) => void;
  signOut: () => void;
}

const Ctx = createContext<AppState | null>(null);

export function useApp() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp must be used inside <Providers>");
  return v;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  const [user, setUser] = useState<User | null>(null);
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("nh.lang") as Lang | null;
      if (saved && ["en", "kn", "hi"].includes(saved)) setLangState(saved);
    } catch { /* storage blocked */ }
    if (getToken()) {
      api<User>("/v2/auth/me").then(setUser).catch(() => setUser(null)).finally(() => setAuthReady(true));
    } else setAuthReady(true);
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);

  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { window.localStorage.setItem("nh.lang", l); } catch { /* ignore */ }
    if (getToken()) api("/v2/auth/me", { method: "PATCH", body: JSON.stringify({ language: l }) }).catch(() => {});
  }, []);

  const value = useMemo<AppState>(() => ({
    lang, setLang, user, authReady,
    t: (key, vars) => translate(lang, key, vars),
    signIn: (token, u) => { setToken(token); setUser(u); if (u.language) setLangState(u.language); },
    signOut: () => { setToken(null); setUser(null); },
  }), [lang, setLang, user, authReady]);

  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <Ctx.Provider value={value}>
        {children}
        <Toaster position="bottom-center" toastOptions={{ className: "!rounded-[10px] !border-line !bg-surface !text-ink" }} />
      </Ctx.Provider>
    </ThemeProvider>
  );
}
