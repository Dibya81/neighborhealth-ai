import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, IBM_Plex_Sans_Condensed, IBM_Plex_Sans_Devanagari, Noto_Sans_Kannada } from "next/font/google";

import { AppShell } from "@/components/shell/app-shell";
import { Providers } from "@/components/providers";

import "./globals.css";

const plex = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex", display: "swap" });
const plexCondensed = IBM_Plex_Sans_Condensed({ subsets: ["latin"], weight: ["500", "600"], variable: "--font-plex-condensed", display: "swap" });
const plexHi = IBM_Plex_Sans_Devanagari({ subsets: ["devanagari"], weight: ["400", "500", "600"], variable: "--font-plex-hi", display: "swap" });
const notoKn = Noto_Sans_Kannada({ subsets: ["kannada"], weight: ["400", "500", "600"], variable: "--font-plex-kn", display: "swap" });

export const metadata: Metadata = {
  title: { default: "NeighborHealth: dengue early warning for Bengaluru", template: "%s · NeighborHealth" },
  description: "Weekly dengue forecasts for Bengaluru with honest uncertainty, ward risk estimates, citizen reports and alerts.",
  applicationName: "NeighborHealth",
  appleWebApp: { capable: true, title: "NeighborHealth", statusBarStyle: "default" },
  icons: { icon: "/icons/icon-192.png", apple: "/icons/icon-192.png" },
};

export const viewport: Viewport = {
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#F4F7F6" }, { media: "(prefers-color-scheme: dark)", color: "#0D1626" }],
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${plex.variable} ${plexCondensed.variable} ${plexHi.variable} ${notoKn.variable}`}>
      <body className="min-h-dvh font-sans">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
