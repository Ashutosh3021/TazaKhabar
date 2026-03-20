"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchBadgeCounts } from "@/lib/api";

const navLinks = [
  { href: "/setup/1", label: "01/SETUP", matchPrefix: "/setup" },
  { href: "/jobs", label: "02/JOBS", matchPrefix: "/jobs" },
  { href: "/trends", label: "03/TRENDS", matchPrefix: "/trends" },
  { href: "/digest", label: "04/DIGEST", matchPrefix: "/digest" },
];

export default function TopNav() {
  const pathname = usePathname();
  const [badgeCount, setBadgeCount] = useState(0);

  // FRESH-04: Poll badge counts every 5 minutes
  useEffect(() => {
    const fetchAndSetBadge = async () => {
      try {
        const counts = await fetchBadgeCounts();
        const total = counts.radar_new_count + counts.feed_new_count;
        setBadgeCount(total);
      } catch {
        // Silently fail, keep current badge count
      }
    };

    // Fetch immediately on mount
    fetchAndSetBadge();

    // Poll every 5 minutes
    const interval = setInterval(fetchAndSetBadge, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-50 border-b border-border-dark bg-background-dark px-6 py-4 md:px-20">
      <div className="flex items-center justify-between">
        <Link href="/setup/1" className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[26px] text-neutral-beige">
            radar
          </span>
          <span className="mono-label text-sm text-neutral-beige">TazaKhabar</span>
        </Link>

        <nav className="hidden items-center gap-8 md:flex">
          {navLinks.map((l) => {
            const isActive = pathname === l.href || pathname.startsWith(l.matchPrefix);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`mono-label text-sm tracking-[0.05em] transition-colors ${
                  isActive ? "text-primary" : "text-dim-text hover:text-neutral-beige"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-4">
          {/* Badge indicator for new items */}
          {badgeCount > 0 && (
            <div className="relative">
              <span className="material-symbols-outlined text-[20px] text-primary">
                circle
              </span>
              <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-background-dark">
                {badgeCount > 99 ? "99+" : badgeCount}
              </span>
            </div>
          )}
          <Link href="/profile" className="text-neutral-beige hover:text-primary">
            <span className="material-symbols-outlined text-[26px]">person</span>
          </Link>
        </div>
      </div>
    </header>
  );
}

