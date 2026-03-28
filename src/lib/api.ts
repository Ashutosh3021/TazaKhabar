/**
 * TazaKhabar API client — replaces mock data with live backend calls.
 * @deprecated Data functions are now imported from this module.
 */
import type { DigestItem, Job, Trend } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

/**
 * Get user ID from localStorage profile.
 */
function getUserIdHeader(): Record<string, string> {
  const headers: Record<string, string> = {};
  if (typeof window !== "undefined") {
    try {
      const profile = localStorage.getItem("tazakhabar:userProfile");
      if (profile) {
        const parsed = JSON.parse(profile);
        if (parsed.id) headers["X-User-ID"] = parsed.id;
      }
    } catch {
      // ignore
    }
  }
  return headers;
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
}): Promise<{ data: Job[]; meta: { total: number; skip: number; limit: number; has_more: boolean } }> {
  const params: Record<string, unknown> = {};
  if (filters?.roles?.length) params.roles = filters.roles;
  if (filters?.remote) params.remote = filters.remote;
  if (filters?.startup_only) params.startup_only = filters.startup_only;
  if (filters?.skip !== undefined) params.skip = filters.skip;
  if (filters?.limit !== undefined) params.limit = filters.limit;

  const qs = buildQuery(params);
  const url = `${API_BASE}/api/jobs${qs}`;

  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    next: { revalidate: 300 },
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
  const url = `${API_BASE}/api/news${qs}`;

  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
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
 * Fetch badge counts (new items since last scrape).
 */
export async function fetchBadgeCounts(): Promise<{ radar_new_count: number; feed_new_count: number }> {
  try {
    const url = `${API_BASE}/api/badge`;
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });

    if (!res.ok) {
      throw new Error(`Failed to fetch badge counts: ${res.status}`);
    }

    const json = await res.json();
    return {
      radar_new_count: json.radar_new_count ?? 0,
      feed_new_count: json.feed_new_count ?? 0,
    };
  } catch {
    return { radar_new_count: 0, feed_new_count: 0 };
  }
}

/**
 * Fetch trending keywords with week-over-week analysis.
 */
export async function fetchTrends(params?: {
  limit?: number;
}): Promise<{ data: Trend[]; meta: Record<string, unknown> }> {
  const limit = params?.limit ?? 20;
  const url = `${API_BASE}/api/trends?limit=${limit}`;

  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
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
 * Trigger report refresh (swap Report 2 → Report 1).
 */
export async function triggerRefresh(): Promise<{ status: string; radar_new_count: number; feed_new_count: number }> {
  const url = `${API_BASE}/api/refresh`;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    throw new Error(`Failed to trigger refresh: ${res.status} ${res.statusText}`);
  }

  const json = await res.json();
  return {
    status: json.status ?? "swapped",
    radar_new_count: json.radar_new_count ?? 0,
    feed_new_count: json.feed_new_count ?? 0,
  };
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

  const res = await fetch(`${API_BASE}/api/resume/analyse`, {
    method: "POST",
    headers: getUserIdHeader(),
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
  const url = `${API_BASE}/api/digest${qs ? `?${qs}` : ""}`;

  const res = await fetch(url, {
    headers: { ...getUserIdHeader(), "Content-Type": "application/json" },
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
  resume_text: string | null;
  ats_score: number | null;
  ats_critical_issues: string[];
  ats_missing_keywords: string[];
  ats_suggested_additions: string[];
  last_analysis_at: string | null;
  preferences: Record<string, unknown>;
}> {
  const res = await fetch(`${API_BASE}/api/profile`, {
    headers: { ...getUserIdHeader(), "Content-Type": "application/json" },
  });
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
  const res = await fetch(`${API_BASE}/api/profile`, {
    method: "POST",
    headers: { ...getUserIdHeader(), "Content-Type": "application/json" },
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
  const res = await fetch(`${API_BASE}/api/observation`, {
    headers: { "Content-Type": "application/json" },
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
  const res = await fetch(`${API_BASE}/api/csv/stats`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`Failed to fetch CSV stats: ${res.status}`);
  return res.json();
}

/**
 * Load jobs from CSV into the database.
 */
export async function loadJobsFromCsv(
  limit: number = 100,
  clearExisting: boolean = false
): Promise<{
  status: string;
  message: string;
  data: {
    success: number;
    errors: string[];
    total: number;
  };
}> {
  const res = await fetch(
    `${API_BASE}/api/csv/load-jobs?limit=${limit}&clear_existing=${clearExisting}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    }
  );
  if (!res.ok) throw new Error(`Failed to load CSV jobs: ${res.status}`);
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
  const res = await fetch(`${API_BASE}/api/qa/profile`, {
    headers: { ...getUserIdHeader(), "Content-Type": "application/json" },
  });
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
  const res = await fetch(`${API_BASE}/api/qa/matches?limit=${limit}`, {
    headers: { ...getUserIdHeader(), "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`Failed to fetch role matches: ${res.status}`);
  return res.json();
}

/**
 * Get market velocity for user's skills.
 */
export async function fetchMarketVelocity(): Promise<MarketVelocity> {
  const res = await fetch(`${API_BASE}/api/qa/market-velocity`, {
    headers: { ...getUserIdHeader(), "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`Failed to fetch market velocity: ${res.status}`);
  return res.json();
}

/**
 * Get network influence score.
 */
export async function fetchNetworkInfluence(): Promise<NetworkInfluence> {
  const res = await fetch(`${API_BASE}/api/qa/network-influence`, {
    headers: { ...getUserIdHeader(), "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`Failed to fetch network influence: ${res.status}`);
  return res.json();
}

/**
 * Get action items for user profile.
 */
export async function fetchActionRequired(): Promise<ActionRequired> {
  const res = await fetch(`${API_BASE}/api/qa/action-required`, {
    headers: { ...getUserIdHeader(), "Content-Type": "application/json" },
  });
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
  const res = await fetch(`${API_BASE}/api/qa/chat`, {
    method: "POST",
    headers: { ...getUserIdHeader(), "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`Failed to send chat message: ${res.status}`);
  return res.json();
}
