# Express Intelligence OS production activation

## Current delivery state

The application code supports log preflight, asynchronous full analysis, immutable run history, URL/status evidence, CSV exports, GSC performance/sitemap sync, and quota-aware URL Inspection.

It must not be opened to company users until the controls and external inputs below are completed.

## Required activation inputs

1. A machine or private server running Docker services.
2. Persistent PostgreSQL, Redis/queue, source-file storage, export storage, and backups.
3. Google Cloud service account with Search Console API enabled and read-only access to the Indian Express and Financial Express properties.
4. Secret file mounted as `GOOGLE_SERVICE_ACCOUNT_FILE`; never commit the JSON key.
5. A raw-log retention and query-string masking decision.

This deployment intentionally has no product login, OTP, SSO, allowlist, roles, custom DNS, or custom TLS configuration. Therefore the API and data services must remain on localhost or a restricted private network. Do not expose the unauthenticated API directly to the public internet.

## Production substitutions

The frontend may remain local with the Docker stack. If it is deployed to Vercel, the backend still needs a private access control layer; an unauthenticated public backend is not supported for sensitive log data. Replace Docker development services only when required:

- `source-files` volume -> India-region object storage with resumable multipart uploads and lifecycle rules.
- Docker PostgreSQL -> managed India-region PostgreSQL with encryption, point-in-time recovery, and private networking.
- Docker Redis -> managed regional Redis or durable queue/orchestrator.
- Docker worker -> regional autoscaled container jobs with checkpointing and dead-letter handling.
- Local environment file -> managed secret vault.

The API contracts and database evidence model should remain stable during these substitutions.

## GSC activation

1. Enable the Search Console API in the company Google Cloud project.
2. Create a read-only service account and store its key in the approved vault.
3. Add the service-account email to each Search Console property.
4. Configure each property exactly as it appears in GSC, including `sc-domain:` when applicable.
5. Trigger a 28-day sync and verify performance dates, sitemap records, and connector health.
6. Inspect controlled test URLs and confirm host validation, quota accounting, evidence timestamps, and raw-response retention.
7. Confirm that the interface never presents Search Analytics or sampled inspections as a complete index inventory.

## Private-use launch checks

- No missing evidence displayed as zero.
- Parser reconciliation passes for every approved CDN/origin format.
- Source files and database volumes are backed up if their loss is unacceptable.
- The API, PostgreSQL and Redis ports are not exposed to an untrusted network.
- The GSC key file is outside source control and readable only by the runtime account.
- Controlled Indian Express and Financial Express URLs are used to validate property access.
