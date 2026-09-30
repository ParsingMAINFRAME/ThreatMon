import { humanize } from "@/lib/presentation";
import type { ThreatScore } from "@/lib/types";

const metrics: Array<{ key: keyof Pick<ThreatScore, "severity" | "credibility" | "velocity" | "exposure" | "uncertainty_penalty">; label: string }> = [
  { key: "severity", label: "Severity" },
  { key: "credibility", label: "Credibility" },
  { key: "velocity", label: "Velocity" },
  { key: "exposure", label: "Exposure" },
  { key: "uncertainty_penalty", label: "Uncertainty penalty" },
];

export function ScoreBreakdown({ score }: { score: ThreatScore }) {
  return (
    <section className="report-section report-margin-section report-assessment">
      <div className="report-section-heading"><h2>Priority assessment</h2></div>
      <div className="report-priority">
        <p className="report-priority-value">{score.priority.toFixed(2)}<span> / 100</span></p>
        <p className="report-priority-caption">Deterministic triage score</p>
      </div>
      <div className="report-confidence"><span>Assessment confidence</span><strong>{humanize(score.confidence)}</strong></div>
      <dl className="report-score-inputs">{metrics.map((metric) => {
        const value = score[metric.key];
        return (
          <div key={metric.key} className={metric.key === "uncertainty_penalty" ? "report-score-penalty" : undefined}>
            <dt>{metric.label}</dt>
            <dd><span>{value.toFixed(1)}</span><div role="meter" aria-label={metric.label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value} className="report-meter"><div style={{ width: `${Math.min(100, Math.max(0, value))}%` }} /></div></dd>
          </div>
        );
      })}</dl>
      <details className="report-rationale">
        <summary>Inspect rationale & formula</summary>
        <code>100 × S/100 × C/100 × V/100 × E/100 × (1 − U/100)</code>
        <ul>{score.rationale.map((item) => <li key={item}>{item}</li>)}</ul>
      </details>
      <p className="report-footnote">Inputs are assessments, not calibrated probabilities or movement indicators. Uncertainty reduces priority; event status remains separate.</p>
    </section>
  );
}
