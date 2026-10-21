import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Digest",
  description:
    "Your briefing feed: top signal, hiring moves, layoffs, funding and skill shifts summarized from the latest scrape cycle.",
  alternates: { canonical: "/digest" },
};

export default function DigestLayout({ children }: { children: React.ReactNode }) {
  return children;
}
