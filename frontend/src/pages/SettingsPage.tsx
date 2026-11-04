import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { redditApi } from "@/api/client";
import { Button } from "@/components/ui/button";

export function SettingsPage() {
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const flash = useMemo(() => params.get("reddit"), [params]);

  const status = useQuery({
    queryKey: ["reddit-status"],
    queryFn: () => redditApi.status(),
  });

  const connect = useMutation({
    mutationFn: () => redditApi.oauthStart(),
    onSuccess: (data) => {
      if (data.authorize_url) {
        window.location.href = data.authorize_url;
      }
    },
  });

  const disconnect = useMutation({
    mutationFn: () => redditApi.disconnect(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["reddit-status"] });
    },
  });

  const data = status.data;

  return (
    <section className="space-y-8">
      <header className="space-y-2">
        <h1
          className="text-3xl text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Settings
        </h1>
        <p className="max-w-2xl text-black/70">
          Connect the official Reddit OAuth API with minimal scopes
          (identity, read). Approving drafts never publishes comments.
        </p>
      </header>

      {flash === "connected" && (
        <p className="rounded-md border border-[var(--color-moss)]/30 bg-white/70 px-3 py-2 text-sm text-[var(--color-moss-deep)]">
          Reddit connected successfully.
        </p>
      )}
      {flash === "error" && (
        <p className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          Reddit OAuth failed ({params.get("detail") ?? "unknown"}).
        </p>
      )}

      <div className="space-y-4 border-t border-[var(--color-line)] pt-6">
        <h2
          className="text-xl text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Reddit connection
        </h2>

        {status.isLoading && <p className="text-sm text-black/50">Loading status…</p>}
        {status.isError && (
          <p className="text-sm text-red-700">Could not load Reddit status.</p>
        )}

        {data && (
          <dl className="grid max-w-xl gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-black/45">Mode</dt>
              <dd className="font-medium">{data.mode}</dd>
            </div>
            <div>
              <dt className="text-black/45">Status</dt>
              <dd className="font-medium">{data.status ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-black/45">Username</dt>
              <dd className="font-medium">{data.reddit_username ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-black/45">Scopes</dt>
              <dd className="font-medium">{data.scopes ?? "—"}</dd>
            </div>
          </dl>
        )}

        <div className="flex flex-wrap gap-3 pt-2">
          {data?.mode === "fixture" ? (
            <p className="max-w-xl text-sm text-black/60">
              Fixture mode is active. Set <code>REDDIT_MODE=live</code> and Reddit
              app credentials in <code>.env</code>, then restart to enable OAuth.
            </p>
          ) : (
            <Button
              onClick={() => connect.mutate()}
              disabled={connect.isPending || data?.status === "connected"}
            >
              {data?.status === "connected" ? "Connected" : "Connect Reddit"}
            </Button>
          )}
          {data?.status === "connected" && (
            <Button
              variant="outline"
              onClick={() => disconnect.mutate()}
              disabled={disconnect.isPending}
            >
              Disconnect
            </Button>
          )}
        </div>

        {connect.data?.mode === "fixture" && connect.data.detail && (
          <p className="text-sm text-black/55">{connect.data.detail}</p>
        )}
        {connect.isError && (
          <p className="text-sm text-red-700">
            {(connect.error as Error).message}
          </p>
        )}
      </div>
    </section>
  );
}
