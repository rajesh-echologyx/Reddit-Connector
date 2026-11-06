import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { reviewApi, type DraftResponse } from "@/api/client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type QueueTab = {
  id: string;
  label: string;
  status: string;
};

const TABS: QueueTab[] = [
  { id: "queue", label: "Queue", status: "in_review,draft" },
  { id: "later", label: "Saved", status: "saved_for_later" },
  { id: "approved", label: "Approved", status: "approved" },
  { id: "published", label: "Published", status: "published" },
  { id: "rejected", label: "Rejected", status: "rejected" },
];

function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

function redditHref(draft: DraftResponse): string | null {
  const url = draft.reddit_url || draft.permalink;
  if (!url) return null;
  if (url.startsWith("http")) return url;
  return `https://www.reddit.com${url}`;
}

export function ReviewPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<QueueTab>(TABS[0]!);
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [confirmApproveId, setConfirmApproveId] = useState<string | null>(null);

  const queue = useQuery({
    queryKey: ["review-queue", tab.status],
    queryFn: () => reviewApi.queue(tab.status),
  });

  const results = queue.data?.results ?? [];
  const selected = useMemo(
    () => results.find((d) => d.id === selectedId) ?? results[0] ?? null,
    [results, selectedId],
  );

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["review-queue"] });
  };

  const afterAction = async (message: string) => {
    setFlash(message);
    setConfirmApproveId(null);
    await invalidate();
  };

  const saveEdit = useMutation({
    mutationFn: ({ id, body }: { id: string; body: string }) =>
      reviewApi.edit(id, body),
    onSuccess: async () => afterAction("Edit saved."),
  });
  const saveNotes = useMutation({
    mutationFn: ({ id, private_notes }: { id: string; private_notes: string }) =>
      reviewApi.notes(id, private_notes),
    onSuccess: async (data) => afterAction(data.detail),
  });
  const approve = useMutation({
    mutationFn: (id: string) => reviewApi.approve(id),
    onSuccess: async (data) => afterAction(data.detail),
  });
  const reject = useMutation({
    mutationFn: ({ id, notes: n }: { id: string; notes?: string }) =>
      reviewApi.reject(id, n ?? ""),
    onSuccess: async (data) => afterAction(data.detail),
  });
  const saveLater = useMutation({
    mutationFn: (id: string) => reviewApi.saveForLater(id),
    onSuccess: async (data) => afterAction(data.detail),
  });
  const reopen = useMutation({
    mutationFn: (id: string) => reviewApi.reopen(id),
    onSuccess: async (data) => afterAction(data.detail),
  });
  const markPublished = useMutation({
    mutationFn: (id: string) => reviewApi.markPublished(id),
    onSuccess: async (data) => afterAction(data.detail),
  });
  const regenerate = useMutation({
    mutationFn: (id: string) => reviewApi.regenerate(id),
    onSuccess: async (data) => afterAction(data.detail),
  });
  const copyExport = useMutation({
    mutationFn: async (id: string) => {
      const data = await reviewApi.export(id);
      await navigator.clipboard.writeText(data.text);
      return data;
    },
    onSuccess: () =>
      setFlash("Copied draft locally. Nothing was posted to Reddit."),
  });

  const bodyFor = (draft: DraftResponse) =>
    editing[draft.id] ??
    draft.effective_body ??
    draft.body_edited ??
    draft.body;

  const notesFor = (draft: DraftResponse) =>
    notes[draft.id] ?? draft.private_notes ?? "";

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
          Human review queue for AI drafts. Approve and mark-published update
          local status only — nothing is auto-submitted to Reddit.
        </p>
      </header>

      <div className="flex flex-wrap gap-1 border-b border-[var(--color-line)] pb-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => {
              setTab(t);
              setSelectedId(null);
              setFlash(null);
            }}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm transition-colors",
              tab.id === t.id
                ? "bg-[var(--color-moss)] text-white"
                : "text-black/70 hover:bg-black/5",
            )}
          >
            {t.label}
            {tab.id === t.id && queue.data
              ? ` · ${queue.data.count}`
              : ""}
          </button>
        ))}
      </div>

      {flash && (
        <p
          role="status"
          className="rounded-md border border-[var(--color-moss)]/30 bg-white/70 px-3 py-2 text-sm text-[var(--color-moss-deep)]"
        >
          {flash}
        </p>
      )}

      {queue.isLoading && <p className="text-sm text-black/50">Loading queue…</p>}
      {queue.isError && (
        <p className="text-sm text-red-700">{(queue.error as Error).message}</p>
      )}

      {!queue.isLoading && results.length === 0 && (
        <p className="text-sm text-black/50">
          No drafts in this list. Analyze a relevant post and generate a draft
          from Posts.
        </p>
      )}

      {results.length > 0 && (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]">
          <ul className="space-y-1">
            {results.map((draft) => {
              const active = selected?.id === draft.id;
              return (
                <li key={draft.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(draft.id)}
                    className={cn(
                      "w-full rounded-md px-3 py-2 text-left transition-colors",
                      active
                        ? "bg-[var(--color-moss)]/10 text-[var(--color-moss-deep)]"
                        : "hover:bg-black/5",
                    )}
                  >
                    <p
                      className="line-clamp-2 text-sm"
                      style={{ fontFamily: "var(--font-display)" }}
                    >
                      {draft.post_title || "Draft"}
                    </p>
                    <p className="mt-0.5 text-xs text-black/45">
                      r/{draft.post_subreddit} · {draft.relevance_score ?? "—"}
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>

          {selected && (
            <article className="space-y-5 border-t border-[var(--color-line)] pt-5 lg:border-t-0 lg:pt-0">
              <div className="space-y-2">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <h2
                    className="text-2xl text-[var(--color-moss-deep)]"
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    {selected.post_title || "Draft"}
                  </h2>
                  <span className="text-xs uppercase tracking-wide text-black/45">
                    {statusLabel(selected.status)}
                  </span>
                </div>
                <p className="text-sm text-black/55">
                  r/{selected.post_subreddit}
                  {selected.post_author ? ` · u/${selected.post_author}` : ""}
                  {typeof selected.post_score === "number"
                    ? ` · ${selected.post_score} upvotes`
                    : ""}
                  {selected.relevance_score != null
                    ? ` · relevance ${selected.relevance_score}`
                    : ""}
                </p>
                {selected.post_selftext && (
                  <blockquote className="max-h-40 overflow-y-auto border-l-2 border-[var(--color-moss)]/40 pl-3 text-sm text-black/70 whitespace-pre-wrap">
                    {selected.post_selftext}
                  </blockquote>
                )}
              </div>

              <div className="space-y-2">
                <label
                  className="text-xs uppercase tracking-wide text-black/45"
                  htmlFor={`draft-body-${selected.id}`}
                >
                  Reply draft
                </label>
                <textarea
                  id={`draft-body-${selected.id}`}
                  className="min-h-40 w-full rounded-md border border-[var(--color-line)] bg-white/70 px-3 py-2 text-sm"
                  value={bodyFor(selected)}
                  onChange={(e) =>
                    setEditing((prev) => ({
                      ...prev,
                      [selected.id]: e.target.value,
                    }))
                  }
                />
                {selected.needs_human_check?.length > 0 && (
                  <p className="text-xs text-amber-800">
                    Check: {selected.needs_human_check.join("; ")}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <label
                  className="text-xs uppercase tracking-wide text-black/45"
                  htmlFor={`draft-notes-${selected.id}`}
                >
                  Private notes
                </label>
                <textarea
                  id={`draft-notes-${selected.id}`}
                  className="min-h-20 w-full max-w-xl rounded-md border border-[var(--color-line)] bg-white/70 px-3 py-2 text-sm"
                  placeholder="Operator-only notes — never sent to Reddit"
                  value={notesFor(selected)}
                  onChange={(e) =>
                    setNotes((prev) => ({
                      ...prev,
                      [selected.id]: e.target.value,
                    }))
                  }
                />
              </div>

              {confirmApproveId === selected.id && (
                <div className="rounded-md border border-[var(--color-moss)]/35 bg-white/80 px-3 py-3 text-sm space-y-3">
                  <p>
                    Approve locally? Nothing will be posted to Reddit. You can
                    copy the draft and open the original post next.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      type="button"
                      onClick={() => approve.mutate(selected.id)}
                      disabled={approve.isPending}
                    >
                      Confirm approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      type="button"
                      onClick={() => setConfirmApproveId(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  type="button"
                  onClick={() =>
                    saveEdit.mutate({
                      id: selected.id,
                      body: bodyFor(selected),
                    })
                  }
                  disabled={saveEdit.isPending}
                >
                  Save edit
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  onClick={() =>
                    saveNotes.mutate({
                      id: selected.id,
                      private_notes: notesFor(selected),
                    })
                  }
                  disabled={saveNotes.isPending}
                >
                  Save notes
                </Button>
                {(selected.status === "in_review" ||
                  selected.status === "draft" ||
                  selected.status === "saved_for_later") && (
                  <Button
                    size="sm"
                    type="button"
                    onClick={() => setConfirmApproveId(selected.id)}
                  >
                    Approve (local only)
                  </Button>
                )}
                {(selected.status === "in_review" ||
                  selected.status === "draft") && (
                  <Button
                    size="sm"
                    variant="outline"
                    type="button"
                    onClick={() => saveLater.mutate(selected.id)}
                    disabled={saveLater.isPending}
                  >
                    Save for later
                  </Button>
                )}
                {selected.status === "saved_for_later" && (
                  <Button
                    size="sm"
                    variant="outline"
                    type="button"
                    onClick={() => reopen.mutate(selected.id)}
                    disabled={reopen.isPending}
                  >
                    Return to queue
                  </Button>
                )}
                {(selected.status === "in_review" ||
                  selected.status === "draft" ||
                  selected.status === "saved_for_later" ||
                  selected.status === "approved") && (
                  <Button
                    size="sm"
                    variant="outline"
                    type="button"
                    onClick={() =>
                      reject.mutate({
                        id: selected.id,
                        notes: notesFor(selected),
                      })
                    }
                    disabled={reject.isPending}
                  >
                    Reject
                  </Button>
                )}
                {(selected.status === "in_review" ||
                  selected.status === "draft" ||
                  selected.status === "saved_for_later" ||
                  selected.status === "rejected") && (
                  <Button
                    size="sm"
                    variant="outline"
                    type="button"
                    onClick={() => regenerate.mutate(selected.id)}
                    disabled={regenerate.isPending}
                  >
                    Regenerate
                  </Button>
                )}
                {(selected.status === "approved" ||
                  selected.status === "in_review" ||
                  selected.status === "saved_for_later") && (
                  <Button
                    size="sm"
                    variant="outline"
                    type="button"
                    onClick={() => markPublished.mutate(selected.id)}
                    disabled={markPublished.isPending}
                  >
                    Mark published
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  onClick={() => copyExport.mutate(selected.id)}
                  disabled={copyExport.isPending}
                >
                  Copy draft
                </Button>
                {redditHref(selected) && (
                  <a
                    href={redditHref(selected)!}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-8 items-center justify-center rounded-md border border-[var(--color-line)] bg-transparent px-3 text-sm text-[var(--color-moss-deep)] transition-colors hover:bg-black/5"
                  >
                    Open original
                  </a>
                )}
              </div>

              <p className="text-xs text-black/45">
                Submit to Reddit via API is{" "}
                {selected.reddit_submit_enabled ||
                queue.data?.reddit_submit_enabled
                  ? "flagged on (still not auto)"
                  : "disabled"}
                . Default path: copy draft → open original → paste yourself.
              </p>
            </article>
          )}
        </div>
      )}
    </section>
  );
}
