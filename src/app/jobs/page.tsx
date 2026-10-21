"use client";

import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/Icon";
import AppShell from "@/components/AppShell";
import { useTaza } from "@/components/TazaContext";
import { fetchJobs } from "@/lib/api";
import type { ActiveFilters, LocationType, Job } from "@/types";

const ROLE_CHIPS = [
  "Frontend Dev",
  "Backend Dev",
  "Full Stack",
  "Data Engineer",
  "ML Engineer",
  "Data Science",
  "Gen AI",
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
  const [skip, setSkip] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const PAGE_SIZE = 50;

  // Fetch jobs from live API when version changes or filters change
  useEffect(() => {
    let cancelled = false;
    async function loadJobs() {
      try {
        const result = await fetchJobs({
          roles: activeFilters.roles,
          remote: activeFilters.location === "Remote",
          skip: 0,
          limit: PAGE_SIZE,
        });
        if (!cancelled) {
          setJobs(result.data);
          setSkip(PAGE_SIZE);
          setHasMore(result.meta.has_more);
          setApiError(null);
        }
      } catch (err) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : "Failed to load jobs";
          setApiError(msg);
          console.error("[JobsPage] fetchJobs error:", msg);
          setJobs([]);
        }
      }
    }
    loadJobs();
    return () => {
      cancelled = true;
    };
  }, [radarVersion, activeFilters.roles, activeFilters.location]);

  // Load more jobs for infinite scroll
  const loadMoreJobs = async () => {
    if (loadingMore || !hasMore) return;

    setLoadingMore(true);
    try {
      const result = await fetchJobs({
        roles: activeFilters.roles,
        remote: activeFilters.location === "Remote",
        skip: skip,
        limit: PAGE_SIZE,
      });
      if (result.data.length > 0) {
        setJobs((prev) => [...prev, ...result.data]);
        setSkip((prev) => prev + PAGE_SIZE);
        setHasMore(result.meta.has_more);
      } else {
        setHasMore(false);
      }
    } catch (err) {
      console.error("Failed to load more jobs:", err);
    } finally {
      setLoadingMore(false);
    }
  };

  // Intersection observer for infinite scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loadingMore) {
          loadMoreJobs();
        }
      },
      { threshold: 0.1 },
    );

    const sentinel = document.getElementById("jobs-sentinel");
    if (sentinel) {
      observer.observe(sentinel);
    }

    return () => observer.disconnect();
  }, [hasMore, loadingMore, skip]);

  const companySizes = useMemo(() => {
    const set = new Set(jobs.map((j) => j.companySize));
    return Array.from(set);
  }, [jobs]);

  const rotatedJobs = useMemo(() => {
    if (jobs.length === 0) return jobs;
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
      ? locationFiltered.filter((j) => activeFilters.companySize.includes(j.companySize))
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
  ]);

  const countJobsForRole = (role: string) => {
    const roleFiltered = rotatedJobs.filter((j) => j.role === role);

    const locationFiltered = activeFilters.location
      ? roleFiltered.filter((j) => j.locationType === activeFilters.location)
      : roleFiltered;

    const companyFiltered = activeFilters.companySize.length
      ? locationFiltered.filter((j) => activeFilters.companySize.includes(j.companySize))
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
      <div className="-mx-5 md:-mx-12">
        {radarNewCount > 0 ? (
          <button type="button" onClick={() => refreshRadar()} className="strip" data-intro data-reveal="fade">
            <span className="lamp lamp--ok" aria-hidden />
            New data available, swap the report
            <span aria-hidden>↑</span>
          </button>
        ) : null}
      </div>

      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mono-label text-primary">02 / Job radar</p>
          <h1 className="display mt-3 text-[clamp(2rem,1.3rem+2.8vw,3.25rem)]" data-split="lines" data-intro>
            Who is <span className="accent">hiring.</span>
          </h1>
          <p className="mono-label mt-4 text-dim-text">
            Source: HN Who Is Hiring · contact details extracted from each post
          </p>
        </div>
        <p className="mono-data text-[13px] text-dim-text">
          <span className="text-primary">{String(filteredJobs.length).padStart(3, "0")}</span> roles on the board
        </p>
      </header>

      <div className="grid grid-cols-1 gap-8 md:grid-cols-12">
        {/* Desktop faceplate */}
        <aside className="hidden md:col-span-4 md:block lg:col-span-3">
          <FilterPanel
            activeFilters={activeFilters}
            setActiveFilters={setActiveFilters}
            experienceFilter={experienceFilter}
            setExperienceFilter={setExperienceFilter}
            companySizes={companySizes}
            toggleRole={toggleRole}
            toggleCompanySize={toggleCompanySize}
            clearFilters={clearFilters}
            countJobsForRole={countJobsForRole}
          />
        </aside>

        {/* Mobile filters */}
        <div className="md:hidden">
          <button
            type="button"
            onClick={() => setMobileFiltersOpen(true)}
            className="btn btn--block"
            aria-expanded={mobileFiltersOpen}
          >
            Open filters
            <Icon name="tune" className="text-[16px]" aria-hidden />
          </button>
          {mobileFiltersOpen ? (
            <div className="fixed inset-0 z-[60] bg-black/70 p-4" role="dialog" aria-modal="true" aria-label="Radar filters">
              <div className="panel h-full overflow-auto p-5">
                <div className="mb-4 flex items-center justify-between">
                  <p className="mono-label text-primary">Filters</p>
                  <button type="button" onClick={() => setMobileFiltersOpen(false)} className="btn !py-2 !px-3">
                    Close
                  </button>
                </div>
                <FilterPanel
                  activeFilters={activeFilters}
                  setActiveFilters={setActiveFilters}
                  experienceFilter={experienceFilter}
                  setExperienceFilter={setExperienceFilter}
                  companySizes={companySizes}
                  toggleRole={toggleRole}
                  toggleCompanySize={toggleCompanySize}
                  clearFilters={clearFilters}
                  countJobsForRole={countJobsForRole}
                  compact
                />
                <button
                  type="button"
                  onClick={() => setMobileFiltersOpen(false)}
                  className="btn btn--primary btn--block mt-6"
                >
                  Apply filters
                </button>
              </div>
            </div>
          ) : null}
        </div>

        {/* Main ledger */}
        <section className="md:col-span-8 lg:col-span-9">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Listing views">
              {(["ALL", "SAVED", "APPLIED"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  aria-pressed={tab === t}
                  onClick={() => setTab(t)}
                  className="tab"
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {apiError ? (
            <div className="panel panel--accent p-6 text-center">
              <p className="mono-label text-primary">Radar offline</p>
              <p className="mono-label mt-2 text-dim-text">{apiError}</p>
              <button
                type="button"
                onClick={() => {
                  setApiError(null);
                  setJobs([]);
                  setSkip(0);
                }}
                className="btn mt-5"
              >
                Retry sweep
              </button>
            </div>
          ) : isFetchingRadar ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {[0, 1, 2].map((i) => (
                <JobCardSkeleton key={i} />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {filteredJobs.map((job, i) => (
                <JobCard
                  key={job.id}
                  job={job}
                  index={i}
                  saved={savedJobs.includes(job.id)}
                  onToggleSaved={() => toggleSavedJob(job.id)}
                />
              ))}
            </div>
          )}

          {/* Sentinel for infinite scroll */}
          <div id="jobs-sentinel" className="h-4" />

          {loadingMore && (
            <div className="flex items-center justify-center gap-3 py-8">
              <span className="lamp lamp--live" aria-hidden />
              <p className="mono-label text-dim-text">Advancing the tape</p>
            </div>
          )}

          {!hasMore && jobs.length > 0 && (
            <div className="scribe mt-6 pt-5 text-center">
              <p className="mono-label text-dim-text">
                End of tape · {jobs.length} roles loaded
              </p>
            </div>
          )}

          {!isFetchingRadar && jobs.length > 0 && filteredJobs.length === 0 ? (
            <RadarEmptyState onClear={clearFilters} />
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}

function FilterPanel({
  activeFilters,
  setActiveFilters,
  experienceFilter,
  setExperienceFilter,
  companySizes,
  toggleRole,
  toggleCompanySize,
  clearFilters,
  countJobsForRole,
  compact,
}: {
  activeFilters: ActiveFilters;
  setActiveFilters: (f: ActiveFilters) => void;
  experienceFilter: string;
  setExperienceFilter: (v: "" | "I" | "II" | "III" | "IV") => void;
  companySizes: string[];
  toggleRole: (r: string) => void;
  toggleCompanySize: (s: string) => void;
  clearFilters: () => void;
  countJobsForRole: (r: string) => number;
  compact?: boolean;
}) {
  return (
    <div className="panel p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="mono-label text-primary">Filter faceplate</p>
          <p className="mono-label mt-2 flex items-center gap-2 text-dim-text">
            <span className="lamp lamp--live" aria-hidden />
            Live board
          </p>
        </div>
        <button type="button" onClick={clearFilters} className="btn !px-3 !py-2">
          Reset
        </button>
      </div>

      <section className="scribe pt-5">
        <span className="plate-label">Role</span>
        <div className="mt-4 flex flex-col gap-2">
          {ROLE_CHIPS.map((r) => {
            const checked = activeFilters.roles.includes(r);
            const matches = checked ? countJobsForRole(r) : 0;
            return (
              <label key={r} className="flex cursor-pointer items-center gap-3 py-1">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleRole(r)}
                  className="machined-check"
                />
                <span className="mono-label flex-1 text-neutral-beige/90">{r}</span>
                {checked ? (
                  <span
                    className="mono-data text-[11px]"
                    style={{ color: matches === 0 ? "#4a4d4b" : "#FF2D00" }}
                  >
                    {String(matches).padStart(2, "0")}
                  </span>
                ) : null}
              </label>
            );
          })}
        </div>
      </section>

      <section className="scribe pt-5">
        <span className="plate-label">Experience</span>
        <div className="mt-4 flex flex-col gap-2">
          <label className="flex cursor-pointer items-center justify-between gap-3 py-1">
            <span className="mono-label text-neutral-beige/90">Any</span>
            <input
              type="radio"
              checked={experienceFilter === ""}
              onChange={() => setExperienceFilter("")}
              name="exp"
              className="machined-check"
            />
          </label>
          {EXPERIENCE_OPTIONS.map((t) => (
            <label key={t} className="flex cursor-pointer items-center justify-between gap-3 py-1">
              <span className="mono-label text-neutral-beige/90">Tier {t}</span>
              <input
                type="radio"
                checked={experienceFilter === t}
                onChange={() => setExperienceFilter(t)}
                name="exp"
                className="machined-check"
              />
            </label>
          ))}
        </div>
      </section>

      <section className="scribe pt-5">
        <span className="plate-label">Location</span>
        <div className="mt-4 flex flex-col gap-2">
          <label className="flex cursor-pointer items-center justify-between gap-3 py-1">
            <span className="mono-label text-neutral-beige/90">Any</span>
            <input
              type="radio"
              checked={activeFilters.location === ""}
              onChange={() => setActiveFilters({ ...activeFilters, location: "" })}
              name="loc"
              className="machined-check"
            />
          </label>
          {LOCATION_OPTIONS.map((loc) => (
            <label key={loc} className="flex cursor-pointer items-center justify-between gap-3 py-1">
              <span className="mono-label text-neutral-beige/90">{loc}</span>
              <input
                type="radio"
                checked={activeFilters.location === loc}
                onChange={() => setActiveFilters({ ...activeFilters, location: loc })}
                name="loc"
                className="machined-check"
              />
            </label>
          ))}
        </div>
      </section>

      {companySizes.length > 0 ? (
        <section className="scribe pt-5">
          <span className="plate-label">Company size</span>
          <div className="mt-4 flex flex-wrap gap-2">
            {companySizes.map((s) => {
              const selected = activeFilters.companySize.includes(s);
              return (
                <button
                  key={s}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => toggleCompanySize(s)}
                  className={`chip ${selected ? "is-on" : ""}`}
                >
                  {s}
                </button>
              );
            })}
          </div>
        </section>
      ) : null}

      {!compact ? (
        <section className="scribe pt-5">
          <span className="plate-label">Salary range</span>
          <div className="mt-4 space-y-3">
            <div className="meter" aria-hidden>
              <div className="meter__fill meter__fill--muted" style={{ width: "40%" }} />
            </div>
            <p className="mono-label text-dim-text">Calibration pending · salary data not yet fed</p>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function JobCard({
  job,
  index,
  saved,
  onToggleSaved,
}: {
  job: Job;
  index: number;
  saved: boolean;
  onToggleSaved: () => void;
}) {
  const active = job.hiringStatus === "HIRING_ACTIVE";

  return (
    <article className="panel flex flex-col gap-4 p-5" data-reveal="up">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mono-data text-[10px] text-dim-text">
              RK-{String(index + 1).padStart(4, "0")}
            </span>
            <p className="mono-label truncate text-neutral-beige">{job.company}</p>
            {job.is_ghost_job && (
              <span className="mono-label border border-primary bg-primary/15 px-2 py-0.5 text-primary">
                Likely ghost
              </span>
            )}
          </div>
          <h2 className="display text-[19px] leading-tight">{job.title}</h2>
        </div>

        <button
          type="button"
          onClick={onToggleSaved}
          className="tab shrink-0 !border-transparent !p-2"
          aria-pressed={saved}
          aria-label={saved ? "Remove bookmark" : "Bookmark job"}
        >
          <Icon
            name={saved ? "bookmark" : "bookmark_border"}
            className="text-[20px]"
            aria-hidden
          />
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="chip !cursor-default">{job.locationType}</span>
        <span className="chip !cursor-default">{job.salary}</span>
      </div>

      <div className="flex items-center gap-2">
        <span className={`lamp ${active ? "lamp--ok" : "lamp--off"}`} aria-hidden />
        <span className="mono-label text-dim-text">
          {active ? "Hiring active" : "Slow hiring"}
        </span>
      </div>

      <div className="meter" aria-hidden>
        <div
          className={`meter__fill ${active ? "meter__fill--ok" : "meter__fill--muted"}`}
          style={{ width: active ? "72%" : "34%" }}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {job.skills.slice(0, 5).map((s) => (
          <span key={s} className="chip !cursor-default">
            {s}
          </span>
        ))}
      </div>

      <div className="mt-auto flex gap-2 pt-1">
        <button
          type="button"
          disabled={!job.emailAvailable || job.is_ghost_job}
          className={`btn flex-1 ${job.emailAvailable && !job.is_ghost_job ? "btn--signal" : "btn--dead"}`}
        >
          <Icon name="mail" className="text-[15px]" aria-hidden />
          Email
        </button>
        <a
          href={job.applyAvailable && !job.is_ghost_job ? job.applyLink || "#" : "#"}
          target="_blank"
          rel="noopener noreferrer"
          tabIndex={job.applyAvailable && !job.is_ghost_job ? 0 : -1}
          aria-disabled={!(job.applyAvailable && !job.is_ghost_job)}
          className={`btn flex-1 ${job.applyAvailable && !job.is_ghost_job ? "btn--signal" : "btn--dead"}`}
        >
          <Icon name="rocket_launch" className="text-[15px]" aria-hidden />
          Apply
        </a>
      </div>

      <div className="scribe flex items-center justify-between gap-3 pt-4">
        <p className="mono-label text-dim-text">
          Posted {job.postedDays}d ago · {job.fundingStage}
        </p>
        <p className="mono-label text-dim-text">Lvl {job.experienceTier}</p>
      </div>
      <p className="mono-label text-[10px] text-dim-text">
        {job.deadline ? `Closes ${job.deadline}` : "Deadline unknown"}
      </p>
    </article>
  );
}

function RadarEmptyState({ onClear }: { onClear: () => void }) {
  return (
    <div className="panel flex min-h-[320px] flex-col items-center justify-center px-6 py-12 text-center">
      <p className="mono-data text-[clamp(3rem,2rem+6vw,5rem)] leading-none text-primary">00</p>
      <p className="display mt-4 text-[clamp(1.25rem,1rem+1.5vw,1.75rem)]">No roles on this filter</p>
      <p className="mt-3 max-w-[40ch] text-[15px] leading-relaxed text-dim-text">
        The board repopulates after the next scrape cycle. Loosen a filter or check the
        declining channels.
      </p>
      <button type="button" onClick={onClear} className="btn mt-6">
        Clear filters
        <span aria-hidden>→</span>
      </button>
    </div>
  );
}

function JobCardSkeleton() {
  return (
    <article className="panel flex flex-col gap-4 p-5" aria-hidden>
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-3">
          <div className="tk-skel h-3 w-[180px]" />
          <div className="tk-skel h-4 w-[120px]" />
        </div>
        <div className="tk-skel h-5 w-5" />
      </div>
      <div className="flex gap-2">
        <div className="tk-skel h-6 w-[90px]" />
        <div className="tk-skel h-6 w-[120px]" />
      </div>
      <div className="tk-skel h-[10px] w-full" />
      <div className="flex gap-2">
        <div className="tk-skel h-6 w-[60px]" />
        <div className="tk-skel h-6 w-[60px]" />
        <div className="tk-skel h-6 w-[60px]" />
      </div>
      <div className="flex gap-2 pt-2">
        <div className="tk-skel h-10 flex-1" />
        <div className="tk-skel h-10 flex-1" />
      </div>
    </article>
  );
}
