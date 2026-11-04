import { useQuery } from "@tanstack/react-query";

import { opsApi } from "@/api/client";
import { useAuth } from "@/hooks/useAuth";

export function DashboardPage() {
  const { user } = useAuth();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => opsApi.health(),
  });

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
          Welcome{user ? `, ${user.username}` : ""}. Phase 1 foundation is live —
          monitors, analysis, and review land in later phases.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Due reviews" value="—" hint="Phase 4" />
        <Stat label="New relevant posts" value="—" hint="Phase 3" />
        <Stat
          label="Reddit connection"
          value={health.data?.reddit_mode ?? "…"}
          hint={health.data?.db ? "API healthy" : "Checking…"}
        />
      </div>

      <p className="text-sm text-black/50">
        Hard invariant: never auto-publish Reddit comments
        {health.data?.never_auto_publish ? " ✓" : ""}.
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
  hint: string;
}) {
  return (
    <div className="rounded-xl border border-[var(--color-line)] bg-white/65 px-4 py-5">
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
