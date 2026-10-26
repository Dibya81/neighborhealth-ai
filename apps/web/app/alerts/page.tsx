"use client";

import { Briefcase, Home, MapPin, School, Trash2 } from "lucide-react";
import dynamic from "next/dynamic";
import { useState } from "react";
import { toast } from "sonner";

import type { PickedLocation } from "@/components/map/location-picker";
import { useApp } from "@/components/providers";
import { RequireAuth } from "@/components/require-auth";
import { BandPill, Button, Field, Input, PageHeader, Segmented, Skeleton } from "@/components/ui/primitives";
import { api, track, useApi } from "@/lib/api";
import { cn, timeAgo } from "@/lib/format";
import { LANG_NAMES } from "@/lib/i18n";
import type { Band, Lang, Subscription } from "@/lib/types";

const LocationPicker = dynamic(() => import("@/components/map/location-picker"), { ssr: false, loading: () => <Skeleton className="h-[240px]" /> });

const PLACE_ICON = { home: Home, office: Briefcase, school: School, other: MapPin } as const;
const PLACE_NAME = { home: "Home", office: "Office", school: "School", other: "Other place" } as const;

function NewPlace({ onSaved }: { onSaved: () => void }) {
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
    <form onSubmit={save} className="space-y-6 rounded-lg border border-line bg-surface p-5 md:p-6">
      <fieldset>
        <legend className="text-sm font-medium">Which place?</legend>
        <div className="mt-2 grid grid-cols-4 gap-2">
          {(Object.keys(PLACE_NAME) as Subscription["label"][]).map((k) => {
            const Icon = PLACE_ICON[k];
            return (
              <button type="button" key={k} onClick={() => setLabel(k)} aria-pressed={label === k}
                className={cn("flex flex-col items-center gap-1.5 rounded border py-3 text-xs", label === k ? "border-lake bg-lake-soft/60 text-ink" : "border-line text-muted")}>
                <Icon className="h-5 w-5" />{PLACE_NAME[k]}
              </button>
            );
          })}
        </div>
      </fieldset>

      <LocationPicker value={loc} onChange={setLoc} height={240} />

      <Field label={`Watch an area of ${radius >= 1000 ? `${radius / 1000} km` : `${radius} m`} around it`}>
        <input type="range" min={300} max={3000} step={100} value={radius} onChange={(e) => setRadius(+e.target.value)} className="w-full accent-[#0E7C7B]" />
      </Field>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">How should we reach you?</legend>
        <div className="flex flex-wrap gap-2">
          {[["whatsapp", "WhatsApp"], ["sms", "SMS"], ["email", "Email"]].map(([v, l]) => (
            <label key={v} className={cn("flex cursor-pointer items-center gap-2 rounded border px-3 py-2 text-sm", channels.includes(v) ? "border-lake bg-lake-soft/60" : "border-line")}>
              <input type="checkbox" checked={channels.includes(v)} onChange={() => toggle(v)} className="accent-[#0E7C7B]" />{l}
            </label>
          ))}
        </div>
        {channels.some((c) => c !== "email") && <Input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91 98xxxxxxxx" aria-label="Phone number" />}
        {channels.includes("email") && <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" aria-label="Email" />}
      </fieldset>

      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Message language">
          <Segmented label="Message language" value={msgLang} onChange={setMsgLang} size="sm"
            options={(Object.keys(LANG_NAMES) as Lang[]).map((l) => ({ value: l, label: LANG_NAMES[l] }))} />
        </Field>
        <Field label="Tell me when risk reaches">
          <Segmented label="Alert threshold" value={threshold} onChange={setThreshold} size="sm"
            options={[{ value: "moderate", label: "Moderate" }, { value: "high", label: "High" }, { value: "very_high", label: "Very high" }]} />
        </Field>
      </div>

      <label className="flex items-center gap-3 text-sm">
        <input type="checkbox" checked={quiet} onChange={(e) => setQuiet(e.target.checked)} className="accent-[#0E7C7B]" />
        No messages between 9 pm and 8 am
      </label>
      <label className="flex gap-3 text-sm">
        <input type="checkbox" required checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 accent-[#0E7C7B]" />
        <span>I agree to receive dengue risk messages for this place. At most two a week; reply STOP or remove the place to stop them.</span>
      </label>
      <Button type="submit" size="lg" loading={busy}>Save place</Button>
    </form>
  );
}

interface MyAlert { id: string; ward_name: string | null; band: Band; status: string; created_at: string; feedback: string | null; channel: string }

function AlertsInner() {
  const { lang } = useApp();
  const subs = useApi<{ subscriptions: Subscription[] }>("/v2/subscriptions");
  const alerts = useApi<{ alerts: MyAlert[] }>("/v2/alerts/mine");
  const [adding, setAdding] = useState(false);

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
    <div className="grid gap-10 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
      <div className="space-y-4">
        {!subs.data && <Skeleton className="h-28" />}
        {subs.data && list.length === 0 && !adding && (
          <div className="rounded-lg border border-dashed border-line p-8 text-center">
            <p className="font-medium">No places saved yet</p>
            <p className="mt-1 text-sm text-muted">Start with your home. You can save up to five places.</p>
            <Button className="mt-5" onClick={() => setAdding(true)}>Save a place</Button>
          </div>
        )}
        {list.map((s) => {
          const Icon = PLACE_ICON[s.label];
          return (
            <article key={s.id} className="flex items-start gap-4 rounded-lg border border-line bg-surface p-5">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded bg-lake-soft text-lake"><Icon className="h-5 w-5" /></span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-medium">{PLACE_NAME[s.label]}</h3>
                  {s.last_band && <BandPill band={s.last_band} lang={lang} />}
                </div>
                <p className="mt-1 truncate text-sm text-muted">{s.wards.map((w) => w.ward_name).join(", ")}</p>
                <p className="mt-1 text-xs text-muted">Alerts at {s.threshold_band.replace("_", " ")} or above, by {s.channels.join(" and ")}, in {LANG_NAMES[s.language]}{s.quiet_start ? ", quiet at night" : ""}.</p>
              </div>
              <button onClick={() => remove(s.id)} aria-label={`Remove ${PLACE_NAME[s.label]}`} className="grid h-9 w-9 place-items-center rounded text-muted hover:bg-ink/5 hover:text-[#9E2338]">
                <Trash2 className="h-4 w-4" />
              </button>
            </article>
          );
        })}
        {adding ? <NewPlace onSaved={() => { setAdding(false); subs.mutate(); }} /> : list.length > 0 && list.length < 5 && (
          <Button variant="secondary" onClick={() => setAdding(true)}>Save another place</Button>
        )}
      </div>

      <aside>
        <h2 className="text-sm font-medium">Recent alerts</h2>
        {!alerts.data ? <Skeleton className="mt-3 h-24" /> : alerts.data.alerts.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No alerts yet. That usually means the risk around your places is below your threshold.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {alerts.data.alerts.map((a) => (
              <li key={a.id} className="rounded border border-line bg-surface p-4 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{a.ward_name}</span><BandPill band={a.band} lang={lang} />
                </div>
                <p className="mt-1 text-xs text-muted">{a.channel} · {timeAgo(a.created_at)} · {a.status === "suppressed" ? "held back (alert limit)" : a.status}</p>
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
      </aside>
    </div>
  );
}

export default function AlertsPage() {
  const { t } = useApp();
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 md:px-6 md:py-12">
      <PageHeader title={t("alerts.title")} lede={t("alerts.lede")} />
      <RequireAuth reason="Alerts are sent to the phone or email you save, so they need an account."><AlertsInner /></RequireAuth>
    </div>
  );
}
