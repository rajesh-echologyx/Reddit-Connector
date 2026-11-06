import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";

import { reviewApi } from "@/api/client";
import { DevModeBanner } from "@/components/DevModeBanner";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/review", label: "Review", badgeKey: "review" as const },
  { to: "/posts", label: "Posts" },
  { to: "/monitors", label: "Monitors" },
  { to: "/tasks", label: "Tasks" },
  { to: "/profile", label: "Profile" },
  { to: "/settings", label: "Settings" },
  { to: "/analytics", label: "Analytics" },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const dueReviews = useQuery({
    queryKey: ["review-queue", "in_review,draft"],
    queryFn: () => reviewApi.queue("in_review,draft"),
    refetchInterval: 60_000,
  });
  const dueCount = dueReviews.data?.count ?? 0;

  return (
    <div className="min-h-screen">
      <DevModeBanner />
      <header className="border-b border-[var(--color-line)] bg-white/55 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-baseline gap-3">
            <span
              className="text-xl tracking-tight text-[var(--color-moss-deep)]"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Raddit Connector
            </span>
            <span className="hidden text-xs text-black/50 sm:inline">
              research · draft · human approve
            </span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-black/60 sm:inline">{user?.username}</span>
            <Button variant="outline" size="sm" onClick={() => void logout()}>
              Log out
            </Button>
          </div>
        </div>
        <nav className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-4 pb-2">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-1.5 text-sm whitespace-nowrap transition-colors",
                  isActive
                    ? "bg-[var(--color-moss)] text-white"
                    : "text-black/70 hover:bg-black/5",
                )
              }
            >
              {item.label}
              {"badgeKey" in item && dueCount > 0 ? (
                <span className="ml-1.5 text-xs opacity-80">{dueCount}</span>
              ) : null}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
