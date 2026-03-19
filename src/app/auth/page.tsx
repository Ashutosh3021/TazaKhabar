"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTaza } from "@/components/TazaContext";

export default function AuthPage() {
  const router = useRouter();
  const { userProfile, setUserProfile } = useTaza();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6">
      <div className="w-full max-w-[448px]">
        <div className="flex items-center justify-between mb-10">
          <Link
            href="/"
            className="flex items-center gap-2 text-dim-text hover:text-neutral-beige mono-label"
          >
            <span className="material-symbols-outlined text-[20px]">
              arrow_back
            </span>
            BACK
          </Link>
        </div>

        <h1 className="font-serif text-4xl md:text-5xl font-black leading-tight">
          Enter your{" "}
          <span className="text-primary italic font-black">email.</span>
        </h1>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            setUserProfile({ ...userProfile, email });
            router.push("/setup/1");
          }}
          className="mt-10 flex flex-col gap-4"
        >
          <div className="flex flex-col gap-2">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              className="w-full bg-background-dark text-neutral-beige py-3 px-4 brutalist-border"
            />
          </div>

          <div className="flex flex-col gap-2">
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="w-full bg-background-dark text-neutral-beige py-3 px-4 brutalist-border pr-12"
              />

              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-dim-text hover:text-neutral-beige"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                <span className="material-symbols-outlined text-[22px]">
                  {showPassword ? "visibility_off" : "visibility"}
                </span>
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="mt-2 bg-primary text-black py-4 mono-label uppercase tracking-[0.05em] flex items-center justify-center gap-2 hover:opacity-90 transition-opacity"
          >
            <span className="material-symbols-outlined text-[20px]">arrow_forward</span>
            SIGN IN
          </button>
        </form>

        <div className="mt-8 text-center">
          <span className="mono-label text-[10px] text-dim-text">
            NO ACCOUNT?
          </span>{" "}
          <Link
            href="/auth"
            className="mono-label text-[10px] text-primary hover:underline inline-block"
          >
            REGISTER BELOW →
          </Link>
        </div>
      </div>
    </div>
  );
}

