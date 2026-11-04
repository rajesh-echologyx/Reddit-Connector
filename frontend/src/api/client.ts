/** Session-authenticated fetch client with CSRF support. */

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

function getCookie(name: string): string | null {
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=")[1] ?? "") : null;
}

export class ApiError extends Error {
  status: number;
  code?: string;
  errors?: unknown;

  constructor(status: number, detail: string, code?: string, errors?: unknown) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.errors = errors;
  }
}

async function ensureCsrf(): Promise<string> {
  let token = getCookie("csrftoken");
  if (!token) {
    await fetch(`${API_BASE}/auth/csrf/`, { credentials: "include" });
    token = getCookie("csrftoken");
  }
  if (!token) {
    throw new ApiError(400, "CSRF token unavailable");
  }
  return token;
}

type Json = Record<string, unknown> | undefined;

export async function api<T>(
  path: string,
  options: RequestInit & { json?: Json } = {},
): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);

  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
    const csrf = await ensureCsrf();
    headers.set("X-CSRFToken", csrf);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    method,
    credentials: "include",
    headers,
    body: options.json !== undefined ? JSON.stringify(options.json) : options.body,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(
      response.status,
      (data as { detail?: string }).detail?.toString() ?? response.statusText,
      (data as { code?: string }).code,
      (data as { errors?: unknown }).errors,
    );
  }
  return data as T;
}

export type User = {
  id: string;
  username: string;
  email: string;
  is_personal_owner: boolean;
  date_joined: string;
  created_at: string;
  updated_at: string;
};

export type Health = {
  status: string;
  db: boolean;
  redis: boolean;
  reddit_mode: string;
  never_auto_publish: boolean;
};

export const authApi = {
  me: () => api<User>("/auth/me/"),
  login: (username: string, password: string) =>
    api<User>("/auth/login/", { method: "POST", json: { username, password } }),
  logout: () => api<{ detail: string }>("/auth/logout/", { method: "POST", json: {} }),
  bootstrap: (username: string, password: string, email = "") =>
    api<User>("/auth/bootstrap/", {
      method: "POST",
      json: { username, password, email },
    }),
  csrf: () => api<{ csrfToken: string }>("/auth/csrf/"),
};

export const opsApi = {
  health: () => api<Health>("/health/"),
};

export type RedditStatus = {
  connected: boolean;
  status: string | null;
  reddit_username: string | null;
  scopes: string | null;
  mode: string;
  token_expires_at: string | null;
  never_auto_publish: boolean;
};

export type RedditPost = {
  id: string;
  reddit_fullname: string;
  reddit_id: string;
  subreddit: string;
  title: string;
  selftext: string;
  author: string;
  url: string;
  permalink: string;
  reddit_url: string;
  score: number;
  num_comments: number;
  created_utc: string | null;
  status: string;
  monitor_id: string | null;
  created_at: string;
  updated_at: string;
};

export type Keyword = {
  id: string;
  phrase: string;
  match_mode: "any" | "all_words" | "exact_phrase";
  created_at: string;
  updated_at: string;
};

export type Subreddit = {
  id: string;
  name: string;
  reddit_id: string;
  created_at: string;
  updated_at: string;
};

export type Monitor = {
  id: string;
  name: string;
  is_active: boolean;
  poll_interval_minutes: number;
  min_score: number | null;
  min_comments: number | null;
  include_nsfw: boolean;
  keywords: Keyword[];
  subreddits: Subreddit[];
  last_polled_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export const redditApi = {
  status: () => api<RedditStatus>("/reddit/status/"),
  oauthStart: () =>
    api<{ authorize_url: string | null; mode: string; detail?: string; state?: string }>(
      "/reddit/oauth/start/",
    ),
  disconnect: () =>
    api<{ detail: string; status: string }>("/reddit/disconnect/", {
      method: "POST",
      json: {},
    }),
  posts: (params?: Record<string, string>) => {
    const qs = params ? `?${new URLSearchParams(params)}` : "";
    return api<Paginated<RedditPost>>(`/posts/${qs}`);
  },
  post: (id: string) => api<RedditPost>(`/posts/${id}/`),
};

export const monitorsApi = {
  list: () => api<Paginated<Monitor>>("/monitors/"),
  create: (body: {
    name: string;
    poll_interval_minutes?: number;
    is_active?: boolean;
    include_nsfw?: boolean;
    min_score?: number | null;
    min_comments?: number | null;
    subreddit_names?: string[];
  }) => api<Monitor>("/monitors/", { method: "POST", json: body }),
  update: (id: string, body: Record<string, unknown>) =>
    api<Monitor>(`/monitors/${id}/`, { method: "PATCH", json: body }),
  remove: (id: string) => api<void>(`/monitors/${id}/`, { method: "DELETE" }),
  addKeyword: (id: string, phrase: string, match_mode: Keyword["match_mode"] = "any") =>
    api<Keyword>(`/monitors/${id}/keywords/`, {
      method: "POST",
      json: { phrase, match_mode },
    }),
  deleteKeyword: (monitorId: string, keywordId: string) =>
    api<void>(`/monitors/${monitorId}/keywords/${keywordId}/`, { method: "DELETE" }),
  setSubreddits: (id: string, subreddits: string[]) =>
    api<Monitor>(`/monitors/${id}/subreddits/`, {
      method: "PUT",
      json: { subreddits },
    }),
  run: (id: string) =>
    api<{ detail: string; task_id: string; result?: unknown }>(`/monitors/${id}/run/`, {
      method: "POST",
      json: {},
    }),
};
