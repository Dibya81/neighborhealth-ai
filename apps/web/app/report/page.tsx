"use client";

import { Camera, CheckCircle2, ImagePlus } from "lucide-react";
import dynamic from "next/dynamic";
import { useRef, useState } from "react";
import { toast } from "sonner";

import type { PickedLocation } from "@/components/map/location-picker";
import { useApp } from "@/components/providers";
import { RequireAuth } from "@/components/require-auth";
import { Button, Field, PageHeader, Panel, Skeleton, Textarea } from "@/components/ui/primitives";
import { api, track, useApi } from "@/lib/api";
import { cn, timeAgo } from "@/lib/format";

const LocationPicker = dynamic(() => import("@/components/map/location-picker"), { ssr: false, loading: () => <Skeleton className="h-[260px]" /> });

const CATEGORIES = [
  { value: "container", label: "Bucket, drum or container" },
  { value: "tyre", label: "Old tyres" },
  { value: "drain", label: "Blocked drain" },
  { value: "construction", label: "Construction site" },
  { value: "garbage", label: "Garbage holding water" },
  { value: "other", label: "Something else" },
];

const STATUS_COPY: Record<string, { text: string; tone: "good" | "wait" | "no" }> = {
  pending: { text: "Waiting for review", tone: "wait" },
  verified: { text: "Confirmed by the health team", tone: "good" },
  rejected: { text: "Not a breeding spot", tone: "no" },
  duplicate: { text: "Already reported by someone", tone: "no" },
  spam: { text: "Not accepted", tone: "no" },
};

interface MyReport { id: string; ward_id: string | null; category: string; status: string; created_at: string }

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="grid grid-cols-[2rem_1fr] gap-x-4">
      <span className="num grid h-8 w-8 place-items-center rounded-full bg-lake-soft text-sm font-semibold text-lake" aria-hidden>{n}</span>
      <div className="min-w-0">
        <h2 className="pt-1 text-base font-semibold">{title}</h2>
        <div className="mt-3">{children}</div>
      </div>
    </section>
  );
}

function ReportForm() {
  const { t } = useApp();
  const fileRef = useRef<HTMLInputElement>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loc, setLoc] = useState<PickedLocation | null>(null);
  const [category, setCategory] = useState("container");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ message: string } | null>(null);
  const mine = useApi<{ reports: MyReport[]; trust: { score: number; verified: number } }>("/v2/reports/mine");

  const pick = (f: File | undefined) => {
    if (!f) return;
    if (!f.type.startsWith("image/")) return toast.error("Please choose a photo.");
    setPhoto(f);
    setPreview(URL.createObjectURL(f));
    track("report_started");
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!photo) return toast.error("Add a photo of the spot.");
    if (!loc) return toast.error("Choose where the spot is.");
    setBusy(true);
    const fd = new FormData();
    fd.append("lat", String(loc.lat));
    fd.append("lon", String(loc.lon));
    fd.append("category", category);
    if (notes) fd.append("description", notes);
    fd.append("photo", photo);
    try {
      const r = await api<{ message: string; status: string }>("/v2/reports", { method: "POST", body: fd });
      setDone({ message: r.message });
      track("report_submitted", { ward_id: loc.ward_id ?? "" });
      mine.mutate();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <Panel className="max-w-xl p-8 md:p-10">
        <CheckCircle2 className="h-10 w-10 text-lake" />
        <h2 className="mt-5 text-2xl font-semibold tracking-tight">{t("report.sent")}</h2>
        <p className="mt-2 text-muted">{done.message}</p>
        <p className="mt-4 text-sm text-muted">You can follow the review status of every report you send on this page.</p>
        <Button className="mt-7" variant="secondary" onClick={() => { setDone(null); setPhoto(null); setPreview(null); setNotes(""); }}>Report another spot</Button>
      </Panel>
    );
  }

  return (
    <div className="grid gap-12 lg:grid-cols-[minmax(0,7fr)_minmax(0,4fr)] lg:gap-16">
      <form onSubmit={submit} className="space-y-10">
        <Step n={1} title={t("report.photo")}>
          <input ref={fileRef} type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} aria-label={t("report.photo")} />
          <button type="button" onClick={() => fileRef.current?.click()}
            className={cn("relative grid w-full place-items-center overflow-hidden rounded-lg border-2 border-dashed border-line-strong bg-sunken/60 text-muted transition-colors hover:border-lake hover:text-ink",
              preview ? "h-72" : "h-44")}>
            {preview ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={preview} alt="Selected photo" className="absolute inset-0 h-full w-full object-cover" />
            ) : (
              <span className="flex flex-col items-center gap-2 px-4 text-center text-sm">
                <Camera className="h-7 w-7" />
                <span className="font-medium text-ink">{t("report.takePhoto")}</span>
                <span>One clear photo of the water or container</span>
              </span>
            )}
            {preview && <span className="absolute bottom-3 right-3 flex items-center gap-1.5 rounded bg-ink/85 px-2.5 py-1.5 text-xs font-medium text-paper"><ImagePlus className="h-3.5 w-3.5" />Change photo</span>}
          </button>
        </Step>

        <Step n={2} title={t("report.location")}>
          <LocationPicker value={loc} onChange={setLoc} autoLocate />
        </Step>

        <Step n={3} title={t("report.category")}>
          <fieldset>
            <legend className="sr-only">{t("report.category")}</legend>
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              {CATEGORIES.map((c) => (
                <label key={c.value} className={cn("flex min-h-[48px] cursor-pointer items-center gap-3 rounded-lg border px-4 text-sm transition-colors",
                  category === c.value ? "border-lake bg-lake-soft/70 font-medium" : "border-line-strong bg-surface hover:border-ink/40")}>
                  <input type="radio" name="category" value={c.value} checked={category === c.value} onChange={() => setCategory(c.value)} className="h-4 w-4 accent-[rgb(var(--lake))]" />
                  {c.label}
                </label>
              ))}
            </div>
          </fieldset>
        </Step>

        <Step n={4} title={t("report.notes")}>
          <Field label="Anything that helps the team find it" htmlFor="notes" hint="For example: behind the bus stop, near the school gate.">
            <Textarea id="notes" maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Field>
        </Step>

        <div className="pl-12">
          <Button type="submit" size="lg" loading={busy} className="w-full sm:w-auto">{t("report.submit")}</Button>
          <p className="mt-4 max-w-prose text-xs text-muted">The hidden location data inside your photo is removed before it is saved. On the public map, report locations are shown only to about 100 metres.</p>
        </div>
      </form>

      <aside className="space-y-10">
        <div>
          <h2 className="text-base font-semibold">A good report</h2>
          <ul className="mt-3 space-y-2.5 text-sm text-muted">
            <li>Show the water or the container clearly, in daylight if you can.</li>
            <li>Keep people, faces and vehicle number plates out of the photo.</li>
            <li>Only report places you can see from where you are allowed to be.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-base font-semibold">{t("report.mine")}</h2>
          {mine.data && mine.data.trust.verified > 0 && (
            <p className="mt-1 text-sm text-muted">{mine.data.trust.verified} of your reports {mine.data.trust.verified === 1 ? "was" : "were"} confirmed. Thank you.</p>
          )}
          {!mine.data ? <Skeleton className="mt-3 h-32" /> : mine.data.reports.length === 0 ? (
            <p className="mt-3 text-sm text-muted">Reports you send will appear here with their review status.</p>
          ) : (
            <ul className="mt-3 divide-y divide-line border-y border-line">
              {mine.data.reports.slice(0, 12).map((r) => {
                const s = STATUS_COPY[r.status] ?? { text: r.status, tone: "wait" as const };
                return (
                  <li key={r.id} className="flex items-start justify-between gap-4 py-3.5 text-sm">
                    <span>{CATEGORIES.find((c) => c.value === r.category)?.label ?? r.category}<span className="mt-0.5 block text-xs text-muted">{timeAgo(r.created_at)}</span></span>
                    <span className={cn("shrink-0 text-xs font-medium", s.tone === "good" ? "text-lake" : "text-muted")}>{s.text}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}

export default function ReportPage() {
  const { t } = useApp();
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-10 md:px-6 md:py-14">
      <PageHeader title={t("report.title")} lede={t("report.lede")} />
      <RequireAuth reason="Reports are linked to an account so the health team can trust them and you can follow their status."><ReportForm /></RequireAuth>
    </div>
  );
}
