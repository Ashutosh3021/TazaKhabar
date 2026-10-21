import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Calibration wizard",
  robots: { index: false },
};

export default function SetupLayout({ children }: { children: React.ReactNode }) {
  return children;
}
