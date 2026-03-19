"use client";

import { useRouter } from "next/navigation";
import { useTaza } from "@/components/TazaContext";
import Link from "next/link";

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

export default function SetupStep1Page() {
  const router = useRouter();
  const { userProfile, setUserProfile } = useTaza();

  const selected = userProfile.roles;

  function toggleRole(role: string) {
    const has = selected.includes(role);
    const nextRoles = has
      ? selected.filter((r) => r !== role)
      : [...selected, role];
    setUserProfile({ ...userProfile, roles: nextRoles });
  }

  return (
    <div className="min-h-screen flex flex-col px-6 py-10 bg-background-dark">
      <div className="w-full max-w-2xl mx-auto flex flex-col flex-1">
        <div className="w-full">
          <div className="h-[2px] bg-border-dark">
            <div style={{ width: "33%" }} className="h-full bg-primary" />
          </div>

          <p className="mono-label text-[10px] text-primary mt-6">
            STEP 01 OF 03
          </p>

          <h1 className="font-serif text-4xl md:text-5xl font-black mt-6">
            What roles are{" "}
            <span className="text-primary italic font-black">you targeting?</span>
          </h1>
        </div>

        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {ROLE_CHIPS.map((role) => {
            const isSelected = selected.includes(role);
            return (
              <button
                key={role}
                type="button"
                onClick={() => toggleRole(role)}
                className={`px-4 py-3 text-left brutalist-border font-mono text-[12px] uppercase tracking-[0.05em] transition-colors ${
                  isSelected
                    ? "brutalist-border-primary bg-[rgba(255,45,0,0.1)]"
                    : "bg-background-dark hover:bg-primary/10"
                }`}
              >
                {role}
              </button>
            );
          })}
        </div>

        <div className="mt-auto pt-10 flex items-center justify-between gap-4">
          <Link
            href="/auth"
            className="brutalist-border px-6 py-3 mono-label text-[11px] hover:bg-primary/10"
          >
            BACK
          </Link>
          <button
            type="button"
            onClick={() => router.push("/setup/2")}
            className="brutalist-border-primary bg-primary/10 px-6 py-3 mono-label text-[11px] text-neutral-beige hover:bg-primary/20 transition-colors"
          >
            CONTINUE
          </button>
        </div>
      </div>
    </div>
  );
}

