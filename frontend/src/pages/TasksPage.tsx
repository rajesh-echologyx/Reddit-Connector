import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";

import { tasksApi, type TaskRun } from "@/api/client";

export function TasksPage() {
  const [status, setStatus] = useState<string>("");
  const automation = useQuery({
    queryKey: ["automation-status"],
    queryFn: () => tasksApi.automationStatus(),
    refetchInterval: 30_000,
  });
  const tasks = useQuery({
    queryKey: ["tasks", status],
    queryFn: () =>
      tasksApi.list(status ? { status } : undefined),
    refetchInterval: 15_000,
  });

  const items = tasks.data?.results ?? [];
  const summary = automation.data;

  return (
    <section className="space-y-8">
      <header className="space-y-2">
        <h1
          className="text-3xl text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Tasks
        </h1>
        <p className="max-w-2xl text-black/70">
          Celery automation runs for keyword monitors. Discover → analyze → draft
          into review — never auto-publish.
        </p>
      </header>

      {summary && (
        <div className="grid gap-4 border-t border-[var(--color-line)] pt-5 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Active monitors" value={String(summary.monitors_active)} />
          <Metric label="Paused" value={String(summary.monitors_paused)} />
          <Metric label="Failed runs" value={String(summary.task_runs_failed)} />
          <Metric label="Due reviews" value={String(summary.due_reviews)} />
        </div>
      )}

      {summary && summary.failing_monitors.length > 0 && (
        <div className="space-y-2 border-t border-[var(--color-line)] pt-5">
          <h2
            className="text-lg text-[var(--color-moss-deep)]"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Monitor failures
          </h2>
          <ul className="space-y-2 text-sm">
            {summary.failing_monitors.map((m) => (
              <li key={m.id} className="text-black/70">
                <Link className="underline underline-offset-2" to="/monitors">
                  {m.name}
                </Link>
                : {m.last_error}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 border-t border-[var(--color-line)] pt-5">
        <label className="text-sm text-black/55">
          Status{" "}
          <select
            className="ml-2 rounded-md border border-[var(--color-line)] bg-white/70 px-2 py-1"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
            <option value="retry">Retry</option>
            <option value="skipped">Skipped</option>
            <option value="started">Started</option>
          </select>
        </label>
        <p className="text-xs text-black/45">
          Beat: {(summary?.beat_schedule ?? []).join(", ") || "…"} · never auto-publish
          {summary?.never_auto_publish ? " ✓" : ""}
        </p>
      </div>

      <div className="space-y-4">
        {tasks.isLoading && <p className="text-sm text-black/50">Loading…</p>}
        {items.map((run) => (
          <TaskRow key={run.id} run={run} />
        ))}
        {!tasks.isLoading && items.length === 0 && (
          <p className="text-sm text-black/50">No task runs recorded yet.</p>
        )}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-black/45">{label}</p>
      <p
        className="mt-1 text-2xl text-[var(--color-moss-deep)]"
        style={{ fontFamily: "var(--font-display)" }}
      >
        {value}
      </p>
    </div>
  );
}

function TaskRow({ run }: { run: TaskRun }) {
  return (
    <article className="space-y-1 border-t border-[var(--color-line)] pt-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3
          className="text-base text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          {run.task_name}
        </h3>
        <span className="text-xs uppercase tracking-wide text-black/45">{run.status}</span>
      </div>
      <p className="text-xs text-black/45">
        {run.monitor_name ? `${run.monitor_name} · ` : ""}
        {run.started_at ? new Date(run.started_at).toLocaleString() : "—"}
        {run.retries > 0 ? ` · retries ${run.retries}` : ""}
      </p>
      {run.message && <p className="text-sm text-black/65">{run.message}</p>}
    </article>
  );
}
