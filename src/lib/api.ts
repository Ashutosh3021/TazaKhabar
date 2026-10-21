/**
 * TazaKhabar API client — every call goes through the backend with the
 * session cookie (httpOnly, set by the backend on sign in).
 */
import type { DigestItem, Job, Trend } from "@/types";

/** Production: set NEXT_PUBLIC_API_URL in Vercel (no trailing slash). */
function getApiBase(): string {
  const fromEnv = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
  if (fromEnv) return fromEnv;
  if (process.env.NODE_ENV !== "production") {
    return "http://localhost:8000";
  }
  throw new Error(
    "Collector bus offline. Point the instrument at an API host to resume sweeps."
  );
}

/**
 * Wrapper around fetch that always sends the session cookie.
 */
async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(url, { ...init, headers, credentials: "include" });
}

/**
 * Build query string from filter object.
 */
function buildQuery(params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      value.forEach((v) => searchParams.append(key, String(v)));
    } else {
      searchParams.set(key, String(value));
    }
  }
  const qs = searchParams.toString();
  return qs ? `?${qs}` : "";
}

// ============================================================================
// Auth
// ============================================================================

export interface SessionUser {
  id: string | null;
  email: string | null;
  authenticated: boolean;
}

export interface AuthResult {
  authenticated: boolean;
  user: SessionUser;
  message?: string;
}

/**
 * First-party hint cookie, set on the frontend domain after a sign in.
 *
 * The real session cookie (tk_session) is httpOnly and host-only on the API
 * domain, so the frontend domain can never read it. This hint only tells the
 * Next.js middleware which pages to send to /auth; the API still validates
 * every request.
 */
export const SESSION_HINT_COOKIE = "tk_hint";

export function setSessionHint() {
  if (typeof document === "undefined") return;
  const maxAge = 60 * 60 * 24 * 14;
  document.cookie = `${SESSION_HINT_COOKIE}=1; path=/; max-age=${maxAge}; SameSite=Lax`;
}

export function clearSessionHint() {
  if (typeof document === "undefined") return;
  document.cookie = `${SESSION_HINT_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
}

export type AuthProvider = {
  id: string;
  name: string;
  configured: boolean;
};

/** Which sign-in methods the backend has configured. */
export async function fetchAuthProviders(): Promise<AuthProvider[]> {
  try {
    const res = await apiFetch(`${getApiBase()}/api/auth/providers`, { cache: "no-store" });
    if (!res.ok) return [];
    const body = await res.json();
    return (body.providers ?? []) as AuthProvider[];
  } catch {
    return [];
  }
}

/**
 * Send the browser to the backend, which starts the Google or GitHub flow.
 * The backend comes back to /auth/callback once the provider is done.
 */
export function startOAuth(provider: "google" | "github") {
  window.location.assign(`${getApiBase()}/api/auth/oauth/${provider}`);
}

/** Drop the session on the backend and in the browser. */
export async function signOut(): Promise<void> {
  await apiFetch(`${getApiBase()}/api/auth/logout`, { method: "POST" });
  clearSessionHint();
}

/** Resolve the current session. */
export async function fetchSession(): Promise<AuthResult> {
  try {
    const res = await apiFetch(`${getApiBase()}/api/auth/me`, { cache: "no-store" });
    if (!res.ok) return { authenticated: false, user: { id: null, email: null, authenticated: false } };
    return res.json();
  } catch {
    return { authenticated: false, user: { id: null, email: null, authenticated: false } };
  }
}

/**
 * Fetch paginated jobs from the backend API.
 */
export async function fetchJobs(filters?: {
  roles?: string[];
  remote?: boolean;
  startup_only?: boolean;
  skip?: number;
  limit?: number;
  personalize?: boolean;
}): Promise<{ data: Job[]; meta: { total: number; skip: number; limit: number; has_more: boolean } }> {
  const params: Record<string, unknown> = {};
  if (filters?.roles?.length) params.roles = filters.roles;
  if (filters?.remote) params.remote = filters.remote;
  if (filters?.startup_only) params.startup_only = filters.startup_only;
  if (filters?.skip !== undefined) params.skip = filters.skip;
  if (filters?.limit !== undefined) params.limit = filters.limit;
  if (filters?.personalize) params.personalize = filters.personalize;

  const qs = buildQuery(params);
  const url = `${getApiBase()}/api/jobs${qs}`;

  const res = await apiFetch(url, {
    cache: "no-store", // Jobs change frequently; never serve stale cached empty responses
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch jobs: ${res.status} ${res.statusText}`);
  }

  const json = await res.json();
  return {
    data: (json.data as Job[]) ?? [],
    meta: json.meta ?? { total: 0, skip: 0, limit: 20, has_more: false },
  };
}

/**
 * Fetch paginated news items from the backend API.
 */
export async function fetchNews(params?: {
  type?: string;
  skip?: number;
  limit?: number;
}): Promise<{ data: DigestItem[]; meta: { total: number; skip: number; limit: number; has_more: boolean } }> {
  const queryParams: Record<string, unknown> = {};
  if (params?.type && params.type !== "all") queryParams.type = params.type;
  if (params?.skip !== undefined) queryParams.skip = params.skip;
  if (params?.limit !== undefined) queryParams.limit = params.limit;

  const qs = buildQuery(queryParams);
  const url = `${getApiBase()}/api/news${qs}`;

  const res = await apiFetch(url, {
    next: { revalidate: 300 },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch news: ${res.status} ${res.statusText}`);
  }

  const json = await res.json();
  return {
    data: (json.data as DigestItem[]) ?? [],
    meta: json.meta ?? { total: 0, skip: 0, limit: 20, has_more: false },
  };
}

/**
 * Fetch badge counts (items the user has not seen yet).
 */
export async function fetchBadgeCounts(): Promise<{ new_jobs: number; new_news: number }> {
  try {
    const url = `${getApiBase()}/api/badge`;
    const res = await apiFetch(url, { cache: "no-store" });

    if (!res.ok) {
      throw new Error(`Failed to fetch badge counts: ${res.status}`);
    }

    const json = await res.json();
    return {
      new_jobs: json.new_jobs ?? 0,
      new_news: json.new_news ?? 0,
    };
  } catch {
    return { new_jobs: 0, new_news: 0 };
  }
}

/**
 * Mark everything as seen for the signed-in user.
 */
export async function markFeedSeen(): Promise<{ new_jobs: number; new_news: number }> {
  const res = await apiFetch(`${getApiBase()}/api/badge/seen`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`Failed to mark the feed as seen: ${res.status}`);
  }
  const json = await res.json();
  return { new_jobs: json.new_jobs ?? 0, new_news: json.new_news ?? 0 };
}

/**
 * Fetch trending keywords with week-over-week analysis.
 */
export async function fetchTrends(params?: {
  limit?: number;
}): Promise<{ data: Trend[]; meta: Record<string, unknown> }> {
  const limit = params?.limit ?? 20;
  const url = `${getApiBase()}/api/trends?limit=${limit}`;

  const res = await apiFetch(url, {
    next: { revalidate: 300 },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch trends: ${res.status} ${res.statusText}`);
  }

  const json = await res.json();
  return {
    data: (json.data as Trend[]) ?? [],
    meta: json.meta ?? {},
  };
}

/**
 * Fetch trend predictions (W+2, W+4) for keywords.
 */
export async function fetchTrendPredictions(): Promise<{ data: Array<{ keyword: string; current: number; w2: number | null; w4: number | null; confidence: number }>; meta: Record<string, unknown> }> {
  const url = `${getApiBase()}/api/trends/predictions`;
  const res = await apiFetch(url);
  if (!res.ok) throw new Error(`Failed to fetch trend predictions: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase 2: Intelligence & Personalization APIs
// ---------------------------------------------------------------------------

/**
 * Upload and analyze a resume. Returns ATS score, critical issues, suggested additions.
 */
export async function analyseResume(file: File): Promise<{
  ats_score: number;
  critical_issues: string[];
  missing_keywords: string[];
  suggested_additions: string[];
  resume_text_length: number;
}> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await apiFetch(`${getApiBase()}/api/resume/analyse`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload failed" }));
    if (error.code === "REANALYSIS_COOLDOWN") {
      throw Object.assign(new Error(`Re-analysis available in ${error.days_remaining} days`), {
        code: "REANALYSIS_COOLDOWN",
        days_remaining: error.days_remaining,
      });
    }
    if (res.status === 429 && error.retry_after) {
      throw Object.assign(new Error("Rate limit exceeded"), { retry_after: error.retry_after });
    }
    throw new Error(error.detail || `Upload failed: ${res.status}`);
  }

  return res.json();
}

/**
 * Fetch personalized digest with match percentages.
 */
export async function fetchDigest(params?: {
  skip?: number;
  limit?: number;
}): Promise<{
  data: Array<{
    id: string;
    headline: string;
    source: string;
    summary: string;
    category: string;
    readTime: string;
    score: number;
    match_percentage: number;
    featured: boolean;
  }>;
  meta: { total: number; skip: number; limit: number; has_more: boolean };
}> {
  const searchParams = new URLSearchParams();
  if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
  if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));

  const qs = searchParams.toString();
  const url = `${getApiBase()}/api/digest${qs ? `?${qs}` : ""}`;

  const res = await apiFetch(url, {
    next: { revalidate: 300 },
  });

  if (!res.ok) throw new Error(`Failed to fetch digest: ${res.status}`);
  return res.json();
}

/**
 * Fetch user profile from backend.
 */
export async function fetchProfile(): Promise<{
  id: string;
  name: string;
  email: string;
  roles: string[];
  experience_level: string;
  resume_text_length: number | null;
  ats_score: number | null;
  ats_critical_issues: string[];
  ats_missing_keywords: string[];
  ats_suggested_additions: string[];
  last_analysis_at: string | null;
  resume_path: string | null;
  preferences: Record<string, unknown>;
}> {
  const res = await apiFetch(`${getApiBase()}/api/profile`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch profile: ${res.status}`);
  return res.json();
}

/**
 * Update user profile on backend.
 */
export async function updateProfile(data: {
  name?: string;
  email?: string;
  roles?: string[];
  experience_level?: string;
  preferences?: Record<string, unknown>;
}): Promise<{ id: string }> {
  const res = await apiFetch(`${getApiBase()}/api/profile`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to update profile: ${res.status}`);
  return res.json();
}

/**
 * Fetch market observation from trends API.
 */
export async function fetchObservation(): Promise<{
  text: string;
  generated_at: string | null;
  fallback: boolean;
}> {
  const res = await apiFetch(`${getApiBase()}/api/observation`, {
    next: { revalidate: 3600 },
  });
  if (!res.ok) throw new Error(`Failed to fetch observation: ${res.status}`);
  return res.json();
}

/**
 * Get CSV file statistics.
 */
export async function getCsvStats(): Promise<{
  status: string;
  data: {
    jobs_csv_exists: boolean;
    company_csv_exists: boolean;
    jobs_count: number;
    companies_count: number;
    sample_jobs: Array<{
      title: string;
      company: string;
      location: string;
      apply_link: boolean;
    }>;
  };
}> {
  const res = await apiFetch(`${getApiBase()}/api/csv/stats`);
  if (!res.ok) throw new Error(`Failed to fetch CSV stats: ${res.status}`);
  return res.json();
}

// ============================================================================
// Q&A / Career Bot API
// ============================================================================

export interface QaProfile {
  has_profile: boolean;
  name?: string;
  roles: string[];
  experience_level: string;
  ats_score?: number;
  has_resume: boolean;
  suggested_skills: string[];
  missing_skills: string[];
}

export interface RoleMatch {
  role: string;
  match_percentage: number;
  job_count: number;
  skills: string[];
  why: string;
  locked: boolean;
}

export interface MarketVelocity {
  overall_velocity: number;
  skills: Array<{
    skill: string;
    demand_count: number;
    velocity: number;
    trend: string;
  }>;
  region: string;
  updated_at: string;
}

export interface NetworkInfluence {
  score: number;
  percentile: string;
  factors: Array<{
    name: string;
    value: string;
    description: string;
  }>;
}

export interface ActionRequired {
  actions: Array<{
    type: string;
    priority: string;
    title: string;
    description: string;
    action_text: string;
    link: string;
  }>;
}

/**
 * Get user profile for Q&A page.
 */
export async function fetchQaProfile(): Promise<QaProfile> {
  const res = await apiFetch(`${getApiBase()}/api/qa/profile`);
  if (!res.ok) throw new Error(`Failed to fetch Q&A profile: ${res.status}`);
  return res.json();
}

/**
 * Get job role matches based on user profile.
 */
export async function fetchRoleMatches(limit: number = 5): Promise<{
  matches: RoleMatch[];
  total_available: number;
}> {
  const res = await apiFetch(`${getApiBase()}/api/qa/matches?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch role matches: ${res.status}`);
  return res.json();
}

/**
 * Get market velocity for user's skills.
 */
export async function fetchMarketVelocity(): Promise<MarketVelocity> {
  const res = await apiFetch(`${getApiBase()}/api/qa/market-velocity`);
  if (!res.ok) throw new Error(`Failed to fetch market velocity: ${res.status}`);
  return res.json();
}

/**
 * Get network influence score.
 */
export async function fetchNetworkInfluence(): Promise<NetworkInfluence> {
  const res = await apiFetch(`${getApiBase()}/api/qa/network-influence`);
  if (!res.ok) throw new Error(`Failed to fetch network influence: ${res.status}`);
  return res.json();
}

/**
 * Get action items for user profile.
 */
export async function fetchActionRequired(): Promise<ActionRequired> {
  const res = await apiFetch(`${getApiBase()}/api/qa/action-required`);
  if (!res.ok) throw new Error(`Failed to fetch action required: ${res.status}`);
  return res.json();
}

/**
 * Chat with the career bot.
 */
export async function sendChatMessage(message: string): Promise<{
  response: string;
  timestamp: string;
}> {
  const res = await apiFetch(`${getApiBase()}/api/qa/chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`Failed to send chat message: ${res.status}`);
  return res.json();
}

// ============================================================================
// Scraper Status API
// ============================================================================

export interface ScraperStatus {
  scraper_id: string;
  name: string;
  is_active: boolean;
  progress_percentage: number;
  items_scraped: number;
  items_remaining: number;
  status: string;
  last_updated: string | null;
  next_run: string | null;
}

/**
 * Fetch real-time progress status for all HN scrapers.
 */
export async function fetchScraperStatus(): Promise<{ scrapers: ScraperStatus[] }> {
  const res = await apiFetch(`${getApiBase()}/api/scrapers/status`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to fetch scraper status: ${res.status}`);
  return res.json();
}
