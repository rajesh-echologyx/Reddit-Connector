import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { redditApi } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function PostsPage() {
  const [q, setQ] = useState("");
  const [subreddit, setSubreddit] = useState("");
  const [applied, setApplied] = useState<Record<string, string>>({});

  const posts = useQuery({
    queryKey: ["posts", applied],
    queryFn: () => redditApi.posts(applied),
  });

  const results = posts.data?.results ?? [];

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
          Discovered Reddit submissions (deduped by reddit_fullname). Relevance
          scoring arrives in Phase 3.
        </p>
      </header>

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

      <ul className="space-y-5">
        {results.map((post) => (
          <li
            key={post.id}
            className="space-y-1 border-t border-[var(--color-line)] pt-4"
          >
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <a
                href={post.reddit_url || post.url}
                target="_blank"
                rel="noreferrer"
                className="text-lg text-[var(--color-moss-deep)] underline-offset-2 hover:underline"
                style={{ fontFamily: "var(--font-display)" }}
              >
                {post.title}
              </a>
              <span className="text-xs text-black/45">r/{post.subreddit}</span>
            </div>
            <p className="text-xs text-black/45">
              {post.reddit_fullname} · score {post.score} · {post.num_comments} comments ·{" "}
              u/{post.author || "?"} · {post.status}
            </p>
            {post.selftext && (
              <p className="max-w-3xl text-sm text-black/65 line-clamp-3">
                {post.selftext}
              </p>
            )}
          </li>
        ))}
      </ul>

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
