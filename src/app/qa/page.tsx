import type { Metadata } from "next";
import AppShell from "@/components/AppShell";
import QaCareerBotDesktop from "@/components/qa/QaCareerBotDesktop";
import QaCareerBotMobile from "@/components/qa/QaCareerBotMobile";

export const metadata: Metadata = {
  title: "Q&A | TazaKhabar",
  description: "Career bot and Radar AI — role optimization.",
};

export default function QaPage() {
  return (
    <AppShell>
      <div className="-mx-6 md:mx-0">
        <div className="md:hidden">
          <QaCareerBotMobile />
        </div>
        <div className="hidden md:block">
          <QaCareerBotDesktop />
        </div>
      </div>
    </AppShell>
  );
}
