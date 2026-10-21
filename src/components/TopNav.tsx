"use client";

import Link from "next/link";
import { Icon } from "@/components/Icon";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchBadgeCounts, markFeedSeen } from "@/lib/api";

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

  const handleMarkSeen = async () => {
    setRefreshing(true);
    try {
      const counts = await markFeedSeen();
      setNewJobs(counts.new_jobs ?? 0);
      setNewNews(counts.new_news ?? 0);
      setBadgeCount((counts.new_jobs ?? 0) + (counts.new_news ?? 0));
      setBannerDismissedTotal(0);
    } catch (e) {
      console.error("Could not mark the feed as seen", e);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <header className="sticky top-0 z-50 border-b border-border-dark bg-background-dark/95 backdrop-blur-[2px]">
      <div className="mx-auto flex w-full max-w-[1440px] items-center justify-between gap-6 px-5 py-3 md:px-12">
        <Link href="/setup/1" className="group flex items-center gap-3">
          <span className="relative flex h-6 w-6 items-center justify-center border border-border-dark">
            <span className="lamp lamp--live" aria-hidden />
          </span>
          <span className="mono-label text-neutral-beige">
            TazaKhabar<span className="text-dim-text">/MK-II</span>
          </span>
        </Link>

        <nav aria-label="Primary" className="hidden items-center gap-1 md:flex">
          {navLinks.map((l) => {
            const isActive = pathname === l.href || pathname.startsWith(l.matchPrefix);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={isActive ? "page" : undefined}
                className={`tab border-transparent px-3 py-2 ${isActive ? "" : "!border-transparent"}`}
              >
                <span className={`lamp ${isActive ? "lamp--live" : "lamp--off"}`} aria-hidden />
                {l.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          {badgeCount > 0 && (
            <div
              className="flex items-center gap-2 border border-primary/50 bg-primary/10 px-2 py-1"
              role="status"
              aria-label={`${badgeCount} new items available`}
            >
              <span className="lamp lamp--live" aria-hidden />
              <span className="mono-data text-[11px] font-semibold text-primary">
                {badgeCount > 99 ? "99+" : String(badgeCount).padStart(2, "0")}
              </span>
            </div>
          )}
          <Link
            href="/profile"
            className="tab border-transparent px-2 py-2"
            aria-label="Profile"
            aria-current={pathname.startsWith("/profile") ? "page" : undefined}
          >
            <Icon name="person" className="text-[20px]" aria-hidden />
          </Link>
        </div>
      </div>

      {/* Refresh strip shown below nav when there are new items */}
      {((newJobs > 0 || newNews > 0) &&
        (bannerDismissedTotal ?? -1) !== newJobs + newNews) && (
        <div className="border-t border-border-dark bg-card-dark">
          <div className="mx-auto flex w-full max-w-[1440px] flex-wrap items-center justify-between gap-3 px-5 py-3 md:px-12">
            <div className="flex items-center gap-3">
              <span className="lamp lamp--live" aria-hidden />
              <div>
                <p className="mono-label text-neutral-beige">
                  {newJobs > 0 && <span>{newJobs} new job{newJobs > 1 ? "s" : ""}</span>}
                  {newJobs > 0 && newNews > 0 && <span className="px-2 text-dim-text">/</span>}
                  {newNews > 0 && <span>{newNews} new news</span>}
                </p>
                <p className="mono-label mt-1 text-[10px] text-dim-text">
                  New items found since you last checked in.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button type="button" onClick={dismissBanner} className="btn !py-2 !px-3">
                Dismiss
              </button>
              <button
                type="button"
                onClick={handleMarkSeen}
                disabled={refreshing}
                className="btn btn--primary !py-2 !px-3"
              >
                {refreshing ? "Saving..." : "Mark as seen"}
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
