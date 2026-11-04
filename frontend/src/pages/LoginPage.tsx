import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";

export function LoginPage() {
  const { user, loading, login, bootstrap } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "bootstrap">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) {
    return <Navigate to="/" replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      if (mode === "login") {
        await login(username, password);
      } else {
        await bootstrap(username, password);
      }
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Something went wrong.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <div className="mb-8 space-y-2 text-center">
        <h1
          className="text-4xl text-[var(--color-moss-deep)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Raddit Connector
        </h1>
        <p className="text-sm text-black/65">
          Personal Reddit research assistant. Replies are never auto-published.
        </p>
      </div>

      <form
        onSubmit={onSubmit}
        className="space-y-4 rounded-xl border border-[var(--color-line)] bg-white/70 p-6 shadow-sm"
      >
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant={mode === "login" ? "default" : "outline"}
            onClick={() => setMode("login")}
          >
            Log in
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === "bootstrap" ? "default" : "outline"}
            onClick={() => setMode("bootstrap")}
          >
            First-run bootstrap
          </Button>
        </div>

        <label className="block space-y-1 text-sm">
          <span>Username</span>
          <Input
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label className="block space-y-1 text-sm">
          <span>Password</span>
          <Input
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        {error ? <p className="text-sm text-red-700">{error}</p> : null}

        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Working…" : mode === "login" ? "Log in" : "Create owner"}
        </Button>
      </form>
    </div>
  );
}
