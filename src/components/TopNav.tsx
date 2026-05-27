"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchBadgeCounts, triggerRefresh } from "@/lib/api";

const navLinks = [
  { href: "/setup/1", label: "01/SETUP", matchPrefix: "/setup" },
  { href: "/jobs", label: "02/JOBS", matchPrefix: "/jobs" },
  { href: "/trends", label: "03/TRENDS", matchPrefix: "/trends" },
  { href: "/qa", label: "04/Q&A", matchPrefix: "/qa" },
  { href: "/digest", label: "05/DIGEST", matchPrefix: "/digest" },
];

export default function TopNav() {
  const pathname = usePathname();
  const [badgeCount, setBadgeCount] = useState(0);
  const [newJobs, setNewJobs] = useState(0);
  const [newNews, setNewNews] = useState(0);
  const [bannerDismissedTotal, setBannerDismissedTotal] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // FRESH-04 / M3: Poll badge counts every 60 seconds and update local state
  useEffect(() => {
    const localKey = "tazakhabar:refreshDismissedTotal";
    try {
      const raw = localStorage.getItem(localKey);
      if (raw !== null) setBannerDismissedTotal(Number(raw));
    } catch {
      /* ignore */
    }

    const fetchAndSetBadge = async () => {
      try {
        const counts = await fetchBadgeCounts();
        const total = (counts.new_jobs ?? 0) + (counts.new_news ?? 0);
        setNewJobs(counts.new_jobs ?? 0);
        setNewNews(counts.new_news ?? 0);
        setBadgeCount(total);
      } catch {
        // Silently fail, keep current badge count
      }
    };

    // Fetch immediately on mount
    fetchAndSetBadge();

    // Poll every 60 seconds
    const interval = setInterval(fetchAndSetBadge, 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  // Persist dismiss
  const dismissBanner = () => {
    const total = newJobs + newNews;
    try {
      localStorage.setItem("tazakhabar:refreshDismissedTotal", String(total));
    } catch {
      // ignore
    }
    setBannerDismissedTotal(total);
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await triggerRefresh();
      const total = (res.new_jobs ?? 0) + (res.new_news ?? 0);
      setNewJobs(res.new_jobs ?? 0);
      setNewNews(res.new_news ?? 0);
      setBadgeCount(total);
      // after refresh, persist dismissed total so banner stays hidden
      try {
        localStorage.setItem("tazakhabar:refreshDismissedTotal", String(total));
      } catch {}
      setBannerDismissedTotal(total);
    } catch (e) {
      console.error("Refresh failed", e);
    } finally {
      setRefreshing(false);
    }
  };

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
      {/* Refresh banner shown below nav when there are new items */}
      {((newJobs > 0 || newNews > 0) && (bannerDismissedTotal ?? -1) !== (newJobs + newNews)) && (
        <div className="mt-2 flex items-center justify-between gap-4 rounded-b-md bg-primary/10 px-6 py-3 text-sm text-primary">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-[20px]">notifications</span>
            <div>
              <div>
                {newJobs > 0 && <span className="font-semibold">{newJobs} new job{newJobs>1?"s":""}</span>}
                {newJobs > 0 && newNews > 0 && <span className="px-1">•</span>}
                {newNews > 0 && <span className="font-semibold">{newNews} new news</span>}
              </div>
              <div className="text-xs text-primary/80">New items are available since the last report.</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={dismissBanner}
              className="rounded-md border border-primary/30 bg-transparent px-3 py-1 text-sm text-primary hover:bg-primary/5"
            >
              Dismiss
            </button>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="rounded-md bg-primary px-3 py-1 text-sm font-semibold text-background-dark disabled:opacity-60"
            >
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>
      )}
    </header>
  );
}

