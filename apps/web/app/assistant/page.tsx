"use client";

import { AlertTriangle, ExternalLink, Phone, SendHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useApp } from "@/components/providers";
import { Button, PageHeader } from "@/components/ui/primitives";
import { api, track } from "@/lib/api";
import { cn, nf } from "@/lib/format";
import type { AssistantAnswer } from "@/lib/types";

type Msg = { role: "user"; text: string } | { role: "assistant"; a: AssistantAnswer } | { role: "error"; text: string };

const SUGGESTIONS = {
  en: ["What are the warning signs of severe dengue?", "How do I stop mosquitoes breeding at home?", "Which painkillers should be avoided in dengue?", "How long does dengue fever last?"],
  kn: ["ತೀವ್ರ ಡೆಂಗ್ಯೂವಿನ ಎಚ್ಚರಿಕೆ ಲಕ್ಷಣಗಳೇನು?", "ಮನೆಯಲ್ಲಿ ಸೊಳ್ಳೆ ಉತ್ಪತ್ತಿ ತಡೆಯುವುದು ಹೇಗೆ?"],
  hi: ["गंभीर डेंगू के चेतावनी संकेत क्या हैं?", "घर में मच्छरों को पनपने से कैसे रोकें?"],
};

function Answer({ a }: { a: AssistantAnswer }) {
  const { lang } = useApp();
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="space-y-3">
      {a.urgent && a.urgent_message && (
        <div role="alert" className="rounded border border-[#9E2338]/50 bg-[#9E2338]/[0.07] p-4">
          <p className="flex items-start gap-2 font-medium text-[#9E2338]"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />{a.urgent_message}</p>
          <a href="tel:108" className="mt-3 inline-flex items-center gap-2 rounded bg-[#9E2338] px-4 py-2 text-sm font-medium text-white"><Phone className="h-4 w-4" />Call 108</a>
          {a.nearby && a.nearby.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm">
              {a.nearby.map((c) => <li key={c.id}>{c.name} <span className="text-muted">· {nf(c.distance_m / 1000, 1)} km</span></li>)}
            </ul>
          )}
        </div>
      )}
      <p className="whitespace-pre-line leading-relaxed" lang={lang}>{a.answer}</p>
      {a.citations.length > 0 && (
        <div>
          <p className="text-xs text-muted">Sources</p>
          <ol className="mt-1.5 space-y-1.5">
            {a.citations.map((c) => (
              <li key={c.n} className="text-sm">
                <button onClick={() => { setOpen(open === c.n ? null : c.n); track("citation_opened"); }} aria-expanded={open === c.n}
                  className="text-left text-lake underline-offset-2 hover:underline">
                  [{c.n}] {c.org}, {c.title}{c.page > 1 ? `, p. ${c.page}` : ""}
                </button>
                {open === c.n && (
                  <blockquote className="mt-1.5 border-l-2 border-line pl-3 text-xs text-muted">
                    “{c.quote}…”
                    {c.url && <a href={c.url} target="_blank" rel="noreferrer" className="ml-1 inline-flex items-center gap-1 text-lake">open<ExternalLink className="h-3 w-3" /></a>}
                  </blockquote>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
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
    <div className="mx-auto flex max-w-[820px] flex-col px-4 py-8 md:px-6 md:py-12">
      <PageHeader title={t("assistant.title")} lede={t("assistant.lede")} />

      <div className="flex-1 space-y-6" aria-live="polite">
        {msgs.length === 0 && (
          <div className="grid gap-2 sm:grid-cols-2">
            {(SUGGESTIONS[lang] ?? SUGGESTIONS.en).map((s) => (
              <button key={s} onClick={() => ask(s)} className="rounded border border-line bg-surface px-4 py-3 text-left text-sm hover:border-lake">{s}</button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={cn(m.role === "user" ? "ml-auto max-w-[85%] rounded-lg bg-ink px-4 py-3 text-paper" : "max-w-full")}>
            {m.role === "user" && <p>{m.text}</p>}
            {m.role === "assistant" && <Answer a={m.a} />}
            {m.role === "error" && <p className="text-sm text-[#9E2338]">{m.text}</p>}
          </div>
        ))}
        {busy && <p className="text-sm text-muted">Checking the guidelines…</p>}
        <div ref={endRef} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); ask(q); }}
        className="sticky bottom-20 mt-8 flex gap-2 rounded-lg border border-line bg-surface p-2 shadow-float lg:bottom-4">
        <label htmlFor="q" className="sr-only">{t("assistant.title")}</label>
        <input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("assistant.placeholder")} maxLength={800}
          className="h-11 flex-1 bg-transparent px-3 text-base placeholder:text-muted/80 focus:outline-none" />
        <Button type="submit" size="lg" loading={busy} aria-label={t("assistant.send")}><SendHorizontal className="h-4 w-4" /></Button>
      </form>
      <p className="mt-3 text-center text-xs text-muted">Not a doctor. For high fever, see a doctor. Emergency: 108 · Health helpline: 104</p>
    </div>
  );
}
