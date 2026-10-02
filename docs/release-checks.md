# Public-release verification

Verified on **October 2, 2026**. This release changes documentation and graphics; application code is the tested `a6f92cf` baseline.

## Reproducibility

A separate clean checkout used new dependency directories, the committed lockfiles, Python 3.12 and Node.js 22. No source-feed access is required for the test suites.

| Check | Result |
| --- | --- |
| `uv==0.12.21`, frozen backend installation | Passed |
| Backend tests | 351 passed, 92% coverage |
| `npm ci` | Passed; lockfile unchanged |
| Frontend tests | 48 passed |
| ESLint / TypeScript `--noEmit` | Passed |
| Next.js production build | Passed |
| Full and production npm audit | Zero known vulnerabilities reported |
| Backend `pip-audit` | Zero known vulnerabilities across 38 third-party packages; none skipped |
| Current headless checks | Passed: stored sample, demo labeling, matching hotspot/drawer counts, desktop errors, 375px and 320px interaction/overflow |
| Full local history and artifact audit | No actual credentials or private artifacts found |
| Docker Compose | Docker unavailable locally; the public CI workflow runs the Compose smoke check |

One existing Starlette/httpx deprecation warning remains in the backend suite. Audit results are dated observations, not guarantees against future vulnerabilities. Dependencies retain their own licenses; see [third-party notices](../THIRD_PARTY_NOTICES.md).

## Source evidence

The saved September 30 GDELT request returned 250 canonical articles from 185 publisher domains after an earlier 429 and its cooldown. It reached the query cap. The conservative matcher produced zero candidate event groups and zero supported incident points. The release does not loosen rules to manufacture a populated map.

Fresh captures use the actual saved snapshots and show stale retrievals. Demonstration screenshots use the separate, visibly fictional fixture edition. Source caches, databases, local logs and raw validation artifacts are not part of the public repository. No full publisher bodies or images were downloaded for this release.

## Operating boundary

The release does not deploy a service or start a polling worker. Local ports remain bound to loopback by default. Opening or refreshing the console only reads storage. Authentication, dependable ongoing collection and reviewed incident geolocation remain future work.

Follow the [CI workflow](https://github.com/ParsingMAINFRAME/ThreatMon/actions/workflows/ci.yml) for the results associated with the published commit. See [graphics provenance](graphics/README.md) for the screenshot compositions.
