"use client";

import { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import { useTaza } from "@/components/TazaContext";
import { fetchJobs } from "@/lib/api";
import type { LocationType, Job } from "@/types";

const ROLE_CHIPS = [
  "Frontend Dev",
  "Backend Dev",
  "Full Stack",
  "Data Engineer",
  "ML Engineer",
  "DevOps/SRE",
  "Product Manager",
  "Mobile Dev",
  "QA Engineer",
  "Security",
  "Cloud Architect",
  "Data Analyst",
] as const;

const LOCATION_OPTIONS: LocationType[] = ["Remote", "Hybrid", "On-site"];
const EXPERIENCE_OPTIONS = ["I", "II", "III", "IV"] as const;

export default function JobsPage() {
  const {
    savedJobs,
    toggleSavedJob,
    activeFilters,
    setActiveFilters,
    radarNewCount,
    refreshRadar,
    isFetchingRadar,
    radarVersion,
  } = useTaza();

  const [jobs, setJobs] = useState<Job[]>([]);
  const [apiError, setApiError] = useState<string | null>(null);
  const [experienceFilter, setExperienceFilter] = useState<
    (typeof EXPERIENCE_OPTIONS)[number] | ""
  >("");
  const [tab, setTab] = useState<"ALL" | "SAVED" | "APPLIED">("ALL");
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  // Fetch jobs from live API when version changes or filters change
  useEffect(() => {
    let cancelled = false;
    async function loadJobs() {
      try {
        const result = await fetchJobs({
          roles: activeFilters.roles,
          remote: activeFilters.location === "Remote",
          skip: 0,
          limit: 50,
        });
        if (!cancelled) {
          setJobs(result.data);
          setApiError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setApiError(err instanceof Error ? err.message : "Failed to load jobs");
          setJobs([]);
        }
      }
    }
    loadJobs();
    return () => { cancelled = true; };
  }, [radarVersion, activeFilters.roles, activeFilters.location]);

  const companySizes = useMemo(() => {
    const set = new Set(jobs.map((j) => j.companySize));
    return Array.from(set);
  }, [jobs]);

  const rotatedJobs = useMemo(() => {
    const shift = radarVersion % jobs.length;
    return [...jobs.slice(shift), ...jobs.slice(0, shift)];
  }, [radarVersion, jobs]);

  const filteredJobs = useMemo(() => {
    const roleFiltered = activeFilters.roles.length
      ? rotatedJobs.filter((j) => activeFilters.roles.includes(j.role))
      : rotatedJobs;

    const locationFiltered = activeFilters.location
      ? roleFiltered.filter((j) => j.locationType === activeFilters.location)
      : roleFiltered;

    const companyFiltered = activeFilters.companySize.length
      ? locationFiltered.filter((j) =>
          activeFilters.companySize.includes(j.companySize),
        )
      : locationFiltered;

    const experienceFiltered = experienceFilter
      ? companyFiltered.filter((j) => j.experienceTier === experienceFilter)
      : companyFiltered;

    const tabFiltered =
      tab === "SAVED"
        ? experienceFiltered.filter((j) => savedJobs.includes(j.id))
        : tab === "APPLIED"
          ? experienceFiltered.filter((j) => j.applied)
          : experienceFiltered;

    return tabFiltered;
  }, [
    activeFilters.companySize,
    activeFilters.location,
    activeFilters.roles,
    experienceFilter,
    savedJobs,
    tab,
    rotatedJobs,
    jobs,
  ]);

  const countJobsForRole = (role: string) => {
    const roleFiltered = rotatedJobs.filter((j) => j.role === role);

    const locationFiltered = activeFilters.location
      ? roleFiltered.filter((j) => j.locationType === activeFilters.location)
      : roleFiltered;

    const companyFiltered = activeFilters.companySize.length
      ? locationFiltered.filter((j) =>
          activeFilters.companySize.includes(j.companySize),
        )
      : locationFiltered;

    const experienceFiltered = experienceFilter
      ? companyFiltered.filter((j) => j.experienceTier === experienceFilter)
      : companyFiltered;

    const tabFiltered =
      tab === "SAVED"
        ? experienceFiltered.filter((j) => savedJobs.includes(j.id))
        : tab === "APPLIED"
          ? experienceFiltered.filter((j) => j.applied)
          : experienceFiltered;

    return tabFiltered.length;
  };

  function toggleRole(role: string) {
    const has = activeFilters.roles.includes(role);
    setActiveFilters({
      ...activeFilters,
      roles: has ? activeFilters.roles.filter((r) => r !== role) : [...activeFilters.roles, role],
    });
  }

  function toggleCompanySize(size: string) {
    const has = activeFilters.companySize.includes(size);
    setActiveFilters({
      ...activeFilters,
      companySize: has
        ? activeFilters.companySize.filter((s) => s !== size)
        : [...activeFilters.companySize, size],
    });
  }

  function clearFilters() {
    setActiveFilters({ roles: [], location: "", companySize: [] });
    setExperienceFilter("");
    setTab("ALL");
  }

  return (
    <AppShell>
      {radarNewCount > 0 ? (
        <button
          type="button"
          onClick={() => refreshRadar()}
          className="-mx-6 md:-mx-20 h-[36px] w-[calc(100%+48px)] md:w-[calc(100%+160px)] bg-[#FF2D00] text-[#0E0E0E] flex items-center justify-center relative z-10"
        >
          <span className="font-mono text-[10px] font-bold uppercase tracking-[2px]">
            NEW DATA AVAILABLE — TAP TO REFRESH
          </span>
          <span className="absolute right-4 text-[#0E0E0E] font-mono text-[14px]">
            ↑
          </span>
        </button>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 md:gap-8">
        {/* Desktop sidebar */}
        <aside className="hidden md:block md:col-span-3 lg:col-span-3">
          <div className="brutalist-border bg-card-dark p-5 space-y-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="mono-label text-[10px] text-primary">
                  FILTERS
                </p>
                <p className="mono-label text-[10px] text-dim-text mt-2">
                  LIVE
                </p>
              </div>
              <button
                type="button"
                onClick={clearFilters}
                className="mono-label text-[10px] text-dim-text hover:text-neutral-beige"
              >
                RESET
              </button>
            </div>

            {/* Role filter */}
            <section className="space-y-3">
              <p className="mono-label text-[10px] text-dim-text">ROLE</p>
              <div className="flex flex-col gap-2">
                {ROLE_CHIPS.map((r) => {
                  const checked = activeFilters.roles.includes(r);
                  const matches = checked ? countJobsForRole(r) : 0;
                  return (
                    <label
                      key={r}
                      className="flex items-center gap-2 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleRole(r)}
                        className="accent-primary"
                      />
                      <span className="flex items-center gap-[6px]">
                        <span className="mono-label text-[11px] text-neutral-beige/90">
                          {r}
                        </span>
                        {checked ? (
                          <span
                            className="mono-label text-[10px]"
                            style={{ color: matches === 0 ? "#444" : "#FF2D00" }}
                          >
                            {matches}
                          </span>
                        ) : null}
                      </span>
                    </label>
                  );
                })}
              </div>
            </section>

            {/* Experience Level */}
            <section className="space-y-3">
              <p className="mono-label text-[10px] text-dim-text">
                EXPERIENCE LEVEL
              </p>
              <div className="flex flex-col gap-2">
                <label className="flex items-center justify-between gap-3 cursor-pointer">
                  <span className="mono-label text-[11px] text-neutral-beige/90">
                    Any
                  </span>
                  <input
                    type="radio"
                    checked={experienceFilter === ""}
                    onChange={() => setExperienceFilter("")}
                    name="exp"
                    className="accent-primary"
                  />
                </label>
                {EXPERIENCE_OPTIONS.map((t) => (
                  <label
                    key={t}
                    className="flex items-center justify-between gap-3 cursor-pointer"
                  >
                    <span className="mono-label text-[11px] text-neutral-beige/90">
                      {t}
                    </span>
                    <input
                      type="radio"
                      checked={experienceFilter === t}
                      onChange={() => setExperienceFilter(t)}
                      name="exp"
                      className="accent-primary"
                    />
                  </label>
                ))}
              </div>
            </section>

            {/* Location */}
            <section className="space-y-3">
              <p className="mono-label text-[10px] text-dim-text">LOCATION</p>
              <div className="flex flex-col gap-2">
                <label className="flex items-center justify-between gap-3 cursor-pointer">
                  <span className="mono-label text-[11px] text-neutral-beige/90">
                    Any
                  </span>
                  <input
                    type="radio"
                    checked={activeFilters.location === ""}
                    onChange={() => setActiveFilters({ ...activeFilters, location: "" })}
                    name="loc"
                    className="accent-primary"
                  />
                </label>
                {LOCATION_OPTIONS.map((loc) => (
                  <label
                    key={loc}
                    className="flex items-center justify-between gap-3 cursor-pointer"
                  >
                    <span className="mono-label text-[11px] text-neutral-beige/90">
                      {loc}
                    </span>
                    <input
                      type="radio"
                      checked={activeFilters.location === loc}
                      onChange={() =>
                        setActiveFilters({ ...activeFilters, location: loc })
                      }
                      name="loc"
                      className="accent-primary"
                    />
                  </label>
                ))}
              </div>
            </section>

            {/* Company size */}
            <section className="space-y-3">
              <p className="mono-label text-[10px] text-dim-text">COMPANY SIZE</p>
              <div className="flex flex-wrap gap-2">
                {companySizes.map((s) => {
                  const selected = activeFilters.companySize.includes(s);
                  return (
                    <button
                      key={s}
                      type="button"
                      onClick={() => toggleCompanySize(s)}
                      className={`px-3 py-2 mono-label text-[10px] uppercase tracking-[0.05em] brutalist-border ${
                        selected
                          ? "brutalist-border-primary bg-[rgba(255,45,0,0.1)]"
                          : "bg-card-dark hover:bg-primary/10"
                      }`}
                    >
                      {s}
                    </button>
                  );
                })}
              </div>
            </section>

            {/* Salary range slider placeholder */}
            <section className="space-y-3">
              <p className="mono-label text-[10px] text-dim-text">
                SALARY RANGE
              </p>
              <div className="space-y-3">
                <input
                  type="range"
                  min={0}
                  max={100}
                  defaultValue={40}
                  disabled
                  className="w-full accent-primary opacity-50"
                />
                <p className="mono-label text-[10px] text-dim-text uppercase tracking-[0.05em]">
                  placeholder slider
                </p>
              </div>
            </section>
          </div>
        </aside>

        {/* Mobile filters */}
        <div className="md:hidden col-span-1">
          <button
            type="button"
            onClick={() => setMobileFiltersOpen(true)}
            className="brutalist-border-primary bg-primary/10 px-4 py-3 w-full mono-label text-[11px] uppercase tracking-[0.05em]"
          >
            OPEN FILTERS
          </button>
          {mobileFiltersOpen ? (
            <div className="fixed inset-0 z-[60] bg-black/70 p-4">
              <div className="brutalist-border bg-card-dark p-5 h-full overflow-auto">
                <div className="flex items-center justify-between mb-4">
                  <p className="mono-label text-[10px] text-primary">
                    FILTERS
                  </p>
                  <button
                    type="button"
                    onClick={() => setMobileFiltersOpen(false)}
                    className="mono-label text-[10px] text-dim-text"
                  >
                    CLOSE
                  </button>
                </div>
                {/* Reuse sidebar content via quick inline call */}
                <div className="space-y-6">
                  <div className="space-y-3">
                    <p className="mono-label text-[10px] text-dim-text">ROLE</p>
                    <div className="flex flex-col gap-2">
                      {ROLE_CHIPS.map((r) => {
                        const checked = activeFilters.roles.includes(r);
                        const matches = checked ? countJobsForRole(r) : 0;
                        return (
                          <label
                            key={r}
                            className="flex items-center gap-2 cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleRole(r)}
                              className="accent-primary"
                            />
                            <span className="flex items-center gap-[6px]">
                              <span className="mono-label text-[11px] text-neutral-beige/90">
                                {r}
                              </span>
                              {checked ? (
                                <span
                                  className="mono-label text-[10px]"
                                  style={{
                                    color: matches === 0 ? "#444" : "#FF2D00",
                                  }}
                                >
                                  {matches}
                                </span>
                              ) : null}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <p className="mono-label text-[10px] text-dim-text">
                      EXPERIENCE LEVEL
                    </p>
                    <div className="flex flex-col gap-2">
                      <label className="flex items-center justify-between gap-3 cursor-pointer">
                        <span className="mono-label text-[11px] text-neutral-beige/90">
                          Any
                        </span>
                        <input
                          type="radio"
                          checked={experienceFilter === ""}
                          onChange={() => setExperienceFilter("")}
                          name="exp_mobile"
                          className="accent-primary"
                        />
                      </label>
                      {EXPERIENCE_OPTIONS.map((t) => (
                        <label
                          key={t}
                          className="flex items-center justify-between gap-3 cursor-pointer"
                        >
                          <span className="mono-label text-[11px] text-neutral-beige/90">
                            {t}
                          </span>
                          <input
                            type="radio"
                            checked={experienceFilter === t}
                            onChange={() => setExperienceFilter(t)}
                            name="exp_mobile"
                            className="accent-primary"
                          />
                        </label>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <p className="mono-label text-[10px] text-dim-text">
                      LOCATION
                    </p>
                    <div className="flex flex-col gap-2">
                      <label className="flex items-center justify-between gap-3 cursor-pointer">
                        <span className="mono-label text-[11px] text-neutral-beige/90">
                          Any
                        </span>
                        <input
                          type="radio"
                          checked={activeFilters.location === ""}
                          onChange={() =>
                            setActiveFilters({ ...activeFilters, location: "" })
                          }
                          name="loc_mobile"
                          className="accent-primary"
                        />
                      </label>
                      {LOCATION_OPTIONS.map((loc) => (
                        <label
                          key={loc}
                          className="flex items-center justify-between gap-3 cursor-pointer"
                        >
                          <span className="mono-label text-[11px] text-neutral-beige/90">
                            {loc}
                          </span>
                          <input
                            type="radio"
                            checked={activeFilters.location === loc}
                            onChange={() =>
                              setActiveFilters({ ...activeFilters, location: loc })
                            }
                            name="loc_mobile"
                            className="accent-primary"
                          />
                        </label>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <p className="mono-label text-[10px] text-dim-text">
                      COMPANY SIZE
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {companySizes.map((s) => {
                        const selected = activeFilters.companySize.includes(s);
                        return (
                          <button
                            key={s}
                            type="button"
                            onClick={() => toggleCompanySize(s)}
                            className={`px-3 py-2 mono-label text-[10px] uppercase tracking-[0.05em] brutalist-border ${
                              selected
                                ? "brutalist-border-primary bg-[rgba(255,45,0,0.1)]"
                                : "bg-card-dark hover:bg-primary/10"
                            }`}
                          >
                            {s}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <p className="mono-label text-[10px] text-dim-text">
                      SALARY RANGE
                    </p>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      defaultValue={40}
                      disabled
                      className="w-full accent-primary opacity-50"
                    />
                  </div>

                  <div className="pt-4">
                    <button
                      type="button"
                      onClick={() => setMobileFiltersOpen(false)}
                      className="brutalist-border-primary bg-primary/10 w-full py-3 mono-label text-[11px] uppercase tracking-[0.05em]"
                    >
                      APPLY FILTERS
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {/* Main content */}
        <section className="md:col-span-9 lg:col-span-9">
          <header className="mb-4">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#555]">
              SOURCED FROM HN WHO'S HIRING · LAST PULL 14 MIN AGO
            </p>
            <p className="mono-label text-[10px] text-[#555] uppercase tracking-[0.2em] mt-1">
              LAST UPDATED · 2H AGO
            </p>
          </header>

          <div className="flex flex-col gap-6">
            <div className="flex items-end justify-between gap-4">
              <div>
                <span className="mono-label text-[10px] tracking-[0.2em] text-primary uppercase">
                  {filteredJobs.length} ROLES_FOUND
                </span>
              </div>

              <div className="flex items-center gap-2">
                {(["ALL", "SAVED", "APPLIED"] as const).map((t) => {
                  const isActive = tab === t;
                  return (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setTab(t)}
                      className={`mono-label text-[11px] uppercase tracking-[0.05em] px-5 py-3 border border-border-dark transition-colors ${
                        isActive
                          ? "active-tab border-border-dark text-primary"
                          : "bg-background-dark text-dim-text hover:bg-primary/10 hover:text-neutral-beige"
                      }`}
                    >
                      {t}
                    </button>
                  );
                })}
              </div>
            </div>

            {isFetchingRadar || jobs.length === 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[0, 1, 2].map((i) => (
                  <JobCardSkeleton key={i} />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredJobs.map((job) => (
                  <JobCard
                    key={job.id}
                    job={job}
                    saved={savedJobs.includes(job.id)}
                    onToggleSaved={() => toggleSavedJob(job.id)}
                  />
                ))}
              </div>
            )}

            {!isFetchingRadar && jobs.length > 0 && filteredJobs.length === 0 ? (
              <RadarEmptyState onClear={clearFilters} />
            ) : null}
          </div>

          <div className="mt-10 text-center">
            <p className="mono-label text-[10px] text-dim-text uppercase tracking-[0.2em]">
              Scroll-resistant brutalist listings
            </p>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function JobCard({
  job,
  saved,
  onToggleSaved,
}: {
  job: Job;
  saved: boolean;
  onToggleSaved: () => void;
}) {
  const status =
    job.hiringStatus === "HIRING_ACTIVE"
      ? {
          text: "HIRING_ACTIVE",
          cls: "border-success-glow/70 text-success-glow bg-[rgba(0,255,65,0.08)]",
        }
      : {
          text: "SLOW_HIRING",
          cls: "border-neutral-border/70 text-dim-text bg-[rgba(255,255,255,0.02)] opacity-70",
        };

  return (
    <article className="brutalist-border bg-card-dark p-5 flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="mono-label text-[10px] text-dim-text">
              {job.company}
            </p>
            {job.is_ghost_job && (
              <span className="px-2 py-0.5 text-[9px] font-bold bg-red-600 text-white uppercase tracking-[0.05em]">LIKELY GHOST</span>
            )}
          </div>
          <h3 className="font-serif text-[20px] font-black leading-tight">
            {job.title}
          </h3>
        </div>

        <button
          type="button"
          onClick={onToggleSaved}
          className="text-dim-text hover:text-primary transition-colors"
          aria-label={saved ? "Remove bookmark" : "Bookmark job"}
        >
          <span className="material-symbols-outlined text-[22px]">
            {saved ? "bookmark" : "bookmark_border"}
          </span>
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="mono-label text-[10px] px-2 py-1 border border-border-dark text-neutral-beige/90">
          {job.locationType.toUpperCase()}
        </span>
        <span className="mono-label text-[10px] px-2 py-1 border border-border-dark text-dim-text">
          {job.salary}
        </span>
      </div>

      <div className={`mono-label text-[10px] px-3 py-1 border ${status.cls} w-fit`}>
        {status.text}
      </div>

      <div className="flex flex-wrap gap-2">
        {job.skills.slice(0, 5).map((s) => (
          <span
            key={s}
            className="mono-label text-[10px] px-2 py-1 border border-border-dark text-dim-text uppercase tracking-[0.02em]"
          >
            {s}
          </span>
        ))}
      </div>

      <div className="flex gap-4 pt-2">
        <button
          type="button"
          disabled={!job.emailAvailable || job.is_ghost_job}
          className={`flex-1 py-3 font-mono text-[11px] font-bold uppercase tracking-widest border ${
            job.is_ghost_job
              ? "border-border-dark text-[#444]/40 bg-[#000000]/5 cursor-not-allowed"
              : job.emailAvailable
                ? "border-[#00FF41]/80 text-[#00FF41] bg-[#00FF41]/5 hover:bg-[#00FF41]/15 hover:text-[#00FF41]"
                : "border-border-dark text-[#444] bg-[#000000]/10 cursor-not-allowed"
          }`}
        >
          <span className="material-symbols-outlined text-sm mr-2">
            mail
          </span>
          EMAIL
        </button>
        <button
          type="button"
          disabled={!job.applyAvailable || job.is_ghost_job}
          className={`flex-1 py-3 font-mono text-[11px] font-bold uppercase tracking-widest border ${
            job.is_ghost_job
              ? "border-border-dark text-[#444]/40 bg-[#000000]/5 cursor-not-allowed"
              : job.applyAvailable
                ? "border-[#00FF41]/80 text-[#00FF41] bg-[#00FF41]/5 hover:bg-[#00FF41]/15 hover:text-[#00FF41]"
                : "border-border-dark text-[#444] bg-[#000000]/10 cursor-not-allowed"
          }`}
        >
          <span className="material-symbols-outlined text-sm mr-2">
            rocket_launch
          </span>
          APPLY
        </button>
      </div>

      <div className="flex items-center justify-between mt-auto pt-2">
        <p className="mono-label text-[10px] text-dim-text uppercase tracking-[0.05em]">
          Posted {job.postedDays} days ago · {job.fundingStage}
        </p>
        <p className="mono-label text-[10px] text-dim-text uppercase tracking-[0.05em]">
          LVL {job.experienceTier}
        </p>
      </div>
      {!job.deadline && (
        <p className="mono-label text-[9px] text-[#666] uppercase tracking-[0.05em]">DEADLINE UNKNOWN</p>
      )}
      {job.deadline && (
        <p className="mono-label text-[9px] text-dim-text uppercase tracking-[0.05em]">CLOSES {job.deadline}</p>
      )}
    </article>
  );
}

function RadarEmptyState({ onClear }: { onClear: () => void }) {
  return (
    <div className="min-h-[340px] flex flex-col items-center justify-center text-center col-span-full">
      <div className="font-serif text-[48px] font-black text-primary leading-none">
        —
      </div>
      <div className="font-mono text-[14px] font-bold uppercase tracking-[3px] text-neutral-beige mt-4">
        NO JOBS FOUND
      </div>
      <div className="font-mono text-[12px] text-[#8c8c8c] mt-3">
        Try a different filter or check back after the next data pull
      </div>
      <button
        type="button"
        onClick={onClear}
        className="mt-6 border-1.5 border-primary text-primary bg-transparent font-mono text-[11px] font-bold uppercase tracking-[0.05em] px-5 py-3 cursor-pointer hover:bg-primary/10"
      >
        CLEAR FILTERS →
      </button>
    </div>
  );
}

function JobCardSkeleton() {
  return (
    <article className="brutalist-border bg-card-dark p-5 flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-3">
          <div className="tazakhabar-skeleton-bar w-[180px] h-[16px]" />
          <div className="tazakhabar-skeleton-bar w-[120px] h-[12px]" />
        </div>
        <div className="tazakhabar-skeleton-bar w-[22px] h-[22px]" />
      </div>

      <div className="flex gap-2">
        <div className="tazakhabar-skeleton-bar w-[90px] h-[20px]" />
        <div className="tazakhabar-skeleton-bar w-[120px] h-[20px]" />
      </div>

      <div className="tazakhabar-skeleton-bar w-[110px] h-[24px]" />

      <div className="flex gap-2">
        <div className="tazakhabar-skeleton-bar w-[60px] h-[24px]" />
        <div className="tazakhabar-skeleton-bar w-[60px] h-[24px]" />
        <div className="tazakhabar-skeleton-bar w-[60px] h-[24px]" />
      </div>

      <div className="flex gap-4 pt-2">
        <div className="tazakhabar-skeleton-bar flex-1 h-[44px]" />
        <div className="tazakhabar-skeleton-bar flex-1 h-[44px]" />
      </div>
    </article>
  );
}

