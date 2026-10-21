"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchSession, setSessionHint } from "@/lib/api";

/**
 * Landing page after the OAuth provider sends the browser back.
 * The session cookie is already set on the API domain; this page confirms it,
 * writes the first-party hint cookie the route gate reads, then continues.
 */
export default function AuthCallbackPage() {
  const router = useRouter();
  const [message, setMessage] = useState("Confirming your session...");

  useEffect(() => {
    let cancelled = false;

    async function confirm() {
      const result = await fetchSession();
      if (cancelled) return;

      if (result.authenticated) {
        setSessionHint();
        router.replace("/setup/1");
        router.refresh();
        return;
      }

      setMessage("The sign in could not be confirmed. Please try again.");
    }

    void confirm();
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div className="relative flex min-h-screen flex-col bg-background-dark">
      <div aria-hidden className="machine-grid pointer-events-none absolute inset-0" />
      <main
        id="main"
        tabIndex={-1}
        className="relative z-10 mx-auto flex w-full max-w-[520px] flex-1 flex-col justify-center px-5 py-14 md:px-0"
      >
        <div className="panel p-6 md:p-8" data-intro data-reveal="up">
          <div className="flex items-center justify-between">
            <p className="mono-label text-primary">01 / Authentication</p>
            <span className="lamp lamp--live" aria-hidden />
          </div>
          <p className="mono-label mt-6 text-dim-text">{message}</p>
        </div>
      </main>
    </div>
  );
}
