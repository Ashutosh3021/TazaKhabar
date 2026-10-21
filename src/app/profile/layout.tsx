import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Profile",
  description:
    "Operator panel: target roles, experience tier, resume uploads, ATS scoring and operational preferences.",
  alternates: { canonical: "/profile" },
  robots: { index: false },
};

export default function ProfileLayout({ children }: { children: React.ReactNode }) {
  return children;
}
