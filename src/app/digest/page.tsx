"use client";

import { useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import { digestItems } from "@/lib/mockData";
import { useTaza } from "@/components/TazaContext";

type Tab = "ALL" | "HIRING" | "LAYOFFS" | "FUNDING" | "SKILLS";

function formatMonoDate(d: Date) {
  // Brutal fixed-ish format; no locale dependence.
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function DigestPage() {
  const [tab, setTab] = useState<Tab>("ALL");
  const { feedNewCount, refreshFeed, isFetchingFeed, feedVersion } = useTaza();
  const featured = useMemo(
    () => {
      const shift = feedVersion % digestItems.length;
      const rotated = [
        ...digestItems.slice(shift),
        ...digestItems.slice(0, shift),
      ];
      return rotated.find((d) => d.featured) ?? rotated[0];
    },
    [feedVersion],
  );

  const [bookmarked, setBookmarked] = useState<string[]>([]);

  const rotatedDigest = useMemo(() => {
    const shift = feedVersion % digestItems.length;
    return [...digestItems.slice(shift), ...digestItems.slice(0, shift)];
  }, [feedVersion]);

  const list = useMemo(() => {
    const nonFeatured = rotatedDigest.filter((d) => d.id !== featured.id);
    return tab === "ALL" ? nonFeatured : nonFeatured.filter((d) => d.category === tab);
  }, [featured.id, tab, rotatedDigest]);

  const today = typeof window === "undefined" ? new Date() : new Date();

  return (
    <AppShell>
      <div className="space-y-10">
        {feedNewCount > 0 ? (
          <button
            type="button"
            onClick={() => refreshFeed()}
            className="-mx-6 md:-mx-20 h-[36px] w-[calc(100%+48px)] md:w-[calc(100%+160px)] bg-[#FF2D00] text-[#0E0E0E] flex items-center justify-center relative z-10"
          >
            <span className="font-mono text-[10px] font-bold uppercase tracking-[2px]">
              NEW DATA AVAILABLE — TAP TO REFRESH
            </span>
            <span className="absolute right-4 text-[#0E0E0E] font-mono">
              ↑
            </span>
          </button>
        ) : null}

        <header className="pt-6">
          <h1 className="font-serif text-4xl md:text-6xl font-black leading-tight">
            Your{" "}
            <span className="text-primary italic font-black">Digest.</span>
          </h1>

          <p className="mono-label text-[11px] text-dim-text uppercase tracking-[0.2em] mt-4">
            SOFTWARE ENGINEER | 5 YRS EXP | MACHINE LEARNING
          </p>
          <p className="font-mono text-[10px] text-[#444] uppercase tracking-[0.2em] mt-2">
            LAST UPDATED · 2H AGO
          </p>
        </header>

        {featured && !isFetchingFeed ? (
          <article className="brutalist-border bg-card-dark p-6 news-card-border">
            <div className="flex items-start justify-between gap-4">
              <span className="mono-label text-[10px] text-primary uppercase tracking-[0.2em]">
                TOP SIGNAL
              </span>
              <span className="mono-label text-[10px] text-dim-text uppercase">
                {featured.source}
              </span>
            </div>
            <h2 className="font-serif text-3xl md:text-4xl font-black mt-6 leading-tight">
              {featured.headline}
            </h2>
            <div className="mt-5 flex items-center justify-between gap-4">
              <span className="mono-label text-[10px] text-dim-text uppercase">
                READ TIME · {featured.readTime}
              </span>
              <span className="mono-label text-[10px] text-primary uppercase">
                {featured.category}
              </span>
            </div>
          </article>
        ) : null}

        <section className="space-y-6">
          <div className="flex flex-wrap gap-2">
            {(["ALL", "HIRING", "LAYOFFS", "FUNDING", "SKILLS"] as Tab[]).map(
              (t) => {
                const isActive = tab === t;
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setTab(t)}
                    className={`mono-label text-[11px] uppercase tracking-[0.05em] px-5 py-3 border border-border-dark transition-colors ${
                      isActive
                        ? "active-tab border-border-dark text-primary"
                        : "bg-background-dark text-dim-text hover:bg-primary/10 hover:text-neutral-beige"
                    }`}
                  >
                    {t}
                  </button>
                );
              },
            )}
          </div>

          {isFetchingFeed ? (
            <div className="space-y-4">
              {[0, 1].map((i) => (
                <FeedNewsSkeleton key={i} />
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              {list.map((item) => (
                <DigestRow
                  key={item.id}
                  item={item}
                  bookmarked={bookmarked.includes(item.id)}
                  onToggleBookmark={() => {
                    setBookmarked((prev) =>
                      prev.includes(item.id)
                        ? prev.filter((id) => id !== item.id)
                        : [...prev, item.id],
                    );
                  }}
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
  item: (typeof digestItems)[number];
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
    <article className="brutalist-border bg-card-dark p-6 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="mono-label text-[10px] text-dim-text uppercase tracking-[0.2em]">
            {item.source}
          </p>
          <h3 className="font-serif text-2xl font-black leading-tight">
            {item.headline}
          </h3>
          <p className="font-mono text-[13px] text-dim-text leading-relaxed">
            {item.summary}
          </p>
        </div>

        <div className="flex flex-col gap-2 items-end">
          <button
            type="button"
            onClick={share}
            className="text-dim-text hover:text-primary transition-colors"
            aria-label="Share"
          >
            <span className="material-symbols-outlined text-[22px]">share</span>
          </button>
          <button
            type="button"
            onClick={onToggleBookmark}
            className="text-dim-text hover:text-primary transition-colors"
            aria-label={bookmarked ? "Unbookmark" : "Bookmark"}
          >
            <span className="material-symbols-outlined text-[22px]">
              {bookmarked ? "bookmark" : "bookmark_border"}
            </span>
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between gap-4">
        <span className="mono-label text-[10px] px-2 py-1 border border-border-dark text-dim-text uppercase tracking-[0.05em]">
          {item.category}
        </span>
        <span className="mono-label text-[10px] text-dim-text uppercase">
          {item.readTime}
        </span>
      </div>
    </article>
  );
}

function FeedNewsSkeleton() {
  return (
    <article className="brutalist-border bg-card-dark p-6 news-card-border">
      <div className="flex items-start justify-between gap-4">
        <div className="tazakhabar-skeleton-bar w-[96px] h-[18px]" />
        <div className="tazakhabar-skeleton-bar w-[120px] h-[14px]" />
      </div>
      <div className="mt-6 space-y-3">
        <div className="tazakhabar-skeleton-bar w-[75%] h-[18px]" />
        <div className="tazakhabar-skeleton-bar w-[60%] h-[14px]" />
        <div className="tazakhabar-skeleton-bar w-[55%] h-[14px]" />
      </div>
      <div className="mt-5 flex items-center justify-between gap-4">
        <div className="tazakhabar-skeleton-bar w-[120px] h-[16px]" />
        <div className="tazakhabar-skeleton-bar w-[80px] h-[16px]" />
      </div>
    </article>
  );
}

function DigestRowSkeleton() {
  return (
    <article className="brutalist-border bg-card-dark p-6 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-3">
          <div className="tazakhabar-skeleton-bar w-[140px] h-[12px]" />
          <div className="tazakhabar-skeleton-bar w-[92%] h-[16px]" />
          <div className="tazakhabar-skeleton-bar w-[90%] h-[12px]" />
        </div>
        <div className="space-y-3 flex flex-col items-end">
          <div className="tazakhabar-skeleton-bar w-[22px] h-[22px] rounded-none" />
          <div className="tazakhabar-skeleton-bar w-[22px] h-[22px] rounded-none" />
        </div>
      </div>
      <div className="flex items-center justify-between gap-4">
        <div className="tazakhabar-skeleton-bar w-[90px] h-[18px]" />
        <div className="tazakhabar-skeleton-bar w-[60px] h-[18px]" />
      </div>
    </article>
  );
}

