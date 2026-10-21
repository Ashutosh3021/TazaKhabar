"use client";

import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/Icon";
import AppShell from "@/components/AppShell";
import { useTaza } from "@/components/TazaContext";
import { fetchDigest } from "@/lib/api";
import type { DigestItem } from "@/types";

type Tab = "ALL" | "HIRING" | "LAYOFFS" | "FUNDING" | "SKILLS";

function formatMonoDate(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function DigestPage() {
  const [tab, setTab] = useState<Tab>("ALL");
  const { feedNewCount, refreshFeed, isFetchingFeed, feedVersion, savedJobs, toggleSavedJob, userProfile } =
    useTaza();
  const [digestItems, setDigestItems] = useState<DigestItem[]>([]);
  const [apiError, setApiError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadDigest() {
      try {
        const result = await fetchDigest({ skip: 0, limit: 20 });
        if (!cancelled) {
          setDigestItems(result.data as DigestItem[]);
          setApiError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setApiError(err instanceof Error ? err.message : "Failed to load digest");
          setDigestItems([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadDigest();
    return () => {
      cancelled = true;
    };
  }, [feedVersion]);

  const featured = useMemo(() => {
    if (digestItems.length === 0) return null;
    const shift = feedVersion % digestItems.length;
    const rotated = [...digestItems.slice(shift), ...digestItems.slice(0, shift)];
    return rotated.find((d) => d.featured) ?? rotated[0];
  }, [feedVersion, digestItems]);

  const rotatedDigest = useMemo(() => {
    if (digestItems.length === 0) return [];
    const shift = feedVersion % digestItems.length;
    return [...digestItems.slice(shift), ...digestItems.slice(0, shift)];
  }, [feedVersion, digestItems]);

  const list = useMemo(() => {
    const nonFeatured = featured
      ? rotatedDigest.filter((d) => d.id !== featured.id)
      : rotatedDigest;
    return tab === "ALL" ? nonFeatured : nonFeatured.filter((d) => d.category === tab);
  }, [featured, tab, rotatedDigest]);

  const isBookmarked = (id: string) => savedJobs.includes(id);

  const handleToggleBookmark = (id: string) => {
    toggleSavedJob(id);
  };

  const today = typeof window === "undefined" ? new Date() : new Date();
  const trackLine =
    userProfile.roles.length > 0
      ? userProfile.roles.join(" | ")
      : "General engineering track";

  return (
    <AppShell>
      <div className="-mx-5 md:-mx-12">
        {feedNewCount > 0 ? (
          <button type="button" onClick={() => refreshFeed()} className="strip" data-intro data-reveal="fade">
            <span className="lamp lamp--ok" aria-hidden />
            New data available, swap the feed
            <span aria-hidden>↑</span>
          </button>
        ) : null}
      </div>

      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mono-label text-primary">03 / Briefing feed</p>
          <h1 className="display mt-3 text-[clamp(2rem,1.3rem+2.8vw,3.25rem)]" data-split="lines" data-intro>
            Your <span className="accent">digest.</span>
          </h1>
          <p className="mono-label mt-4 text-dim-text">{trackLine}</p>
        </div>
        <p className="mono-data text-[13px] text-dim-text">{formatMonoDate(today)}</p>
      </header>

      <div className="space-y-10">
        {featured && !isFetchingFeed ? (
          <article className="panel panel--accent p-6 md:p-8" data-reveal="up">
            <div className="flex items-start justify-between gap-4">
              <span className="plate-label text-primary">Top signal</span>
              <span className="mono-label text-dim-text">{featured.source}</span>
            </div>
            <h2 className="display mt-6 text-[clamp(1.5rem,1.2rem+2vw,2.5rem)] leading-tight">
              {featured.headline}
            </h2>
            <p className="mt-4 max-w-[68ch] text-[15px] leading-relaxed text-dim-text">
              {featured.summary}
            </p>
            <div className="scribe mt-6 flex flex-wrap items-center justify-between gap-4 pt-4">
              <span className="mono-label text-dim-text">
                Read time · {featured.readTime}
              </span>
              <div className="flex items-center gap-3">
                {featured.match_percentage !== undefined && featured.match_percentage > 0 && (
                  <span className="mono-label border border-primary/40 bg-primary/10 px-2 py-1 text-primary">
                    {featured.match_percentage}% match
                  </span>
                )}
                <span className="mono-label text-primary">{featured.category}</span>
              </div>
            </div>
          </article>
        ) : null}

        <section className="space-y-6">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Digest channels">
            {(["ALL", "HIRING", "LAYOFFS", "FUNDING", "SKILLS"] as Tab[]).map((t) => (
              <button
                key={t}
                type="button"
                aria-pressed={tab === t}
                onClick={() => setTab(t)}
                className="tab"
              >
                {t}
              </button>
            ))}
          </div>

          {isFetchingFeed || loading ? (
            <div className="h-[360px] space-y-4 overflow-hidden">
              {[0, 1].map((i) => (
                <FeedNewsSkeleton key={i} />
              ))}
            </div>
          ) : apiError ? (
            <div className="panel panel--accent flex min-h-[360px] flex-col items-center justify-center p-6 text-center">
              <p className="mono-label text-primary">Feed fault</p>
              <p className="mono-label mt-2 text-dim-text">{apiError}</p>
            </div>
          ) : list.length === 0 && digestItems.length === 0 ? (
            <div className="panel flex min-h-[280px] flex-col items-center justify-center px-6 py-12 text-center">
              <p className="mono-data text-[clamp(3rem,2rem+6vw,5rem)] leading-none text-primary">00</p>
              <p className="display mt-4 text-[clamp(1.25rem,1rem+1.5vw,1.75rem)]">
                Digest empty
              </p>
              <p className="mt-3 max-w-[44ch] text-[15px] leading-relaxed text-dim-text">
                The feed populates after the HN scrapers run and each item gets its summary.
                Check back after the next scrape cycle.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {list.map((item) => (
                <DigestRow
                  key={item.id}
                  item={item}
                  bookmarked={isBookmarked(item.id)}
                  onToggleBookmark={() => handleToggleBookmark(item.id)}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}

function DigestRow({
  item,
  bookmarked,
  onToggleBookmark,
}: {
  item: DigestItem;
  bookmarked: boolean;
  onToggleBookmark: () => void;
}) {
  const share = async () => {
    const url = typeof window !== "undefined" ? window.location.href : "";
    try {
      if (navigator.share) {
        await navigator.share({
          title: item.headline,
          text: item.summary,
          url,
        });
      } else {
        await navigator.clipboard.writeText(url);
      }
    } catch {
      // ignore
    }
  };

  return (
    <article className="panel space-y-4 p-5 md:p-6" data-reveal="up">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <p className="mono-label text-dim-text">{item.source}</p>
          <h3 className="display text-[clamp(1.1rem,1rem+0.8vw,1.4rem)] leading-tight">
            {item.headline}
          </h3>
          <p className="text-[14px] leading-relaxed text-dim-text">{item.summary}</p>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-2">
          <button
            type="button"
            onClick={share}
            className="tab !border-transparent !p-2 text-dim-text hover:text-primary"
            aria-label="Share"
          >
            <Icon name="share" className="text-[20px]" aria-hidden />
          </button>
          <button
            type="button"
            onClick={onToggleBookmark}
            className="tab !border-transparent !p-2 text-dim-text hover:text-primary"
            aria-pressed={bookmarked}
            aria-label={bookmarked ? "Unbookmark" : "Bookmark"}
          >
            <Icon
              name={bookmarked ? "bookmark" : "bookmark_border"}
              className="text-[20px]"
              aria-hidden
            />
          </button>
        </div>
      </div>

      <div className="scribe flex flex-wrap items-center justify-between gap-4 pt-4">
        <span className="mono-label border border-border-dark px-2 py-1 text-dim-text">
          {item.category}
        </span>
        <div className="flex items-center gap-3">
          {item.match_percentage !== undefined && item.match_percentage > 0 && (
            <span className="mono-label border border-primary/40 bg-primary/10 px-2 py-1 text-primary">
              {item.match_percentage}% match
            </span>
          )}
          <span className="mono-label text-dim-text">{item.readTime}</span>
        </div>
      </div>
    </article>
  );
}

function FeedNewsSkeleton() {
  return (
    <article className="panel space-y-4 p-5 md:p-6" aria-hidden>
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-3">
          <div className="tk-skel h-3 w-[96px]" />
          <div className="tk-skel h-5 w-[280px] max-w-full" />
        </div>
        <div className="tk-skel h-5 w-5" />
      </div>
      <div className="tk-skel h-4 w-[92%]" />
      <div className="tk-skel h-4 w-[70%]" />
      <div className="flex items-center justify-between gap-4 pt-2">
        <div className="tk-skel h-6 w-[90px]" />
        <div className="tk-skel h-6 w-[70px]" />
      </div>
    </article>
  );
}
