import type { Metadata } from "next";
import "@fontsource-variable/archivo";
import "@fontsource/instrument-serif/latin-400-italic.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "./globals.css";
import SiteShell from "@/components/site-shell";

export const metadata: Metadata = {
  title: { default: "ConjunctionTriage — An orbital observatory", template: "%s · ConjunctionTriage" },
  description: "An interactive exploration of satellite close approaches, positional uncertainty, and the evidence behind automated collision-risk triage.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><SiteShell>{children}</SiteShell></body></html>;
}
