"use client";

/**
 * ScraperStatusPanel
 *
 * Displays real-time progress bars for all HN scrapers.
 * Polls GET /api/scrapers/status every 10 seconds while any scraper is active,
 * and every 60 seconds otherwise.
 *
 * Usage:
 *   import ScraperStatusPanel from "@/components/ScraperStatusPanel";
 *   <ScraperStatusPanel />
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchScraperStatus, type ScraperStatus } from "@/lib/api";

// ----------------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------------

function formatTimestamp(iso: string | null): string {
  if (!iso) return "Never";
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function statusColor(status: string): string {
  switch (status) {
    case "running":
      return "text-blue-400";
    case "completed":
      return "text-green-400";
    case "failed":
      return "text-red-400";
    default:
      return "text-zinc-500";
  }
}

function barColor(status: string, pct: number): string {
  if (status === "failed") return "bg-red-500";
  if (status === "running") return "bg-blue-500";
  if (pct === 100) return "bg-green-500";
  return "bg-zinc-500";
}

// ----------------------------------------------------------------------------
// Sub-component: single scraper row
// ----------------------------------------------------------------------------

function ScraperRow({ s }: { s: ScraperStatus }) {
  const pct = Math.max(0, Math.min(100, s.progress_percentage));

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800/60 p-4 space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {/* Active pulse indicator */}
          {s.is_active ? (
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-500" />
            </span>
          ) : (
            <span className={`inline-flex h-2.5 w-2.5 rounded-full ${s.status === "completed" ? "bg-green-500" : s.status === "failed" ? "bg-red-500" : "bg-zinc-600"}`} />
          )}
          <span className="font-medium text-sm text-zinc-100">{s.name}</span>
        </div>

        <span className={`text-xs font-semibold uppercase tracking-wide ${statusColor(s.status)}`}>
          {s.status === "never_run" ? "never run" : s.status}
        </span>
      </div>

      {/* Progress bar */}
      <div
        className="relative w-full h-2 rounded-full bg-zinc-700 overflow-hidden"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${s.name} progress`}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor(s.status, pct)} ${s.is_active ? "animate-pulse" : ""}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Stats row */}
      <div className="flex items-center justify-between text-xs text-zinc-400">
        <span>
          <span className="text-zinc-200 font-medium">{s.items_scraped.toLocaleString()}</span> scraped
          {s.items_remaining > 0 && (
            <> &middot; <span className="text-zinc-200 font-medium">{s.items_remaining.toLocaleString()}</span> remaining</>
          )}
        </span>
        <span className="font-semibold text-zinc-300">{pct}%</span>
      </div>

      {/* Timestamps */}
      <div className="flex items-center justify-between text-xs text-zinc-500">
        <span>Last run: {formatTimestamp(s.last_updated)}</span>
        {s.next_run && <span>Next: {formatTimestamp(s.next_run)}</span>}
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Main component
// ----------------------------------------------------------------------------

export default function ScraperStatusPanel() {
  const [scrapers, setScrapers] = useState<ScraperStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchScraperStatus();
      setScrapers(data.scrapers);
      setError(null);
      setLastRefreshed(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load scraper status");
    } finally {
      setLoading(false);
    }
  }, []);

  // Schedule next poll: 10 s if anything is active, 60 s otherwise
  const scheduleNext = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    const anyActive = scrapers.some((s) => s.is_active);
    timerRef.current = setTimeout(() => {
      load().then(scheduleNext);
    }, anyActive ? 10_000 : 60_000);
  }, [scrapers, load]);

  useEffect(() => {
    load().then(scheduleNext);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-schedule whenever scrapers list changes
  useEffect(() => {
    scheduleNext();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [scheduleNext]);

  return (
    <section aria-label="Scraper status" className="space-y-3">
      {/* Panel header */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-100">Scraper Status</h2>
        <div className="flex items-center gap-3">
          {lastRefreshed && (
            <span className="text-xs text-zinc-500">
              Updated {formatTimestamp(lastRefreshed.toISOString())}
            </span>
          )}
          <button
            onClick={() => load()}
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            aria-label="Refresh scraper status"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* States */}
      {loading && scrapers.length === 0 && (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-lg border border-zinc-700 bg-zinc-800/60 p-4 animate-pulse h-24" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-700/50 bg-red-900/20 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {!loading && !error && scrapers.length === 0 && (
        <p className="text-sm text-zinc-500">No scraper data available.</p>
      )}

      {scrapers.map((s) => (
        <ScraperRow key={s.scraper_id} s={s} />
      ))}
    </section>
  );
}
