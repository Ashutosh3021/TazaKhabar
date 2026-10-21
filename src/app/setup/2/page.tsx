"use client";

import { useRouter } from "next/navigation";
import { useTaza } from "@/components/TazaContext";
import { SetupFrame } from "@/components/SetupFrame";
import { updateProfile } from "@/lib/api";

const OPTIONS = [
  { roman: "I", title: "Fresher / Student", years: "0 to 1 years" },
  { roman: "II", title: "Early Career", years: "1 to 3 years" },
  { roman: "III", title: "Mid-Level", years: "3 to 7 years" },
  { roman: "IV", title: "Senior+", years: "7+ years" },
] as const;

export default function SetupStep2Page() {
  const router = useRouter();
  const { userProfile, setUserProfile } = useTaza();

  return (
    <SetupFrame
      step={2}
      title={
        <>
          Experience <span className="accent">level?</span>
        </>
      }
      backHref="/setup/1"
      backLabel="Back"
      onNext={() => router.push("/setup/3")}
      nextLabel="Continue"
    >
      <div className="flex flex-col gap-2">
        {OPTIONS.map((o) => {
          const isSelected = userProfile.experienceLevel === o.roman;
          return (
            <button
              key={o.roman}
              type="button"
              aria-pressed={isSelected}
              onClick={() => {
                setUserProfile({ ...userProfile, experienceLevel: o.roman });
                updateProfile({ experience_level: o.roman }).catch(() => undefined);
              }}
              className={`panel flex items-center justify-between gap-4 p-5 text-left transition-colors ${
                isSelected ? "panel--accent bg-primary/[0.06]" : "hover:bg-card-hi"
              }`}
            >
              <div>
                <p className="mono-label text-neutral-beige">{o.title}</p>
                <p className="mono-label mt-1 text-[10px] text-dim-text">{o.years}</p>
              </div>
              <div className="flex items-center gap-4">
                <span
                  className={`display text-[clamp(2rem,1.5rem+2vw,3rem)] ${isSelected ? "text-primary" : "text-neutral-beige/25"}`}
                  aria-hidden
                >
                  {o.roman}
                </span>
                <span className={`lamp ${isSelected ? "lamp--live" : "lamp--off"}`} aria-hidden />
              </div>
            </button>
          );
        })}
      </div>
    </SetupFrame>
  );
}
