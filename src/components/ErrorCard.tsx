"use client";

import type { ReactNode } from "react";

export default function ErrorCard({
  messageTitle = "FAILED TO LOAD DATA",
  children,
  onRetry,
}: {
  messageTitle?: string;
  children?: ReactNode;
  onRetry?: () => void;
}) {
  return (
    <div
      className="w-full bg-[#0f0f0f] p-5"
      style={{ border: "1.5px solid #7a1a1a", borderRadius: 0 }}
    >
      <div className="flex items-start gap-3">
        <div className="font-mono text-[16px] font-bold text-[#FF2D00] leading-none">
          ✕
        </div>
        <div>
          <div className="font-mono text-[11px] font-bold uppercase tracking-[0.05em] text-[#F0EDE6]">
            {messageTitle}
          </div>
          <div className="font-mono text-[12px] text-[#8c8c8c] mt-2">
            {children ?? "Check your connection or try again"}
          </div>
        </div>
      </div>

      <div className="flex justify-end mt-4">
        <button
          type="button"
          onClick={onRetry}
          className="border-1.5 border-[#FF2D00] text-[#FF2D00] font-mono text-[11px] font-bold uppercase tracking-[0.05em] px-4 py-2 bg-transparent cursor-pointer hover:bg-[#FF2D00]/10"
        >
          RETRY →
        </button>
      </div>
    </div>
  );
}

