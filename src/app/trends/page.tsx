import AppShell from "@/components/AppShell";
import { fetchTrends } from "@/lib/api";
import type { Trend } from "@/types";

export default async function TrendsPage() {
  // Fetch live trends data from API
  let trends: Trend[] = [];
  let meta: Record<string, unknown> = {};
  
  try {
    const response = await fetchTrends({ limit: 20 });
    trends = response.data;
    meta = response.meta;
  } catch {
    // If API fails, show empty state (no mock fallback per TRND-07)
    trends = [];
  }

  const avgChange = trends.length > 0
    ? trends.reduce((acc, t) => acc + t.weeklyChange, 0) / trends.length
    : 0;
  const topSkill = trends[0]?.skill ?? "N/A";

  const moodScore = Math.round(
    trends.length > 0
      ? trends.reduce((acc, t) => acc + t.percentage, 0) / trends.length
      : 0,
  );

  const moodLabel =
    avgChange >= 3 ? "CAUTIOUSLY_OPTIMISTIC" : avgChange <= 0
      ? "NEUTRAL_SIGNAL"
      : "TIGHTENING_GRIP";

  // Split booming and declining from live data
  const booming = trends.filter(t => t.weeklyChange > 20).slice(0, 4);
  const declining = trends.filter(t => t.weeklyChange < -20).slice(0, 3);

  return (
    <AppShell>
      <div className="space-y-10">
        <header className="pt-6">
          <h1 className="font-serif text-4xl md:text-6xl font-black leading-tight">
            Market{" "}
            <span className="text-primary italic font-black">Trends.</span>
          </h1>
        </header>

        <section className="flex gap-4 overflow-x-auto pb-2">
          <StatCard
            label="HIRING_VELOCITY"
            value={`${avgChange >= 0 ? "+" : ""}${avgChange.toFixed(1)}%`}
            accent="primary"
          />
          <StatCard
            label="TOP_SKILL_OF_WEEK"
            value={topSkill}
            accent="neutral"
          />
          <StatCard
            label="LAYOFF_SIGNAL"
            value={avgChange >= 2 ? "LOW_RISK" : "ELEVATED"}
            accent={avgChange >= 2 ? "success" : "primary"}
          />
        </section>

        <section className="space-y-10">
          <div className="space-y-6">
            <h2 className="flex items-center gap-3 mono-label text-[11px] tracking-[0.2em] text-primary uppercase">
              <span className="tazakhabar-live-dot" />
              BOOMING ROLES →
            </h2>

            <div className="space-y-4">
              {booming.map((t) => (
                <TrendBarRow key={t.skill} t={t} />
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <h2 className="flex items-center gap-3 mono-label text-[11px] tracking-[0.2em] text-primary uppercase">
              <span className="tazakhabar-live-dot" />
              DECLINING ROLES →
            </h2>

            <div className="space-y-4">
              {declining.map((t) => (
                <TrendBarRow key={t.skill} t={t} />
              ))}
            </div>
          </div>
        </section>

        <section className="space-y-6">
          <div className="flex items-end justify-between gap-4">
            <h2 className="mono-label text-[11px] tracking-[0.2em] text-primary uppercase">
              SIGNAL LOG
            </h2>
          </div>

          <div className="space-y-4">
            {/* Signals from trend data will be shown in Phase 2 UI */}
            {/* For now, show placeholder cards */}
            {booming.length === 0 && declining.length === 0 && (
              <p className="mono-label text-[11px] text-dim-text uppercase">
                Trends are being computed. Check back after your first scrape cycle.
              </p>
            )}
          </div>
        </section>

        <section>
          <div className="brutalist-border bg-card-dark p-8 relative overflow-hidden">
            <div className="mono-label text-[10px] text-dim-text uppercase tracking-[0.2em]">
              MARKET MOOD INDEX
            </div>
            <div className="mt-4 flex items-end justify-between gap-6">
              <div>
                <div className="font-serif text-7xl font-black text-primary leading-none italic">
                  {moodScore}
                </div>
                <div className="mono-label text-[12px] text-neutral-beige mt-2 uppercase">
                  {moodLabel}
                </div>
              </div>
              <div className="hidden md:block text-right">
                <p className="mono-label text-[10px] text-dim-text uppercase tracking-[0.2em]">
                  ANALYTICS SNAPSHOT
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: "primary" | "neutral" | "success";
}) {
  const accentCls =
    accent === "primary"
      ? "text-primary"
      : accent === "success"
        ? "text-success-glow"
        : "text-neutral-beige";
  const borderCls =
    accent === "success"
      ? "border-success-glow/60"
      : accent === "primary"
        ? "border-primary/60"
        : "border-border-dark";

  return (
    <div className={`min-w-[240px] brutalist-border bg-card-dark p-6 ${borderCls}`}>
      <p className="mono-label text-[10px] text-dim-text uppercase tracking-[0.2em]">
        {label}
      </p>
      <div className={`mt-5 font-serif text-3xl font-black ${accentCls} leading-tight`}>
        {value}
      </div>
    </div>
  );
}

function TrendBarRow({ t }: { t: Trend }) {
  return (
    <div
      className="flex items-center gap-4 border border-border-dark bg-card-dark p-4"
    >
      <div className="w-[180px] shrink-0">
        <p className="mono-label text-[11px] text-neutral-beige/90 uppercase">
          {t.skill}
        </p>
      </div>

      <div className="flex-1">
        <div className="h-3 bg-neutral-border relative overflow-hidden">
          <div className="h-full bg-primary" style={{ width: `${t.percentage}%` }} />
        </div>
      </div>

      <div className="w-[90px] text-right">
        <p className="mono-label text-[11px] text-primary">
          {t.percentage}%
        </p>
        <p className="mono-label text-[10px] text-dim-text">
          {t.weeklyChange >= 0 ? "+" : ""}
          {t.weeklyChange.toFixed(0)}w
        </p>
      </div>
    </div>
  );
}

