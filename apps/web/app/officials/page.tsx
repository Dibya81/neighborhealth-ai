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
import { BandPill, Button, Notice, PageHeader, Segmented, Skeleton } from "@/components/ui/primitives";
import { API_URL, api, getToken, useApi } from "@/lib/api";
import { cn, nf, timeAgo } from "@/lib/format";
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

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="border-l border-line pl-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="tnum mt-1 font-display text-3xl font-semibold">{value}</p>
      {note && <p className="text-xs text-muted">{note}</p>}
    </div>
  );
}

function OverviewTab() {
  const { lang } = useApp();
  const { data, error } = useApi<Overview>("/v2/officials/overview", { refreshInterval: 60_000 });
  if (error) return <Notice tone="warn" title="Overview unavailable">{error.message}</Notice>;
  if (!data) return <Skeleton className="h-80" />;
  const next = data.forecast?.[0];
  return (
    <div className="space-y-10">
      <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
        <Stat label="Expected cases next week" value={nf(next?.median)} note={next ? `80%: ${nf(next.lo80)}–${nf(next.hi80)}` : undefined} />
        <Stat label="Reports to review" value={nf(data.review_queue)} />
        <Stat label="Open field tasks" value={nf(data.tasks.open)} note={data.tasks.median_hours_to_complete != null ? `median ${nf(data.tasks.median_hours_to_complete, 1)} h to complete` : undefined} />
        <Stat label="Alerts sent (4 wk)" value={nf(data.alerts.alerts_sent)} note={data.alerts.useful_rate != null ? `${Math.round(data.alerts.useful_rate * 100)}% rated useful` : undefined} />
      </div>
      {data.drift === "drift" && <Notice tone="warn" title="Recent data looks different from the training data">Check the forecast page before acting on this week&apos;s numbers.</Notice>}
      <div className="grid gap-10 lg:grid-cols-2">
        <section>
          <h2 className="font-medium">Wards to prioritise</h2>
          <p className="text-xs text-muted">Highest estimated rate next week, with 80% range and chance of high risk.</p>
          <table className="mt-3 w-full text-sm">
            <tbody className="tnum">
              {data.top_wards.map((w) => (
                <tr key={w.ward_id} className="border-b border-line/70">
                  <td className="py-2.5">{w.ward_name}</td>
                  <td className="py-2.5"><BandPill band={w.band} lang={lang} /></td>
                  <td className="py-2.5 text-right">{nf(w.rate_per_100k, 1)} <span className="text-xs text-muted">({nf(w.rate_lo80, 1)}–{nf(w.rate_hi80, 1)})</span></td>
                  <td className="py-2.5 text-right text-muted">{Math.round(w.p_high * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section>
          <h2 className="font-medium">Report hotspots (last 4 weeks)</h2>
          <p className="text-xs text-muted">Clusters of at least 3 credible reports within 250 m.</p>
          {data.hotspots.length === 0 ? <p className="mt-3 text-sm text-muted">No clusters yet.</p> : (
            <ul className="mt-3 divide-y divide-line">
              {data.hotspots.map((h) => (
                <li key={h.id} className="flex items-center justify-between py-2.5 text-sm">
                  <span>{h.ward_name ?? "Unknown ward"}<span className="block text-xs text-muted">{h.reports} reports, {h.verified} verified · latest {timeAgo(h.latest)}</span></span>
                  <span className="tnum text-muted">~{h.radius_m} m</span>
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

const VISION_COPY: Record<string, string> = {
  likely_breeding_site: "Photo looks like a breeding site",
  uncertain: "Photo check unsure",
  unlikely: "Photo doesn't look like a breeding site",
  unavailable: "Photo check off",
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
  if (data.reports.length === 0) return <p className="text-sm text-muted">The review queue is empty.</p>;
  return (
    <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {data.reports.map((r) => (
        <li key={r.id} className="overflow-hidden rounded-lg border border-line bg-surface">
          <div className="aspect-[4/3] bg-ink/5"><AuthImage path={r.photo_url} alt={`Reported ${r.category}`} /></div>
          <div className="space-y-2 p-4 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium capitalize">{r.category}</span>
              <span className="text-xs text-muted">{timeAgo(r.created_at)}</span>
            </div>
            {r.description && <p className="text-muted">{r.description}</p>}
            <p className={cn("text-xs", r.vision_label === "likely_breeding_site" ? "text-lake" : r.vision_label === "unlikely" ? "text-[#9E2338]" : "text-muted")}>
              {VISION_COPY[r.vision_label] ?? r.vision_label}{r.vision_score != null ? ` (${Math.round(r.vision_score * 100)}%)` : ""}
            </p>
            <p className="text-xs text-muted">Reporter trust {Math.round(r.reporter_trust.score * 100)}% · {r.reporter_trust.verified}/{r.reporter_trust.total} verified</p>
            {r.flags.length > 0 && <p className="flex items-center gap-1 text-xs text-[#B7791F]"><ShieldAlert className="h-3.5 w-3.5" />{r.flags.join(", ").replaceAll("_", " ")}</p>}
            <div className="flex gap-2 pt-2">
              <Button size="sm" onClick={() => decide(r.id, "verified")} loading={busy === r.id}><Check className="h-4 w-4" />Verify</Button>
              <Button size="sm" variant="secondary" onClick={() => decide(r.id, "rejected")} disabled={busy === r.id}><X className="h-4 w-4" />Reject</Button>
              <Button size="sm" variant="ghost" onClick={() => decide(r.id, "spam")} disabled={busy === r.id}>Spam</Button>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

const NEXT_STATUS: Record<Task["status"], Task["status"][]> = {
  open: ["in_progress", "closed"], assigned: ["in_progress", "closed"], in_progress: ["inspected", "cleared"],
  inspected: ["cleared", "closed"], cleared: ["closed"], closed: [],
};
const STATUS_LABEL: Record<Task["status"], string> = { open: "Open", assigned: "Assigned", in_progress: "In progress", inspected: "Inspected", cleared: "Cleared", closed: "Closed" };

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
        {data && <p className="text-sm text-muted">{data.stats.open} open · {data.stats.completed} done</p>}
      </div>
      {!data ? <Skeleton className="h-64" /> : tasks.length === 0 ? <p className="text-sm text-muted">Nothing here. Verified reports become tasks automatically.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="text-left text-muted"><tr className="border-b border-line">
              <th className="py-2 font-normal">Task</th><th className="py-2 font-normal">Ward</th><th className="py-2 font-normal">Priority</th>
              <th className="py-2 font-normal">Team</th><th className="py-2 font-normal">Status</th><th className="py-2 font-normal">Update</th></tr></thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id} className="border-b border-line/70">
                  <td className="py-2.5 capitalize">{t.kind.replace("_", " ")}<span className="block text-xs text-muted">{timeAgo(t.created_at)}</span></td>
                  <td className="py-2.5">{t.ward_id ?? "–"}</td>
                  <td className="py-2.5">{["", "High", "Normal", "Low"][t.priority]}</td>
                  <td className="py-2.5">{t.team ?? "–"}</td>
                  <td className="py-2.5">{STATUS_LABEL[t.status]}</td>
                  <td className="py-2.5"><div className="flex gap-1.5">{NEXT_STATUS[t.status].map((s) => (
                    <Button key={s} size="sm" variant={s === "closed" ? "ghost" : "secondary"} onClick={() => move(t, s)}>{STATUS_LABEL[s]}</Button>
                  ))}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
    <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
      <div className="space-y-5">
        <p className="text-sm text-muted">{data ? `${data.tasks.length} open tasks.` : "Loading tasks…"} Plan the shortest rounds for your field teams. Low-priority stops are left out first if a shift can&apos;t fit everything.</p>
        <div>
          <p className="mb-1.5 text-sm font-medium">Field teams</p>
          <Segmented label="Teams" value={teams} onChange={setTeams} options={[1, 2, 3, 4].map((n) => ({ value: n, label: String(n) }))} />
        </div>
        <div>
          <p className="mb-1.5 text-sm font-medium">Shift length</p>
          <Segmented label="Shift" value={shift} onChange={setShift} options={[{ value: 240, label: "4 h" }, { value: 360, label: "6 h" }, { value: 480, label: "8 h" }]} />
        </div>
        <Button onClick={run} loading={busy} disabled={!data?.tasks.length} size="lg"><RouteIcon className="h-4 w-4" />Plan routes</Button>
        {plan && (
          <div className="space-y-3 border-t border-line pt-4 text-sm">
            <p className="text-muted">{plan.method}</p>
            {saving != null && <p><b className="tnum">{Math.round(saving * 100)}%</b> less time than visiting stops in the order they came in.</p>}
            {plan.routes.map((r) => (
              <div key={r.team} className="flex items-center justify-between">
                <span className="flex items-center gap-2"><i className="h-3 w-3 rounded-full" style={{ background: TEAM_COLORS[(r.team - 1) % TEAM_COLORS.length] }} />Team {r.team}: {r.stops.length} stops</span>
                <span className="tnum text-muted">{Math.round(r.total_minutes)} min</span>
              </div>
            ))}
            {plan.dropped.length > 0 && <p className="text-[#B7791F]">{plan.dropped.length} stops didn&apos;t fit in the shift and stay open.</p>}
          </div>
        )}
      </div>
      <div className="h-[520px] overflow-hidden rounded-lg border border-line">
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
  const rows: [string, unknown][] = [
    ["Registered residents", data.registered_citizens], ["Residents with alerts on", data.subscribed_users],
    ["Weekly active users", data.weekly_active_users], ["Reports (4 weeks)", data.reports],
    ["Verified reports (4 weeks)", data.verified_reports], ["Field tasks completed", data.tasks_completed],
  ];
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted">Group:</span>
        <Segmented label="Pilot group" value={cohort} onChange={setCohort}
          options={[{ value: "", label: "All" }, ...data.cohorts.map((c) => ({ value: c.cohort, label: `${c.cohort} (${c.users})` }))]} />
      </div>
      <div className="grid grid-cols-2 gap-6 md:grid-cols-3">
        {rows.map(([k, v]) => <Stat key={k} label={k} value={nf(v as number)} />)}
      </div>
      {q && (
        <div className="grid grid-cols-2 gap-6 md:grid-cols-3">
          <Stat label="Assistant questions" value={nf(q.questions)} note={q.grounded_rate != null ? `${Math.round(q.grounded_rate * 100)}% answered from sources` : undefined} />
          <Stat label="Ward explanations" value={nf(q.explanations)} note={q.explanations_verified_rate != null ? `${Math.round(q.explanations_verified_rate * 100)}% passed fact check` : undefined} />
          <Stat label="Diagnosis requests declined" value={nf(q.diagnosis_refusals)} />
        </div>
      )}
    </div>
  );
}

export default function OfficialsPage() {
  return (
    <div className="mx-auto max-w-[1240px] px-4 py-8 md:px-6 md:py-12">
      <PageHeader title="Health team" lede="Where to act this week: forecast hotspots, citizen reports to check, field tasks and routes." />
      <RequireAuth roles={["official", "admin"]} reason="This dashboard is for BBMP health officials.">
        <Tabs.Root defaultValue="overview">
          <Tabs.List aria-label="Sections" className="mb-8 flex gap-1 overflow-x-auto border-b border-line">
            {[["overview", "Overview"], ["queue", "Review reports"], ["tasks", "Field tasks"], ["routes", "Route planner"], ["pilot", "Pilot"]].map(([v, l]) => (
              <Tabs.Trigger key={v} value={v}
                className="-mb-px whitespace-nowrap border-b-2 border-transparent px-3 py-2.5 text-sm text-muted data-[state=active]:border-ink data-[state=active]:font-medium data-[state=active]:text-ink">
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
