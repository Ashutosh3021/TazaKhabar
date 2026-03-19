"use client";

import { useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import { digestItems } from "@/lib/mockData";

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
  const featured = useMemo(
    () => digestItems.find((d) => d.featured) ?? digestItems[0],
    [],
  );

  const [bookmarked, setBookmarked] = useState<string[]>([]);

  const list = useMemo(() => {
    const nonFeatured = digestItems.filter((d) => d.id !== featured.id);
    return tab === "ALL" ? nonFeatured : nonFeatured.filter((d) => d.category === tab);
  }, [featured.id, tab]);

  const today = typeof window === "undefined" ? new Date() : new Date();

  return (
    <AppShell>
      <div className="space-y-10">
        <header className="pt-6">
          <h1 className="font-serif text-4xl md:text-6xl font-black leading-tight">
            Your{" "}
            <span className="text-primary italic font-black">Digest.</span>
          </h1>
          <p className="mono-label text-[11px] text-dim-text uppercase tracking-[0.2em] mt-4">
            {formatMonoDate(today)} · PERSONALIZED INTELLIGENCE
          </p>
        </header>

        {featured ? (
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

