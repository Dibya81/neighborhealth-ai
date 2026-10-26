"use client";

import { AlertTriangle, ExternalLink, Phone, SendHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useApp } from "@/components/providers";
import { Button, PageHeader, Panel } from "@/components/ui/primitives";
import { api, track } from "@/lib/api";
import { cn, nf } from "@/lib/format";
import type { AssistantAnswer } from "@/lib/types";

type Msg = { role: "user"; text: string } | { role: "assistant"; a: AssistantAnswer } | { role: "error"; text: string };

const SUGGESTIONS = {
  en: ["What are the warning signs of severe dengue?", "How do I stop mosquitoes breeding at home?", "Which painkillers should be avoided in dengue?", "How long does dengue fever last?"],
  kn: ["ತೀವ್ರ ಡೆಂಗ್ಯೂವಿನ ಎಚ್ಚರಿಕೆ ಲಕ್ಷಣಗಳೇನು?", "ಮನೆಯಲ್ಲಿ ಸೊಳ್ಳೆ ಉತ್ಪತ್ತಿ ತಡೆಯುವುದು ಹೇಗೆ?"],
  hi: ["गंभीर डेंगू के चेतावनी संकेत क्या हैं?", "घर में मच्छरों को पनपने से कैसे रोकें?"],
};

function Urgent({ a }: { a: AssistantAnswer }) {
  return (
    <div role="alert" className="rounded-lg border border-[#9E2338]/60 bg-[#9E2338]/[0.07] p-5">
      <p className="flex items-start gap-3 text-base font-semibold text-[#9E2338] dark:text-[#F5A3B0]">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />{a.urgent_message}
      </p>
      <a href="tel:108" className="mt-4 inline-flex h-12 items-center gap-2 rounded bg-[#9E2338] px-5 text-base font-semibold text-white transition-colors hover:bg-[#8A1E31]">
        <Phone className="h-4 w-4" />Call 108 now
      </a>
      {a.nearby && a.nearby.length > 0 && (
        <div className="mt-5">
          <p className="text-sm font-medium">Nearest hospitals</p>
          <ul className="mt-2 divide-y divide-[#9E2338]/20 border-y border-[#9E2338]/20 text-sm">
            {a.nearby.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-3 py-2.5">
                <span className="min-w-0"><span className="block truncate font-medium">{c.name}</span><span className="num text-xs text-muted">{nf(c.distance_m / 1000, 1)} km away</span></span>
                {c.phone && <a href={`tel:${c.phone}`} className="shrink-0 rounded border border-[#9E2338]/40 px-3 py-1.5 text-xs font-medium hover:bg-[#9E2338]/10">Call</a>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Answer({ a }: { a: AssistantAnswer }) {
  const { lang } = useApp();
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="space-y-4">
      {a.urgent && a.urgent_message && <Urgent a={a} />}
      <Panel className="p-5">
        <p className="whitespace-pre-line text-base leading-relaxed" lang={lang}>{a.answer}</p>
        {a.citations.length > 0 && (
          <div className="mt-5 border-t border-line pt-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">Sources</p>
            <ol className="mt-2 space-y-2">
              {a.citations.map((c) => (
                <li key={c.n} className="text-sm">
                  <button onClick={() => { setOpen(open === c.n ? null : c.n); track("citation_opened"); }} aria-expanded={open === c.n}
                    className="text-left font-medium text-lake underline-offset-2 hover:underline">
                    [{c.n}] {c.org}, {c.title}{c.page > 1 ? `, page ${c.page}` : ""}
                  </button>
                  {open === c.n && (
                    <blockquote className="mt-2 rounded-lg bg-sunken p-3 text-xs leading-relaxed text-muted">
                      &ldquo;{c.quote}...&rdquo;
                      {c.url && <a href={c.url} target="_blank" rel="noreferrer" className="ml-2 inline-flex items-center gap-1 font-medium text-lake">Open the document<ExternalLink className="h-3 w-3" /></a>}
                    </blockquote>
                  )}
                </li>
              ))}
            </ol>
          </div>
        )}
      </Panel>
    </div>
  );
}

export default function AssistantPage() {
  const { t, lang } = useApp();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const coords = useRef<{ lat: number; lon: number } | null>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, busy]);

  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setQ("");
    setBusy(true);
    track("assistant_question", { language: lang });
    try {
      const a = await api<AssistantAnswer>("/v2/assistant/ask", {
        method: "POST", body: JSON.stringify({ question, language: lang, ...(coords.current ?? {}) }),
      });
      setMsgs((m) => [...m, { role: "assistant", a }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "error", text: (e as Error).message }]);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    navigator.geolocation?.getCurrentPosition((p) => { coords.current = { lat: p.coords.latitude, lon: p.coords.longitude }; }, () => {}, { timeout: 5000 });
  }, []);

  return (
    <div className="mx-auto flex max-w-[820px] flex-col px-4 py-10 md:px-6 md:py-14">
      <PageHeader title={t("assistant.title")} lede={t("assistant.lede")} />

      <div className="mb-8 flex items-start gap-3 rounded-lg border border-[#9E2338]/40 bg-[#9E2338]/[0.05] p-4 text-sm">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#9E2338] dark:text-[#F5A3B0]" aria-hidden />
        <p className="flex-1">
          <strong className="font-semibold">Seriously unwell?</strong> Severe stomach pain, repeated vomiting, bleeding, or trouble breathing:
          go to a hospital now or <a href="tel:108" className="font-semibold underline underline-offset-2">call 108</a>. Do not wait for an answer here.
        </p>
      </div>

      <div className="flex-1 space-y-6" aria-live="polite">
        {msgs.length === 0 && (
          <div>
            <h2 className="text-sm font-semibold">Common questions</h2>
            <ul className="mt-3 divide-y divide-line border-y border-line">
              {(SUGGESTIONS[lang] ?? SUGGESTIONS.en).map((s) => (
                <li key={s}>
                  <button onClick={() => ask(s)} className="flex min-h-[52px] w-full items-center justify-between gap-4 py-3 text-left text-base transition-colors hover:text-lake">
                    {s}<SendHorizontal className="h-4 w-4 shrink-0 text-muted" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={cn(m.role === "user" ? "ml-auto w-fit max-w-[85%] rounded-lg bg-ink px-4 py-3 text-paper" : "max-w-full")}>
            {m.role === "user" && <p>{m.text}</p>}
            {m.role === "assistant" && <Answer a={m.a} />}
            {m.role === "error" && <p className="rounded-lg border border-[#9E2338]/40 bg-[#9E2338]/[0.05] p-4 text-sm text-[#9E2338] dark:text-[#F5A3B0]">{m.text}</p>}
          </div>
        ))}
        {busy && (
          <Panel className="space-y-2.5 p-5" >
            <div className="h-3 w-3/4 animate-pulse rounded bg-ink/[0.08]" /><div className="h-3 w-full animate-pulse rounded bg-ink/[0.08]" /><div className="h-3 w-1/2 animate-pulse rounded bg-ink/[0.08]" />
            <p className="sr-only">Checking the guidelines</p>
          </Panel>
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); ask(q); }}
        className="sticky bottom-[calc(72px+env(safe-area-inset-bottom))] mt-8 flex gap-2 rounded-lg border border-line-strong bg-surface p-2 shadow-float lg:bottom-4">
        <label htmlFor="q" className="sr-only">{t("assistant.title")}</label>
        <input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("assistant.placeholder")} maxLength={800}
          className="h-12 min-w-0 flex-1 bg-transparent px-3 text-base placeholder:text-muted/70 focus:outline-none" />
        <Button type="submit" size="lg" loading={busy} aria-label={t("assistant.send")}><SendHorizontal className="h-4 w-4" /></Button>
      </form>
      <p className="mt-4 text-center text-xs text-muted">This is information from official guidelines, not medical advice. For a high fever, see a doctor. Health helpline: 104.</p>
    </div>
  );
}
