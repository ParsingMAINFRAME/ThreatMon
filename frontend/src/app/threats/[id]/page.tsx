import Link from "next/link";
import { notFound } from "next/navigation";

import { ClaimPanel } from "@/components/ClaimPanel";
import { ConsoleShell } from "@/components/ConsoleShell";
import { DataNotice } from "@/components/DataNotice";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { SourcePanel } from "@/components/SourcePanel";
import { Timeline } from "@/components/Timeline";
import { ApiError, getThreat } from "@/lib/api";
import { categoryLabels, displayText, displayTitle, formatDateTime, humanize } from "@/lib/presentation";
import { parseRegisterState, registerHref } from "@/lib/register-state";
import type { ThreatDetailResponse } from "@/lib/types";
import { LAND_PATHS, projectLocation } from "@/lib/world-map";
import "../../report.css";

export const dynamic = "force-dynamic";

async function loadThreat(id: string): Promise<{ data: ThreatDetailResponse | null; error: string | null }> {
  try { return { data: await getThreat(id), error: null }; }
  catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return { data: null, error: error instanceof Error ? error.message : "Unable to load event." };
  }
}

export default async function ThreatDetailPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { id } = await params;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(await searchParams)) {
    if (value !== undefined) query.set(key, Array.isArray(value) ? value[0] : value);
  }
  const returnHref = registerHref(parseRegisterState(query), true);
  const { data, error } = await loadThreat(id);
  const threat = data?.item;
  const mode = threat ? threat.is_demo ? "demo" : "live" : "unavailable";
  const location = threat?.map_location;
  const point = location ? projectLocation(location.lon, location.lat) : null;

  return (
    <ConsoleShell mode={mode} detail>
      <div className="dossier">
        <Link href={returnHref} className="report-back">← Event register</Link>
        {error ? (
          <section className="report-error">
            <p className="report-kicker">Evidence dossier / Unavailable</p>
            <h1>Event unavailable</h1>
            <p>The data service could not load this evidence brief. Refresh once the backend is available.</p>
            <p className="report-error-detail">{error}</p>
          </section>
        ) : null}
        {threat ? <>
          <header className="dossier-header">
            <div className="dossier-heading-line">
              <p className="report-kicker">Evidence dossier <span aria-hidden="true">/</span> {categoryLabels[threat.category]}</p>
              <p className="dossier-status"><span>Status</span> {humanize(threat.status)}</p>
            </div>
            <h1 className="dossier-title">{displayTitle(threat.title)}</h1>
            <p className="dossier-summary">{displayText(threat.summary)}</p>
            <dl className="dossier-filing">
              <div><dt>Geography</dt><dd>{threat.geography.join(" · ") || "Unspecified"}</dd></div>
              <div><dt>{threat.is_demo ? "Scenario snapshot" : "Record updated"}</dt><dd><time dateTime={threat.updated_at}>{formatDateTime(threat.updated_at)}</time></dd></div>
              <div><dt>References</dt><dd><a href="#source-register">{threat.sources.length} source {threat.sources.length === 1 ? "record" : "records"}</a></dd></div>
            </dl>
          </header>

          <DataNotice mode={mode} />

          <div className="dossier-columns">
            <div className="dossier-body">
              <ClaimPanel claims={threat.extracted_claims} sources={threat.sources} />
              <ReportList number="02" title="Key uncertainties" items={threat.key_uncertainties} emptyText="No uncertainties have been recorded. This does not establish certainty." />
              <ReportList number="03" title="Contradictory evidence" items={threat.contradictory_evidence} emptyText="No contradictions are recorded in this event. Absence of confirmation is not contradictory evidence." />
              <Timeline entries={threat.timeline} sources={threat.sources} />
              <ReportList number="05" title="Operational implications" items={threat.implications} emptyText="No operational implications recorded." />
            </div>
            <aside className="dossier-margin" aria-label="Assessment and references">
              {location && point ? <section className="report-section report-margin-section report-location">
                <div className="report-section-heading"><h2>Geographic reference</h2></div>
                <svg viewBox="0 0 1000 500" role="img" aria-label={`World map showing ${location.label}`}>
                  <rect width="1000" height="500" fill="var(--wash)" />
                  <g fill="#b8b9ad">{LAND_PATHS.map((path, index) => <path key={index} d={path} fillRule="evenodd" />)}</g>
                  <g stroke="var(--accent)" fill="none" strokeWidth="2"><line x1={point.x} y1="0" x2={point.x} y2="500" strokeDasharray="5 9" opacity=".4" /><line x1="0" y1={point.y} x2="1000" y2={point.y} strokeDasharray="5 9" opacity=".4" /><circle cx={point.x} cy={point.y} r="20" /></g>
                  <circle cx={point.x} cy={point.y} r="7" fill="var(--accent)" />
                </svg>
                <p className="report-location-label">{location.label}</p>
                <p className="report-location-coordinates">{Math.abs(location.lat).toFixed(2)}° {location.lat < 0 ? "S" : "N"} / {Math.abs(location.lon).toFixed(2)}° {location.lon < 0 ? "W" : "E"}</p>
                <p className="report-footnote">{location.origin === "synthetic_demo" ? "Illustrative position for a synthetic scenario." : "Point coordinates reported by the source. This marker does not show an affected area."} <a href={`#source-${location.source_id}`}>Location reference ↗</a></p>
              </section> : null}
              <ScoreBreakdown score={threat.score} />
              <ReportList title="Next watch items" items={threat.next_watch_items} margin />
              <SourcePanel sources={threat.sources} />
            </aside>
          </div>
          <p className="dossier-reference">Record reference <span>{threat.id}</span></p>
        </> : null}
      </div>
    </ConsoleShell>
  );
}

function ReportList({ number, title, items, emptyText = "No items recorded.", margin = false }: { number?: string; title: string; items: string[]; emptyText?: string; margin?: boolean }) {
  return (
    <section className={`report-section${margin ? " report-margin-section" : ""}`}>
      <div className="report-section-heading">
        <h2>{number ? <span className="report-section-number">{number}</span> : null}{title}</h2>
        <span className="report-count">{String(items.length).padStart(2, "0")}</span>
      </div>
      {items.length ? <ul className="report-prose-list">{items.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="report-empty">{emptyText}</p>}
    </section>
  );
}
