"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import MoodGauge from "@/components/MoodGauge";
import { fetchTrends, fetchObservation, fetchTrendPredictions } from "@/lib/api";
import type { Trend } from "@/types";

export default function TrendsPage() {
  const [trends, setTrends] = useState<Trend[]>([]);
  const [observation, setObservation] = useState<{
    text: string;
    generated_at: string | null;
    fallback: boolean;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [trendsRes, obsRes, predsRes] = await Promise.all([
          fetchTrends({ limit: 20 }),
          fetchObservation(),
          fetchTrendPredictions(),
        ]);

        const predsMap = new Map<string, any>();
        predsRes.data.forEach((p: any) => predsMap.set(p.keyword.toLowerCase(), p));

        const merged = trendsRes.data.map((t) => {
          const key = (t.skill || t.skill || "").toLowerCase();
          const p = predsMap.get(key);
          return { ...t, prediction: p };
        });

        if (!cancelled) {
          setTrends(merged);
          setObservation(obsRes);
        }
      } catch {
        // show empty on error
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const avgChange =
    trends.length > 0 ? trends.reduce((acc, t) => acc + t.weeklyChange, 0) / trends.length : 0;
  const topSkill = trends[0]?.skill ?? "N/A";
  const moodScore = Math.round(
    trends.length > 0 ? trends.reduce((acc, t) => acc + t.percentage, 0) / trends.length : 0,
  );
  const moodLabel =
    avgChange >= 3 ? "Cautiously optimistic" : avgChange <= 0 ? "Neutral signal" : "Tightening grip";
  const moodStatus: "up" | "flat" | "down" =
    avgChange >= 3 ? "up" : avgChange <= 0 ? "flat" : "down";
  const booming = trends.filter((t) => t.weeklyChange > 20).slice(0, 4);
  const declining = trends.filter((t) => t.weeklyChange < -20).slice(0, 3);

  return (
    <AppShell>
      <div className="space-y-10">
        <header>
          <p className="mono-label text-primary">04 / Trend board</p>
          <h1 className="display mt-3 text-[clamp(2rem,1.3rem+2.8vw,3.25rem)]" data-split="lines" data-intro>
            Market <span className="accent">trends.</span>
          </h1>
          <p className="mono-label mt-4 text-dim-text">
            99 keywords tracked · week over week deltas
          </p>
        </header>

        {/* Observation block: market intelligence reading */}
        {loading ? (
          <div className="panel p-6 md:p-8" aria-hidden>
            <div className="tk-skel h-3 w-[180px]" />
            <div className="tk-skel mt-5 h-4 w-full" />
            <div className="tk-skel mt-3 h-4 w-3/4" />
          </div>
        ) : observation && !observation.fallback && observation.text ? (
          <section className="panel panel--accent p-6 md:p-8" data-reveal="up">
            <div className="flex items-center gap-3">
              <span className="lamp lamp--live" aria-hidden />
              <p className="mono-label text-primary">Market intelligence</p>
              {observation.generated_at && (
                <span className="mono-label text-dim-text">
                  · {new Date(observation.generated_at).toLocaleDateString()}
                </span>
              )}
            </div>
            <p className="display mt-5 max-w-[70ch] text-[clamp(1.1rem,1rem+1vw,1.6rem)] leading-relaxed text-neutral-beige">
              {observation.text}
            </p>
          </section>
        ) : !loading ? (
          <section className="panel p-6">
            <p className="mono-label text-dim-text">
              Market intelligence · first analysis generates after the scheduler runs at
              midnight UTC.
            </p>
          </section>
        ) : null}

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Key readouts">
          <StatCard label="Hiring velocity" value={`${avgChange >= 0 ? "+" : ""}${avgChange.toFixed(1)}%`} tone="primary" />
          <StatCard label="Top skill of week" value={topSkill} tone="neutral" />
          <StatCard
            label="Layoff signal"
            value={avgChange >= 2 ? "Low risk" : "Elevated"}
            tone={avgChange >= 2 ? "ok" : "primary"}
          />
        </section>

        <section className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          <div className="space-y-5">
            <h2 className="mono-label flex items-center gap-3 text-primary">
              <span className="lamp lamp--live" aria-hidden />
              Booming roles
            </h2>
            <div className="space-y-3">
              {booming.length > 0 ? (
                booming.map((t) => <TrendBarRow key={t.skill} t={t} />)
              ) : (
                <p className="mono-label text-dim-text">
                  Trends are being computed. Check back after your first scrape cycle.
                </p>
              )}
            </div>
          </div>

          <div className="space-y-5">
            <h2 className="mono-label flex items-center gap-3 text-primary">
              <span className="lamp lamp--ok" aria-hidden />
              Declining roles
            </h2>
            <div className="space-y-3">
              {declining.length > 0 ? (
                declining.map((t) => <TrendBarRow key={t.skill} t={t} />)
              ) : (
                <p className="mono-label text-dim-text">
                  No declining roles detected this week.
                </p>
              )}
            </div>
          </div>
        </section>

        {/* Signature moment: the market mood gauge */}
        <section aria-label="Market mood index">
          <MoodGauge score={moodScore} label={moodLabel} status={moodStatus} />
        </section>
      </div>
    </AppShell>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "primary" | "neutral" | "ok";
}) {
  const toneCls =
    tone === "primary" ? "text-primary" : tone === "ok" ? "text-signal" : "text-neutral-beige";
  return (
    <div className="panel p-5" data-reveal="up">
      <p className="mono-label text-dim-text">{label}</p>
      <p className={`display mt-4 break-words text-[clamp(1.4rem,1.1rem+1.6vw,2rem)] ${toneCls}`}>
        {value}
      </p>
      <div className="tick-rule mt-5 h-[6px] opacity-70" aria-hidden />
    </div>
  );
}

function TrendBarRow({ t }: { t: Trend }) {
  const isBooming = t.weeklyChange > 20 || t.direction === "booming";
  const isDeclining = t.weeklyChange < -20 || t.direction === "declining";
  const fillCls = isDeclining ? "meter__fill--muted" : isBooming ? "meter__fill--ok" : "";

  return (
    <div className="panel p-4" data-reveal="up">
      <div className="flex items-center gap-4">
        <div className="w-[140px] shrink-0 md:w-[180px]">
          <p className="mono-label truncate text-neutral-beige/90">{t.skill}</p>
        </div>
        <div className="min-w-0 flex-1">
          <div className="meter" aria-hidden>
            <div className={`meter__fill ${fillCls}`} style={{ width: `${t.percentage}%` }} />
          </div>
          {t.prediction && (
            <div className="mt-2 flex items-center gap-3 text-[11px] text-dim-text">
              <span className="mono-label">W+2: {t.prediction.w2 ?? "n/a"}</span>
              <span className="mono-label">W+4: {t.prediction.w4 ?? "n/a"}</span>
              <span className="mono-label ml-auto">
                conf {(t.prediction.confidence ?? 0).toFixed(2)}
              </span>
            </div>
          )}
        </div>
        <div className="w-[76px] shrink-0 text-right">
          <p className="mono-data text-[13px] text-primary">{t.percentage}%</p>
          <p className="mono-label mt-1 text-[10px] text-dim-text">
            {t.weeklyChange >= 0 ? "+" : ""}
            {t.weeklyChange.toFixed(0)}w
          </p>
        </div>
      </div>
    </div>
  );
}
