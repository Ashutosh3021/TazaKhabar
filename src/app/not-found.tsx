import type { Metadata } from "next";
import { Icon } from "@/components/Icon";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Signal lost",
  description: "The requested route is not wired into this instrument.",
  robots: { index: false },
};

export default function NotFound() {
  return (
    <div className="relative flex min-h-screen flex-col bg-background-dark">
      <div aria-hidden className="machine-grid pointer-events-none absolute inset-0" />

      <div className="relative z-10 flex items-center justify-between border-b border-border-dark px-5 py-3 md:px-12">
        <span className="mono-label text-neutral-beige">TazaKhabar/MK-II</span>
        <span className="mono-label text-primary">Fault</span>
      </div>

      <main
        id="main"
        tabIndex={-1}
        className="relative z-10 mx-auto flex w-full max-w-[720px] flex-1 flex-col justify-center px-5 py-16"
      >
        <div className="panel panel--accent p-6 md:p-10">
          <div className="flex items-center justify-between">
            <p className="mono-label text-primary">Error 404</p>
            <span className="lamp lamp--live" aria-hidden />
          </div>
          <p className="display mt-6 text-[clamp(3rem,2rem+8vw,6.5rem)] leading-none" aria-hidden>
            E-404
          </p>
          <h1 className="display mt-6 text-[clamp(1.5rem,1.2rem+2vw,2.25rem)]">
            Signal <span className="accent">lost.</span>
          </h1>
          <p className="mt-4 max-w-[48ch] text-[15px] leading-relaxed text-dim-text">
            No route is wired to this address. The reading you asked for either moved or
            never existed.
          </p>
          <div className="scribe mt-8 flex flex-wrap gap-3 pt-5">
            <Link href="/" className="btn btn--primary">
              Return to base
              <Icon name="home" className="text-[16px]" aria-hidden />
            </Link>
            <Link href="/jobs" className="btn">
              Open job radar
            </Link>
          </div>
        </div>
        <p className="mono-label mt-6 text-center text-dim-text">
          Log the route if you followed a link from inside the app.
        </p>
      </main>
    </div>
  );
}
