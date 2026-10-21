"use client";

import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { useRef, useState } from "react";
import { useTaza } from "@/components/TazaContext";
import { SetupFrame } from "@/components/SetupFrame";

export default function SetupStep3Page() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [fileName, setFileName] = useState<string>("");
  const { setResumeUploaded } = useTaza();

  return (
    <SetupFrame
      step={3}
      optional
      title={
        <>
          Load your <span className="accent">resume.</span>
        </>
      }
      backHref="/setup/2"
      backLabel="Skip"
      onNext={() => {
        // Treat completion as having a resume attached (even if user skipped uploading).
        setResumeUploaded(true);
        router.push("/jobs");
      }}
      nextLabel="Complete setup"
    >
      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        className="panel group flex w-full items-start gap-4 p-6 text-left transition-colors hover:bg-card-hi md:p-8"
      >
        <Icon name="upload_file" className="text-[36px] text-primary" aria-hidden />
        <span className="grid gap-2">
          <span className="mono-label text-neutral-beige">
            {fileName || "Load resume file"}
          </span>
          <span className="mono-label text-[10px] text-dim-text">
            PDF or TXT, max 5MB. Parsed locally, scored against live market demand.
          </span>
          {fileName ? (
            <span className="mono-label text-primary">File armed: {fileName}</span>
          ) : null}
        </span>
      </button>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.txt,.docx"
        className="sr-only"
        aria-label="Resume file"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) {
            setFileName(f.name);
            setResumeUploaded(true);
          }
        }}
      />

      <p className="mono-label mt-6 text-dim-text">
        You can upload later from the profile panel.
      </p>
    </SetupFrame>
  );
}
