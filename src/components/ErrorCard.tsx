"use client";

import { Icon } from "@/components/Icon";

import type { ReactNode } from "react";

export default function ErrorCard({
  messageTitle = "Failed to load data",
  children,
  onRetry,
}: {
  messageTitle?: string;
  children?: ReactNode;
  onRetry?: () => void;
}) {
  return (
    <div className="panel panel--accent w-full p-5" role="alert">
      <div className="flex items-start gap-3">
        <Icon name="error" className="text-[18px] text-primary" aria-hidden />
        <div>
          <div className="mono-label text-neutral-beige">{messageTitle}</div>
          <div className="mono-label mt-2 text-dim-text">
            {children ?? "Check your connection or try again"}
          </div>
        </div>
      </div>

      {onRetry ? (
        <div className="mt-4 flex justify-end">
          <button type="button" onClick={onRetry} className="btn">
            Retry
            <Icon name="refresh" className="text-[15px]" aria-hidden />
          </button>
        </div>
      ) : null}
    </div>
  );
}
