import { formatDateTime, humanize, safeSourceUrl } from "@/lib/presentation";
import type { SourceItem } from "@/lib/types";

export function SourcePanel({ sources }: { sources: SourceItem[] }) {
  return (
    <section className="report-section report-margin-section report-sources" id="source-register">
      <div className="report-section-heading"><h2>Source register</h2><span className="report-count">{String(sources.length).padStart(2, "0")}</span></div>
      <p className="report-section-note">Revisions are separate source records, not independent corroboration.</p>
      {sources.length ? <ol className="report-source-list">{sources.map((source, index) => {
        const url = safeSourceUrl(source.url);
        return (
          <li key={source.id} id={`source-${source.id}`}>
            <div className="report-source-heading"><span className="report-source-number">[{index + 1}]</span><span>{humanize(source.source_type)}</span><strong className={source.is_demo ? "report-source-demo" : undefined}>{source.is_demo ? "Demo citation" : "Official snapshot"}</strong></div>
            <h3>{source.title}</h3>
            <p className="report-source-publisher">{source.source_name}{source.is_official ? <span> · Official source</span> : null}</p>
            <blockquote className="report-source-citation">{source.citation}</blockquote>
            <dl className="report-source-metadata">
              <div><dt>Reliability</dt><dd>{humanize(source.reliability_tier)}</dd></div>
              <div><dt>Published</dt><dd>{formatDateTime(source.published_at)}</dd></div>
              <div><dt>Retrieved</dt><dd>{formatDateTime(source.retrieved_at)}</dd></div>
            </dl>
            {source.notes ? <p className="report-source-note">{source.notes}</p> : null}
            {url ? <a className="report-source-link" href={url} target="_blank" rel="noreferrer">View original source <span aria-hidden="true">↗</span><span className="sr-only"> (opens in a new tab)</span></a> : <p className="report-source-note">{source.is_demo ? "Local synthetic citation · no external source" : "No external URL recorded"}</p>}
          </li>
        );
      })}</ol> : <p className="report-empty">No sources recorded.</p>}
    </section>
  );
}
