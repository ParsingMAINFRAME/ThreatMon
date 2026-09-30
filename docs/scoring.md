# Scoring Model

The scoring model is deterministic and intentionally simple. It is a triage heuristic, not a probability or validated estimate of harm.

## Inputs

Each input is scored from `0` to `100`.

- Severity: potential human, economic, operational, infrastructure, geopolitical, or market impact.
- Credibility: source quality, corroboration, official confirmation, historical reliability, and contradiction level.
- Velocity: how quickly source count, mentions, geography, or official updates are changing.
- Exposure: relevance to tracked geographies, sectors, companies, commodities, supply chains, or watchlists.
- Uncertainty penalty: reduction for weak source support, ambiguous claims, unknown material facts, or contradiction.

## Formula

```text
raw_priority =
  (severity / 100)
  * (credibility / 100)
  * (velocity / 100)
  * (exposure / 100)
  * 100

priority = raw_priority * (1 - uncertainty_penalty / 100)
```

The result is rounded to two decimal places and remains on a `0` to `100` scale.

## Confidence Label

- High: credibility at least `80`, uncertainty penalty at most `20`, and no contradictions.
- Medium: credibility at least `50`, uncertainty penalty at most `40`, and no more than one contradiction.
- Low: anything else.

## Limitations

- The formula is not a risk forecast.
- A low score can still deserve monitoring if uncertainty is high.
- A high credibility score confirms source support, not necessarily high impact.
- The first version does not estimate probability, casualties, losses, stock moves, or macroeconomic impact.
- All score inputs must remain traceable to visible source records or analyst-entered assumptions.

## Official connector policy v1

The current feeds do not measure organizational exposure, event velocity, or realized impact. Normalization labels the following assumptions in every record's rationale:

| Input | Policy | Meaning |
| --- | --- | --- |
| Severity | USGS magnitude × 10, clamped to 0–100; otherwise 50 | A magnitude proxy or unknown-severity baseline, not damage or CVSS |
| Credibility | 92 | Official-source support for the published event/catalog entry |
| Velocity | 50 | Fixed unmeasured baseline; no trend is asserted |
| Exposure | 25 | Conservative unmeasured baseline; no asset or population inventory |
| Uncertainty penalty | 50% | Impact and exposure remain unmeasured |

These records receive low score confidence under the same thresholds used elsewhere. "Confirmed" refers to an official published entry, and automatic USGS estimates remain visibly preliminary. Scores cannot be compared across categories as calibrated risk.

Seeded scenarios use hand-selected illustrative inputs to demonstrate the interface and confidence rules. Those values do not represent live observations.
