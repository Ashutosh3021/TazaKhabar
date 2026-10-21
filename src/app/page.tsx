import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "TazaKhabar | Job market instrument",
  description:
    "Hacker News job data measured honestly: live Who Is Hiring radar, ghost-job flags, trend readings and an ATS resume score.",
  alternates: { canonical: "/" },
};

const READOUTS = [
  { label: "Source", value: "HN Who Is Hiring", note: "scraped every 2h" },
  { label: "Ghost filter", value: "Contact required", note: "no email, no apply link, no listing" },
  { label: "Trend model", value: "Week over week", note: "99 keywords tracked" },
  { label: "Resume", value: "ATS 0 to 100", note: "scored against live demand" },
];

const CYCLE = [
  {
    name: "Scrape",
    note: "The Who Is Hiring thread is pulled on a fixed two-hour cadence.",
  },
  {
    name: "Extract",
    note: "Titles, stacks, locations and contact channels are pulled out of raw text.",
  },
  {
    name: "Flag",
    note: "No contact channel means the listing never reaches the radar.",
  },
  {
    name: "Score",
    note: "Your resume is matched against what the market is actually asking for.",
  },
];

export default function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-background-dark">
      <div aria-hidden className="machine-grid pointer-events-none absolute inset-0" />

      {/* Top bezel */}
      <div className="relative z-10 flex items-center justify-between border-b border-border-dark px-5 py-3 md:px-12">
        <div className="flex items-center gap-3">
          <span className="flex h-6 w-6 items-center justify-center border border-border-dark">
            <span className="lamp lamp--live" aria-hidden />
          </span>
          <span className="mono-label text-neutral-beige">TazaKhabar/MK-II</span>
        </div>
        <span className="mono-label hidden text-dim-text sm:block">
          Job market instrument
        </span>
        <span className="mono-label text-dim-text">EST. 2026</span>
      </div>

      <main
        id="main"
        tabIndex={-1}
        className="relative z-10 mx-auto grid w-full max-w-[1440px] flex-1 gap-10 px-5 py-12 md:grid-cols-12 md:gap-8 md:px-12 md:py-16"
      >
        {/* Left: the display plate */}
        <div className="md:col-span-7 lg:col-span-7">
          <p className="mono-label text-primary" data-intro data-reveal="fade">
            Signal in. Noise out.
          </p>
          <h1
            className="display mt-6 text-[clamp(2.5rem,1.1rem+6.5vw,5.75rem)]"
            data-split="lines"
            data-intro
          >
            The tech job market, <span className="accent">measured.</span>
          </h1>
          <p
            className="mt-8 max-w-[46ch] text-[clamp(1rem,0.95rem+0.3vw,1.125rem)] leading-relaxed text-dim-text"
            data-intro
            data-reveal="up"
            data-delay="0.35"
          >
            TazaKhabar scrapes Hacker News every two hours, extracts real contact
            details, flags ghost listings, scores your resume against live demand and
            reads the trends underneath. No career fluff. Just the instrument.
          </p>

          <div
            className="mt-10 flex w-full max-w-[420px] flex-col gap-3"
            data-intro
            data-reveal="up"
            data-delay="0.5"
          >
            <Link href="/auth" className="btn btn--primary btn--block">
              Open the terminal
            </Link>
            <a href="#specification" className="btn btn--block">
              Read the specification
            </a>
          </div>

          <p className="mono-label mt-8 text-dim-text" data-intro data-reveal="fade" data-delay="0.65">
            Free tier: live radar, contacts, basic ATS score.
          </p>
        </div>

        {/* Right: the readout column */}
        <aside
          id="specification"
          className="md:col-span-5 lg:col-span-4 lg:col-start-9"
          aria-label="Instrument specifications"
        >
          <div className="panel p-5" data-intro data-reveal="up" data-delay="0.3">
            <div className="flex items-center justify-between">
              <p className="mono-label text-primary">Unit specification</p>
              <span className="lamp lamp--live" aria-hidden />
            </div>
            <dl className="mt-6 divide-y divide-border-dark">
              {READOUTS.map((r) => (
                <div key={r.label} className="grid gap-1 py-4 first:pt-0 last:pb-0">
                  <dt className="mono-label text-dim-text">{r.label}</dt>
                  <dd className="mono-data text-[15px] text-neutral-beige">{r.value}</dd>
                  <dd className="text-[13px] leading-snug text-dim-text">{r.note}</dd>
                </div>
              ))}
            </dl>
          </div>
          <p className="mono-label mt-4 text-dim-text">
            Fig. 01 / readouts update with each scrape cycle
          </p>
        </aside>
      </main>

      {/* Second act: what one cycle does */}
      <section
        aria-labelledby="cycle-title"
        className="relative z-10 border-t border-border-dark px-5 py-14 md:px-12 md:py-20"
      >
        <div className="mx-auto w-full max-w-[1440px]">
          <p className="mono-label text-primary" data-reveal="fade">
            Fig. 02 / every two hours
          </p>
          <h2
            id="cycle-title"
            className="display mt-4 text-[clamp(1.75rem,1.2rem+2vw,3.25rem)]"
            data-split="lines"
          >
            One pass. Four stations.
          </h2>

          <ol className="mt-10 grid gap-px border border-border-dark bg-border-dark sm:grid-cols-2 lg:grid-cols-4">
            {CYCLE.map((s, i) => (
              <li
                key={s.name}
                className="bg-card-dark p-6"
                data-reveal="up"
                data-delay={(i * 0.08).toFixed(2)}
              >
                <span className="mono-label text-dim-text">
                  ST-{String(i + 1).padStart(2, "0")}
                </span>
                <h3 className="mono-label mt-4 text-[13px] text-neutral-beige">
                  {s.name}
                </h3>
                <p className="mt-3 text-[14px] leading-snug text-dim-text">
                  {s.note}
                </p>
              </li>
            ))}
          </ol>

          <figure className="panel mt-6 p-5" data-reveal="up">
            <figcaption className="flex flex-wrap items-center justify-between gap-3">
              <span className="mono-label text-primary">Specimen row / format</span>
              <span className="mono-label text-dim-text">Fig. 03</span>
            </figcaption>
            <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-border-dark pt-5">
              <span className="mono-data text-[13px] text-dim-text">RK-4417</span>
              <span className="mono-data text-[15px] text-neutral-beige">
                Senior Backend Engineer
              </span>
              <span className="mono-label text-dim-text">Series B fintech</span>
              <span className="chip">NODE</span>
              <span className="chip">POSTGRES</span>
              <span className="chip">REMOTE</span>
              <span className="mono-label flex items-center gap-2 text-signal">
                <span className="lamp lamp--live" aria-hidden />
                CONTACT ON FILE
              </span>
            </div>
            <p className="mono-label mt-4 text-dim-text">
              A row ships only when a contact channel survives extraction.
            </p>
          </figure>
        </div>
      </section>

      <footer className="relative z-10 border-t border-border-dark px-5 py-4 md:px-12">
        <div className="mx-auto flex w-full max-w-[1440px] flex-wrap items-center justify-between gap-3">
          <span className="mono-label text-dim-text">
            © {new Date().getFullYear()} TazaKhabar
          </span>
          <span className="mono-label text-dim-text">
            Built on public Hacker News data
          </span>
          <span className="mono-label text-dim-text">
            Readouts are informational, not advice
          </span>
        </div>
      </footer>
    </div>
  );
}
