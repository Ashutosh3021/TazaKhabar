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
    // Next.js caching: revalidate every 5 minutes
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
      // Poll every 5 minutes, don't cache
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
    // Return zeros on error to avoid breaking the UI
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
    // Cache for 5 minutes
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
