import { displayText, formatDateTime } from "@/lib/presentation";
import type { SourceItem, ThreatTimelineEntry } from "@/lib/types";

export function Timeline({ entries, sources }: { entries: ThreatTimelineEntry[]; sources: SourceItem[] }) {
  const sorted = [...entries].sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at));
  return (
    <section className="report-section report-history">
      <div className="report-section-heading"><h2><span className="report-section-number">04</span>Event timeline</h2><span className="report-count">{String(entries.length).padStart(2, "0")}</span></div>
      <p className="report-section-note">Latest first / All times UTC</p>
      {entries.length ? <ol className="report-timeline">{sorted.map((entry) => (
        <li key={entry.id}>
          <div className="report-timeline-date"><time dateTime={entry.occurred_at}>{formatDateTime(entry.occurred_at)}</time>{entry.material_change ? <span>Material change</span> : null}</div>
          <div className="report-timeline-entry"><h3>{entry.title}</h3><p>{displayText(entry.description)}</p><div className="report-timeline-sources">{entry.source_ids.map((sourceId) => {
            const index = sources.findIndex((source) => source.id === sourceId);
            return index >= 0 ? <a key={sourceId} href={`#source-${sourceId}`}>Source [{index + 1}]</a> : null;
          })}</div></div>
        </li>
      ))}</ol> : <p className="report-empty">No timeline entries recorded.</p>}
    </section>
  );
}
