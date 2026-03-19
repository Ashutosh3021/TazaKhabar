import type { Metadata } from "next";
import "./globals.css";
import { IBM_Plex_Mono, JetBrains_Mono, Playfair_Display, Space_Grotesk, Work_Sans } from "next/font/google";
import { TazaProvider } from "@/components/TazaContext";

const workSans = Work_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "900"],
  variable: "--font-work-sans",
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ["400", "700", "900"],
  style: ["italic", "normal"],
  variable: "--font-playfair-display",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-ibm-plex-mono",
});

const jetBrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-jetbrains-mono",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-space-grotesk",
});

export const metadata: Metadata = {
  title: "TazaKhabar",
  description: "Tech job market intelligence with honest signals.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${workSans.variable} ${playfair.variable} ${ibmPlexMono.variable} ${jetBrainsMono.variable} ${spaceGrotesk.variable}`}
    >
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined"
        />
      </head>
      <body className="font-sans">
        <TazaProvider>{children}</TazaProvider>
      </body>
    </html>
  );
}
