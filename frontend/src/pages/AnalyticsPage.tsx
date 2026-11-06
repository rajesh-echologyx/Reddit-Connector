import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { analyticsApi, type FunnelStage } from "@/api/client";

type RangeDays = 7 | 30;

function pct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function funnelWidth(stage: FunnelStage, max: number): string {
  if (max <= 0) return "0%";
  return `${Math.max(4, Math.round((stage.count / max) * 100))}%`;
}

export function AnalyticsPage() {
  const [range, setRange] = useState<RangeDays>(7);
  const summary = useQuery({
    queryKey: ["analytics-summary", range],
    queryFn: () => analyticsApi.summary(range),
  });
  const funnel = useQuery({
    queryKey: ["analytics-funnel", range],
    queryFn: () => analyticsApi.funnel(range),
  });

  const totals = summary.data?.totals;
  const stages = funnel.data?.stages ?? [];
  const maxStage = Math.max(1, ...stages.map((s) => s.count));
  const series = summary.data?.series ?? [];

  return (
    <section className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <h1
            className="text-3xl text-[var(--color-moss-deep)]"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Analytics
          </h1>
          <p className="max-w-2xl text-black/70">
            Discovery → relevance → draft → approval from real database
            counters. Approvals stay local — nothing is auto-published.
          </p>
        </div>
        <div className="flex gap-2 text-sm">
          {([7, 30] as const).map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setRange(d)}
              className={
                range === d
                  ? "rounded-md bg-[var(--color-moss)] px-3 py-1.5 text-white"
                  : "rounded-md px-3 py-1.5 text-black/65 hover:bg-black/5"
              }
            >
              {d}d
            </button>
          ))}
        </div>
      </header>

      <div className="grid gap-4 border-t border-[var(--color-line)] pt-5 sm:grid-cols-2 lg:grid-cols-5">
        <Metric label="Discovered" value={totals?.posts_discovered} />
        <Metric label="Relevant" value={totals?.relevant_count} />
        <Metric label="Drafts" value={totals?.drafts_generated} />
        <Metric label="Approved" value={totals?.approved} />
        <Metric label="Rejected" value={totals?.rejected} />
      </div>

      <div className="space-y-4 border-t border-[var(--color-line)] pt-5">
        <h2
          className="text-lg text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Funnel
        </h2>
        {stages.length === 0 && (summary.isLoading || funnel.isLoading) ? (
          <p className="text-sm text-black/50">Loading…</p>
        ) : (
          <ul className="space-y-3">
            {stages.map((stage) => (
              <li key={stage.key} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-black/70">{stage.label}</span>
                  <span className="tabular-nums text-black/55">{stage.count}</span>
                </div>
                <div className="h-2 w-full bg-black/5">
                  <div
                    className="h-2 bg-[var(--color-moss)] transition-[width] duration-500"
                    style={{ width: funnelWidth(stage, maxStage) }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
        {funnel.data?.conversion && (
          <p className="text-sm text-black/50">
            Conversion: discovered→relevant {pct(funnel.data.conversion.discovered_to_relevant)} ·
            relevant→drafted {pct(funnel.data.conversion.relevant_to_drafted)} · drafted→approved{" "}
            {pct(funnel.data.conversion.drafted_to_approved)}
          </p>
        )}
      </div>

      <div className="space-y-3 border-t border-[var(--color-line)] pt-5">
        <h2
          className="text-lg text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Daily series
        </h2>
        {series.length === 0 ? (
          <p className="text-sm text-black/50">
            No activity in this window yet. Run monitors or{" "}
            <Link className="underline underline-offset-2" to="/review">
              clear the review queue
            </Link>{" "}
            to populate counters.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-black/45">
                <tr>
                  <th className="py-2 font-medium">Date</th>
                  <th className="py-2 font-medium">Discovered</th>
                  <th className="py-2 font-medium">Relevant</th>
                  <th className="py-2 font-medium">Drafts</th>
                  <th className="py-2 font-medium">Approved</th>
                  <th className="py-2 font-medium">Rejected</th>
                </tr>
              </thead>
              <tbody>
                {series.map((row) => (
                  <tr key={row.date} className="border-t border-[var(--color-line)]">
                    <td className="py-2 tabular-nums">{row.date}</td>
                    <td className="py-2 tabular-nums">{row.posts_discovered}</td>
                    <td className="py-2 tabular-nums">{row.relevant_count}</td>
                    <td className="py-2 tabular-nums">{row.drafts_generated}</td>
                    <td className="py-2 tabular-nums">{row.approved}</td>
                    <td className="py-2 tabular-nums">{row.rejected}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <p className="text-sm text-black/45">
        Hard invariant: never auto-publish
        {summary.data?.never_auto_publish || funnel.data?.never_auto_publish ? " ✓" : ""}.
        Window {summary.data?.start_date ?? "…"} → {summary.data?.end_date ?? "…"}.
      </p>
    </section>
  );
}

function Metric({ label, value }: { label: string; value?: number }) {
  return (
    <div className="border-t border-[var(--color-line)] pt-4 sm:border-t-0 sm:pt-0">
      <p className="text-xs uppercase tracking-wide text-black/45">{label}</p>
      <p
        className="mt-2 text-2xl text-[var(--color-moss-deep)]"
        style={{ fontFamily: "var(--font-display)" }}
      >
        {value == null ? "…" : value}
      </p>
    </div>
  );
}
