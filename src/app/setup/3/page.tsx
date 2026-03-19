"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

export default function SetupStep3Page() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [fileName, setFileName] = useState<string>("");

  return (
    <div className="min-h-screen flex flex-col px-6 py-10 bg-background-dark">
      <div className="w-full max-w-2xl mx-auto flex flex-col flex-1">
        <div className="h-[2px] bg-border-dark">
          <div style={{ width: "100%" }} className="h-full bg-primary" />
        </div>

        <p className="mono-label text-[10px] text-primary mt-6">
          STEP 03 OF 03 · OPTIONAL
        </p>

        <h1 className="font-serif text-4xl md:text-5xl font-black mt-6 leading-tight">
          Upload your{" "}
          <span className="text-primary italic font-black">resume.</span>
        </h1>

        <div className="mt-10">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="w-full text-left p-8 rounded-none border-2 border-dashed border-neutral-border hover:border-primary/60 transition-colors"
          >
            <div className="flex items-start gap-4">
              <span className="material-symbols-outlined text-[44px] text-primary">
                upload_file
              </span>
              <div>
                <p className="mono-label text-[12px] text-neutral-beige">
                  DRAG & DROP RESUME HERE
                </p>
                <p className="mono-label text-[10px] text-dim-text mt-2">
                  PDF, DOCX · MAX 5MB
                </p>
                {fileName ? (
                  <p className="mono-label text-[10px] text-primary mt-3">
                    {fileName}
                  </p>
                ) : null}
              </div>
            </div>
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setFileName(f.name);
            }}
          />
        </div>

        <div className="mt-auto pt-10 flex items-center justify-between gap-4">
          <Link
            href="/jobs"
            className="brutalist-border px-6 py-3 mono-label text-[11px] hover:bg-primary/10"
          >
            SKIP
          </Link>
          <button
            type="button"
            onClick={() => router.push("/jobs")}
            className="brutalist-border-primary bg-primary/10 px-6 py-3 mono-label text-[11px] text-neutral-beige hover:bg-primary/20 transition-colors"
          >
            COMPLETE SETUP
          </button>
        </div>
      </div>
    </div>
  );
}

