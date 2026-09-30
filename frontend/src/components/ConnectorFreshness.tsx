import { assessConnectorFreshness, STALE_AFTER_HOURS } from "@/lib/freshness";
import { formatDateTime, humanize } from "@/lib/presentation";
import type { ConnectorStatusResponse } from "@/lib/types";
import "@/app/freshness.css";

const connectorNames: Record<string, string> = {
  usgs_earthquakes: "USGS earthquakes",
  cisa_kev: "CISA exploited vulnerabilities",
};

export function ConnectorFreshness({ data, assessedAt }: { data: ConnectorStatusResponse | null; assessedAt: number }) {
  const assessedTime = new Date(assessedAt).toISOString();
  return (
    <section className="feed-status" aria-labelledby="feed-status-title">
      <div className="feed-status-heading">
        <h2 id="feed-status-title">Feed retrieval</h2>
        <p>{data?.automatic_refresh_enabled ? "Source scheduling enabled" : "Manual ingestion"} · Refresh reads stored records</p>
      </div>
      <p className="feed-status-context">Successful official-feed fetches, separate from event updates. Demo fixtures do not count.</p>
      {data && data.connectors.length ? <ul className="feed-status-list">{data.connectors.map((connector) => {
        const assessment = assessConnectorFreshness(connector, assessedAt);
        const attemptLabel = assessment.attemptState === "error" ? "Latest fetch failed" : assessment.attemptState === "never_run" ? "Never fetched" : "Fetch succeeded";
        const ageStateLabel = assessment.ageState === "stale" ? `Stale · over ${STALE_AFTER_HOURS}h` : assessment.ageState === "within_threshold" ? `Within ${STALE_AFTER_HOURS}h` : assessment.ageState === "unknown" ? "Age unavailable" : null;
        return <li key={connector.name} className={`feed-status-item feed-status-${assessment.ageState}`}>
          <div className="feed-status-name"><h3>{connectorNames[connector.name] ?? humanize(connector.name)}</h3><span className={assessment.attemptState === "error" ? "feed-status-error" : undefined}>{attemptLabel}</span></div>
          <dl>
            <div><dt>Last successful fetch</dt><dd>{assessment.lastSuccessAt ? <time dateTime={assessment.lastSuccessAt}>{formatDateTime(assessment.lastSuccessAt)}</time> : assessment.ageState === "never_fetched" ? "No successful fetch recorded" : "Retrieval time unavailable"}</dd></div>
            {assessment.ageLabel || ageStateLabel ? <div className="feed-status-age"><dt>Retrieval age</dt><dd>{assessment.ageLabel ? <span>{assessment.ageLabel}</span> : null}{ageStateLabel ? <strong>{ageStateLabel}</strong> : null}</dd></div> : null}
            {assessment.attemptState === "error" && assessment.lastAttemptAt ? <div><dt>Failed attempt</dt><dd><time dateTime={assessment.lastAttemptAt}>{formatDateTime(assessment.lastAttemptAt)}</time></dd></div> : null}
          </dl>
        </li>;
      })}</ul> : <p className="feed-status-unavailable">Feed status unavailable. The event register loads independently; retrieval age cannot be assessed.</p>}
      <p className="feed-status-policy">Stale means more than {STALE_AFTER_HOURS}h since a successful fetch; a recent fetch does not establish current conditions. Ages assessed at <time dateTime={assessedTime}>{formatDateTime(assessedTime)}</time>.</p>
    </section>
  );
}
