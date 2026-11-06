import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { reviewApi } from "@/api/client";
import { Button } from "@/components/ui/button";

export function ReviewPage() {
  const queryClient = useQueryClient();
  const queue = useQuery({
    queryKey: ["review-queue"],
    queryFn: () => reviewApi.queue(),
  });
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [flash, setFlash] = useState<string | null>(null);

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["review-queue"] });
  };

  const approve = useMutation({
    mutationFn: (id: string) => reviewApi.approve(id),
    onSuccess: async (data) => {
      setFlash(data.detail);
      await invalidate();
    },
  });
  const reject = useMutation({
    mutationFn: (id: string) => reviewApi.reject(id, "rejected from UI"),
    onSuccess: async () => {
      setFlash("Rejected.");
      await invalidate();
    },
  });
  const saveEdit = useMutation({
    mutationFn: ({ id, body }: { id: string; body: string }) => reviewApi.edit(id, body),
    onSuccess: async () => {
      setFlash("Edit saved.");
      await invalidate();
    },
  });
  const copyExport = useMutation({
    mutationFn: async (id: string) => {
      const data = await reviewApi.export(id);
      await navigator.clipboard.writeText(data.text);
      return data;
    },
    onSuccess: () => setFlash("Copied draft locally. Nothing was posted to Reddit."),
  });

  const results = queue.data?.results ?? [];

  return (
    <section className="space-y-8">
      <header className="space-y-2">
        <h1
          className="text-3xl text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Review
        </h1>
        <p className="max-w-2xl text-black/70">
          Human review queue for AI drafts. Approve marks local status only —
          nothing is posted to Reddit.
        </p>
      </header>

      {flash && (
        <p className="rounded-md border border-[var(--color-moss)]/30 bg-white/70 px-3 py-2 text-sm text-[var(--color-moss-deep)]">
          {flash}
        </p>
      )}

      {queue.isLoading && <p className="text-sm text-black/50">Loading queue…</p>}
      {queue.isError && (
        <p className="text-sm text-red-700">{(queue.error as Error).message}</p>
      )}

      <ul className="space-y-8">
        {results.map((draft) => {
          const body =
            editing[draft.id] ??
            draft.effective_body ??
            draft.body_edited ??
            draft.body;
          return (
            <li key={draft.id} className="space-y-3 border-t border-[var(--color-line)] pt-5">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <p
                  className="text-lg text-[var(--color-moss-deep)]"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {draft.post_title || "Draft"}
                </p>
                <span className="text-xs text-black/45">
                  r/{draft.post_subreddit} · score {draft.relevance_score ?? "—"} ·{" "}
                  {draft.status}
                </span>
              </div>
              <textarea
                className="min-h-32 w-full max-w-3xl rounded-md border border-[var(--color-line)] bg-white/70 px-3 py-2 text-sm"
                value={body}
                onChange={(e) =>
                  setEditing((prev) => ({ ...prev, [draft.id]: e.target.value }))
                }
              />
              {draft.needs_human_check?.length > 0 && (
                <p className="text-xs text-amber-800">
                  Check: {draft.needs_human_check.join("; ")}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  type="button"
                  onClick={() => saveEdit.mutate({ id: draft.id, body })}
                >
                  Save edit
                </Button>
                <Button
                  size="sm"
                  type="button"
                  onClick={() => approve.mutate(draft.id)}
                >
                  Approve (local only)
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  onClick={() => reject.mutate(draft.id)}
                >
                  Reject
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  onClick={() => copyExport.mutate(draft.id)}
                >
                  Copy draft
                </Button>
              </div>
            </li>
          );
        })}
      </ul>

      {!queue.isLoading && results.length === 0 && (
        <p className="text-sm text-black/50">
          No drafts in review. Analyze a relevant post and generate a draft from
          Posts.
        </p>
      )}
    </section>
  );
}
