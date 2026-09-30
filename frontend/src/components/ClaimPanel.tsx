import { displayText, humanize } from "@/lib/presentation";
import type { ExtractedClaim, SourceItem } from "@/lib/types";

export function ClaimPanel({ claims, sources }: { claims: ExtractedClaim[]; sources: SourceItem[] }) {
  return (
    <section className="report-section report-claims">
      <div className="report-section-heading">
        <h2><span className="report-section-number">01</span>Claim ledger</h2>
        <span className="report-count">{String(claims.length).padStart(2, "0")}</span>
      </div>
      <p className="report-section-note">Support applies to each claim. Confidence values are assigned by normalization rules and are not calibrated probabilities. They do not establish broader impact.</p>
      {claims.length ? (
        <table className="report-claim-table">
          <caption className="sr-only">Extracted claims, supporting sources, and confidence assessments</caption>
          <thead><tr><th scope="col">Statement & provenance</th><th scope="col">Assessment</th></tr></thead>
          <tbody>{claims.map((claim, index) => {
            const sourceIndex = sources.findIndex((source) => source.id === claim.source_id);
            const source = sources[sourceIndex];
            return (
              <tr key={claim.id} id={`claim-${claim.id}`}>
                <td>
                  <div className="report-claim-statement"><span className="report-claim-number">{String(index + 1).padStart(2, "0")}</span><p>{displayText(claim.text)}</p></div>
                  <div className="report-claim-citation">{source ? <a href={`#source-${source.id}`}>[{sourceIndex + 1}] {source.source_name}</a> : <span>Source reference unavailable</span>}{claim.is_material ? <span>Material claim</span> : null}</div>
                  {claim.contradicts_claim_ids.length ? <p className="report-claim-conflict">Contradicts {claim.contradicts_claim_ids.map((claimId, linkedIndex) => {
                    const matchingIndex = claims.findIndex((item) => item.id === claimId);
                    return <span key={claimId}>{linkedIndex > 0 ? ", " : ""}{matchingIndex >= 0 ? <a href={`#claim-${claimId}`}>claim {String(matchingIndex + 1).padStart(2, "0")}</a> : "a linked claim outside this record"}</span>;
                  })}.</p> : null}
                </td>
                <td className="report-claim-assessment">
                  <span className="report-support">{humanize(claim.support_level)}</span>
                  <span className="report-confidence-value">{(claim.confidence * 100).toFixed(0)}<small> / 100</small></span>
                  <span className="report-confidence-label">Claim confidence</span>
                </td>
              </tr>
            );
          })}</tbody>
        </table>
      ) : <p className="report-empty">No extracted claims recorded.</p>}
    </section>
  );
}
