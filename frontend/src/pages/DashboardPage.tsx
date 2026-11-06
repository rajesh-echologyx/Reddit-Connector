import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  analyticsApi,
  monitorsApi,
  opsApi,
  redditApi,
  reviewApi,
  tasksApi,
} from "@/api/client";
import { useAuth } from "@/hooks/useAuth";

export function DashboardPage() {
  const { user } = useAuth();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => opsApi.health(),
  });
  const reddit = useQuery({
    queryKey: ["reddit-status"],
    queryFn: () => redditApi.status(),
  });
  const posts = useQuery({
    queryKey: ["posts", {}],
    queryFn: () => redditApi.posts(),
  });
  const monitors = useQuery({
    queryKey: ["monitors"],
    queryFn: () => monitorsApi.list(),
  });
  const review = useQuery({
    queryKey: ["review-queue"],
    queryFn: () => reviewApi.queue(),
  });
  const automation = useQuery({
    queryKey: ["automation-status"],
    queryFn: () => tasksApi.automationStatus(),
    refetchInterval: 60_000,
  });
  const analytics = useQuery({
    queryKey: ["analytics-summary", 7],
    queryFn: () => analyticsApi.summary(7),
  });

  const connectionLabel =
    reddit.data?.reddit_username ||
    reddit.data?.status ||
    health.data?.reddit_mode ||
    "…";

  const failing = automation.data?.failing_monitors ?? [];
  const tokenExpired = automation.data?.reddit_status === "expired";

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1
          className="text-3xl text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Dashboard
        </h1>
        <p className="max-w-2xl text-black/70">
          Welcome{user ? `, ${user.username}` : ""}. Beat keeps monitors polling;
          drafts land in review for a human — never auto-submit.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Due reviews"
          value={String(review.data?.count ?? "…")}
          hint={<Link to="/review">Open queue</Link>}
        />
        <Stat
          label="Monitors"
          value={String(monitors.data?.count ?? "…")}
          hint={<Link to="/monitors">Manage keywords</Link>}
        />
        <Stat
          label="Discovered posts"
          value={String(posts.data?.count ?? "…")}
          hint={<Link to="/posts">Browse posts</Link>}
        />
        <Stat
          label="Reddit connection"
          value={connectionLabel}
          hint={
            <Link to="/settings">
              {reddit.data?.mode === "fixture" ? "Fixture mode" : "Settings"}
            </Link>
          }
        />
      </div>

      {(tokenExpired || failing.length > 0 || (automation.data?.task_runs_failed ?? 0) > 0) && (
        <div className="space-y-2 border-t border-[var(--color-line)] pt-5">
          <h2
            className="text-lg text-[var(--color-moss-deep)]"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Automation alerts
          </h2>
          {tokenExpired && (
            <p className="text-sm text-black/70">
              Reddit token expired — scheduled polls are paused.{" "}
              <Link className="underline underline-offset-2" to="/settings">
                Reconnect in Settings
              </Link>
              .
            </p>
          )}
          {failing.slice(0, 3).map((m) => (
            <p key={m.id} className="text-sm text-black/70">
              {m.name}: {m.last_error}
            </p>
          ))}
          {(automation.data?.task_runs_failed ?? 0) > 0 && (
            <p className="text-sm text-black/55">
              <Link className="underline underline-offset-2" to="/tasks">
                View {automation.data?.task_runs_failed} failed task run
                {(automation.data?.task_runs_failed ?? 0) === 1 ? "" : "s"}
              </Link>
            </p>
          )}
        </div>
      )}

      <div className="space-y-2 border-t border-[var(--color-line)] pt-5">
        <h2
          className="text-lg text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Last 7 days
        </h2>
        <p className="text-sm text-black/70">
          {analytics.data
            ? `${analytics.data.totals.posts_discovered} discovered · ${analytics.data.totals.relevant_count} relevant · ${analytics.data.totals.drafts_generated} drafts · ${analytics.data.totals.approved} approved`
            : "Loading analytics…"}{" "}
          <Link className="underline underline-offset-2" to="/analytics">
            Open analytics
          </Link>
        </p>
      </div>

      <p className="text-sm text-black/50">
        Hard invariant: never auto-publish Reddit comments
        {health.data?.never_auto_publish ? " ✓" : ""}. OpenAI mode:{" "}
        {health.data?.openai_mode ?? "…"}. Active monitors:{" "}
        {automation.data?.monitors_active ?? "…"}.
      </p>
    </section>
  );
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: ReactNode;
}) {
  return (
    <div className="border-t border-[var(--color-line)] pt-4">
      <p className="text-xs uppercase tracking-wide text-black/45">{label}</p>
      <p
        className="mt-2 text-2xl text-[var(--color-moss-deep)]"
        style={{ fontFamily: "var(--font-display)" }}
      >
        {value}
      </p>
      <p className="mt-1 text-xs text-black/45">{hint}</p>
    </div>
  );
}
