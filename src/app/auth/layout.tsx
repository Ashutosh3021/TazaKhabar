import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Access terminal",
  robots: { index: false },
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return children;
}
