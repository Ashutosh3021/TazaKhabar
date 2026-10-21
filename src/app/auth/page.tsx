"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchAuthProviders, startOAuth, type AuthProvider } from "@/lib/api";

const ERROR_MESSAGES: Record<string, string> = {
  invalid_state: "The sign in could not be verified. Please try again.",
  missing_code: "The provider did not return a code. Please try again.",
  oauth_failed: "The provider refused the sign in. Please try again.",
  access_denied: "The sign in was cancelled.",
};

export default function AuthPage() {
  const [providers, setProviders] = useState<AuthProvider[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    void fetchAuthProviders().then(setProviders);
  }, []);

  useEffect(() => {
    // Read the error the backend put on the URL without useSearchParams, which
    // would need a Suspense boundary on this statically rendered page.
    const code = new URLSearchParams(window.location.search).get("error");
    if (code) setError(ERROR_MESSAGES[code] ?? "Sign in failed. Please try again.");
  }, []);

  const begin = (provider: string) => {
    setBusy(provider);
    setError(null);
    startOAuth(provider as "google" | "github");
  };

  const available = providers.filter((p) => p.configured);

  return (
    <div className="relative flex min-h-screen flex-col bg-background-dark">
      <div aria-hidden className="machine-grid pointer-events-none absolute inset-0" />

      <div className="relative z-10 flex items-center justify-between border-b border-border-dark px-5 py-3 md:px-12">
        <Link href="/" className="tab border-transparent">
          <span className="material-symbols-outlined text-[18px]" aria-hidden>
            arrow_back
          </span>
          Back
        </Link>
        <span className="mono-label text-dim-text">Access terminal</span>
      </div>

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

          <h1 className="display mt-6 text-[clamp(2rem,1.4rem+2.5vw,3rem)]" data-split="lines" data-intro>
            Identify <span className="accent">yourself.</span>
          </h1>
          <p className="mono-label mt-4 text-dim-text">
            Sign in with the account you already own. No passcode, nothing to remember.
          </p>

          {error && (
            <p role="alert" className="mono-label mt-6 text-[11px] text-primary">
              {error}
            </p>
          )}

          <div className="mt-8 flex flex-col gap-3">
            {available.length === 0 && (
              <p className="mono-label text-[11px] text-dim-text">
                No sign-in method is configured on this deployment yet.
              </p>
            )}

            {available.map((provider) => (
              <button
                key={provider.id}
                type="button"
                onClick={() => begin(provider.id)}
                disabled={busy !== null}
                className="btn btn--primary btn--block"
              >
                {busy === provider.id
                  ? "Redirecting..."
                  : `Continue with ${provider.name}`}
                <span className="material-symbols-outlined text-[18px]" aria-hidden>
                  arrow_forward
                </span>
              </button>
            ))}
          </div>

          <div className="scribe mt-8 pt-4">
            <span className="mono-label text-dim-text">
              Your profile, resume and ATS results are stored against your account.
            </span>
          </div>
        </div>

        <p className="mono-label mt-6 text-center text-dim-text">
          The session cookie lives on the API domain and is httpOnly.
        </p>
      </main>
    </div>
  );
}
