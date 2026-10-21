import Link from "next/link";

/** Shared calibration frame for the three setup steps: tick-scale progress + bezel. */
export function SetupFrame({
  step,
  optional,
  title,
  children,
  backHref,
  backLabel,
  onNext,
  nextLabel,
}: {
  step: 1 | 2 | 3;
  optional?: boolean;
  title: React.ReactNode;
  children: React.ReactNode;
  backHref: string;
  backLabel: string;
  onNext: () => void;
  nextLabel: string;
}) {
  return (
    <div className="relative flex min-h-screen flex-col bg-background-dark">
      <div aria-hidden className="machine-grid pointer-events-none absolute inset-0" />

      <div className="relative z-10 border-b border-border-dark px-5 py-3 md:px-12">
        <div className="mx-auto flex w-full max-w-[880px] items-center justify-between">
          <span className="mono-label text-neutral-beige">Calibration wizard</span>
          <span className="mono-label text-dim-text">
            Step {String(step).padStart(2, "0")} of 03{optional ? " / optional" : ""}
          </span>
        </div>
      </div>

      <main
        id="main"
        tabIndex={-1}
        className="relative z-10 mx-auto flex w-full max-w-[880px] flex-1 flex-col px-5 py-10 md:px-0 md:py-14"
      >
        {/* Tick-scale progress: three click-stops, not a smooth bar */}
        <div className="flex items-end gap-2" aria-hidden>
          {[1, 2, 3].map((s) => (
            <div key={s} className="flex-1">
              <div className={`h-[3px] ${s <= step ? "bg-primary" : "bg-border-dark"}`} />
              <div className="tick-rule mt-1 h-[6px] opacity-60" />
            </div>
          ))}
        </div>
        <p className="mono-label mt-4 text-primary">
          Step {String(step).padStart(2, "0")} of 03{optional ? " / optional" : ""}
        </p>

        <h1 className="display mt-5 text-[clamp(2rem,1.4rem+3vw,3.25rem)]" data-split="lines" data-intro>
          {title}
        </h1>

        <div className="mt-9 flex-1">{children}</div>

        <div className="mt-10 flex items-center justify-between gap-4">
          <Link href={backHref} className="btn">
            {backLabel}
          </Link>
          <button type="button" onClick={onNext} className="btn btn--primary">
            {nextLabel}
          </button>
        </div>
      </main>
    </div>
  );
}
