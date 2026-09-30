import type { NewsEventView } from "@/lib/news-types";
import { formatNewsTime, humanizeNewsLabel } from "@/lib/news-view";

type CoveragePanelProps = {
  event: NewsEventView | null;
  asOf: string;
  edition: "demo" | "snapshot";
};

function safeArticleUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return null;
    return url.href;
  } catch {
    return null;
  }
}

export function CoveragePanel({ event, asOf, edition }: CoveragePanelProps) {
  if (!event) {
    return (
      <section className="news-coverage news-coverage-empty" id="news-coverage" aria-labelledby="news-coverage-title">
        <p className="news-eyebrow">Selected coverage</p>
        <h2 id="news-coverage-title">Choose an event to inspect its coverage</h2>
        <p>Select a map marker or an event in the register to see its stories, publishers, timestamps and location basis. If no events match, adjust the filters.</p>
        <p className="news-coverage-note">{edition === "demo" ? "Synthetic demo edition. These scenarios are fictional, not reports of actual events." : "Stored news snapshot. Reporting may have changed since retrieval."}</p>
        <p className="news-coverage-note">Edition as of (UTC): {formatNewsTime(asOf)}</p>
      </section>
    );
  }

  const isDemo = edition === "demo" || event.is_demo;
  const location = event.scope === "located" ? event.location : null;
  const locationDescription = event.scope === "global"
    ? "Global relevance; no single incident location"
    : location?.label ?? "Location not established; no map point assigned";

  return (
    <section className="news-coverage" id="news-coverage" aria-labelledby="news-coverage-title">
      <header className="news-coverage-header">
        <p className="news-eyebrow">Selected coverage / {humanizeNewsLabel(event.category)}</p>
        <span className="news-coverage-badge">{isDemo ? "Synthetic demo scenario" : "News snapshot"}</span>
        <h2 id="news-coverage-title">{isDemo ? event.title.replace(/^DEMO /, "") : event.title}</h2>
        {isDemo ? <p className="news-coverage-note"><strong>Fictional scenario, not an actual incident.</strong> Severity is an authored assumption.</p> : <p className="news-coverage-summary">{event.summary}</p>}
      </header>

      <dl className="news-coverage-metrics">
        <div><dt>Stories in this view</dt><dd>{event.story_count}</dd></div>
        <div><dt>Distinct publishers</dt><dd>{event.publisher_count}</dd></div>
      </dl>
      <p className="news-coverage-note">Deduplicated within the current filters. Publisher breadth is not independent corroboration.</p>

      <dl className="news-coverage-meta">
        <div><dt>Reporting status</dt><dd>{humanizeNewsLabel(event.status)}</dd></div>
        <div><dt>Severity</dt><dd>{humanizeNewsLabel(event.severity)}</dd></div>
        <div><dt>Location</dt><dd>{locationDescription}</dd></div>
        <div><dt>Latest publication (UTC)</dt><dd>{formatNewsTime(event.freshest_published_at)}</dd></div>
        <div><dt>Latest retrieval (UTC)</dt><dd>{formatNewsTime(event.last_retrieved_at)}</dd></div>
      </dl>
      <details className="news-coverage-details">
        <summary>Evidence and location details</summary>
        <dl className="news-coverage-meta">
          <div><dt>Severity basis</dt><dd>{event.severity_basis}</dd></div>
          {location ? <>
            <div><dt>Location precision</dt><dd>{humanizeNewsLabel(location.precision)}</dd></div>
            <div><dt>Location confidence</dt><dd>{humanizeNewsLabel(location.confidence)}</dd></div>
            <div><dt>Location basis</dt><dd>{location.basis}</dd></div>
          </> : <>
            <div><dt>Location precision</dt><dd>{event.scope === "global" ? "Not applicable to global coverage" : "Unknown"}</dd></div>
            <div><dt>Location confidence</dt><dd>{event.scope === "global" ? "Not applicable" : "Unknown"}</dd></div>
          </>}
          <div><dt>Edition as of (UTC)</dt><dd>{formatNewsTime(asOf)}</dd></div>
          <div><dt>Why these stories are grouped</dt><dd>{event.grouping_basis}</dd></div>
        </dl>
        <p className="news-coverage-note">Status describes available reporting, not independent verification. Syndicated stories may share an original report. Retrieval records collection time, not event time.</p>
      </details>

      <h3>Stories behind this event</h3>
      {event.articles.length ? (
        <ol className="news-story-list">
          {event.articles.map((article) => {
            const isSyntheticStory = isDemo || article.is_demo;
            const url = isSyntheticStory ? null : safeArticleUrl(article.canonical_url);
            return (
              <li key={article.id}>
                <article className="news-story">
                  <header className="news-story-header">
                    <p className="news-eyebrow">{isSyntheticStory ? "Synthetic demo story" : "Source story"}</p>
                    <h4>{article.headline}</h4>
                    <p>{article.publisher}{isSyntheticStory ? " / Demo publisher label" : ""}</p>
                  </header>
                  <dl className="news-story-meta">
                    <div><dt>Published (UTC)</dt><dd>{formatNewsTime(article.published_at)}</dd></div>
                    <div><dt>Retrieved (UTC)</dt><dd>{formatNewsTime(article.retrieved_at)}</dd></div>
                  </dl>
                  {isSyntheticStory ? (
                    <details className="news-story-preview">
                      <summary>Read synthetic preview<span className="sr-only">: {article.headline}</span></summary>
                      <div className="news-story-preview-body">
                        <p><strong>Fictional demonstration text. This is not a real news report.</strong></p>
                        <p>{article.summary}</p>
                        <p>No external article exists for this synthetic story.</p>
                      </div>
                    </details>
                  ) : <>
                    <p>{article.summary}</p>
                    {url ? <a className="news-story-link" href={url} target="_blank" rel="noopener noreferrer">Read original article<span className="sr-only">: {article.headline} (opens in a new tab)</span></a> : <p className="news-coverage-note">No usable original article URL is available in this snapshot.</p>}
                  </>}
                  {article.syndication_key ? <p className="news-coverage-note">A syndication relationship is recorded; this story may share reporting with other publishers.</p> : null}
                  {article.duplicate_urls.length > 0 ? <p className="news-coverage-note">{article.duplicate_urls.length} duplicate {article.duplicate_urls.length === 1 ? "URL is" : "URLs are"} recorded with this story; they do not add to the story count.</p> : null}
                </article>
              </li>
            );
          })}
        </ol>
      ) : <p className="news-coverage-note">No stories match the current filters for this event.</p>}
    </section>
  );
}
