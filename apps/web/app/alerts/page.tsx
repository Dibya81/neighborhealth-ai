"use client";

import { Briefcase, Home, MapPin, Plus, School, Trash2 } from "lucide-react";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";

import type { PickedLocation } from "@/components/map/location-picker";
import { useApp } from "@/components/providers";
import { RequireAuth } from "@/components/require-auth";
import { BandPill, Button, Field, Input, Notice, PageHeader, Panel, Segmented, Skeleton } from "@/components/ui/primitives";
import { api, track, useApi } from "@/lib/api";
import { cn, timeAgo } from "@/lib/format";
import { longDate, useFreshness } from "@/lib/freshness";
import { LANG_NAMES } from "@/lib/i18n";
import type { Band, Lang, Subscription } from "@/lib/types";

const LocationPicker = dynamic(() => import("@/components/map/location-picker"), { ssr: false, loading: () => <Skeleton className="h-[240px]" /> });

const PLACE_ICON = { home: Home, office: Briefcase, school: School, other: MapPin } as const;
const PLACE_NAME = { home: "Home", office: "Office", school: "School", other: "Other place" } as const;
const CHANNEL_NAME: Record<string, string> = { whatsapp: "WhatsApp", sms: "SMS", email: "email" };

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-line pt-6 first:border-t-0 first:pt-0">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function NewPlace({ onSaved, onCancel, fromWard }: { onSaved: () => void; onCancel: () => void; fromWard?: string | null }) {
  const { lang, user } = useApp();
  const [label, setLabel] = useState<Subscription["label"]>("home");
  const [loc, setLoc] = useState<PickedLocation | null>(null);
  const [radius, setRadius] = useState(1000);
  const [channels, setChannels] = useState<string[]>(["whatsapp"]);
  const [phone, setPhone] = useState("+91");
  const [email, setEmail] = useState(user?.email ?? "");
  const [msgLang, setMsgLang] = useState<Lang>(lang);
  const [threshold, setThreshold] = useState<Band>("high");
  const [quiet, setQuiet] = useState(true);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);

  const toggle = (c: string) => setChannels((cs) => (cs.includes(c) ? cs.filter((x) => x !== c) : [...cs, c]));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loc) return toast.error("Choose the place on the map.");
    if (channels.length === 0) return toast.error("Pick at least one way to reach you.");
    setBusy(true);
    try {
      await api("/v2/subscriptions", {
        method: "POST",
        body: JSON.stringify({
          label, lat: loc.lat, lon: loc.lon, radius_m: radius, channels,
          phone: channels.some((c) => c !== "email") ? phone.replace(/\s/g, "") : undefined,
          email: channels.includes("email") ? email : undefined,
          language: msgLang, threshold_band: threshold,
          quiet_start: quiet ? "21:00" : null, quiet_end: quiet ? "08:00" : null, consent,
        }),
      });
      toast.success("Place saved");
      track("subscription_created", { channel: channels.join("+") });
      onSaved();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={save}>
      <Panel className="space-y-6 p-5 md:p-7">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold tracking-tight">Save a place</h2>
          <Button type="button" variant="ghost" size="sm" onClick={onCancel}>Cancel</Button>
        </div>
        {fromWard && <p className="rounded-lg bg-lake-soft px-4 py-3 text-sm">You came from <strong className="font-semibold">{fromWard}</strong>. Tap the exact place on the map below.</p>}

        <Section title="Which place?">
          <div className="grid grid-cols-4 gap-2">
            {(Object.keys(PLACE_NAME) as Subscription["label"][]).map((k) => {
              const Icon = PLACE_ICON[k];
              return (
                <button type="button" key={k} onClick={() => setLabel(k)} aria-pressed={label === k}
                  className={cn("flex min-h-[64px] flex-col items-center justify-center gap-1.5 rounded-lg border text-xs font-medium transition-colors",
                    label === k ? "border-lake bg-lake-soft/70 text-ink" : "border-line-strong text-muted hover:border-ink/40 hover:text-ink")}>
                  <Icon className="h-5 w-5" />{PLACE_NAME[k]}
                </button>
              );
            })}
          </div>
        </Section>

        <Section title="Where is it?">
          <LocationPicker value={loc} onChange={setLoc} height={240} />
          <div className="mt-5">
            <Field label={`Watch an area of ${radius >= 1000 ? `${radius / 1000} km` : `${radius} m`} around it`}>
              <input type="range" min={300} max={3000} step={100} value={radius} onChange={(e) => setRadius(+e.target.value)} className="w-full accent-[rgb(var(--lake))]" />
            </Field>
          </div>
        </Section>

        <Section title="How should we reach you?">
          <div className="flex flex-wrap gap-2">
            {[["whatsapp", "WhatsApp"], ["sms", "SMS"], ["email", "Email"]].map(([v, l]) => (
              <label key={v} className={cn("flex min-h-[44px] cursor-pointer items-center gap-2.5 rounded-lg border px-4 text-sm transition-colors", channels.includes(v) ? "border-lake bg-lake-soft/70 font-medium" : "border-line-strong hover:border-ink/40")}>
                <input type="checkbox" checked={channels.includes(v)} onChange={() => toggle(v)} className="h-4 w-4 accent-[rgb(var(--lake))]" />{l}
              </label>
            ))}
          </div>
          <div className="mt-3 space-y-3">
            {channels.some((c) => c !== "email") && <Input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91 98xxxxxxxx" aria-label="Phone number" />}
            {channels.includes("email") && <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" aria-label="Email" />}
          </div>
        </Section>

        <Section title="When and in which language?">
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Tell me when risk reaches">
              <Segmented label="Alert threshold" value={threshold} onChange={setThreshold} size="sm"
                options={[{ value: "moderate", label: "Moderate" }, { value: "high", label: "High" }, { value: "very_high", label: "Very high" }]} />
            </Field>
            <Field label="Message language">
              <Segmented label="Message language" value={msgLang} onChange={setMsgLang} size="sm"
                options={(Object.keys(LANG_NAMES) as Lang[]).map((l) => ({ value: l, label: LANG_NAMES[l] }))} />
            </Field>
          </div>
          <label className="mt-5 flex items-center gap-3 text-sm">
            <input type="checkbox" checked={quiet} onChange={(e) => setQuiet(e.target.checked)} className="h-4 w-4 accent-[rgb(var(--lake))]" />
            No messages between 9 pm and 8 am
          </label>
        </Section>

        <Section title="Your consent">
          <label className="flex gap-3 text-sm">
            <input type="checkbox" required checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5 h-4 w-4 shrink-0 accent-[rgb(var(--lake))]" />
            <span>I agree to receive dengue risk messages for this place, at most two a week. I can stop them any time: every email has an unsubscribe link, I can reply STOP to a text or WhatsApp message, or I can remove the place on this page.</span>
          </label>
        </Section>

        <Button type="submit" size="lg" loading={busy}>Save place</Button>
      </Panel>
    </form>
  );
}

interface MyAlert { id: string; ward_name: string | null; band: Band; status: string; created_at: string; feedback: string | null; channel: string }

function AlertsInner() {
  const { lang } = useApp();
  const fresh = useFreshness();
  const params = useSearchParams();
  const wardParam = params.get("ward");
  const ward = useApi<{ ward_name: string }>(wardParam ? `/v2/wards/${encodeURIComponent(wardParam)}` : null);
  const subs = useApi<{ subscriptions: Subscription[] }>("/v2/subscriptions");
  const alerts = useApi<{ alerts: MyAlert[] }>("/v2/alerts/mine");
  const [adding, setAdding] = useState(!!wardParam);

  const remove = async (id: string) => {
    await api(`/v2/subscriptions/${id}`, { method: "DELETE" });
    toast.success("Place removed");
    subs.mutate();
  };
  const feedback = async (id: string, fb: string) => {
    await api(`/v2/alerts/${id}/feedback`, { method: "POST", body: JSON.stringify({ feedback: fb }) });
    toast.success("Thanks for the feedback");
    alerts.mutate();
  };

  const list = subs.data?.subscriptions ?? [];
  return (
    <>
      {fresh.stale && fresh.dataThrough && (
        <div className="mb-8">
          <Notice tone="warn" title="Alerts are paused while the data is archived">
            The forecast is built from bulletins up to {longDate(fresh.dataThrough, lang)}, so no alerts are being sent. Places you save now will start receiving alerts when live data is connected.
          </Notice>
        </div>
      )}
      <div className="grid gap-12 lg:grid-cols-[minmax(0,7fr)_minmax(0,4fr)] lg:gap-16">
        <div className="space-y-4">
          {!subs.data && <Skeleton className="h-28" />}
          {subs.data && list.length === 0 && !adding && (
            <Panel className="border-dashed p-8 text-center md:p-12">
              <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-lake-soft text-lake"><MapPin className="h-6 w-6" /></span>
              <p className="mt-4 text-lg font-semibold">No places saved yet</p>
              <p className="mx-auto mt-1 max-w-sm text-sm text-muted">Start with your home. You can save up to five places, each with its own settings.</p>
              <Button className="mt-6" size="lg" onClick={() => setAdding(true)}><Plus className="h-4 w-4" />Save a place</Button>
            </Panel>
          )}
          {list.map((s) => {
            const Icon = PLACE_ICON[s.label];
            return (
              <Panel key={s.id} className="flex items-start gap-4 p-5">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded bg-lake-soft text-lake"><Icon className="h-5 w-5" /></span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-semibold">{PLACE_NAME[s.label]}</h3>
                    {s.last_band && <BandPill band={s.last_band} lang={lang} />}
                  </div>
                  <p className="mt-1 truncate text-sm text-muted">{s.wards.map((w) => w.ward_name).join(", ")}</p>
                  <p className="mt-1 text-xs text-muted">
                    Alerts at {s.threshold_band.replace("_", " ")} risk or above, by {s.channels.map((c) => CHANNEL_NAME[c] ?? c).join(" and ")}, in {LANG_NAMES[s.language]}{s.quiet_start ? ", quiet at night" : ""}.
                  </p>
                </div>
                <button onClick={() => remove(s.id)} aria-label={`Remove ${PLACE_NAME[s.label]}`} className="grid h-10 w-10 place-items-center rounded text-muted transition-colors hover:bg-[#9E2338]/10 hover:text-[#B42A42]">
                  <Trash2 className="h-4 w-4" />
                </button>
              </Panel>
            );
          })}
          {adding
            ? <NewPlace fromWard={ward.data?.ward_name} onCancel={() => setAdding(false)} onSaved={() => { setAdding(false); subs.mutate(); }} />
            : list.length > 0 && list.length < 5 && <Button variant="secondary" onClick={() => setAdding(true)}><Plus className="h-4 w-4" />Save another place</Button>}
        </div>

        <aside className="space-y-10">
          <div>
            <h2 className="text-base font-semibold">How alerts work</h2>
            <ul className="mt-3 space-y-2.5 text-sm text-muted">
              <li>You hear from us only when risk around a place rises past the level you choose.</li>
              <li>At most two messages a week, and never during your quiet hours.</li>
              <li>Messages are area estimates, never a diagnosis.</li>
            </ul>
          </div>
          <div>
            <h2 className="text-base font-semibold">Recent alerts</h2>
            {!alerts.data ? <Skeleton className="mt-3 h-24" /> : alerts.data.alerts.length === 0 ? (
              <p className="mt-3 text-sm text-muted">No alerts yet. That usually means the risk around your places is below your threshold.</p>
            ) : (
              <ul className="mt-3 divide-y divide-line border-y border-line">
                {alerts.data.alerts.map((a) => (
                  <li key={a.id} className="py-4 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{a.ward_name}</span><BandPill band={a.band} lang={lang} />
                    </div>
                    <p className="mt-1 text-xs text-muted">{CHANNEL_NAME[a.channel] ?? a.channel}, {timeAgo(a.created_at)}{a.status === "suppressed" ? ", held back by the weekly limit" : a.status === "sent" ? "" : `, ${a.status}`}</p>
                    {a.status === "sent" && !a.feedback && (
                      <div className="mt-3 flex gap-2">
                        <Button size="sm" variant="secondary" onClick={() => feedback(a.id, "useful")}>Useful</Button>
                        <Button size="sm" variant="ghost" onClick={() => feedback(a.id, "not_useful")}>Not useful</Button>
                      </div>
                    )}
                    {a.feedback && <p className="mt-2 text-xs text-lake">You said: {a.feedback.replace("_", " ")}</p>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </>
  );
}

export default function AlertsPage() {
  const { t } = useApp();
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-10 md:px-6 md:py-14">
      <PageHeader title={t("alerts.title")} lede={t("alerts.lede")} />
      <RequireAuth reason="Alerts are sent to the phone or email you save, so they need an account.">
        <Suspense fallback={<Skeleton className="h-64" />}><AlertsInner /></Suspense>
      </RequireAuth>
    </div>
  );
}
