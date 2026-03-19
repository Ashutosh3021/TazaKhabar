"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTaza } from "@/components/TazaContext";

const OPTIONS = [
  { roman: "I", title: "Fresher / Student", years: "0-1 Years" },
  { roman: "II", title: "Early Career", years: "1-3 Years" },
  { roman: "III", title: "Mid-Level", years: "3-7 Years" },
  { roman: "IV", title: "Senior+", years: "7+ Years" },
] as const;

export default function SetupStep2Page() {
  const router = useRouter();
  const { userProfile, setUserProfile } = useTaza();

  return (
    <div className="min-h-screen flex flex-col px-6 py-10 bg-background-dark">
      <div className="w-full max-w-2xl mx-auto flex flex-col flex-1">
        <div className="h-[2px] bg-border-dark">
          <div style={{ width: "66%" }} className="h-full bg-primary" />
        </div>

        <p className="mono-label text-[10px] text-primary mt-6">STEP 02 OF 03</p>

        <h1 className="font-serif text-4xl md:text-5xl font-black mt-6 leading-tight">
          Experience{" "}
          <span className="text-primary italic font-black">level?</span>
        </h1>

        <div className="mt-10 flex flex-col gap-4">
          {OPTIONS.map((o) => {
            const isSelected = userProfile.experienceLevel === o.roman;
            return (
              <button
                key={o.roman}
                type="button"
                onClick={() =>
                  setUserProfile({ ...userProfile, experienceLevel: o.roman })
                }
                className={`text-left px-5 py-5 brutalist-border transition-colors ${
                  isSelected
                    ? "brutalist-border-primary bg-[rgba(255,45,0,0.1)]"
                    : "bg-background-dark hover:bg-primary/10"
                }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="mono-label text-[11px] text-neutral-beige/80">
                      {o.title}
                    </p>
                    <p className="mono-label text-[10px] text-dim-text mt-1">
                      {o.years}
                    </p>
                  </div>
                  <div className="font-serif text-5xl md:text-6xl font-black italic text-neutral-beige">
                    {o.roman}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-auto pt-10 flex items-center justify-between gap-4">
          <Link
            href="/setup/1"
            className="brutalist-border px-6 py-3 mono-label text-[11px] hover:bg-primary/10"
          >
            BACK
          </Link>
          <button
            type="button"
            onClick={() => router.push("/setup/3")}
            className="brutalist-border-primary bg-primary/10 px-6 py-3 mono-label text-[11px] text-neutral-beige hover:bg-primary/20 transition-colors"
          >
            CONTINUE
          </button>
        </div>
      </div>
    </div>
  );
}

