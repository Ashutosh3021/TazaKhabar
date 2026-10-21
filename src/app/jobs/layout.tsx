import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Job radar",
  description:
    "Live Hacker News Who Is Hiring board: contact details extracted, ghost jobs flagged, filters for role, location and company size.",
  alternates: { canonical: "/jobs" },
};

export default function JobsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
