import type { Metadata } from "next";
import AppShell from "@/components/AppShell";
import QaCareerBotDesktop from "@/components/qa/QaCareerBotDesktop";
import QaCareerBotMobile from "@/components/qa/QaCareerBotMobile";

export const metadata: Metadata = {
  title: "Q&A",
  description:
    "Ask the career bot about role matches, market velocity, skill gaps and your next move against live job market data.",
};

export default function QaPage() {
  return (
    <AppShell>
      <header className="mb-10">
        <p className="mono-label text-primary">06 / Query console</p>
        <h1 className="display mt-3 text-[clamp(2rem,1.3rem+2.8vw,3.25rem)]" data-split="lines" data-intro>
          Career <span className="accent">bot.</span>
        </h1>
        <p className="mono-label mt-4 text-dim-text">
          AI-driven role optimization based on your verified profile
        </p>
      </header>
      <div className="md:hidden">
        <QaCareerBotMobile />
      </div>
      <div className="hidden md:block">
        <QaCareerBotDesktop />
      </div>
    </AppShell>
  );
}
