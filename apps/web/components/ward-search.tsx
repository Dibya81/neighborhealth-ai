"use client";

import { LocateFixed, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useId, useMemo, useState } from "react";
import { toast } from "sonner";

import { useApp } from "@/components/providers";
import { BandPill } from "@/components/ui/primitives";
import { api, track, useApi } from "@/lib/api";
import { cn } from "@/lib/format";
import type { WardRisk } from "@/lib/types";

export function WardSearch({ autoFocus = false, className }: { autoFocus?: boolean; className?: string }) {
  const { t, lang } = useApp();
  const router = useRouter();
  const listId = useId();
  const { data } = useApi<{ wards: WardRisk[] }>("/v2/wards/risk?horizon=1");
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const [locating, setLocating] = useState(false);

  const results = useMemo(() => {
    if (!data || q.trim().length < 2) return [];
    const s = q.trim().toLowerCase();
    return data.wards.filter((w) => w.ward_name.toLowerCase().includes(s)).slice(0, 7);
  }, [data, q]);

  const go = (w: { ward_id: string }) => {
    track("search", { ward_id: w.ward_id });
    router.push(`/map?ward=${encodeURIComponent(w.ward_id)}`);
  };

  const locate = () => {
    if (!navigator.geolocation) return toast.error("Location isn't available in this browser.");
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const r = await api<{ ward_id: string | null }>(`/v2/locate?lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`);
          if (r.ward_id) go({ ward_id: r.ward_id });
          else toast.error("You seem to be outside BBMP. Search for a ward instead.");
        } catch (e) {
          toast.error((e as Error).message);
        } finally {
          setLocating(false);
        }
      },
      () => { setLocating(false); toast.error("Location permission was denied. Search for your ward instead."); },
      { enableHighAccuracy: false, timeout: 10000 },
    );
  };

  return (
    <div className={cn("relative", className)}>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <input
            autoFocus={autoFocus}
            role="combobox"
            aria-expanded={results.length > 0}
            aria-controls={listId}
            aria-label={t("home.search")}
            value={q}
            onChange={(e) => { setQ(e.target.value); setActive(0); }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
              if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
              if (e.key === "Enter" && results[active]) go(results[active]);
            }}
            placeholder={t("home.searchPlaceholder")}
            className="h-12 w-full rounded border border-line-strong bg-surface pl-10 pr-3 text-base placeholder:text-muted/70 transition-colors hover:border-ink/40 focus:border-lake focus:outline-none focus:ring-2 focus:ring-lake/20"
          />
        </div>
        <button onClick={locate} disabled={locating} aria-label={t("home.useLocation")} title={t("home.useLocation")}
          className="grid h-12 w-12 shrink-0 place-items-center rounded border border-line-strong bg-surface text-ink transition-colors hover:border-ink/40 disabled:opacity-60">
          <LocateFixed className={cn("h-5 w-5", locating && "animate-pulse")} />
        </button>
      </div>
      {results.length > 0 && (
        <ul id={listId} role="listbox" className="absolute inset-x-0 top-[54px] z-20 overflow-hidden rounded-lg border border-line-strong bg-surface shadow-float">
          {results.map((w, i) => (
            <li key={w.ward_id} role="option" aria-selected={i === active}>
              <button onMouseEnter={() => setActive(i)} onClick={() => go(w)}
                className={cn("flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-sm", i === active && "bg-ink/[0.05]")}>
                <span>{w.ward_name}</span>
                <BandPill band={w.band} lang={lang} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
