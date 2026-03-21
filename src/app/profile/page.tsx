"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
          setUserProfile({ ...userProfile, roles: profile.roles, experienceLevel: profile.experience_level || userProfile.experienceLevel });
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
    return () => { cancelled = true; };
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

  const handleAnalyze = useCallback(async (file: File) => {
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
    } catch (err: unknown) {
      const error = err as { retry_after?: number; code?: string; message?: string; days_remaining?: number };
      if (error.retry_after) setRateLimitedUntil(Date.now() + error.retry_after * 1000);
      if (error.code === "REANALYSIS_COOLDOWN") setCooldownDays(error.days_remaining ?? null);
      setAnalyzeError(error.message || "Analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  }, [cooldownDays]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
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
  }, [handleAnalyze, setResumeUploaded]);

  const extractedSkills = useMemo(() => {
    if (atsResult?.ats_score) return atsResult.ats_score;
    const base = 12;
    return base + userProfile.roles.length * 3 + (userProfile.experienceLevel ? 2 : 0);
  }, [atsResult, userProfile.roles.length, userProfile.experienceLevel]);

  const remainingSeconds = rateLimitedUntil ? Math.max(0, Math.ceil((rateLimitedUntil - nowMs) / 1000)) : 0;
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;
  const countdownLabel = remainingSeconds > 0 ? `${minutes}:${String(seconds).padStart(2, "0")}` : "0:00";
  const suggestedSkills = atsResult?.suggested_additions ?? [];
  const isRateLimited = Boolean(rateLimitedUntil && rateLimitedUntil > nowMs);

  const exp = EXPERIENCE_MAP[userProfile.experienceLevel] ?? { label: "Senior+", roman: "IV" as const };

  return (
    <AppShell>
      <div className="space-y-10">
        <header className="pt-6">
          <h1 className="font-serif text-4xl md:text-6xl font-black leading-tight">
            Your <span className="text-primary italic font-black">Profile.</span>
          </h1>
          <p className="mono-label text-[11px] text-dim-text uppercase tracking-[0.2em] mt-4">
            Manage your intelligence parameters.
          </p>
        </header>

        {/* Desktop layout */}
        <div className="hidden md:grid md:grid-cols-12 gap-12">
          <aside className="md:col-span-4 flex flex-col gap-12">
            <AccountCard email={userProfile.email} onSignOut={() => { resetAll(); router.push("/"); }} />
            <ResumeCard extractedSkills={extractedSkills} onFileChange={handleFileChange} fileInputRef={fileInputRef} />
          </aside>
          <main className="md:col-span-8 flex flex-col gap-12">
            <RolesCard roles={userProfile.roles} />
            <ExperienceCard label={`${exp.label} / ${exp.roman}`} />
            <ResumeIntelligenceSection
              resumeUploaded={resumeUploaded}
              isAnalyzing={isAnalyzing}
              isRateLimited={isRateLimited}
              countdownLabel={countdownLabel}
              atsResult={atsResult}
              suggestedSkills={suggestedSkills}
              analyzeError={analyzeError}
              cooldownDays={cooldownDays}
              onUpload={() => fileInputRef.current?.click()}
            />
            <OperationalPreferencesSection hasAccount={hasAccount} />
            <TerminalCard extractedSkills={extractedSkills} atsResult={atsResult} suggestedSkills={suggestedSkills} />
          </main>
        </div>

        {/* Mobile layout */}
        <div className="md:hidden">
          <div className="flex gap-2 overflow-x-auto pb-2">
            {(["ACCOUNT", "ROLES", "OUTPUT"] as MobileTab[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setMobileTab(t)}
                className={`mono-label text-[11px] uppercase tracking-[0.05em] px-5 py-3 border border-border-dark transition-colors ${mobileTab === t ? "active-tab border-border-dark text-primary" : "bg-background-dark text-dim-text hover:bg-primary/10 hover:text-neutral-beige"}`}
              >
                {t}
              </button>
            ))}
          </div>
          {mobileTab === "ACCOUNT" && (
            <div className="space-y-10">
              <AccountCard email={userProfile.email} onSignOut={() => { resetAll(); router.push("/"); }} />
              <ResumeCard extractedSkills={extractedSkills} onFileChange={handleFileChange} fileInputRef={fileInputRef} />
            </div>
          )}
          {mobileTab === "ROLES" && (
            <div className="space-y-10">
              <RolesCard roles={userProfile.roles} />
              <ExperienceCard label={`${exp.label} / ${exp.roman}`} />
            </div>
          )}
          {mobileTab === "OUTPUT" && (
            <div className="space-y-12">
              <ResumeIntelligenceSection
                resumeUploaded={resumeUploaded}
                isAnalyzing={isAnalyzing}
                isRateLimited={isRateLimited}
                countdownLabel={countdownLabel}
                atsResult={atsResult}
                suggestedSkills={suggestedSkills}
                analyzeError={analyzeError}
                cooldownDays={cooldownDays}
                onUpload={() => fileInputRef.current?.click()}
              />
              <OperationalPreferencesSection hasAccount={hasAccount} />
              <TerminalCard extractedSkills={extractedSkills} atsResult={atsResult} suggestedSkills={suggestedSkills} />
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

function AccountCard({ email, onSignOut }: { email: string; onSignOut: () => void }) {
  return (
    <section>
      <h3 className="mono-label text-xs font-bold text-primary underline decoration-2 underline-offset-8">01 / ACCOUNT INFO</h3>
      <div className="space-y-4 mt-6">
        <div>
          <p className="mono-label text-[10px] text-neutral-beige/40 mb-1">ID_IDENTIFIER</p>
          <p className="font-mono text-lg">{email || "—"}</p>
        </div>
        <button type="button" onClick={onSignOut} className="mono-label text-xs text-primary hover:line-through inline-block">[ SIGN_OUT ]</button>
      </div>
    </section>
  );
}

function ResumeCard({ extractedSkills, onFileChange, fileInputRef }: { extractedSkills: number; onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void; fileInputRef: React.RefObject<HTMLInputElement> }) {
  return (
    <section>
      <h3 className="mono-label text-xs font-bold text-primary underline decoration-2 underline-offset-8">04 / RESUME MANAGEMENT</h3>
      <div className="brutalist-border p-6 border-dashed border-[#F0EDE6]/40 flex flex-col items-center justify-center text-center gap-4 mt-6">
        <span className="material-symbols-outlined text-4xl text-[#F0EDE6]/20">upload_file</span>
        <div>
          <p className="font-mono text-sm mb-1 uppercase">RESUME.PDF</p>
          <p className="mono-label text-[10px] text-primary">{extractedSkills} skills extracted_</p>
        </div>
        <label className="w-full">
          <input ref={fileInputRef} type="file" accept=".pdf,.txt" onChange={onFileChange} className="hidden" />
          <button type="button" onClick={() => fileInputRef.current?.click()} className="w-full brutalist-border-primary py-3 mono-label text-xs bg-primary/10 hover:bg-primary hover:text-white transition-all cursor-pointer">REPLACE_RESUME</button>
        </label>
      </div>
    </section>
  );
}

function RolesCard({ roles }: { roles: string[] }) {
  return (
    <section>
      <div className="flex justify-between items-end mb-8">
        <h3 className="mono-label text-xs font-bold text-primary underline decoration-2 underline-offset-8">02 / YOUR ROLES</h3>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {roles.length ? roles.map((r) => (
          <div key={r} className="brutalist-border-primary p-5 flex justify-between items-start bg-[rgba(255,45,0,0.06)]">
            <div>
              <p className="mono-label text-[10px] text-primary mb-2">ACTIVE_ROLE</p>
              <h4 className="font-serif text-[18px] font-black">{r}</h4>
            </div>
            <span className="material-symbols-outlined text-primary">check_circle</span>
          </div>
        )) : (
          <div className="brutalist-border p-6 bg-card-dark col-span-full">
            <p className="mono-label text-[11px] text-dim-text uppercase tracking-[0.05em]">No roles selected yet. Complete setup to personalize.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function ExperienceCard({ label }: { label: string }) {
  return (
    <section>
      <div className="flex justify-between items-end mb-8">
        <h3 className="mono-label text-xs font-bold text-primary underline decoration-2 underline-offset-8">03 / EXPERIENCE LEVEL</h3>
      </div>
      <div className="brutalist-border-primary p-8 bg-primary/5 relative overflow-hidden">
        <div className="relative z-10">
          <p className="mono-label text-xs text-[#F0EDE6]/60 mb-2">CURRENT_TIER</p>
          <h4 className="font-serif text-5xl md:text-6xl font-black italic leading-tight">{label}</h4>
        </div>
        <div className="absolute -right-4 -bottom-8 font-serif text-9xl font-black text-primary/5 select-none pointer-events-none hidden md:block">LVL</div>
      </div>
    </section>
  );
}

function ResumeIntelligenceSection({
  resumeUploaded, isAnalyzing, isRateLimited, countdownLabel, atsResult, suggestedSkills, analyzeError, cooldownDays, onUpload
}: {
  resumeUploaded: boolean; isAnalyzing: boolean; isRateLimited: boolean; countdownLabel: string;
  atsResult: AtsResult | null; suggestedSkills: string[]; analyzeError: string | null;
  cooldownDays: number | null; onUpload: () => void;
}) {
  const disabledByUpload = !resumeUploaded;
  const showRateLimitedText = isRateLimited && resumeUploaded;
  const buttonText = isAnalyzing ? "ANALYZING..." :
    disabledByUpload ? "UPLOAD RESUME TO ANALYZE" :
    showRateLimitedText ? `TRY AGAIN IN ${countdownLabel}` :
    "ANALYZE RESUME →";

  const buttonClassBase = "w-full py-4 mono-label text-[11px] font-bold uppercase tracking-[0.05em] transition-colors";
  const buttonClass = isAnalyzing ? `${buttonClassBase} bg-[#1a1a1a] text-[#666] border-1.5 border-[#2a2a2a] cursor-wait` :
    disabledByUpload ? `${buttonClassBase} bg-[#1a1a1a] text-[#444] border-1.5 border-[#2a2a2a] cursor-not-allowed` :
    showRateLimitedText ? `${buttonClassBase} bg-[#1a1a1a] text-[#666] border-1.5 border-[#2a2a2a] cursor-not-allowed` :
    `${buttonClassBase} bg-[#FF2D00] text-black border-1.5 border-[#FF2D00] cursor-pointer`;

  return (
    <section className={`brutalist-border-primary p-0 bg-card-dark border border-border-dark ${disabledByUpload ? "text-[#333]" : "text-neutral-beige"}`}>
      <div className="p-6 space-y-6">
        <div className="flex items-end justify-between gap-4">
          <h3 className={`mono-label text-xs font-bold ${disabledByUpload ? "text-[#333]" : "text-primary"}`}>05 / RESUME INTELLIGENCE</h3>
          {cooldownDays !== null && (
            <p className="mono-label text-[10px] text-dim-text">Re-analysis in {cooldownDays} days</p>
          )}
        </div>

        {/* ATS Results */}
        {atsResult && (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <span className="font-serif text-5xl font-black text-primary">{atsResult.ats_score}</span>
              <span className="mono-label text-[11px] text-dim-text uppercase">ATS SCORE</span>
            </div>
            {atsResult.critical_issues.length > 0 && (
              <div>
                <p className="mono-label text-[10px] text-primary uppercase mb-2">CRITICAL FIXES</p>
                <ul className="space-y-1">
                  {atsResult.critical_issues.map((issue, i) => (
                    <li key={i} className="font-mono text-[11px] text-neutral-beige/80 flex gap-2">
                      <span className="text-primary">→</span>{issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {suggestedSkills.length > 0 && (
              <div>
                <p className="mono-label text-[10px] text-primary uppercase mb-2">SUGGESTED ADDITIONS</p>
                <div className="flex flex-wrap gap-2">
                  {suggestedSkills.map((skill) => (
                    <span key={skill} className="mono-label text-[10px] px-2 py-1 border border-primary/60 text-primary uppercase tracking-[0.02em]">{skill}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {analyzeError && (
          <p className="font-mono text-[11px] text-primary/80">{analyzeError}</p>
        )}

        <button
          type="button"
          disabled={disabledByUpload || isAnalyzing || showRateLimitedText}
          onClick={disabledByUpload ? onUpload : undefined}
          className={buttonClass}
        >
          {buttonText}
        </button>
      </div>
    </section>
  );
}

function OperationalPreferencesSection({ hasAccount }: { hasAccount: boolean }) {
  const [highDisruption, setHighDisruption] = useState(false);
  const [jobMatchAlerts, setJobMatchAlerts] = useState(false);
  return (
    <section className="space-y-4">
      <h3 className="mono-label text-xs font-bold text-primary underline decoration-2 underline-offset-8">06 / OPERATIONAL PREFERENCES</h3>
      <div className="space-y-4">
        <ToggleRow label="HIGH DISRUPTION ALERT" value={highDisruption} onChange={setHighDisruption} />
        <div className="opacity-100">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-mono text-[10px] text-[#444] uppercase tracking-[0.05em] font-bold">JOB MATCH ALERTS</p>
              <p className="font-mono text-[10px] text-[#8c8c8c] mt-2">REQUIRES ACCOUNT — COMING SOON</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[#8c8c8c] text-[18px] leading-none">🔒</span>
              <ToggleSwitch checked={jobMatchAlerts} onToggle={() => { if (!hasAccount) return; setJobMatchAlerts(v => !v); }} disabled={!hasAccount} />
            </div>
          </div>
          <div className="border-t border-border-dark mt-4" />
        </div>
      </div>
    </section>
  );
}

function ToggleRow({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <p className="font-mono text-[10px] text-neutral-beige uppercase tracking-[0.05em] font-bold">{label}</p>
      <ToggleSwitch checked={value} onToggle={() => onChange(!value)} />
    </div>
  );
}

function ToggleSwitch({ checked, onToggle, disabled }: { checked: boolean; onToggle: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={() => { if (disabled) return; onToggle(); }}
      aria-pressed={checked}
      className={`w-[44px] h-[24px] border-1.5 border-border-dark ${disabled ? "bg-[#1a1a1a] cursor-not-allowed" : checked ? "bg-primary/10 border-primary" : "bg-card-dark hover:bg-primary/5"}`}
    >
      <span className={`block w-[20px] h-[20px] border-1.5 border-border-dark ${checked ? "translate-x-[18px] bg-[#FF2D00]" : "translate-x-[2px] bg-[#0E0E0E]"} transition-transform`} />
    </button>
  );
}

function TerminalCard({ extractedSkills, atsResult, suggestedSkills }: { extractedSkills: number; atsResult: AtsResult | null; suggestedSkills: string[] }) {
  return (
    <section>
      <div className="brutalist-border p-4 bg-black">
        <div className="flex items-center gap-2 mb-4 border-b border-[#F0EDE6]/10 pb-2">
          <div className="w-2 h-2 rounded-none bg-[#FF2D00]" />
          <div className="w-2 h-2 rounded-none bg-[#00ff41]" />
          <div className="w-2 h-2 rounded-none bg-[#f0ede6]/60" />
          <p className="mono-label text-[10px] ml-4 text-[#F0EDE6]/40 uppercase">TERMINAL_OUTPUT_SESSION_LOG</p>
        </div>
        <div className="font-mono text-[11px] leading-relaxed text-[#F0EDE6]/70">
          <p>&gt; INITIALIZING PROFILE_ANALYSIS...</p>
          <p>&gt; ANALYZING {extractedSkills} SKILLS FROM ATTACHMENT...</p>
          {atsResult && <p>&gt; ATS_SCORE: <span className="text-primary">{atsResult.ats_score}</span></p>}
          {suggestedSkills.length > 0 && <p>&gt; SUGGESTED_KEYWORDS: {suggestedSkills.slice(0, 3).join(", ")}...</p>}
          <p>&gt; STATUS: <span className="text-success-glow">OPTIMIZED_FOR_TREND_04</span></p>
          <p className="mt-2">&gt; COMPLETE<span className="terminal-cursor">|</span></p>
        </div>
      </div>
    </section>
  );
}
