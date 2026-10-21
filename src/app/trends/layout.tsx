import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Market trends",
  description:
    "Week over week keyword demand, booming and declining roles, market intelligence readings and the market mood gauge.",
  alternates: { canonical: "/trends" },
};

export default function TrendsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
