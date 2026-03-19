"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTaza } from "./TazaContext";

const tabs = [
  { href: "/setup/1", icon: "radar", label: "SETUP", matchPrefix: "/setup" },
  { href: "/jobs", icon: "work", label: "JOBS", matchPrefix: "/jobs" },
  { href: "/trends", icon: "trending_up", label: "TRENDS", matchPrefix: "/trends" },
  { href: "/digest", icon: "newspaper", label: "DIGEST", matchPrefix: "/digest" },
  { href: "/profile", icon: "person", label: "PROFILE", matchPrefix: "/profile" },
];

export default function BottomNav() {
  const pathname = usePathname();
  const { feedNewCount, radarNewCount } = useTaza();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border-dark bg-background-dark md:hidden">
      <div className="grid grid-cols-5">
        {tabs.map((t) => {
          const isActive = pathname === t.href || pathname.startsWith(t.matchPrefix);
          return (
            <Link
              key={t.href}
              href={t.href}
              className={`flex flex-col items-center justify-center gap-1 py-3 ${
                isActive ? "active-tab text-primary" : "text-dim-text hover:text-neutral-beige"
              }`}
            >
              <span className="relative inline-flex items-center justify-center">
                <span
                  className={`material-symbols-outlined text-[22px] ${
                    isActive ? "text-primary" : "text-dim-text"
                  }`}
                >
                  {t.icon}
                </span>
                {t.icon === "newspaper" && feedNewCount > 0 ? (
                  <span className="absolute -top-2 -right-2 inline-flex h-[8px] w-[8px] items-center justify-center rounded-full bg-[#FF2D00] text-white">
                    <span className="font-mono text-[7px] font-bold leading-none">
                      {feedNewCount}
                    </span>
                  </span>
                ) : null}
                {t.icon === "radar" && radarNewCount > 0 ? (
                  <span className="absolute -top-2 -right-2 inline-flex h-[8px] w-[8px] items-center justify-center rounded-full bg-[#FF2D00] text-white">
                    <span className="font-mono text-[7px] font-bold leading-none">
                      {radarNewCount}
                    </span>
                  </span>
                ) : null}
              </span>
              <span className="mono-label text-[9px] leading-none">{t.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

