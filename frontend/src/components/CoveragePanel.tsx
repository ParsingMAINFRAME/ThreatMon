import type { NewsEventView } from "@/lib/news-types";
import { formatNewsTime, humanizeNewsLabel } from "@/lib/news-view";

type CoveragePanelProps = {
  event: NewsEventView | null;
  asOf: string;
  edition: "demo" | "snapshot";
};

function safeCoverageUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return null;
    return url.href;
  } catch {
    return null;
  }
}

function licenseLabel(value: string): string {
  const url = new URL(value);
  const version = url.pathname.match(/^\/licenses\/by\/(\d+\.\d+)\/?$/)?.[1];
  return ["creativecommons.org", "www.creativecommons.org"].includes(url.hostname) && version
    ? `CC BY ${version} license`
    : "Source license";
}

export function CoveragePanel({ event, asOf, edition }: CoveragePanelProps) {
  if (!event) {
    return (
      <section className="news-coverage news-coverage-empty" id="news-coverage" aria-labelledby="news-coverage-title">
        <p className="news-eyebrow">Selected coverage</p>
        <h2 id="news-coverage-title">Choose an event to inspect its coverage</h2>
        <p>Select a map marker or an event in the register to see its coverage records, sources, timestamps and location basis. If no events match, adjust the filters.</p>
        <p className="news-coverage-note">{edition === "demo" ? "Synthetic demo edition. These scenarios are fictional, not reports of actual events." : "Stored source snapshot. Reporting may have changed since retrieval."}</p>
        <p className="news-coverage-note">Edition as of (UTC): {formatNewsTime(asOf)}</p>
      </section>
    );
  }

  const isDemo = edition === "demo" || event.is_demo;
  const isCandidate = event.grouping_status === "candidate";
  const officialReports = event.articles.filter((article) => (article.record_kind ?? "article") === "official_report");
  const newsArticles = event.articles.filter((article) => (article.record_kind ?? "article") === "article");
  const officialReportCount = event.official_report_count ?? officialReports.length;
  const newsPublisherCount = event.news_publisher_count ?? new Set(newsArticles.map((article) => article.publisher_id || article.publisher.trim().toLowerCase())).size;
  const officialSourceCount = event.official_source_count ?? new Set(officialReports.map((article) => article.publisher_id || article.publisher.trim().toLowerCase())).size;
  const hasOfficialReports = officialReportCount > 0;
  const hasNewsArticles = event.story_count > 0 || !hasOfficialReports;
  const coverageHeading = hasOfficialReports ? (hasNewsArticles ? "Coverage records" : "Official reports") : "News articles";
  const location = event.scope === "located" ? event.location : null;
  const locationSourceUrl = isDemo ? null : safeCoverageUrl(location?.source_url);
  const locationDescription = event.scope === "global"
    ? "Global relevance; no single incident location"
    : location?.label ?? "Location not established; no map point assigned";

  return (
    <section className="news-coverage" id="news-coverage" aria-labelledby="news-coverage-title">
      <header className="news-coverage-header">
        <p className="news-eyebrow">Selected coverage / {humanizeNewsLabel(event.category)}</p>
        <span className="news-coverage-badge">{isDemo ? "Synthetic demo scenario" : "Source snapshot"}</span>
        {isCandidate ? <p className="news-candidate-label">Candidate association · unverified. These reports may not describe the same incident.</p> : null}
        <h2 id="news-coverage-title">{isDemo ? event.title.replace(/^DEMO /, "") : event.title}</h2>
        {isDemo ? <p className="news-coverage-note"><strong>Fictional scenario, not an actual incident.</strong> Severity is an authored assumption.</p> : <p className="news-coverage-summary">{event.summary}</p>}
      </header>

      <dl className="news-coverage-metrics">
        {hasNewsArticles ? <>
          <div><dt>Collected articles</dt><dd>{event.story_count}</dd></div>
          <div><dt>News publishers</dt><dd>{newsPublisherCount}</dd></div>
        </> : null}
        {hasOfficialReports ? <>
          <div><dt>Official reports</dt><dd>{officialReportCount}</dd></div>
          <div><dt>Official sources</dt><dd>{officialSourceCount}</dd></div>
        </> : null}
      </dl>
      <p className="news-coverage-note">Deduplicated within the current filters; a potentially capped sample, not a worldwide total. Source breadth is not independent corroboration. Map color describes article volume, not severity.</p>

      <dl className="news-coverage-meta">
        <div><dt>Source reporting status</dt><dd>{humanizeNewsLabel(event.status)}</dd></div>
        <div><dt>Severity</dt><dd>{humanizeNewsLabel(event.severity)}</dd></div>
        {event.source_alert_level ? <div><dt>Source-model alert</dt><dd>{event.source_alert_level}. Source assessment, not confirmed impact.</dd></div> : null}
        <div><dt>Location</dt><dd>{locationDescription}</dd></div>
        <div><dt>Latest publication (UTC)</dt><dd>{event.freshest_published_at ? formatNewsTime(event.freshest_published_at) : "Not reported"}</dd></div>
        {event.freshest_collected_at ? <div><dt>Latest first collection (UTC)</dt><dd>{formatNewsTime(event.freshest_collected_at)}</dd></div> : null}
        <div><dt>Latest retrieval (UTC)</dt><dd>{formatNewsTime(event.last_retrieved_at)}</dd></div>
      </dl>
      <details className="news-coverage-details">
        <summary>Evidence and location details</summary>
        <dl className="news-coverage-meta">
          <div><dt>Severity basis</dt><dd>{event.severity_basis}</dd></div>
          {event.source_event_id ? <div><dt>Source event identifier</dt><dd>{event.source_event_id}</dd></div> : null}
          {location ? <>
            <div><dt>Location precision</dt><dd>{humanizeNewsLabel(location.precision)}</dd></div>
            <div><dt>Location confidence</dt><dd>{humanizeNewsLabel(location.confidence)}</dd></div>
            <div><dt>Location basis</dt><dd>{location.basis}</dd></div>
            {locationSourceUrl ? <div><dt>Location source</dt><dd><a className="news-story-link" href={locationSourceUrl} target="_blank" rel="noopener noreferrer">View geographic source<span className="sr-only"> (opens in a new tab)</span></a></dd></div> : null}
          </> : <>
            <div><dt>Location precision</dt><dd>{event.scope === "global" ? "Not applicable to global coverage" : "Unknown"}</dd></div>
            <div><dt>Location confidence</dt><dd>{event.scope === "global" ? "Not applicable" : "Unknown"}</dd></div>
          </>}
          <div><dt>Edition as of (UTC)</dt><dd>{formatNewsTime(asOf)}</dd></div>
          <div><dt>Distinct publishers and agencies</dt><dd>{event.publisher_count}</dd></div>
          <div><dt>Why these records are grouped</dt><dd>{event.grouping_basis}</dd></div>
          {event.grouping_status ? <div><dt>Association status</dt><dd>{isCandidate ? "Candidate association — unverified" : event.grouping_status === "source_event" ? "Source-identified event" : "Single-source record"}</dd></div> : null}
          {event.grouping_version ? <div><dt>Grouping method version</dt><dd>{event.grouping_version}</dd></div> : null}
          {event.assignment_revision ? <div><dt>Assignment revision</dt><dd>{event.assignment_revision}</dd></div> : null}
          {event.place_hints?.length ? <div><dt>Unverified place mentions</dt><dd>{event.place_hints.join("; ")}. Textual hints only; no incident location is established from these mentions.</dd></div> : null}
        </dl>
        <p className="news-coverage-note">Status describes available reporting, not independent verification. Syndicated stories may share an original report. Retrieval records collection time, not event time.</p>
      </details>

      <h3>{coverageHeading}</h3>
      {event.articles.length ? (
        <ol className="news-story-list">
          {event.articles.map((article) => {
            const isSyntheticRecord = isDemo || article.is_demo;
            const isOfficialReport = (article.record_kind ?? "article") === "official_report";
            const recordLabel = isOfficialReport ? "Official report" : "News article";
            const url = isSyntheticRecord ? null : safeCoverageUrl(article.canonical_url);
            const licenseUrl = isSyntheticRecord ? null : safeCoverageUrl(article.license_url);
            const hasSourceWindow = Boolean(article.source_window_start || article.source_window_end);
            const observations = article.observations ?? [];
            const providers = Array.from(new Set(observations.map((observation) => observation.provider_id === "gdelt" ? "GDELT" : observation.provider_id)));
            return (
              <li key={article.id}>
                <article className="news-story">
                  <header className="news-story-header">
                    <p className="news-eyebrow">{isSyntheticRecord ? `Synthetic demo / ${recordLabel}` : recordLabel}</p>
                    <h4>{article.headline}</h4>
                    <p>{article.author ? <>By {article.author} / </> : null}{article.publisher}{isSyntheticRecord ? " / Demo source label" : ""}</p>
                    {providers.length ? <p>Discovery provider{providers.length === 1 ? "" : "s"}: {providers.join(", ")}. Publisher attribution is separate.</p> : null}
                  </header>
                  <dl className="news-story-meta">
                    <div><dt>Published (UTC)</dt><dd>{article.published_at ? formatNewsTime(article.published_at) : "Not reported"}</dd></div>
                    {article.first_seen_at ? <div><dt>First collected by ThreatMon (UTC)</dt><dd>{formatNewsTime(article.first_seen_at)}{article.published_at ? "" : "; used for the time filter because publication is unknown"}</dd></div> : null}
                    <div><dt>Retrieved (UTC)</dt><dd>{formatNewsTime(article.retrieved_at)}</dd></div>
                    {hasSourceWindow ? <div><dt>Source coverage window (UTC)</dt><dd>{formatNewsTime(article.source_window_start ?? null)} to {formatNewsTime(article.source_window_end ?? null)}</dd></div> : null}
                  </dl>
                  {hasSourceWindow ? <p className="news-coverage-note">This is the source&apos;s coverage window, not a confirmed occurrence time.</p> : null}
                  {observations.length ? <details className="news-provider-details">
                    <summary>Discovery provenance</summary>
                    {observations.map((observation, index) => {
                      const providerUrl = isSyntheticRecord ? null : safeCoverageUrl(observation.provider_url);
                      const providerName = observation.provider_id === "gdelt" ? "GDELT" : observation.provider_id;
                      return <div key={`${observation.provider_id}-${observation.retrieved_at}-${index}`}>
                        <p><strong>{providerName}</strong> · discovery provider</p>
                        <dl className="news-story-meta"><div><dt>{providerName === "GDELT" ? "GDELT timestamp (seendate; meaning unverified)" : "Provider timestamp (meaning unverified)"}</dt><dd>{observation.provider_timestamp ? formatNewsTime(observation.provider_timestamp) : observation.provider_timestamp_raw ?? "Not reported"}</dd></div><div><dt>Provider record retrieved (UTC)</dt><dd>{formatNewsTime(observation.retrieved_at)}</dd></div>{observation.language ? <div><dt>Provider language label</dt><dd>{observation.language}</dd></div> : null}{observation.source_country ? <div><dt>Provider source-country label</dt><dd>{observation.source_country}; this does not establish incident location</dd></div> : null}</dl>
                        {providerUrl ? <a className="news-story-link" href={providerUrl} target="_blank" rel="noopener noreferrer">View discovery provider<span className="sr-only">: {providerName} (opens in a new tab)</span></a> : null}
                      </div>;
                    })}
                  </details> : null}
                  {isSyntheticRecord ? (
                    <details className="news-story-preview">
                      <summary>Read synthetic preview<span className="sr-only">: {article.headline}</span></summary>
                      <div className="news-story-preview-body">
                        <p><strong>Fictional demonstration text. This is not a real article or official report.</strong></p>
                        <p>{article.summary}</p>
                        <p>No external source exists for this synthetic record.</p>
                      </div>
                    </details>
                  ) : <>
                    <p>{article.summary}</p>
                    {url ? <div><a className="news-story-link" href={url} target="_blank" rel="noopener noreferrer">{isOfficialReport ? "View official source report" : "Read original article"}<span className="sr-only">: {article.headline} (opens in a new tab)</span></a></div> : <p className="news-coverage-note">No usable original source URL is available in this snapshot.</p>}
                    {licenseUrl ? <div><a className="news-story-link" href={licenseUrl} target="_blank" rel="noopener noreferrer">{licenseLabel(licenseUrl)}<span className="sr-only"> for {article.headline} (opens in a new tab)</span></a></div> : null}
                  </>}
                  {article.syndication_key ? <p className="news-coverage-note">A syndication relationship is recorded; this record may share reporting with other publishers.</p> : null}
                  {article.duplicate_urls.length > 0 ? <p className="news-coverage-note">{article.duplicate_urls.length} duplicate {article.duplicate_urls.length === 1 ? "URL is" : "URLs are"} recorded with this item; they do not add to coverage counts.</p> : null}
                </article>
              </li>
            );
          })}
        </ol>
      ) : <p className="news-coverage-note">No records match the current filters for this event.</p>}
    </section>
  );
}
