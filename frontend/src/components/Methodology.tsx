export function Methodology() {
  return (
    <section id="methodology" className="method-section">
      <details>
        <summary><span className="section-kicker">03 / METHOD & LIMITS</span><span>How this register is read <span aria-hidden="true">+</span></span></summary>
        <div className="method-columns">
          <div><h3>A source is a starting point.</h3><p>Confirmation describes the published event or catalog entry. It does not establish damage, organizational exposure, or every possible implication. Revisions from one agency are source records, not independent corroboration.</p><p>Official silence does not disprove a signal. Missing evidence and contradictory evidence are recorded separately.</p></div>
          <div><h3>An index, not a forecast.</h3><p>Priority combines severity, credibility, velocity and exposure, discounted for uncertainty. The inputs are explicit assessments and policy assumptions; the result is not a probability of harm.</p><code>100 × S/100 × C/100 × V/100 × E/100 × (1 − U/100)</code><p>Official connectors use unmeasured baselines for velocity and exposure. Their assessment confidence can be low even when publication is confirmed.</p></div>
          <div><h3>Location has a provenance.</h3><p>USGS points use agency-reported coordinates. Synthetic scenarios use illustrative positions, visibly labeled DEMO. Global catalog entries and near-Earth records are not assigned invented terrestrial locations.</p><p>Marker size and selection rings do not show an impact radius. Refresh reads stored records; ingestion fetches the source.</p></div>
        </div>
      </details>
    </section>
  );
}
