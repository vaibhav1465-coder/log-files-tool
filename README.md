# Express Intelligence OS

Evidence-first log analysis for Financial Express and other approved Express publications.

## Milestone 1

This repository currently provides:

- a Vercel-ready Next.js frontend shell;
- a Dockerized FastAPI control plane;
- PostgreSQL for product metadata;
- Redis for future background-job coordination;
- streaming preflight parsers for the supplied CDN access logs and origin JSONL logs;
- quality-gate calculations that never turn missing evidence into zero.
- an interactive New Analysis preflight for `.log`, `.jsonl`, text, and safe ZIP inputs.
- immutable analysis-run and source-file metadata in PostgreSQL;
- a Redis-backed background worker for full streaming analysis;
- disk-backed URL aggregation and reusable HTTP status aggregates;
- an Analysis Library with live run phase, evidence state, and processed-row counts.
- a run-results dashboard with Googlebot, recrawl, revisit, and HTTP response evidence;
- filtered and paginated URL-level evidence;
- streamed CSV exports with spreadsheet-formula injection protection.
- GSC property configuration, 28-day performance sync, sitemap evidence, and quota-aware URL Inspection;
- connector health, inspection cohorts, and auditable administrative actions.

Production activation requirements are documented in `docs/PRODUCTION_RUNBOOK.md`.

## Deployment modes

Local development remains bound to localhost. The production edition is a
self-hosted team deployment with HTTPS, named gateway credentials, request and
upload limits, durable Redis Stream jobs, persistent host-mounted storage,
multiple workers, and daily PostgreSQL backups. Never publish the development
Compose stack to the internet.

The production stack has no software licence charge, but 500 GB of private
storage and daily analysis require company-provided server capacity. See
`docs/SCALE_500GB_DEPLOYMENT.md` for hardware, security, deployment, recovery,
and release gates.

## Large-file intake

- Exactly one source file is accepted per analysis run.
- The local UI uses resumable chunks. Production admission is configurable up
  to 500 decimal GB, with a 100 GB free-space reserve by default.
- The browser uploads resumable 16 MiB chunks with offset reconciliation and three retry attempts.
- The source is written directly to `D:\Log Files\data\source-files` through the Docker bind mount.
- Preflight and full analysis reuse that same immutable source; there is no second upload or duplicate source copy.
- Admission requires enough free space for the source plus a 10 GB safety reserve.
- URL aggregation is disk-backed and its scratch database is created beside the source on `D:`.
- Completed uploads receive a SHA-256 checksum before analysis is queued.

These controls reduce failure risk, but power loss, physical disk failure, corrupt input, or insufficient PostgreSQL capacity can still interrupt a run. Keep the machine awake and Docker Desktop running during large analyses.

Large production uploads will use direct multipart transfer to an India-region object store. Docker packages the services, but it does not replace persistent production storage, backups, or regional compute.

## Run locally

Copy `.env.example` to `.env`, then run:

```powershell
docker compose up --build
```

Open the frontend at `http://localhost:3001`. Port 3001 is used by default to avoid conflicting with other local applications. The API health endpoint is `http://localhost:8000/api/v1/health`.

The development preflight sends selected files to the local API and inspects at most 10,000 rows per file. This is intentionally separate from the production upload design: large production files will transfer directly to regional object storage through resumable multipart uploads.

After a preflight passes, **Start full analysis** stores an immutable development source file, creates a queued run, and hands it to the worker. The worker persists URL/status evidence and continues independently of the browser.

Run parser tests locally with the bundled or system Python:

```powershell
python -m unittest discover -s apps/api/tests
```

## Delivery sequence

1. Parser preflight and evidence gates
2. Resumable direct uploads and immutable source-file inventory
3. Asynchronous analysis workers and stored aggregates
4. Analysis Library, status evidence, and CSV exports
5. GSC connection and quota-aware URL inspection
6. Admin, auditing, security hardening, and production rollout
