import Link from "next/link";
import { ConsoleShell } from "@/components/ConsoleShell";
import { ConnectorFreshness } from "@/components/ConnectorFreshness";
import { DataNotice } from "@/components/DataNotice";
import { Methodology } from "@/components/Methodology";
import { RefreshButton } from "@/components/RefreshButton";
import { ThreatTable } from "@/components/ThreatTable";
import { NewsMonitor } from "@/components/NewsMonitor";
import { getConnectorStatus, getNews, getThreats } from "@/lib/api";
import { dataMode, formatDateTime } from "@/lib/presentation";
import type { ThreatListResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

async function loadThreats(): Promise<{ data: ThreatListResponse | null; error: string | null }> {
  try { return { data: await getThreats(), error: null }; }
  catch (error) { return { data: null, error: error instanceof Error ? error.message : "Unable to load records." }; }
}

async function loadDashboard() {
  const [{ data, error }, connectorStatus] = await Promise.all([loadThreats(), getConnectorStatus()]);
  return { data, error, connectorStatus, assessedAt: Date.now() };
}

function SignalViews({ bulletins = false }: { bulletins?: boolean }) {
  return <nav className="news-edition-switch" aria-label="Source signal view" style={{ marginBottom: 22 }}>
    <Link href="/signals" aria-current={!bulletins ? "page" : undefined}>Official event register</Link>
    <Link href="/signals?view=bulletins" aria-current={bulletins ? "page" : undefined}>Hazard and agency bulletins</Link>
  </nav>;
}

export default async function SignalsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  if (params.view === "bulletins") {
    const data = await getNews("snapshot", "signals").catch(() => null);
    const mode = data ? data.events.length ? "live" : "empty" : "unavailable";
    return <ConsoleShell mode={mode}>
      <SignalViews bulletins />
      {data ? <NewsMonitor data={data} /> : <section className="service-error"><h1>Source bulletins are unavailable.</h1><p>The stored bulletin snapshots could not be loaded.</p><RefreshButton /></section>}
    </ConsoleShell>;
  }
  const { data, error, connectorStatus, assessedAt } = await loadDashboard();
  const mode = data?.data_mode ?? dataMode(data?.items ?? null);
  const latest = data?.items.reduce<string | null>((date, threat) => !date || threat.updated_at > date ? threat.updated_at : date, null);
  return (
    <ConsoleShell mode={mode}>
      <SignalViews />
      <div className="overview-heading">
        <div><p className="section-kicker">01 / GEOGRAPHIC VIEW</p><h1>Source signals</h1></div>
        <div className="snapshot-stamp"><span>{mode === "demo" ? "SCENARIO SNAPSHOT" : "LATEST STORED UPDATE"}</span><time dateTime={latest ?? undefined}>{formatDateTime(latest ?? null)}</time></div>
      </div>
      <DataNotice mode={mode} />
      <ConnectorFreshness data={connectorStatus} assessedAt={assessedAt} />
      {error ? <section className="service-error"><p className="section-kicker">CONNECTION</p><h2>The register is unavailable.</h2><p>Try refreshing once the data service is available.</p><RefreshButton /><details><summary>Connection details</summary><p>{error}</p></details></section> : null}
      {data ? <ThreatTable threats={data.items} /> : null}
      <Methodology />
    </ConsoleShell>
  );
}
