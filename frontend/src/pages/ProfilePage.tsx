import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { profileApi } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ProfilePage() {
  const queryClient = useQueryClient();
  const profile = useQuery({ queryKey: ["profile"], queryFn: () => profileApi.get() });
  const samples = useQuery({
    queryKey: ["writing-samples"],
    queryFn: () => profileApi.listSamples(),
  });

  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [topics, setTopics] = useState("");
  const [tone, setTone] = useState("");
  const [constraints, setConstraints] = useState("");
  const [relevanceModel, setRelevanceModel] = useState("");
  const [draftModel, setDraftModel] = useState("");
  const [sampleTitle, setSampleTitle] = useState("");
  const [sampleBody, setSampleBody] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!profile.data) return;
    setDisplayName(profile.data.display_name);
    setBio(profile.data.bio_short);
    setTopics((profile.data.expertise_topics || []).join(", "));
    setTone(profile.data.tone_notes);
    setConstraints(profile.data.hard_constraints);
    setRelevanceModel(profile.data.openai_relevance_model);
    setDraftModel(profile.data.openai_draft_model);
  }, [profile.data]);

  const saveProfile = useMutation({
    mutationFn: () =>
      profileApi.update({
        display_name: displayName,
        bio_short: bio,
        expertise_topics: topics
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        tone_notes: tone,
        hard_constraints: constraints,
        openai_relevance_model: relevanceModel,
        openai_draft_model: draftModel,
      }),
    onSuccess: async () => {
      setMessage("Profile saved.");
      await queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (err: Error) => setMessage(err.message),
  });

  const addSample = useMutation({
    mutationFn: () =>
      profileApi.createSample({
        title: sampleTitle,
        body: sampleBody,
        is_active: true,
      }),
    onSuccess: async () => {
      setSampleTitle("");
      setSampleBody("");
      setMessage("Writing sample added.");
      await queryClient.invalidateQueries({ queryKey: ["writing-samples"] });
    },
    onError: (err: Error) => setMessage(err.message),
  });

  const removeSample = useMutation({
    mutationFn: (id: string) => profileApi.deleteSample(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["writing-samples"] });
    },
  });

  const sampleResults = samples.data?.results ?? [];

  return (
    <section className="space-y-10">
      <header className="space-y-2">
        <h1
          className="text-3xl text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Profile
        </h1>
        <p className="max-w-2xl text-black/70">
          Expertise, tone, and constraints feed AI relevance and drafts. Writing
          samples shape style only — never invent experience beyond this profile.
        </p>
      </header>

      {message && <p className="text-sm text-[var(--color-moss-deep)]">{message}</p>}

      <form
        className="max-w-2xl space-y-4 border-t border-[var(--color-line)] pt-6"
        onSubmit={(e) => {
          e.preventDefault();
          saveProfile.mutate();
        }}
      >
        <Field label="Display name">
          <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </Field>
        <Field label="Short bio">
          <textarea
            className="min-h-20 w-full rounded-md border border-[var(--color-line)] bg-white/70 px-3 py-2 text-sm"
            value={bio}
            onChange={(e) => setBio(e.target.value)}
          />
        </Field>
        <Field label="Expertise topics (comma-separated)">
          <Input
            value={topics}
            onChange={(e) => setTopics(e.target.value)}
            placeholder="django, celery, postgres"
          />
        </Field>
        <Field label="Tone notes">
          <textarea
            className="min-h-16 w-full rounded-md border border-[var(--color-line)] bg-white/70 px-3 py-2 text-sm"
            value={tone}
            onChange={(e) => setTone(e.target.value)}
          />
        </Field>
        <Field label="Hard constraints">
          <textarea
            className="min-h-24 w-full rounded-md border border-[var(--color-line)] bg-white/70 px-3 py-2 text-sm"
            value={constraints}
            onChange={(e) => setConstraints(e.target.value)}
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Relevance model override">
            <Input
              value={relevanceModel}
              onChange={(e) => setRelevanceModel(e.target.value)}
              placeholder="gpt-4o-mini"
            />
          </Field>
          <Field label="Draft model override">
            <Input
              value={draftModel}
              onChange={(e) => setDraftModel(e.target.value)}
              placeholder="gpt-4o-mini"
            />
          </Field>
        </div>
        <Button type="submit" disabled={saveProfile.isPending}>
          {saveProfile.isPending ? "Saving…" : "Save profile"}
        </Button>
      </form>

      <div className="space-y-4 border-t border-[var(--color-line)] pt-6">
        <h2
          className="text-xl text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Writing samples
        </h2>
        <p className="text-sm text-black/55">
          Up to 5 active samples for draft style (not used in relevance scoring).
        </p>

        <ul className="space-y-4">
          {sampleResults.map((s) => (
            <li key={s.id} className="space-y-1 border-t border-[var(--color-line)] pt-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-medium">{s.title}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => removeSample.mutate(s.id)}
                >
                  Delete
                </Button>
              </div>
              <p className="text-xs text-black/45">
                {s.source} · {s.is_active ? "active" : "inactive"}
              </p>
              <p className="max-w-3xl text-sm text-black/65 whitespace-pre-wrap">{s.body}</p>
            </li>
          ))}
        </ul>

        <form
          className="max-w-2xl space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            addSample.mutate();
          }}
        >
          <Field label="Sample title">
            <Input value={sampleTitle} onChange={(e) => setSampleTitle(e.target.value)} required />
          </Field>
          <Field label="Sample body">
            <textarea
              className="min-h-28 w-full rounded-md border border-[var(--color-line)] bg-white/70 px-3 py-2 text-sm"
              value={sampleBody}
              onChange={(e) => setSampleBody(e.target.value)}
              required
            />
          </Field>
          <Button type="submit" size="sm" disabled={addSample.isPending}>
            Add sample
          </Button>
        </form>
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1 text-sm">
      <span className="text-black/55">{label}</span>
      {children}
    </label>
  );
}
