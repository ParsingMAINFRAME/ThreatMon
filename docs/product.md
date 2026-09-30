# Product Scope

Threat Situation Room is a disciplined threat-intelligence system for monitoring public information and turning source records into structured threat events.

## Product Goals

- Ingest official sources, reputable news, public datasets, and carefully governed public signals.
- Cluster related source records into live threat events.
- Preserve citations, uncertainties, contradictions, and material timeline changes.
- Explain operational, market, sector, supply-chain, and company relevance only when source support exists.
- Provide transparent, deterministic scoring that analysts can inspect.

## Product Non-Goals

- Fear dashboard or doom feed.
- Generic news aggregator.
- Trading recommendation engine.
- Cyber exploitation assistant.
- Biological protocol or experimental guidance system.
- Speculative panic product.

## MVP Boundary

The portfolio release provides a local-first world atlas, searchable event register, and source-linked evidence dossiers. On-demand USGS and CISA ingestion supplies records with provenance, deterministic prioritization, and material-change timelines persisted through SQLAlchemy. The read-only API supports filtering and pagination.

The atlas plots source-reported USGS points and clearly illustrative demo points over locally bundled Natural Earth geometry. CISA records and the nonterrestrial asteroid demo have no point and remain available in the register. Geographic extent is a view of stored records, not a claim of comprehensive worldwide monitoring. Markers do not represent affected areas or population exposure.

Ingestion is an explicit CLI action. Records represent stored snapshots; the console does not continuously poll source feeds. Demo records and fetched official records have distinct identities and visible origin labels.

Automated cross-source clustering, alerts, user management, watchlists, and automated implication generation remain outside the implemented boundary. The system does not establish damage, casualties, customer counts, or organizational exposure without evidence.
