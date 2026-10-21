"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { requestPasswordReset, signIn, signUp } from "@/lib/api";

type Mode = "signin" | "signup";

export default function AuthPage() {
  const router = useRouter();

  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);

    try {
      if (mode === "signin") {
        await signIn(email, password);
      } else {
        await signUp(email, password);
      }
      router.push("/setup/1");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleForgotPassword() {
    if (!email) {
      setError("Enter your email address first, then request the reset link.");
      return;
    }
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const message = await requestPasswordReset(email);
      setNotice(message);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send the reset email");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen flex-col bg-background-dark">
      <div aria-hidden className="machine-grid pointer-events-none absolute inset-0" />

      <div className="relative z-10 flex items-center justify-between border-b border-border-dark px-5 py-3 md:px-12">
        <Link href="/" className="tab border-transparent">
          <Icon name="arrow_back" className="text-[18px]" aria-hidden />
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
            <p className="mono-label text-primary">
              01 / {mode === "signin" ? "Sign in" : "Register"}
            </p>
            <span className="lamp lamp--live" aria-hidden />
          </div>

          <h1 className="display mt-6 text-[clamp(2rem,1.4rem+2.5vw,3rem)]" data-split="lines" data-intro>
            Identify <span className="accent">yourself.</span>
          </h1>
          <p className="mono-label mt-4 text-dim-text">
            Credentials are checked against the operator registry.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-4">
            <div className="grid gap-2">
              <label htmlFor="email" className="mono-label text-dim-text">
                Email channel
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@domain.com"
                autoComplete="email"
                className="field"
              />
            </div>

            <div className="grid gap-2">
              <label htmlFor="password" className="mono-label text-dim-text">
                Passcode
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === "signup" ? "At least 8 characters" : "Passcode"}
                  autoComplete={mode === "signup" ? "new-password" : "current-password"}
                  className="field pr-24"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="mono-label absolute right-3 top-1/2 min-h-[24px] -translate-y-1/2 py-1 text-dim-text underline-offset-4 hover:text-neutral-beige hover:underline hover:decoration-primary"
                  aria-label={showPassword ? "Hide passcode" : "Show passcode"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            {error && (
              <p role="alert" className="mono-label text-[11px] text-primary">
                {error}
              </p>
            )}
            {notice && (
              <p role="status" className="mono-label text-[11px] text-dim-text">
                {notice}
              </p>
            )}

            <button type="submit" disabled={busy} className="btn btn--primary btn--block mt-2">
              {busy ? "Working..." : mode === "signin" ? "Sign in" : "Create account"}
              <Icon name="arrow_forward" className="text-[18px]" aria-hidden />
            </button>
          </form>

          <div className="scribe mt-8 flex flex-wrap items-center gap-x-4 gap-y-2 pt-4">
            <button
              type="button"
              onClick={() => {
                setMode(mode === "signin" ? "signup" : "signin");
                setError(null);
                setNotice(null);
              }}
              className="prose-link text-neutral-beige underline-offset-[3px] hover:text-primary hover:underline-offset-[6px]"
            >
              {mode === "signin" ? "Register on the same terminal" : "I already have an account"}
            </button>
            <button
              type="button"
              onClick={handleForgotPassword}
              disabled={busy}
              className="mono-label min-h-[24px] py-1 text-dim-text underline-offset-4 hover:text-neutral-beige hover:underline hover:decoration-primary"
            >
              Forgot passcode
            </button>
          </div>
        </div>

        <p className="mono-label mt-6 text-center text-dim-text">
          Session data stays on this device until you sign in.
        </p>
      </main>
    </div>
  );
}
