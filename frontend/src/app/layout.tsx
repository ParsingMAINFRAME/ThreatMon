import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ThreatMon | World news monitor",
    template: "%s | ThreatMon",
  },
  applicationName: "ThreatMon",
  description: "Explore numbered news-event hotspots, inspect story coverage and provenance, and compare official source snapshots with clearly labeled synthetic scenarios.",
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
