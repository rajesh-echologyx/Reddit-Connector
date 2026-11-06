import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { monitorsApi, type Monitor } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function MonitorsPage() {
  const queryClient = useQueryClient();
  const monitors = useQuery({
    queryKey: ["monitors"],
    queryFn: () => monitorsApi.list(),
  });

  const [name, setName] = useState("");
  const [subs, setSubs] = useState("python, learnprogramming");
  const [phrase, setPhrase] = useState("django");
  const [message, setMessage] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: async () => {
      const monitor = await monitorsApi.create({
        name,
        poll_interval_minutes: 15,
        subreddit_names: subs
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      if (phrase.trim()) {
        await monitorsApi.addKeyword(monitor.id, phrase.trim(), "any");
      }
      return monitor;
    },
    onSuccess: async () => {
      setName("");
      setPhrase("django");
      setMessage("Monitor created.");
      await queryClient.invalidateQueries({ queryKey: ["monitors"] });
    },
  });

  const run = useMutation({
    mutationFn: (id: string) => monitorsApi.run(id),
    onSuccess: async (data) => {
      setMessage(`Poll finished / enqueued (${data.task_id.slice(0, 8)}…).`);
      await queryClient.invalidateQueries({ queryKey: ["monitors"] });
      await queryClient.invalidateQueries({ queryKey: ["posts"] });
      await queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: (err: Error) => setMessage(err.message),
  });

  const pause = useMutation({
    mutationFn: (id: string) => monitorsApi.pause(id),
    onSuccess: async () => {
      setMessage("Monitor paused — Beat will skip it.");
      await queryClient.invalidateQueries({ queryKey: ["monitors"] });
      await queryClient.invalidateQueries({ queryKey: ["automation-status"] });
    },
    onError: (err: Error) => setMessage(err.message),
  });

  const resume = useMutation({
    mutationFn: (id: string) => monitorsApi.resume(id),
    onSuccess: async () => {
      setMessage("Monitor resumed.");
      await queryClient.invalidateQueries({ queryKey: ["monitors"] });
      await queryClient.invalidateQueries({ queryKey: ["automation-status"] });
    },
    onError: (err: Error) => setMessage(err.message),
  });

  const remove = useMutation({
    mutationFn: (id: string) => monitorsApi.remove(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["monitors"] });
    },
  });

  const addKeyword = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) =>
      monitorsApi.addKeyword(id, value, "any"),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["monitors"] });
    },
  });

  function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    create.mutate();
  }

  const items = monitors.data?.results ?? [];
  const busy =
    run.isPending || remove.isPending || pause.isPending || resume.isPending;

  return (
    <section className="space-y-8">
      <header className="space-y-2">
        <h1
          className="text-3xl text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Monitors
        </h1>
        <p className="max-w-2xl text-black/70">
          Keyword and subreddit searches on a Celery Beat schedule. Run now
          discovers posts; auto-analyze and auto-draft fill the review queue —
          never publishes comments.
        </p>
      </header>

      <form
        onSubmit={onCreate}
        className="grid max-w-2xl gap-3 border-t border-[var(--color-line)] pt-6 sm:grid-cols-2"
      >
        <label className="space-y-1 text-sm sm:col-span-2">
          <span className="text-black/55">Name</span>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Research watch"
            required
          />
        </label>
        <label className="space-y-1 text-sm sm:col-span-2">
          <span className="text-black/55">Subreddits (comma-separated, empty = global)</span>
          <Input value={subs} onChange={(e) => setSubs(e.target.value)} />
        </label>
        <label className="space-y-1 text-sm sm:col-span-2">
          <span className="text-black/55">First keyword</span>
          <Input value={phrase} onChange={(e) => setPhrase(e.target.value)} />
        </label>
        <div className="sm:col-span-2">
          <Button type="submit" disabled={create.isPending}>
            Create monitor
          </Button>
        </div>
      </form>

      {message && <p className="text-sm text-black/60">{message}</p>}

      <div className="space-y-6">
        {monitors.isLoading && <p className="text-sm text-black/50">Loading…</p>}
        {items.map((monitor) => (
          <MonitorRow
            key={monitor.id}
            monitor={monitor}
            onRun={() => run.mutate(monitor.id)}
            onPause={() => pause.mutate(monitor.id)}
            onResume={() => resume.mutate(monitor.id)}
            onDelete={() => remove.mutate(monitor.id)}
            onAddKeyword={(value) => addKeyword.mutate({ id: monitor.id, value })}
            busy={busy}
          />
        ))}
        {!monitors.isLoading && items.length === 0 && (
          <p className="text-sm text-black/50">No monitors yet.</p>
        )}
      </div>
    </section>
  );
}

function MonitorRow({
  monitor,
  onRun,
  onPause,
  onResume,
  onDelete,
  onAddKeyword,
  busy,
}: {
  monitor: Monitor;
  onRun: () => void;
  onPause: () => void;
  onResume: () => void;
  onDelete: () => void;
  onAddKeyword: (value: string) => void;
  busy: boolean;
}) {
  const [kw, setKw] = useState("");

  return (
    <article className="space-y-3 border-t border-[var(--color-line)] pt-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2
            className="text-xl text-[var(--color-moss-deep)]"
            style={{ fontFamily: "var(--font-display)" }}
          >
            {monitor.name}
          </h2>
          <p className="text-xs text-black/45">
            every {monitor.poll_interval_minutes}m ·{" "}
            {monitor.is_active ? "active" : "paused"} · last polled{" "}
            {monitor.last_polled_at
              ? new Date(monitor.last_polled_at).toLocaleString()
              : "never"}
            {monitor.auto_analyze ? " · auto-analyze" : ""}
            {monitor.auto_draft ? " · auto-draft" : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={onRun} disabled={busy || !monitor.keywords.length || !monitor.is_active}>
            Run now
          </Button>
          {monitor.is_active ? (
            <Button size="sm" variant="outline" onClick={onPause} disabled={busy}>
              Pause
            </Button>
          ) : (
            <Button size="sm" variant="outline" onClick={onResume} disabled={busy}>
              Resume
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={onDelete} disabled={busy}>
            Delete
          </Button>
        </div>
      </div>

      {monitor.last_error ? (
        <p className="text-sm text-red-800/80">Last error: {monitor.last_error}</p>
      ) : null}

      <p className="text-sm text-black/65">
        Subreddits:{" "}
        {monitor.subreddits.length
          ? monitor.subreddits.map((s) => `r/${s.name}`).join(", ")
          : "global search"}
      </p>

      <ul className="flex flex-wrap gap-2 text-sm">
        {monitor.keywords.map((k) => (
          <li
            key={k.id}
            className="rounded-md border border-[var(--color-line)] bg-white/60 px-2 py-1"
          >
            {k.phrase}{" "}
            <span className="text-black/40">({k.match_mode})</span>
          </li>
        ))}
      </ul>

      <form
        className="flex max-w-md gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!kw.trim()) return;
          onAddKeyword(kw.trim());
          setKw("");
        }}
      >
        <Input
          value={kw}
          onChange={(e) => setKw(e.target.value)}
          placeholder="Add keyword"
        />
        <Button type="submit" size="sm" variant="outline">
          Add
        </Button>
      </form>
    </article>
  );
}
