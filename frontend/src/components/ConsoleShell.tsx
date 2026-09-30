import Link from "next/link";
import type { ReactNode } from "react";
import type { DataMode } from "@/lib/presentation";
import { RefreshButton } from "./RefreshButton";

const modeLabels: Record<DataMode, string> = {
  demo: "Demonstration", live: "Official snapshots", mixed: "Mixed records",
  empty: "Empty register", unavailable: "Service unavailable",
};

export function ConsoleShell({ children, mode, detail = false, section = "signals" }: { children: ReactNode; mode: DataMode; detail?: boolean; section?: "news" | "signals" }) {
  return (
    <div className="desk-shell">
      <a href="#main-content" className="skip-link">Skip to content</a>
      <header className="masthead">
        <div className="masthead-brand">
          <Link href="/" aria-label="ThreatMon news map" className="wordmark">Threat<span>Mon</span></Link>
          <p>PUBLIC SOURCE OBSERVATORY</p>
        </div>
        <div className="masthead-tools">
          <span className={`edition-label edition-${mode}`}><span aria-hidden="true" className="edition-dot" />{modeLabels[mode]}</span>
          <RefreshButton />
        </div>
      </header>
      <nav className="desk-nav" aria-label="Main navigation">
        <div className="desk-nav-links">
          <Link href="/" aria-current={!detail && section === "news" ? "page" : undefined}>01 <span>News map</span></Link>
          <Link href="/signals" aria-current={!detail && section === "signals" ? "page" : undefined}>02 <span>Source signals</span></Link>
          <Link href={section === "news" ? "/#news-method" : "/signals#methodology"}>03 <span>Method</span></Link>
        </div>
        <span className="nav-note">SNAPSHOTS, NOT FORECASTS</span>
      </nav>
      <main id="main-content" className="desk-main">{children}</main>
      <footer className="desk-footer"><span>THREATMON / SOURCE-CITED MONITORING</span><span>Publication ≠ impact. All timestamps UTC.</span></footer>
    </div>
  );
}
