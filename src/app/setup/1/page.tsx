"use client";

import { useRouter } from "next/navigation";
import { useTaza } from "@/components/TazaContext";
import { SetupFrame } from "@/components/SetupFrame";
import { updateProfile } from "@/lib/api";

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
    const nextRoles = has ? selected.filter((r) => r !== role) : [...selected, role];
    setUserProfile({ ...userProfile, roles: nextRoles });
    // Keep the server copy in sync so personalization has the same roles.
    updateProfile({ roles: nextRoles }).catch(() => undefined);
  }

  return (
    <SetupFrame
      step={1}
      title={
        <>
          What roles are <span className="accent">you targeting?</span>
        </>
      }
      backHref="/auth"
      backLabel="Back"
      onNext={() => router.push("/setup/2")}
      nextLabel="Continue"
    >
      <p className="mono-label mb-6 text-dim-text">
        {selected.length > 0
          ? `${String(selected.length).padStart(2, "0")} channel${selected.length > 1 ? "s" : ""} armed`
          : "Select every role you want the radar to watch"}
      </p>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {ROLE_CHIPS.map((role) => {
          const isSelected = selected.includes(role);
          return (
            <button
              key={role}
              type="button"
              aria-pressed={isSelected}
              onClick={() => toggleRole(role)}
              className={`chip justify-between !px-4 !py-3 !text-[12px] ${isSelected ? "is-on" : ""}`}
            >
              <span>{role}</span>
              <span className={`lamp ${isSelected ? "lamp--live" : "lamp--off"}`} aria-hidden />
            </button>
          );
        })}
      </div>
    </SetupFrame>
  );
}
