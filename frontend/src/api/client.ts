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
  openai_mode?: string;
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

export type RelevanceAnalysis = {
  id: string;
  relevance_score: number;
  is_relevant: boolean;
  reasons: string[];
  matched_expertise: string[];
  risk_flags: string[];
  summary: string;
  model: string;
  prompt_version: string;
  status: string;
  error_message: string;
  created_at: string;
  updated_at: string;
};

export type DraftResponse = {
  id: string;
  post: string;
  analysis: string | null;
  body: string;
  body_edited: string | null;
  effective_body: string;
  status: string;
  tone: string;
  claims_made: string[];
  needs_human_check: string[];
  model: string;
  prompt_version: string;
  error_message: string;
  generated_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  created_at: string;
  updated_at: string;
  never_auto_publish: boolean;
  post_title?: string;
  post_subreddit?: string;
  relevance_score?: number | null;
  permalink?: string;
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
  relevance_score?: number | null;
  is_relevant?: boolean | null;
  analysis?: RelevanceAnalysis | null;
  drafts?: DraftResponse[];
  created_at: string;
  updated_at: string;
};

export type UserProfile = {
  id: string;
  display_name: string;
  bio_short: string;
  expertise_topics: string[];
  tone_notes: string;
  hard_constraints: string;
  openai_relevance_model: string;
  openai_draft_model: string;
  created_at: string;
  updated_at: string;
};

export type WritingSample = {
  id: string;
  title: string;
  body: string;
  source: "manual" | "imported";
  is_active: boolean;
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
  analyze: (id: string, force = false) =>
    api<{ detail: string; task_id: string; result?: unknown; never_auto_publish: boolean }>(
      `/posts/${id}/analyze/`,
      { method: "POST", json: { force } },
    ),
  draft: (id: string, force = false) =>
    api<{ detail: string; task_id: string; result?: unknown; never_auto_publish: boolean }>(
      `/posts/${id}/draft/`,
      { method: "POST", json: { force } },
    ),
};

export const profileApi = {
  get: () => api<UserProfile>("/profile/"),
  update: (body: Partial<UserProfile>) =>
    api<UserProfile>("/profile/", { method: "PATCH", json: body }),
  listSamples: () => api<Paginated<WritingSample>>("/writing-samples/"),
  createSample: (body: { title: string; body: string; is_active?: boolean }) =>
    api<WritingSample>("/writing-samples/", { method: "POST", json: body }),
  updateSample: (id: string, body: Partial<WritingSample>) =>
    api<WritingSample>(`/writing-samples/${id}/`, { method: "PATCH", json: body }),
  deleteSample: (id: string) =>
    api<void>(`/writing-samples/${id}/`, { method: "DELETE" }),
};

export const reviewApi = {
  queue: (status = "in_review,draft") =>
    api<{ count: number; results: DraftResponse[]; never_auto_publish: boolean }>(
      `/review/queue/?status=${encodeURIComponent(status)}`,
    ),
  edit: (id: string, body_edited: string, notes = "") =>
    api<DraftResponse>(`/review/${id}/edit/`, {
      method: "POST",
      json: { body_edited, notes },
    }),
  approve: (id: string, notes = "") =>
    api<{ detail: string; draft: DraftResponse; never_auto_publish: boolean }>(
      `/review/${id}/approve/`,
      { method: "POST", json: { notes } },
    ),
  reject: (id: string, notes = "") =>
    api<{ detail: string; draft: DraftResponse; never_auto_publish: boolean }>(
      `/review/${id}/reject/`,
      { method: "POST", json: { notes } },
    ),
  regenerate: (id: string) =>
    api<{ detail: string; task_id: string; never_auto_publish: boolean }>(
      `/review/${id}/regenerate/`,
      { method: "POST", json: {} },
    ),
  export: (id: string) =>
    api<{ text: string; permalink: string; never_auto_publish: boolean }>(
      `/review/${id}/export/`,
    ),
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
