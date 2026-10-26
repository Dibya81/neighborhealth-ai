"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { Check, Route as RouteIcon, ShieldAlert, X } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import type { RoutePlan } from "@/components/officials/route-map";
import { TEAM_COLORS } from "@/components/officials/route-map";
import { useApp } from "@/components/providers";
import { RequireAuth } from "@/components/require-auth";
import { BandPill, Button, Notice, PageHeader, Panel, Segmented, Skeleton } from "@/components/ui/primitives";
import { API_URL, api, getToken, useApi } from "@/lib/api";
import { cn, nf, timeAgo } from "@/lib/format";
import { longDate, useFreshness } from "@/lib/freshness";
import type { Band, Hotspot, Task } from "@/lib/types";

const RouteMap = dynamic(() => import("@/components/officials/route-map"), { ssr: false, loading: () => <Skeleton className="h-full w-full" /> });

interface Overview {
  forecast: { horizon: number; week_end: string; median: number; lo80?: number; hi80?: number }[];
  drift: string;
  top_wards: { ward_id: string; ward_name: string; band: Band; rate_per_100k: number; rate_lo80: number; rate_hi80: number; p_high: number; uncertainty: string }[];
  hotspots: Hotspot[];
  review_queue: number;
  tasks: { open: number; completed: number; median_hours_to_complete: number | null; by_status: Record<string, number> };
  alerts: { alerts_sent: number; alerts_per_user_per_week: number; useful_rate: number | null; fatigue_index: number };
}

/** Joined figures: one bordered block, hairline dividers, big numbers. */
function StatStrip({ items, cols = 4 }: { items: { label: string; value: string; note?: string }[]; cols?: 3 | 4 }) {
  return (
    <dl className={cn("grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line", cols === 4 ? "md:grid-cols-4" : "md:grid-cols-3")}>
      {items.map((it) => (
        <div key={it.label} className="bg-surface p-5">
          <dt className="text-sm text-muted">{it.label}</dt>
          <dd className="num mt-2 text-3xl font-semibold leading-none">{it.value}</dd>
          {it.note && <dd className="mt-2 text-xs text-muted">{it.note}</dd>}
        </div>
      ))}
    </dl>
  );
}

function Chip({ tone = "neutral", children }: { tone?: "neutral" | "good" | "warn" | "bad"; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-xs font-medium",
      tone === "neutral" && "bg-sunken text-muted",
      tone === "good" && "bg-lake-soft text-lake",
      tone === "warn" && "bg-warn-bg text-warn-ink",
      tone === "bad" && "bg-[#9E2338]/10 text-[#9E2338] dark:text-[#F5A3B0]")}>{children}</span>
  );
}

function OverviewTab() {
  const { lang } = useApp();
  const fresh = useFreshness();
  const { data, error } = useApi<Overview>("/v2/officials/overview", { refreshInterval: 60_000 });
  if (error) return <Notice tone="warn" title="Overview unavailable">{error.message}</Notice>;
  if (!data) return <Skeleton className="h-80" />;
  const next = data.forecast?.[0];
  return (
    <div className="space-y-10">
      {fresh.stale && fresh.dataThrough && (
        <Notice tone="warn" title="Do not plan field work from this forecast">
          It is built from bulletins up to {longDate(fresh.dataThrough, lang)}. Ward rankings below describe that time, not this week.
        </Notice>
      )}
      <StatStrip items={[
        { label: "Expected cases next week", value: nf(next?.median), note: next ? `80% likely: ${nf(next.lo80)} to ${nf(next.hi80)}` : undefined },
        { label: "Reports to review", value: nf(data.review_queue) },
        { label: "Open field tasks", value: nf(data.tasks.open), note: data.tasks.median_hours_to_complete != null ? `Median ${nf(data.tasks.median_hours_to_complete, 1)} hours to complete` : undefined },
        { label: "Alerts sent (4 weeks)", value: nf(data.alerts.alerts_sent), note: data.alerts.useful_rate != null ? `${Math.round(data.alerts.useful_rate * 100)}% rated useful` : undefined },
      ]} />
      {data.drift === "drift" && <Notice tone="warn" title="Recent data looks different from the training data">Check the forecast page before acting on this week&apos;s numbers.</Notice>}
      <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
        <section>
          <h2 className="text-lg font-semibold tracking-tight">Wards to prioritise</h2>
          <p className="mt-1 text-sm text-muted">Highest estimated rate next week, with the 80% range and the chance of high risk.</p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[420px] text-sm">
              <thead className="text-left text-muted"><tr className="border-b border-line-strong"><th className="py-2 font-medium">Ward</th><th className="py-2 font-medium">Level</th><th className="py-2 text-right font-medium">Per 100k</th><th className="py-2 text-right font-medium">High</th></tr></thead>
              <tbody className="num">
                {data.top_wards.map((w) => (
                  <tr key={w.ward_id} className="border-b border-line">
                    <td className="py-3 font-sans">{w.ward_name}</td>
                    <td className="py-3"><BandPill band={w.band} lang={lang} /></td>
                    <td className="py-3 text-right">{nf(w.rate_per_100k, 1)} <span className="text-xs text-muted">({nf(w.rate_lo80, 1)} to {nf(w.rate_hi80, 1)})</span></td>
                    <td className="py-3 text-right text-muted">{Math.round(w.p_high * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section>
          <h2 className="text-lg font-semibold tracking-tight">Report hotspots</h2>
          <p className="mt-1 text-sm text-muted">Clusters of at least 3 credible reports within 250 m, over the last 4 weeks.</p>
          {data.hotspots.length === 0 ? <p className="mt-4 text-sm text-muted">No clusters yet.</p> : (
            <ul className="mt-4 divide-y divide-line border-y border-line">
              {data.hotspots.map((h) => (
                <li key={h.id} className="flex items-center justify-between gap-4 py-3.5 text-sm">
                  <span>{h.ward_name ?? "Unknown ward"}<span className="mt-0.5 block text-xs text-muted">{h.reports} reports, {h.verified} verified, latest {timeAgo(h.latest)}</span></span>
                  <span className="num text-muted">about {h.radius_m} m</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

interface QueueItem { id: string; lat: number; lon: number; ward_id: string | null; category: string; description: string | null; vision_label: string; vision_score: number | null; created_at: string; flags: string[]; reporter_trust: { score: number; verified: number; total: number }; photo_url: string }

function AuthImage({ path, alt }: { path: string; alt: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    fetch(`${API_URL}${path}`, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((r) => (r.ok ? r.blob() : null)).then((b) => { if (b) { url = URL.createObjectURL(b); setSrc(url); } }).catch(() => {});
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [path]);
  // eslint-disable-next-line @next/next/no-img-element
  return src ? <img src={src} alt={alt} className="h-full w-full object-cover" /> : <Skeleton className="h-full w-full rounded-none" />;
}

const VISION_COPY: Record<string, { text: string; tone: "good" | "warn" | "neutral" }> = {
  likely_breeding_site: { text: "Photo looks like a breeding site", tone: "good" },
  uncertain: { text: "Photo check unsure", tone: "neutral" },
  unlikely: { text: "Photo does not look like a breeding site", tone: "warn" },
  unavailable: { text: "Photo check is off", tone: "neutral" },
};

function QueueTab() {
  const { data, mutate } = useApi<{ reports: QueueItem[] }>("/v2/officials/queue");
  const [busy, setBusy] = useState<string | null>(null);
  const decide = async (id: string, decision: "verified" | "rejected" | "spam") => {
    setBusy(id);
    try {
      await api(`/v2/officials/reports/${id}/review`, { method: "POST", body: JSON.stringify({ decision, create_task: true }) });
      toast.success(decision === "verified" ? "Verified and added to tasks" : decision === "spam" ? "Marked as spam" : "Rejected");
      mutate((d) => d && { reports: d.reports.filter((r) => r.id !== id) }, { revalidate: false });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  if (!data) return <Skeleton className="h-80" />;
  if (data.reports.length === 0) {
    return <Panel className="p-10 text-center"><p className="font-semibold">The review queue is empty</p><p className="mt-1 text-sm text-muted">New citizen reports will appear here, with the photo and how much to trust the reporter.</p></Panel>;
  }
  return (
    <ul className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
      {data.reports.map((r) => {
        const v = VISION_COPY[r.vision_label] ?? { text: r.vision_label, tone: "neutral" as const };
        return (
          <li key={r.id}>
            <Panel className="overflow-hidden">
              <div className="aspect-[4/3] bg-sunken"><AuthImage path={r.photo_url} alt={`Reported ${r.category}`} /></div>
              <div className="space-y-3 p-5 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-base font-semibold capitalize">{r.category}</span>
                  <span className="text-xs text-muted">{timeAgo(r.created_at)}</span>
                </div>
                {r.description && <p className="text-muted">{r.description}</p>}
                <div className="flex flex-wrap gap-1.5">
                  <Chip tone={v.tone}>{v.text}{r.vision_score != null ? ` (${Math.round(r.vision_score * 100)}%)` : ""}</Chip>
                  <Chip>Reporter trust {Math.round(r.reporter_trust.score * 100)}%, {r.reporter_trust.verified} of {r.reporter_trust.total} verified</Chip>
                </div>
                {r.flags.length > 0 && <p className="flex items-center gap-1.5 text-xs text-warn-ink"><ShieldAlert className="h-3.5 w-3.5" />{r.flags.join(", ").replaceAll("_", " ")}</p>}
                <div className="flex flex-wrap gap-2 pt-1">
                  <Button size="sm" onClick={() => decide(r.id, "verified")} loading={busy === r.id}><Check className="h-4 w-4" />Verify</Button>
                  <Button size="sm" variant="secondary" onClick={() => decide(r.id, "rejected")} disabled={busy === r.id}><X className="h-4 w-4" />Reject</Button>
                  <Button size="sm" variant="ghost" onClick={() => decide(r.id, "spam")} disabled={busy === r.id}>Spam</Button>
                </div>
              </div>
            </Panel>
          </li>
        );
      })}
    </ul>
  );
}

const NEXT_STATUS: Record<Task["status"], Task["status"][]> = {
  open: ["in_progress", "closed"], assigned: ["in_progress", "closed"], in_progress: ["inspected", "cleared"],
  inspected: ["cleared", "closed"], cleared: ["closed"], closed: [],
};
const STATUS_LABEL: Record<Task["status"], string> = { open: "Open", assigned: "Assigned", in_progress: "In progress", inspected: "Inspected", cleared: "Cleared", closed: "Closed" };
const STATUS_TONE: Record<Task["status"], "neutral" | "good" | "warn"> = { open: "warn", assigned: "neutral", in_progress: "neutral", inspected: "good", cleared: "good", closed: "neutral" };

function TasksTab() {
  const [filter, setFilter] = useState<"active" | "done">("active");
  const { data, mutate } = useApi<{ tasks: Task[]; stats: Overview["tasks"] }>("/v2/officials/tasks");
  const tasks = useMemo(() => (data?.tasks ?? []).filter((t) => (filter === "active" ? !["inspected", "cleared", "closed"].includes(t.status) : ["inspected", "cleared", "closed"].includes(t.status))), [data, filter]);
  const move = async (t: Task, status: Task["status"]) => {
    try {
      await api(`/v2/officials/tasks/${t.id}/transition`, { method: "POST", body: JSON.stringify({ status }) });
      toast.success(`Marked ${STATUS_LABEL[status].toLowerCase()}`);
      mutate();
    } catch (e) { toast.error((e as Error).message); }
  };
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented label="Task filter" value={filter} onChange={setFilter} options={[{ value: "active", label: "To do" }, { value: "done", label: "Done" }]} />
        {data && <p className="text-sm text-muted">{data.stats.open} open, {data.stats.completed} done</p>}
      </div>
      {!data ? <Skeleton className="h-64" /> : tasks.length === 0 ? (
        <Panel className="p-10 text-center"><p className="font-semibold">Nothing here</p><p className="mt-1 text-sm text-muted">Verified reports become field tasks automatically.</p></Panel>
      ) : (
        <Panel className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="text-left text-muted"><tr className="border-b border-line-strong">
              <th className="px-5 py-3 font-medium">Task</th><th className="py-3 font-medium">Ward</th><th className="py-3 font-medium">Priority</th>
              <th className="py-3 font-medium">Team</th><th className="py-3 font-medium">Status</th><th className="px-5 py-3 font-medium">Update</th></tr></thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id} className="border-b border-line last:border-0">
                  <td className="px-5 py-3.5 font-medium capitalize">{t.kind.replace("_", " ")}<span className="mt-0.5 block text-xs font-normal normal-case text-muted">{timeAgo(t.created_at)}</span></td>
                  <td className="py-3.5">{t.ward_id ?? "n/a"}</td>
                  <td className="py-3.5">{["", "High", "Normal", "Low"][t.priority]}</td>
                  <td className="py-3.5">{t.team ?? "n/a"}</td>
                  <td className="py-3.5"><Chip tone={STATUS_TONE[t.status]}>{STATUS_LABEL[t.status]}</Chip></td>
                  <td className="px-5 py-3.5"><div className="flex gap-1.5">{NEXT_STATUS[t.status].map((s) => (
                    <Button key={s} size="sm" variant={s === "closed" ? "ghost" : "secondary"} onClick={() => move(t, s)}>{STATUS_LABEL[s]}</Button>
                  ))}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}

function RoutesTab() {
  const { data } = useApi<{ tasks: Task[] }>("/v2/officials/tasks?status=open");
  const [teams, setTeams] = useState(2);
  const [shift, setShift] = useState(360);
  const [plan, setPlan] = useState<RoutePlan | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      const p = await api<RoutePlan>("/v2/officials/routes/optimize", { method: "POST", body: JSON.stringify({ teams, shift_minutes: shift, assign: true }) });
      setPlan(p);
      toast.success("Routes planned and tasks assigned");
    } catch (e) { toast.error((e as Error).message); } finally { setBusy(false); }
  };
  const saving = plan && plan.naive_single_route_minutes > 0 ? 1 - plan.total_minutes / plan.naive_single_route_minutes : null;
  return (
    <div className="grid gap-8 lg:grid-cols-[340px_minmax(0,1fr)]">
      <div className="space-y-6">
        <p className="text-sm text-muted">{data ? `${data.tasks.length} open tasks.` : "Loading tasks."} Plan the shortest rounds for your field teams. If a shift cannot fit everything, low-priority stops are left out first.</p>
        <div>
          <p className="mb-2 text-sm font-medium">Field teams</p>
          <Segmented label="Teams" value={teams} onChange={setTeams} options={[1, 2, 3, 4].map((n) => ({ value: n, label: String(n) }))} />
        </div>
        <div>
          <p className="mb-2 text-sm font-medium">Shift length</p>
          <Segmented label="Shift" value={shift} onChange={setShift} options={[{ value: 240, label: "4 hours" }, { value: 360, label: "6 hours" }, { value: 480, label: "8 hours" }]} />
        </div>
        <Button onClick={run} loading={busy} disabled={!data?.tasks.length} size="lg"><RouteIcon className="h-4 w-4" />Plan routes</Button>
        {plan && (
          <div className="space-y-3 border-t border-line pt-5 text-sm">
            <p className="text-muted">{plan.method}</p>
            {saving != null && <p><b className="num text-base">{Math.round(saving * 100)}%</b> less time than visiting stops in the order they came in.</p>}
            {plan.routes.map((r) => (
              <div key={r.team} className="flex items-center justify-between">
                <span className="flex items-center gap-2.5"><i className="h-3 w-3 rounded-full" style={{ background: TEAM_COLORS[(r.team - 1) % TEAM_COLORS.length] }} />Team {r.team}: {r.stops.length} stops</span>
                <span className="num text-muted">{Math.round(r.total_minutes)} min</span>
              </div>
            ))}
            {plan.dropped.length > 0 && <p className="text-warn-ink">{plan.dropped.length} stops did not fit in the shift and stay open.</p>}
          </div>
        )}
      </div>
      <div className="h-[540px] overflow-hidden rounded-lg border border-line-strong">
        <RouteMap plan={plan} tasks={data?.tasks ?? []} />
      </div>
    </div>
  );
}

function PilotTab() {
  const [cohort, setCohort] = useState("");
  const { data } = useApi<Record<string, unknown> & { cohorts: { cohort: string; users: number }[] }>(`/v2/pilot/metrics${cohort ? `?cohort=${encodeURIComponent(cohort)}` : ""}`);
  const { data: q } = useApi<Record<string, number | null>>("/v2/assistant/quality", { shouldRetryOnError: false });
  if (!data) return <Skeleton className="h-64" />;
  const rows = [
    { label: "Registered residents", value: nf(data.registered_citizens as number) },
    { label: "Residents with alerts on", value: nf(data.subscribed_users as number) },
    { label: "Weekly active users", value: nf(data.weekly_active_users as number) },
    { label: "Reports (4 weeks)", value: nf(data.reports as number) },
    { label: "Verified reports (4 weeks)", value: nf(data.verified_reports as number) },
    { label: "Field tasks completed", value: nf(data.tasks_completed as number) },
  ];
  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-muted">Group</span>
        <Segmented label="Pilot group" value={cohort} onChange={setCohort}
          options={[{ value: "", label: "All" }, ...data.cohorts.map((c) => ({ value: c.cohort, label: `${c.cohort} (${c.users})` }))]} />
      </div>
      <StatStrip cols={3} items={rows} />
      {q && (
        <div>
          <h2 className="mb-4 text-lg font-semibold tracking-tight">Assistant quality</h2>
          <StatStrip cols={3} items={[
            { label: "Assistant questions", value: nf(q.questions), note: q.grounded_rate != null ? `${Math.round(q.grounded_rate * 100)}% answered from sources` : undefined },
            { label: "Ward explanations", value: nf(q.explanations), note: q.explanations_verified_rate != null ? `${Math.round(q.explanations_verified_rate * 100)}% passed the fact check` : undefined },
            { label: "Diagnosis requests declined", value: nf(q.diagnosis_refusals) },
          ]} />
        </div>
      )}
    </div>
  );
}

export default function OfficialsPage() {
  return (
    <div className="mx-auto max-w-[1240px] px-4 py-10 md:px-6 md:py-14">
      <PageHeader title="Health team" lede="Where to act this week: forecast hotspots, citizen reports to check, field tasks and routes." />
      <RequireAuth roles={["official", "admin"]} reason="This dashboard is for BBMP health officials.">
        <Tabs.Root defaultValue="overview">
          <Tabs.List aria-label="Sections" className="mb-10 flex gap-1 overflow-x-auto border-b border-line">
            {[["overview", "Overview"], ["queue", "Review reports"], ["tasks", "Field tasks"], ["routes", "Route planner"], ["pilot", "Pilot"]].map(([v, l]) => (
              <Tabs.Trigger key={v} value={v}
                className="-mb-px whitespace-nowrap border-b-2 border-transparent px-4 py-3 text-sm text-muted transition-colors hover:text-ink data-[state=active]:border-lake data-[state=active]:font-semibold data-[state=active]:text-ink">
                {l}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          <Tabs.Content value="overview"><OverviewTab /></Tabs.Content>
          <Tabs.Content value="queue"><QueueTab /></Tabs.Content>
          <Tabs.Content value="tasks"><TasksTab /></Tabs.Content>
          <Tabs.Content value="routes"><RoutesTab /></Tabs.Content>
          <Tabs.Content value="pilot"><PilotTab /></Tabs.Content>
        </Tabs.Root>
      </RequireAuth>
    </div>
  );
}
