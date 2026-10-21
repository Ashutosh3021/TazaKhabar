"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import AppShell from "@/components/AppShell";
import { useRouter } from "next/navigation";
import { useTaza } from "@/components/TazaContext";
import { analyseResume, fetchProfile } from "@/lib/api";

const EXPERIENCE_MAP: Record<string, { label: string; roman: "I" | "II" | "III" | "IV" }> = {
  I: { label: "Fresher", roman: "I" },
  II: { label: "Early Career", roman: "II" },
  III: { label: "Mid-Level", roman: "III" },
  IV: { label: "Senior+", roman: "IV" },
};

type MobileTab = "ACCOUNT" | "ROLES" | "OUTPUT";

interface AtsResult {
  ats_score: number;
  critical_issues: string[];
  suggested_additions: string[];
  missing_keywords: string[];
}

export default function ProfilePage() {
  const router = useRouter();
  const { userProfile, setUserProfile, resetAll, resumeUploaded, setResumeUploaded } = useTaza();
  const { session, sessionLoading, refreshSession, signOutUser } = useTaza();

  const [mobileTab, setMobileTab] = useState<MobileTab>("ACCOUNT");
  const [rateLimitedUntil, setRateLimitedUntil] = useState<number | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [atsResult, setAtsResult] = useState<AtsResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [cooldownDays, setCooldownDays] = useState<number | null>(null);
  const [lastAnalysisAt, setLastAnalysisAt] = useState<string | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null as unknown as HTMLInputElement);
  const hasAccount = Boolean(userProfile.email);

  // Load profile from backend on mount
  useEffect(() => {
    let cancelled = false;
    async function loadProfile() {
      setProfileLoading(true);
      try {
        const profile = await fetchProfile();
        if (cancelled) return;
        if (profile.roles?.length && !userProfile.roles?.length) {
          setUserProfile({
            ...userProfile,
            roles: profile.roles,
            experienceLevel: profile.experience_level || userProfile.experienceLevel,
          });
        }
        if (profile.resume_text_length || profile.ats_score !== null) {
          setResumeUploaded(true);
        }
        if (profile.ats_score !== null && profile.ats_score !== undefined) {
          setAtsResult({
            ats_score: profile.ats_score,
            critical_issues: profile.ats_critical_issues || [],
            suggested_additions: profile.ats_suggested_additions || [],
            missing_keywords: profile.ats_missing_keywords || [],
          });
          setLastAnalysisAt(profile.last_analysis_at);
        }
        if (profile.last_analysis_at) {
          const lastDate = new Date(profile.last_analysis_at);
          const daysSince = (Date.now() - lastDate.getTime()) / (1000 * 60 * 60 * 24);
          const daysLeft = Math.ceil(30 - daysSince);
          if (daysLeft > 0) setCooldownDays(daysLeft);
        }
      } catch {
        // Profile not found
      } finally {
        if (!cancelled) setProfileLoading(false);
      }
    }
    loadProfile();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-analyze on first resume upload
  useEffect(() => {
    const savedResume = localStorage.getItem("taza_resume_pdf");
    if (resumeUploaded && savedResume && !atsResult && !isAnalyzing && cooldownDays === null) {
      const base64 = savedResume.split(",")[1];
      if (!base64) return;
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: "application/pdf" });
      const file = new File([blob], "resume.pdf", { type: "application/pdf" });
      handleAnalyze(file);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeUploaded]);

  // Countdown timer
  useEffect(() => {
    if (!rateLimitedUntil || rateLimitedUntil <= Date.now()) return;
    const id = window.setInterval(() => setNowMs(Date.now()), 250);
    return () => window.clearInterval(id);
  }, [rateLimitedUntil]);

  const handleAnalyze = useCallback(
    async (file: File) => {
      if (cooldownDays !== null) {
        setAnalyzeError(`Re-analysis available in ${cooldownDays} days`);
        return;
      }
      setIsAnalyzing(true);
      setAnalyzeError(null);
      try {
        const result = await analyseResume(file);
        setAtsResult({
          ats_score: result.ats_score,
          critical_issues: result.critical_issues,
          suggested_additions: result.suggested_additions,
          missing_keywords: result.missing_keywords,
        });
        setLastAnalysisAt(new Date().toISOString());
        setCooldownDays(30);

        // Refresh server-side profile so stored ATS fields are synced
        try {
          const profile = await fetchProfile();
          setUserProfile({
            ...userProfile,
            roles: profile.roles || userProfile.roles,
            experienceLevel: profile.experience_level || userProfile.experienceLevel,
            email: profile.email || userProfile.email,
          });
        } catch (e) {
          // non-fatal: keep local ATS result
        }
      } catch (err: unknown) {
        const error = err as {
          retry_after?: number;
          code?: string;
          message?: string;
          days_remaining?: number;
        };
        if (error.retry_after) setRateLimitedUntil(Date.now() + error.retry_after * 1000);
        if (error.code === "REANALYSIS_COOLDOWN") setCooldownDays(error.days_remaining ?? null);
        setAnalyzeError(error.message || "Analysis failed");
      } finally {
        setIsAnalyzing(false);
      }
    },
    [cooldownDays, userProfile, setUserProfile],
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async (ev) => {
        const base64 = ev.target?.result as string;
        localStorage.setItem("taza_resume_pdf", base64);
        setResumeUploaded(true);
        await handleAnalyze(file);
      };
      reader.readAsDataURL(file);
    },
    [handleAnalyze, setResumeUploaded],
  );

  const handleAnalyzeStoredResume = useCallback(async () => {
    const savedResume = localStorage.getItem("taza_resume_pdf");
    if (!savedResume) {
      setAnalyzeError("No stored resume found. Please upload a PDF or TXT file.");
      return;
    }

    const parts = savedResume.split(",");
    if (parts.length < 2) {
      setAnalyzeError("Stored resume data is invalid. Please re-upload your resume.");
      return;
    }

    const prefix = parts[0] || "";
    const base64 = parts[1];
    const contentTypeMatch = prefix.match(/^data:([^;]+);base64$/);
    const contentType = contentTypeMatch?.[1] ?? "application/pdf";
    const extension = contentType === "text/plain" ? "txt" : "pdf";

    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }

    const file = new File([bytes], `resume.${extension}`, { type: contentType });
    await handleAnalyze(file);
  }, [handleAnalyze]);

  const atsScore = atsResult?.ats_score ?? null;

  const trendingSkills = useMemo(() => {
    const suggested = atsResult?.suggested_additions ?? [];
    const missing = new Set((atsResult?.missing_keywords ?? []).map((k) => k.toLowerCase()));
    return suggested.filter((s) => !missing.has(s.toLowerCase()));
  }, [atsResult]);

  const remainingSeconds = rateLimitedUntil
    ? Math.max(0, Math.ceil((rateLimitedUntil - nowMs) / 1000))
    : 0;
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;
  const countdownLabel =
    remainingSeconds > 0 ? `${minutes}:${String(seconds).padStart(2, "0")}` : "0:00";
  const isRateLimited = Boolean(rateLimitedUntil && rateLimitedUntil > nowMs);

  const handleReanalyze = useCallback(() => {
    if (!resumeUploaded) {
      fileInputRef.current?.click();
      return;
    }
    void handleAnalyzeStoredResume();
  }, [resumeUploaded, handleAnalyzeStoredResume]);

  const exp =
    EXPERIENCE_MAP[userProfile.experienceLevel] ?? { label: "Senior+", roman: "IV" as const };

  const handleSignOut = async () => {
    await signOutUser();
    resetAll();
    await refreshSession();
    router.push("/auth");
  };

  const signedIn = Boolean(session);

  return (
    <AppShell>
      <div className="space-y-10">
        <header>
          <p className="mono-label text-primary">05 / Operator panel</p>
          <h1 className="display mt-3 text-[clamp(2rem,1.3rem+2.8vw,3.25rem)]" data-split="lines" data-intro>
            Your <span className="accent">profile.</span>
          </h1>
          <p className="mono-label mt-4 text-dim-text">Manage your intelligence parameters</p>
        </header>

        {!sessionLoading && !signedIn && (
          <div className="panel border-primary/40 p-5" role="status">
            <p className="mono-label text-neutral-beige">Not signed in</p>
            <p className="mono-label mt-2 text-[11px] text-dim-text">
              Sign in to save your roles, resume and ATS results to your account. They are
              kept in this browser only until then.
            </p>
            <Link href="/auth" className="btn btn--primary mt-4">
              Go to the access terminal
              <span className="material-symbols-outlined text-[18px]" aria-hidden>
                arrow_forward
              </span>
            </Link>
          </div>
        )}

        {/* Desktop layout */}
        <div className="hidden md:grid md:grid-cols-12 gap-8">
          <aside className="md:col-span-4 flex flex-col gap-8">
            <AccountCard
              email={session?.email || userProfile.email}
              onSignOut={handleSignOut}
            />
            <ResumeCard
              atsScore={atsScore}
              onFileChange={handleFileChange}
              fileInputRef={fileInputRef}
            />
          </aside>
          <main className="md:col-span-8 flex flex-col gap-8">
            <RolesCard roles={userProfile.roles} />
            <ExperienceCard label={`${exp.label} / ${exp.roman}`} />
            <ResumeIntelligenceSection
              resumeUploaded={resumeUploaded}
              isAnalyzing={isAnalyzing}
              isRateLimited={isRateLimited}
              countdownLabel={countdownLabel}
              atsResult={atsResult}
              trendingSkills={trendingSkills}
              analyzeError={analyzeError}
              cooldownDays={cooldownDays}
              onAnalyze={handleReanalyze}
            />
            <OperationalPreferencesSection hasAccount={hasAccount} />
            <TerminalCard
              atsScore={atsScore}
              atsResult={atsResult}
              trendingSkills={trendingSkills}
            />
          </main>
        </div>

        {/* Mobile layout */}
        <div className="md:hidden">
          <div className="flex gap-2 overflow-x-auto pb-2" role="group" aria-label="Profile sections">
            {(["ACCOUNT", "ROLES", "OUTPUT"] as MobileTab[]).map((t) => (
              <button
                key={t}
                type="button"
                aria-pressed={mobileTab === t}
                onClick={() => setMobileTab(t)}
                className="tab"
              >
                {t}
              </button>
            ))}
          </div>
          {mobileTab === "ACCOUNT" && (
            <div className="space-y-8">
              <AccountCard
                email={session?.email || userProfile.email}
                onSignOut={handleSignOut}
              />
              <ResumeCard
                atsScore={atsScore}
                onFileChange={handleFileChange}
                fileInputRef={fileInputRef}
              />
            </div>
          )}
          {mobileTab === "ROLES" && (
            <div className="space-y-8">
              <RolesCard roles={userProfile.roles} />
              <ExperienceCard label={`${exp.label} / ${exp.roman}`} />
            </div>
          )}
          {mobileTab === "OUTPUT" && (
            <div className="space-y-8">
              <ResumeIntelligenceSection
                resumeUploaded={resumeUploaded}
                isAnalyzing={isAnalyzing}
                isRateLimited={isRateLimited}
                countdownLabel={countdownLabel}
                atsResult={atsResult}
                trendingSkills={trendingSkills}
                analyzeError={analyzeError}
                cooldownDays={cooldownDays}
                onAnalyze={handleReanalyze}
              />
              <OperationalPreferencesSection hasAccount={hasAccount} />
              <TerminalCard
                atsScore={atsScore}
                atsResult={atsResult}
                trendingSkills={trendingSkills}
              />
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SectionPlate({ n, title }: { n: string; title: string }) {
  return (
    <div className="scribe pb-4">
      <span className="plate-label">
        {n} / {title}
      </span>
    </div>
  );
}

function AccountCard({ email, onSignOut }: { email: string; onSignOut: () => void }) {
  return (
    <section className="panel p-5" data-reveal="up">
      <SectionPlate n="01" title="Account info" />
      <div className="space-y-4">
        <div>
          <p className="mono-label mb-1 text-dim-text">ID identifier</p>
          <p className="mono-data text-[15px] break-all">{email || "not set"}</p>
        </div>
        <button
          type="button"
          onClick={onSignOut}
          className="btn btn--block"
        >
          Sign out
          <Icon name="logout" className="text-[16px]" aria-hidden />
        </button>
      </div>
    </section>
  );
}

function ResumeCard({
  atsScore,
  onFileChange,
  fileInputRef,
}: {
  atsScore: number | null;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  fileInputRef: React.RefObject<HTMLInputElement>;
}) {
  const hasAnalysis = atsScore !== null && atsScore > 0;
  return (
    <section className="panel p-5" data-reveal="up">
      <SectionPlate n="04" title="Resume management" />
      <div className="flex flex-col items-center gap-4 border border-dashed border-border-dark p-6 text-center">
        <Icon name="upload_file" className="text-[36px] text-neutral-beige/25" aria-hidden />
        <div>
          <p className="mono-data text-[13px]">resume.pdf</p>
          <p className="mono-label mt-1 text-primary">
            {hasAnalysis ? `ATS score: ${atsScore}` : "No resume uploaded"}
          </p>
        </div>
        <label className="w-full">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt"
            onChange={onFileChange}
            className="sr-only"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="btn btn--block"
          >
            Replace resume
          </button>
        </label>
      </div>
    </section>
  );
}

function RolesCard({ roles }: { roles: string[] }) {
  return (
    <section className="panel p-5" data-reveal="up">
      <SectionPlate n="02" title="Your roles" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {roles.length ? (
          roles.map((r) => (
            <div
              key={r}
              className="panel panel--accent flex justify-between items-start p-4 bg-primary/[0.05]"
            >
              <div>
                <p className="mono-label text-primary">Active role</p>
                <h2 className="display mt-2 text-[18px]">{r}</h2>
              </div>
              <span className="lamp lamp--live mt-1" aria-hidden />
            </div>
          ))
        ) : (
          <div className="panel col-span-full p-5">
            <p className="mono-label text-dim-text">
              No roles selected yet. Complete setup to personalize.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function ExperienceCard({ label }: { label: string }) {
  return (
    <section className="panel panel--accent relative overflow-hidden p-6 md:p-8" data-reveal="up">
      <SectionPlate n="03" title="Experience level" />
      <div className="relative z-10">
        <p className="mono-label text-neutral-beige/60">Current tier</p>
        <h2 className="display mt-3 text-[clamp(2.5rem,2rem+3vw,4rem)] leading-none">{label}</h2>
      </div>
      <div
        className="display pointer-events-none absolute -bottom-8 -right-4 hidden select-none text-[9rem] leading-none text-primary/[0.06] md:block"
        aria-hidden
      >
        LVL
      </div>
      <div className="tick-rule mt-6 h-[6px] opacity-70" aria-hidden />
    </section>
  );
}

function ResumeIntelligenceSection({
  resumeUploaded,
  isAnalyzing,
  isRateLimited,
  countdownLabel,
  atsResult,
  trendingSkills,
  analyzeError,
  cooldownDays,
  onAnalyze,
}: {
  resumeUploaded: boolean;
  isAnalyzing: boolean;
  isRateLimited: boolean;
  countdownLabel: string;
  atsResult: AtsResult | null;
  trendingSkills: string[];
  analyzeError: string | null;
  cooldownDays: number | null;
  onAnalyze: () => void;
}) {
  const showRateLimitedText = isRateLimited && resumeUploaded;
  const buttonText = isAnalyzing
    ? "Analyzing"
    : !resumeUploaded
      ? "Upload resume to analyze"
      : showRateLimitedText
        ? `Try again in ${countdownLabel}`
        : "Re-analyze resume";

  return (
    <section
      className={`panel p-5 md:p-6 ${!resumeUploaded ? "text-dim-text" : "text-neutral-beige"}`}
      data-reveal="up"
    >
      <div className="flex items-end justify-between gap-4">
        <span className="plate-label text-primary">05 / Resume intelligence</span>
        {cooldownDays !== null && (
          <p className="mono-label text-dim-text">Re-analysis in {cooldownDays} days</p>
        )}
      </div>

      {/* ATS bar gauge */}
      {atsResult && (
        <div className="mt-6 space-y-5">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="mono-label text-dim-text">ATS score</p>
              <p className="display mt-2 text-[clamp(2.5rem,2rem+3vw,3.5rem)] leading-none text-primary">
                {String(atsResult.ats_score).padStart(2, "0")}
              </p>
            </div>
            <p className="mono-data text-[13px] text-dim-text">out of 100</p>
          </div>
          <div
            className="meter"
            role="img"
            aria-label={`ATS score ${atsResult.ats_score} out of 100`}
          >
            <div
              className={`meter__fill ${atsResult.ats_score >= 70 ? "meter__fill--ok" : ""}`}
              style={{ width: `${atsResult.ats_score}%` }}
            />
          </div>

          {atsResult.missing_keywords && atsResult.missing_keywords.length > 0 && (
            <div>
              <p className="mono-label text-primary">ATS gap keywords</p>
              <p className="mono-label mt-1 text-dim-text">
                Terms scanners expect but are not clearly on your resume.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {atsResult.missing_keywords.map((kw) => (
                  <span key={kw} className="chip !cursor-default">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}
          {atsResult.critical_issues.length > 0 && (
            <div>
              <p className="mono-label text-primary">Priority fixes</p>
              <p className="mono-label mt-1 text-dim-text">
                Concrete edits to improve your score.
              </p>
              <ul className="mt-3 space-y-2">
                {atsResult.critical_issues.map((issue, i) => (
                  <li
                    key={i}
                    className="flex gap-2 text-[13px] leading-relaxed text-neutral-beige/90"
                  >
                    <span className="mono-label shrink-0 text-primary">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span>{issue}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {trendingSkills.length > 0 && (
            <div>
              <p className="mono-label text-primary">Trending skills to add</p>
              <p className="mono-label mt-1 text-dim-text">
                Hot in current job posts for your target roles.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {trendingSkills.map((skill) => (
                  <span key={skill} className="chip is-on !cursor-default">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {analyzeError && <p className="mono-label mt-4 text-primary">{analyzeError}</p>}

      <button
        type="button"
        disabled={isAnalyzing || showRateLimitedText}
        onClick={onAnalyze}
        className={`btn btn--block mt-6 ${isAnalyzing || showRateLimitedText ? "" : "btn--primary"}`}
        style={isAnalyzing || showRateLimitedText ? { pointerEvents: "none" } : undefined}
      >
        {buttonText}
        {!isAnalyzing && !showRateLimitedText ? (
          <Icon name="arrow_forward" className="text-[16px]" aria-hidden />
        ) : null}
      </button>
    </section>
  );
}

function OperationalPreferencesSection({ hasAccount }: { hasAccount: boolean }) {
  const [highDisruption, setHighDisruption] = useState(false);
  const [jobMatchAlerts, setJobMatchAlerts] = useState(false);
  return (
    <section className="panel p-5" data-reveal="up">
      <SectionPlate n="06" title="Operational preferences" />
      <div className="divide-y divide-border-dark">
        <div className="flex items-center justify-between gap-4 pb-4">
          <p className="mono-label text-neutral-beige">High disruption alert</p>
          <ToggleSwitch
            checked={highDisruption}
            onToggle={() => setHighDisruption(!highDisruption)}
            label="High disruption alert"
          />
        </div>
        <div className="flex items-start justify-between gap-4 pt-4">
          <div>
            <p className="mono-label text-neutral-beige">Job match alerts</p>
            <p className="mono-label mt-2 text-dim-text">Requires account, coming soon</p>
          </div>
          <div className="flex items-center gap-3">
            <Icon
              name="lock"
              className={`text-[16px] ${hasAccount ? "text-dim-text" : "text-[#4a4d4b]"}`}
              aria-hidden
            />
            <ToggleSwitch
              checked={jobMatchAlerts}
              onToggle={() => {
                if (!hasAccount) return;
                setJobMatchAlerts((v) => !v);
              }}
              disabled={!hasAccount}
              label="Job match alerts"
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function ToggleSwitch({
  checked,
  onToggle,
  disabled,
  label,
}: {
  checked: boolean;
  onToggle: () => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={() => {
        if (disabled) return;
        onToggle();
      }}
      aria-pressed={checked}
      aria-label={label}
      disabled={disabled}
      className={`relative h-[26px] w-[48px] border transition-colors ${
        disabled
          ? "cursor-not-allowed border-border-dark bg-[#1a1c1a]"
          : checked
            ? "border-primary bg-primary/10"
            : "border-border-dark bg-background-dark hover:bg-card-hi"
      }`}
    >
      <span
        className={`absolute top-[3px] block h-[18px] w-[18px] border transition-all ${
          checked ? "left-[26px] border-primary bg-primary" : "left-[3px] border-border-dark bg-card-hi"
        }`}
        aria-hidden
      />
    </button>
  );
}

function TerminalCard({
  atsScore,
  atsResult,
  trendingSkills,
}: {
  atsScore: number | null;
  atsResult: AtsResult | null;
  trendingSkills: string[];
}) {
  const hasResumeAnalysis = atsResult != null;
  return (
    <section data-reveal="up">
      <div className="panel panel--flat !bg-black p-4">
        <div className="mb-4 flex items-center gap-2 border-b border-border-dark pb-3">
          <span className="lamp lamp--live" aria-hidden />
          <span className="lamp lamp--ok" aria-hidden />
          <span className="lamp lamp--off" aria-hidden />
          <p className="mono-label ml-4 text-dim-text">Session log</p>
        </div>
        <div className="mono-label leading-loose text-neutral-beige/70">
          <p>&gt; INITIALIZING PROFILE_ANALYSIS</p>
          {hasResumeAnalysis ? (
            <>
              <p>&gt; ANALYZING RESUME ATTACHMENT</p>
              <p>
                &gt; ATS_SCORE: <span className="text-primary">{atsResult.ats_score}</span>
              </p>
              {atsResult.critical_issues.length > 0 && (
                <p>
                  &gt; CRITICAL_ISSUES:{" "}
                  <span className="text-primary">{atsResult.critical_issues.length}</span>{" "}
                  DETECTED
                </p>
              )}
              {trendingSkills.length > 0 && (
                <p>&gt; TRENDING_SKILLS: {trendingSkills.slice(0, 3).join(", ")}</p>
              )}
              {(atsResult.missing_keywords?.length ?? 0) > 0 && (
                <p>&gt; ATS_GAPS: {atsResult.missing_keywords.slice(0, 3).join(", ")}</p>
              )}
              {atsResult.missing_keywords && atsResult.missing_keywords.length > 0 && (
                <p>
                  &gt; MISSING_KEYWORDS:{" "}
                  <span className="text-primary">{atsResult.missing_keywords.length}</span>{" "}
                  SUGGESTED
                </p>
              )}
              <p>
                &gt; STATUS: <span className="text-signal">ANALYSIS_COMPLETE</span>
              </p>
            </>
          ) : (
            <p>
              &gt; STATUS: <span className="text-[#666]">AWAITING_RESUME_UPLOAD</span>
            </p>
          )}
          <p className="mt-2">
            &gt; COMPLETE<span className="terminal-cursor">|</span>
          </p>
        </div>
      </div>
    </section>
  );
}
