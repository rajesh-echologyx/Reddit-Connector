import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { monitorsApi, opsApi, redditApi, reviewApi } from "@/api/client";
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

  const connectionLabel =
    reddit.data?.reddit_username ||
    reddit.data?.status ||
    health.data?.reddit_mode ||
    "…";

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
          Welcome{user ? `, ${user.username}` : ""}. Review drafts, copy replies,
          and open the original Reddit post — never auto-submit.
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

      <p className="text-sm text-black/50">
        Hard invariant: never auto-publish Reddit comments
        {health.data?.never_auto_publish ? " ✓" : ""}. OpenAI mode:{" "}
        {health.data?.openai_mode ?? "…"}.
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
