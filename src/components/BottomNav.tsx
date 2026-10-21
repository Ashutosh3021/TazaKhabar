"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/Icon";
import { useTaza } from "./TazaContext";

const tabs = [
  { href: "/setup/1", icon: "radar", label: "SETUP", matchPrefix: "/setup" },
  { href: "/jobs", icon: "work", label: "JOBS", matchPrefix: "/jobs" },
  { href: "/trends", icon: "trending_up", label: "TRENDS", matchPrefix: "/trends" },
  { href: "/qa", icon: "question_answer", label: "Q&A", matchPrefix: "/qa" },
  { href: "/digest", icon: "newspaper", label: "DIGEST", matchPrefix: "/digest" },
  { href: "/profile", icon: "person", label: "PROFILE", matchPrefix: "/profile" },
];

export default function BottomNav() {
  const pathname = usePathname();
  const { feedNewCount, radarNewCount } = useTaza();

  return (
    <nav
      aria-label="Primary"
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-border-dark bg-background-dark md:hidden"
    >
      <div className="grid grid-cols-6">
        {tabs.map((t) => {
          const isActive = pathname === t.href || pathname.startsWith(t.matchPrefix);
          const feedBadge = t.icon === "newspaper" && feedNewCount > 0;
          const radarBadge = t.icon === "radar" && radarNewCount > 0;
          return (
            <Link
              key={t.href}
              href={t.href}
              aria-current={isActive ? "page" : undefined}
              className={`relative flex min-h-[56px] flex-col items-center justify-center gap-1 py-2 transition-colors ${
                isActive ? "text-primary" : "text-dim-text"
              }`}
            >
              <span
                aria-hidden
                className={`absolute inset-x-0 top-0 h-[2px] origin-left transition-transform duration-200 ${
                  isActive ? "scale-x-100 bg-primary" : "scale-x-0 bg-primary"
                }`}
              />
              <span className="relative inline-flex items-center justify-center">
                <Icon name={t.icon} className="text-[20px]" aria-hidden />
                {(feedBadge || radarBadge) && (
                  <span
                    className="absolute -top-1.5 -right-1.5 inline-flex h-[10px] w-[10px] items-center justify-center bg-primary"
                    aria-hidden
                  />
                )}
              </span>
              <span className="mono-label text-[8px] leading-none">{t.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
