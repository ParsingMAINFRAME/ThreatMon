# AGENTS.md

Rules for future Codex sessions on Threat Situation Room.

## Product Principles

- Keep the system evidence-first, citation-first, and uncertainty-aware.
- Never present unverified social, local, or single-source signals as confirmed.
- Preserve contradictory evidence and key uncertainties.
- Do not fabricate sources, citations, statistics, scores, or company impacts.
- Demo data must remain visibly labeled as demo data.
- Official sources usually carry higher credibility, but official silence alone does not prove a claim false.

## Safety Rules

- Do not add cyber exploit instructions, weaponization detail, credential material, or bypass guidance.
- Do not add biological protocols, experimental instructions, pathogen optimization detail, or misuse-enabling biological content.
- Do not add trading recommendations, investment claims, or technical analysis.
- Avoid panic framing, sensational language, and certainty that the evidence does not support.

## Engineering Rules

- Prefer explicit names over clever abstractions.
- Keep scoring deterministic, transparent, documented, and tested.
- Do not add machine learning in the MVP unless explicitly requested in a later plan.
- Do not add paid APIs in the first scaffold.
- Do not add live social scraping in the first scaffold.
- Keep connectors read-only and source-cited.
- Add tests when changing scoring, reliability, status transitions, normalization, or API contracts.
- Keep backend domain logic independent from the FastAPI route layer where practical.

## Frontend Rules

- The UI should feel like an operational intelligence tool, not a landing page.
- Always display demo/live state clearly.
- Show source citations, uncertainty, contradictions, score breakdowns, and next watch items near each threat detail.
- Avoid decorative layouts that reduce scanability.
