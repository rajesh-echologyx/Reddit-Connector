import { useQuery } from "@tanstack/react-query";

import { redditApi } from "@/api/client";

export function DevModeBanner() {
  const status = useQuery({
    queryKey: ["reddit-status"],
    queryFn: () => redditApi.status(),
    staleTime: 30_000,
  });

  const show =
    status.data?.mode === "fixture" || status.data?.status === "dev_fixture";

  if (!show) {
    return null;
  }

  return (
    <div
      role="status"
      className="border-b border-[var(--color-amber-warn)]/40 bg-[#fff4e0] px-4 py-2 text-center text-sm text-[#7a4a08]"
    >
      Development mode — Reddit API not connected. Fixture data only; nothing is
      posted to Reddit.
    </div>
  );
}
