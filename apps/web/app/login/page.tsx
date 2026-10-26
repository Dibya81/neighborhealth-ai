"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";

import { useApp } from "@/components/providers";
import { Logo } from "@/components/shell/logo";
import { Button, Field, Input, Segmented } from "@/components/ui/primitives";
import { api, track } from "@/lib/api";
import type { Lang, User } from "@/lib/types";

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
    <div className="mx-auto grid min-h-[calc(100dvh-56px)] max-w-[1100px] items-center gap-12 px-4 py-10 md:grid-cols-2 md:px-6">
      <div className="hidden md:block">
        <Logo className="h-12 w-12" />
        <h1 className="mt-6 font-display text-4xl font-semibold leading-tight tracking-tight">Keep an eye on the places you care about.</h1>
        <p className="mt-4 max-w-prose text-muted">An account lets you report breeding spots, save your home, office or child&apos;s school, and get a message when the estimated risk around them rises.</p>
      </div>
      <form onSubmit={submit} className="w-full max-w-md space-y-5 justify-self-center rounded-lg border border-line bg-surface p-6 md:p-8">
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
              <input type="checkbox" required checked={terms} onChange={(e) => setTerms(e.target.checked)} className="mt-1 accent-[#0E7C7B]" />
              <span>I understand forecasts are estimates, not medical advice, and I agree to the terms and privacy notice. Photos I send are stripped of location metadata.</span>
            </label>
            <label className="flex gap-3 text-sm text-muted">
              <input type="checkbox" checked={research} onChange={(e) => setResearch(e.target.checked)} className="mt-1 accent-[#0E7C7B]" />
              <span>Optional: my anonymous usage can be used to evaluate this pilot.</span>
            </label>
          </>
        )}
        {error && <p className="text-sm text-[#9E2338]" role="alert">{error}</p>}
        <Button type="submit" className="w-full" size="lg" loading={busy}>{mode === "signin" ? "Sign in" : "Create account"}</Button>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
