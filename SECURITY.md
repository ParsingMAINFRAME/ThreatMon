# Security

This is a local-first portfolio application with a read-only HTTP API. Ingestion
is an operator CLI action. The default Compose services bind to the loopback
interface. There is no authentication, tenancy, alert delivery, or production
availability guarantee.

Keep credentials, `.env` files, databases, and local exports out of commits. Use
the checked-in lockfiles and keep dependencies updated. Before deploying beyond
your machine, configure TLS, access controls appropriate to the data, request
limits, backups, and an operational refresh policy.

For a vulnerability, use the repository's **Security → Report a vulnerability**
if private reporting is enabled. Otherwise contact the repository owner privately;
do not post secrets or sensitive proof-of-concept details in a public issue.

The [safety policy](docs/safety_policy.md) governs evidence and misuse concerns.
