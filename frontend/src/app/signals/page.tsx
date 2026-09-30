import { ConsoleShell } from "@/components/ConsoleShell";
import { ConnectorFreshness } from "@/components/ConnectorFreshness";
import { DataNotice } from "@/components/DataNotice";
import { Methodology } from "@/components/Methodology";
import { RefreshButton } from "@/components/RefreshButton";
import { ThreatTable } from "@/components/ThreatTable";
import { getConnectorStatus, getThreats } from "@/lib/api";
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

export default async function SignalsPage() {
  const { data, error, connectorStatus, assessedAt } = await loadDashboard();
  const mode = data?.data_mode ?? dataMode(data?.items ?? null);
  const latest = data?.items.reduce<string | null>((date, threat) => !date || threat.updated_at > date ? threat.updated_at : date, null);
  return (
    <ConsoleShell mode={mode}>
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
