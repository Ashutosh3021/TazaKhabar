"use client";

/**
 * ScraperStatusPanel
 *
 * Displays real-time progress gauges for all HN scrapers.
 * Polls GET /api/scrapers/status every 10 seconds while any scraper is active,
 * and every 60 seconds otherwise.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
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

function statusTone(status: string): string {
  switch (status) {
    case "running":
      return "text-primary";
    case "completed":
      return "text-signal";
    case "failed":
      return "text-primary";
    default:
      return "text-dim-text";
  }
}

function meterToneClass(status: string, pct: number): string {
  if (status === "failed") return "";
  if (status === "running") return "meter__fill--pulse";
  if (pct === 100) return "meter__fill--ok";
  return "meter__fill--muted";
}

function lampTone(s: ScraperStatus): string {
  if (s.is_active) return "lamp--live";
  if (s.status === "completed") return "lamp--ok";
  if (s.status === "failed") return "lamp--live";
  return "lamp--off";
}

// ----------------------------------------------------------------------------
// Sub-component: single scraper row
// ----------------------------------------------------------------------------

function ScraperRow({ s }: { s: ScraperStatus }) {
  const pct = Math.max(0, Math.min(100, s.progress_percentage));

  return (
    <div className="panel space-y-3 p-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-3">
          <span className={`lamp ${lampTone(s)}`} aria-hidden />
          <span className="mono-label truncate text-neutral-beige">{s.name}</span>
        </div>
        <span className={`mono-label shrink-0 ${statusTone(s.status)}`}>
          {s.status === "never_run" ? "never run" : s.status}
        </span>
      </div>

      {/* Progress gauge */}
      <div
        className="meter"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${s.name} progress`}
      >
        <div
          className={`meter__fill ${meterToneClass(s.status, pct)} ${s.is_active ? "meter__fill--pulse" : ""}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Stats row */}
      <div className="flex items-center justify-between">
        <span className="mono-label text-dim-text">
          <span className="mono-data text-[11px] text-neutral-beige">
            {s.items_scraped.toLocaleString()}
          </span>{" "}
          scraped
          {s.items_remaining > 0 && (
            <>
              {" "}
              ·{" "}
              <span className="mono-data text-[11px] text-neutral-beige">
                {s.items_remaining.toLocaleString()}
              </span>{" "}
              remaining
            </>
          )}
        </span>
        <span className="mono-data text-[11px] text-primary">{pct}%</span>
      </div>

      {/* Timestamps */}
      <div className="scribe flex items-center justify-between pt-3">
        <span className="mono-label text-dim-text">
          Last run {formatTimestamp(s.last_updated)}
        </span>
        {s.next_run && (
          <span className="mono-label text-dim-text">
            Next {formatTimestamp(s.next_run)}
          </span>
        )}
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
      <div className="flex items-center justify-between gap-3">
        <span className="plate-label">Scraper status</span>
        <div className="flex items-center gap-4">
          {lastRefreshed && (
            <span className="mono-label hidden text-dim-text sm:inline">
              Updated {formatTimestamp(lastRefreshed.toISOString())}
            </span>
          )}
          <button
            type="button"
            onClick={() => load()}
            className="btn !px-3 !py-2"
            aria-label="Refresh scraper status"
          >
            <Icon name="refresh" className="text-[15px]" aria-hidden />
            Refresh
          </button>
        </div>
      </div>

      {/* States */}
      {loading && scrapers.length === 0 && (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="panel h-24 p-4" aria-hidden>
              <div className="tk-skel h-3 w-[140px]" />
              <div className="tk-skel mt-4 h-[10px] w-full" />
              <div className="tk-skel mt-4 h-3 w-[200px]" />
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="panel panel--accent p-4 text-primary" role="alert">
          <p className="mono-label">{error}</p>
        </div>
      )}

      {!loading && !error && scrapers.length === 0 && (
        <p className="mono-label text-dim-text">No scraper data available.</p>
      )}

      {scrapers.map((s) => (
        <ScraperRow key={s.scraper_id} s={s} />
      ))}
    </section>
  );
}
