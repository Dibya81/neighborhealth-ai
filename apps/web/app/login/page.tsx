"use client";

import { Bell, Camera, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";

import { useApp } from "@/components/providers";
import { Logo } from "@/components/shell/logo";
import { Button, Field, Input, Panel, Segmented } from "@/components/ui/primitives";
import { api, track } from "@/lib/api";
import type { Lang, User } from "@/lib/types";

const PERKS = [
  { icon: Camera, text: "Report standing water and follow what the health team does about it." },
  { icon: Bell, text: "Save your home, office or child's school and hear when the estimated risk around it rises." },
  { icon: ShieldCheck, text: "You can export or delete everything we hold about you at any time." },
];

function LoginForm() {
  const { signIn, lang } = useApp();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [cohort, setCohort] = useState(params.get("group") ?? "");
  const [terms, setTerms] = useState(false);
  const [research, setResearch] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const body = mode === "signin"
        ? { email, password }
        : { email, password, name: name || undefined, language: lang as Lang, cohort: cohort || undefined, accept_terms: terms, research_consent: research };
      const r = await api<{ token: string; user: User }>(`/v2/auth/${mode === "signin" ? "login" : "register"}`, { method: "POST", body: JSON.stringify(body) });
      signIn(r.token, r.user);
      if (mode === "register") track("onboarding_done", { step: "registered" });
      toast.success(mode === "signin" ? "Signed in" : "Account created");
      router.push(next);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto grid max-w-[1100px] items-center gap-12 px-4 py-10 md:min-h-[calc(100dvh-140px)] md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] md:gap-20 md:px-6 md:py-16">
      <div>
        <Logo className="h-11 w-11" />
        <h1 className="mt-6 text-balance text-3xl font-semibold leading-tight tracking-tight md:text-4xl">Keep an eye on the places you care about.</h1>
        <ul className="mt-8 hidden space-y-5 md:block">
          {PERKS.map((p) => (
            <li key={p.text} className="flex gap-4">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded bg-lake-soft text-lake"><p.icon className="h-[18px] w-[18px]" /></span>
              <span className="pt-1 text-muted">{p.text}</span>
            </li>
          ))}
        </ul>
      </div>

      <form onSubmit={submit}>
        <Panel className="w-full max-w-md space-y-5 p-6 md:justify-self-end md:p-8">
          <Segmented label="Sign in or create account" value={mode} onChange={(m) => { setMode(m); setError(null); }}
            options={[{ value: "signin", label: "Sign in" }, { value: "register", label: "Create account" }]} />
          {mode === "register" && (
            <Field label="Your name (optional)" htmlFor="name"><Input id="name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></Field>
          )}
          <Field label="Email" htmlFor="email"><Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></Field>
          <Field label="Password" htmlFor="password" hint={mode === "register" ? "At least 8 characters." : undefined}>
            <Input id="password" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "signin" ? "current-password" : "new-password"} />
          </Field>
          {mode === "register" && (
            <>
              <Field label="Group code (optional)" htmlFor="cohort" hint="If your residents' association or college group gave you a code.">
                <Input id="cohort" value={cohort} onChange={(e) => setCohort(e.target.value)} placeholder="e.g. JAYANAGAR-RWA" />
              </Field>
              <label className="flex gap-3 text-sm">
                <input type="checkbox" required checked={terms} onChange={(e) => setTerms(e.target.checked)} className="mt-0.5 h-4 w-4 shrink-0 accent-[rgb(var(--lake))]" />
                <span>I understand forecasts are estimates, not medical advice, and I agree to the <Link href="/terms" target="_blank" className="font-medium text-lake underline underline-offset-2">terms</Link> and <Link href="/privacy" target="_blank" className="font-medium text-lake underline underline-offset-2">privacy notice</Link>.</span>
              </label>
              <label className="flex gap-3 text-sm text-muted">
                <input type="checkbox" checked={research} onChange={(e) => setResearch(e.target.checked)} className="mt-0.5 h-4 w-4 shrink-0 accent-[rgb(var(--lake))]" />
                <span>Optional: my anonymous usage can be used to evaluate this pilot.</span>
              </label>
            </>
          )}
          {error && <p className="rounded-lg border border-[#9E2338]/40 bg-[#9E2338]/[0.06] px-3 py-2.5 text-sm text-[#9E2338] dark:text-[#F5A3B0]" role="alert">{error}</p>}
          <Button type="submit" className="w-full" size="lg" loading={busy}>{mode === "signin" ? "Sign in" : "Create account"}</Button>
        </Panel>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
