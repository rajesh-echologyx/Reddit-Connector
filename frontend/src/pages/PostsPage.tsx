import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { redditApi } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function PostsPage() {
  const queryClient = useQueryClient();
  const [q, setQ] = useState("");
  const [subreddit, setSubreddit] = useState("");
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const posts = useQuery({
    queryKey: ["posts", applied],
    queryFn: () => redditApi.posts(applied),
  });

  const detail = useQuery({
    queryKey: ["post", selectedId],
    queryFn: () => redditApi.post(selectedId!),
    enabled: !!selectedId,
  });

  const analyze = useMutation({
    mutationFn: (id: string) => redditApi.analyze(id),
    onSuccess: async (data) => {
      setActionMsg(data.detail);
      await queryClient.invalidateQueries({ queryKey: ["posts"] });
      await queryClient.invalidateQueries({ queryKey: ["post", selectedId] });
    },
    onError: (err: Error) => setActionMsg(err.message),
  });

  const draft = useMutation({
    mutationFn: (id: string) => redditApi.draft(id),
    onSuccess: async (data) => {
      setActionMsg(`${data.detail} (never auto-publish)`);
      await queryClient.invalidateQueries({ queryKey: ["post", selectedId] });
      await queryClient.invalidateQueries({ queryKey: ["review-queue"] });
    },
    onError: (err: Error) => setActionMsg(err.message),
  });

  const results = posts.data?.results ?? [];
  const selected = detail.data;

  return (
    <section className="space-y-8">
      <header className="space-y-2">
        <h1
          className="text-3xl text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Posts
        </h1>
        <p className="max-w-2xl text-black/70">
          Discovered Reddit submissions with AI relevance scores. Drafts land in
          Review — never auto-published.
        </p>
      </header>

      {actionMsg && (
        <p className="text-sm text-[var(--color-moss-deep)]">{actionMsg}</p>
      )}

      <form
        className="flex flex-wrap items-end gap-3 border-t border-[var(--color-line)] pt-6"
        onSubmit={(e) => {
          e.preventDefault();
          const next: Record<string, string> = {};
          if (q.trim()) next.q = q.trim();
          if (subreddit.trim()) next.subreddit = subreddit.trim().replace(/^r\//, "");
          setApplied(next);
        }}
      >
        <label className="space-y-1 text-sm">
          <span className="text-black/55">Title contains</span>
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="django" />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-black/55">Subreddit</span>
          <Input
            value={subreddit}
            onChange={(e) => setSubreddit(e.target.value)}
            placeholder="python"
          />
        </label>
        <Button type="submit" size="sm">
          Filter
        </Button>
      </form>

      {posts.isLoading && <p className="text-sm text-black/50">Loading posts…</p>}
      {posts.isError && (
        <p className="text-sm text-red-700">{(posts.error as Error).message}</p>
      )}

      <div className="grid gap-8 lg:grid-cols-[1fr_minmax(280px,380px)]">
        <ul className="space-y-5">
          {results.map((post) => (
            <li
              key={post.id}
              className="space-y-1 border-t border-[var(--color-line)] pt-4"
            >
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <button
                  type="button"
                  className="text-left text-lg text-[var(--color-moss-deep)] underline-offset-2 hover:underline"
                  style={{ fontFamily: "var(--font-display)" }}
                  onClick={() => setSelectedId(post.id)}
                >
                  {post.title}
                </button>
                <span className="text-xs text-black/45">r/{post.subreddit}</span>
              </div>
              <p className="text-xs text-black/45">
                {post.reddit_fullname} · score {post.score} · {post.num_comments} comments ·{" "}
                u/{post.author || "?"} · {post.status}
                {post.relevance_score != null && (
                  <> · relevance {post.relevance_score}</>
                )}
              </p>
              {post.selftext && (
                <p className="max-w-3xl text-sm text-black/65 line-clamp-3">
                  {post.selftext}
                </p>
              )}
            </li>
          ))}
        </ul>

        <aside className="space-y-4 border-t border-[var(--color-line)] pt-4 lg:border-t-0 lg:border-l lg:pl-6 lg:pt-0">
          {!selectedId && (
            <p className="text-sm text-black/50">Select a post to analyze or draft.</p>
          )}
          {selectedId && detail.isLoading && (
            <p className="text-sm text-black/50">Loading detail…</p>
          )}
          {selected && (
            <div className="space-y-3">
              <h2
                className="text-xl text-[var(--color-moss-deep)]"
                style={{ fontFamily: "var(--font-display)" }}
              >
                {selected.title}
              </h2>
              <p className="text-xs text-black/45">
                Status: {selected.status}
                {selected.analysis && (
                  <>
                    {" "}
                    · score {selected.analysis.relevance_score} ·{" "}
                    {selected.analysis.is_relevant ? "relevant" : "not relevant"}
                  </>
                )}
              </p>
              {selected.analysis?.summary && (
                <p className="text-sm text-black/70">{selected.analysis.summary}</p>
              )}
              {selected.analysis?.reasons?.length ? (
                <ul className="list-disc space-y-1 pl-5 text-sm text-black/60">
                  {selected.analysis.reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  type="button"
                  disabled={analyze.isPending}
                  onClick={() => analyze.mutate(selected.id)}
                >
                  Analyze relevance
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  disabled={draft.isPending || !selected.analysis?.is_relevant}
                  onClick={() => draft.mutate(selected.id)}
                >
                  Generate draft
                </Button>
              </div>
              {selected.drafts && selected.drafts.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-wide text-black/45">Drafts</p>
                  {selected.drafts.map((d) => (
                    <div key={d.id} className="space-y-1 text-sm">
                      <p className="text-xs text-black/45">
                        {d.status} · {d.tone || "—"}
                      </p>
                      <p className="whitespace-pre-wrap text-black/70">
                        {d.effective_body || d.body}
                      </p>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-xs text-black/40">
                Hard invariant: drafts are never auto-published.
              </p>
            </div>
          )}
        </aside>
      </div>

      {!posts.isLoading && results.length === 0 && (
        <p className="text-sm text-black/50">
          No posts yet. Create a monitor and click Run now, or{" "}
          <code>python manage.py seed_dev_reddit --poll</code>.
        </p>
      )}

      {posts.data && (
        <p className="text-xs text-black/40">{posts.data.count} total</p>
      )}
    </section>
  );
}
