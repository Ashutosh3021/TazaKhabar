"use client";

import { useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import { useRouter } from "next/navigation";
import { useTaza } from "@/components/TazaContext";

const EXPERIENCE_MAP: Record<
  string,
  { label: string; roman: "I" | "II" | "III" | "IV" }
> = {
  I: { label: "Fresher", roman: "I" },
  II: { label: "Early Career", roman: "II" },
  III: { label: "Mid-Level", roman: "III" },
  IV: { label: "Senior+", roman: "IV" },
};

type MobileTab = "ACCOUNT" | "ROLES" | "OUTPUT";

export default function ProfilePage() {
  const router = useRouter();
  const { userProfile, resetAll } = useTaza();

  const [mobileTab, setMobileTab] = useState<MobileTab>("ACCOUNT");

  const extractedSkills = useMemo(() => {
    const base = 12;
    return base + userProfile.roles.length * 3 + (userProfile.experienceLevel ? 2 : 0);
  }, [userProfile.experienceLevel, userProfile.roles.length]);

  const exp = EXPERIENCE_MAP[userProfile.experienceLevel] ?? {
    label: "Senior+",
    roman: "IV" as const,
  };

  return (
    <AppShell>
      <div className="space-y-10">
        <header className="pt-6">
          <h1 className="font-serif text-4xl md:text-6xl font-black leading-tight">
            Your{" "}
            <span className="text-primary italic font-black">Profile.</span>
          </h1>
          <p className="mono-label text-[11px] text-dim-text uppercase tracking-[0.2em] mt-4">
            Manage your intelligence parameters.
          </p>
        </header>

        {/* Desktop layout */}
        <div className="hidden md:grid md:grid-cols-12 gap-12">
          <aside className="md:col-span-4 flex flex-col gap-12">
            <AccountCard
              email={userProfile.email}
              onSignOut={() => {
                resetAll();
                router.push("/");
              }}
            />
            <ResumeCard extractedSkills={extractedSkills} />
          </aside>

          <main className="md:col-span-8 flex flex-col gap-12">
            <RolesCard roles={userProfile.roles} />
            <ExperienceCard label={`${exp.label} / ${exp.roman}`} />
            <TerminalCard extractedSkills={extractedSkills} />
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
                className={`mono-label text-[11px] uppercase tracking-[0.05em] px-5 py-3 border border-border-dark transition-colors ${
                  mobileTab === t
                    ? "active-tab border-border-dark text-primary"
                    : "bg-background-dark text-dim-text hover:bg-primary/10 hover:text-neutral-beige"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {mobileTab === "ACCOUNT" ? (
            <div className="space-y-10">
              <AccountCard
                email={userProfile.email}
                onSignOut={() => {
                  resetAll();
                  router.push("/");
                }}
              />
              <ResumeCard extractedSkills={extractedSkills} />
            </div>
          ) : null}

          {mobileTab === "ROLES" ? (
            <div className="space-y-10">
              <RolesCard roles={userProfile.roles} />
              <ExperienceCard label={`${exp.label} / ${exp.roman}`} />
            </div>
          ) : null}

          {mobileTab === "OUTPUT" ? (
            <TerminalCard extractedSkills={extractedSkills} />
          ) : null}
        </div>
      </div>
    </AppShell>
  );
}

function AccountCard({
  email,
  onSignOut,
}: {
  email: string;
  onSignOut: () => void;
}) {
  return (
    <section>
      <h3 className="mono-label text-xs font-bold text-primary underline decoration-2 underline-offset-8">
        01 / ACCOUNT INFO
      </h3>
      <div className="space-y-4 mt-6">
        <div>
          <p className="mono-label text-[10px] text-neutral-beige/40 mb-1">
            ID_IDENTIFIER
          </p>
          <p className="font-mono text-lg">{email || "—"}</p>
        </div>
        <button
          type="button"
          onClick={onSignOut}
          className="mono-label text-xs text-primary hover:line-through inline-block"
        >
          [ SIGN_OUT ]
        </button>
      </div>
    </section>
  );
}

function ResumeCard({ extractedSkills }: { extractedSkills: number }) {
  return (
    <section>
      <h3 className="mono-label text-xs font-bold text-primary underline decoration-2 underline-offset-8">
        04 / RESUME MANAGEMENT
      </h3>

      <div className="brutalist-border p-6 border-dashed border-[#F0EDE6]/40 flex flex-col items-center justify-center text-center gap-4 mt-6">
        <span className="material-symbols-outlined text-4xl text-[#F0EDE6]/20">
          upload_file
        </span>
        <div>
          <p className="font-mono text-sm mb-1 uppercase">RESUME.PDF</p>
          <p className="mono-label text-[10px] text-primary">
            {extractedSkills} skills extracted_
          </p>
        </div>
        <button
          type="button"
          className="w-full brutalist-border-primary py-3 mono-label text-xs bg-primary/10 hover:bg-primary hover:text-white transition-all"
        >
          REPLACE_RESUME
        </button>
      </div>
    </section>
  );
}

function RolesCard({ roles }: { roles: string[] }) {
  return (
    <section>
      <div className="flex justify-between items-end mb-8">
        <h3 className="mono-label text-xs font-bold text-primary underline decoration-2 underline-offset-8">
          02 / YOUR ROLES
        </h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {roles.length ? (
          roles.map((r) => (
            <div
              key={r}
              className="brutalist-border-primary p-5 flex justify-between items-start bg-[rgba(255,45,0,0.06)]"
            >
              <div>
                <p className="mono-label text-[10px] text-primary mb-2">
                  ACTIVE_ROLE
                </p>
                <h4 className="font-serif text-[18px] font-black">{r}</h4>
              </div>
              <span className="material-symbols-outlined text-primary">
                check_circle
              </span>
            </div>
          ))
        ) : (
          <div className="brutalist-border p-6 bg-card-dark col-span-full">
            <p className="mono-label text-[11px] text-dim-text uppercase tracking-[0.05em]">
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
    <section>
      <div className="flex justify-between items-end mb-8">
        <h3 className="mono-label text-xs font-bold text-primary underline decoration-2 underline-offset-8">
          03 / EXPERIENCE LEVEL
        </h3>
      </div>
      <div className="brutalist-border-primary p-8 bg-primary/5 relative overflow-hidden">
        <div className="relative z-10">
          <p className="mono-label text-xs text-[#F0EDE6]/60 mb-2">
            CURRENT_TIER
          </p>
          <h4 className="font-serif text-5xl md:text-6xl font-black italic leading-tight">
            {label}
          </h4>
        </div>
        <div className="absolute -right-4 -bottom-8 font-serif text-9xl font-black text-primary/5 select-none pointer-events-none hidden md:block">
          LVL
        </div>
      </div>
    </section>
  );
}

function TerminalCard({ extractedSkills }: { extractedSkills: number }) {
  return (
    <section>
      <div className="brutalist-border p-4 bg-black">
        <div className="flex items-center gap-2 mb-4 border-b border-[#F0EDE6]/10 pb-2">
          <div className="w-2 h-2 rounded-none bg-[#ff2f00]" />
          <div className="w-2 h-2 rounded-none bg-[#00ff41]" />
          <div className="w-2 h-2 rounded-none bg-[#f0ede6]/60" />
          <p className="mono-label text-[10px] ml-4 text-[#F0EDE6]/40 uppercase">
            TERMINAL_OUTPUT_SESSION_LOG
          </p>
        </div>

        <div className="font-mono text-[11px] leading-relaxed text-[#F0EDE6]/70">
          <p>&gt; INITIALIZING PROFILE_ANALYSIS...</p>
          <p>&gt; ANALYZING {extractedSkills} SKILLS FROM ATTACHMENT...</p>
          <p>
            &gt; STATUS:{" "}
            <span className="text-success-glow">OPTIMIZED_FOR_TREND_04</span>
          </p>
          <p className="mt-2">
            &gt; COMPLETE
            <span className="terminal-cursor">|</span>
          </p>
        </div>
      </div>
    </section>
  );
}

