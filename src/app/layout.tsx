import type { Metadata } from "next";
import "./globals.css";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import { TazaProvider } from "@/components/TazaContext";
import { Motion } from "@/components/Motion";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-mono",
  display: "swap",
});

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tazakhabar.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "TazaKhabar | Job market instrument",
    template: "%s | TazaKhabar",
  },
  description:
    "Hacker News job data measured honestly: live Who Is Hiring radar, ghost-job flags, market trend readings and an ATS resume score.",
  alternates: { canonical: "./" },
  icons: { icon: "/icon.svg" },
  openGraph: {
    type: "website",
    siteName: "TazaKhabar",
    title: "TazaKhabar | Job market instrument",
    description:
      "Live HN job radar, ghost-job flags, trend readings and ATS scoring. Real jobs. Real contact info.",
    url: siteUrl,
    images: ["/og.png"],
  },
  twitter: { card: "summary_large_image" },
  robots: { index: true, follow: true },
};

// Runs before first paint: hidden-until-revealed styles only apply when JS and motion are on.
const flags = `document.documentElement.classList.add('js');if(!matchMedia('(prefers-reduced-motion: reduce)').matches)document.documentElement.classList.add('motion')`;

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name: "TazaKhabar",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  description:
    "Tech job market intelligence: HN Who Is Hiring radar, ghost-job detection, keyword trend forecasting and ATS resume scoring.",
  url: siteUrl,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${spaceGrotesk.variable} ${plexMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: flags }} />
      </head>
      <body className="font-sans">
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <div id="curtain" aria-hidden="true">
          <div className="curtain__panel" />
        </div>
        <div id="cursor" aria-hidden="true">
          <span data-cursor-label />
        </div>
        <div id="loader" role="status" aria-label="Loading TazaKhabar">
          <div className="loader__inner">
            <div>
              <div className="loader__meta">
                <span data-loader-out>Power-on self test</span>
                <span className="loader__name" data-loader-out>
                  TazaKhabar // MK-II
                </span>
              </div>
              <div className="loader__bar" data-loader-bar />
            </div>
            <span className="loader__count" data-loader-out data-loader-count>
              000
            </span>
          </div>
        </div>
        <TazaProvider>{children}</TazaProvider>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }}
        />
        <Motion />
      </body>
    </html>
  );
}
