# Express Intelligence OS — 500 GB team deployment

## Supported production shape

This edition is a self-hosted, open-source deployment. It stores up to 500 GB
of source logs and serves a team through one HTTPS address. The software has no
licence fee; the server, storage, network, backups, and administration are not
free resources.

Minimum starting server:

- Ubuntu Server 24.04 LTS in an Indian Express office or approved India data centre
- 16 physical CPU cores, 64 GB RAM
- 1 TB usable NVMe for application data
- a separate 1 TB backup target
- a static address and an approved hostname
- Docker Engine with Compose v2

For predictable daily throughput, split exports into 10–25 GB archives. The
system can retain 500 GB and accepts a configured maximum file size of 500 GB,
but a single 500 GB archive is a poor failure and recovery boundary.

## Security boundary

The public internet must never reach PostgreSQL, Redis, the API, or workers.
Only Caddy exposes ports 80 and 443. Caddy provides HTTPS and team credentials;
the API also applies trusted-host checks, Redis-backed request limits, upload
limits, request IDs, and restrictive response headers.

Create a separate password hash for each team member:

```sh
docker run --rm caddy:2.10-alpine caddy hash-password --plaintext 'use-a-password-manager-value'
```

Create `deploy/secrets/caddy-users` with one line per person:

```text
username1 $2a$14$replace_with_generated_hash
username2 $2a$14$replace_with_generated_hash
```

Never commit this file. Remove a departed user immediately and reload Caddy.

## First deployment

1. Copy `.env.production.example` to `.env.production` and replace every
   example value with approved values.
2. Create the data and backup directories on different disks or systems.
3. Confirm the data disk has at least 600 GB free (500 GB plus the default
   100 GB reserve).
4. Start the production stack:

```sh
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

5. Verify all services are healthy, sign in through the HTTPS address, upload
   a controlled sample, and restore a database backup into a test database.

## Persistence and recovery

- Source files live under `${EXPRESS_DATA_ROOT}/source-files`.
- PostgreSQL data lives under `${EXPRESS_DATA_ROOT}/postgres`.
- Redis Streams and pending job state live under `${EXPRESS_DATA_ROOT}/redis`.
- Daily compressed PostgreSQL backups live under `${EXPRESS_BACKUP_ROOT}` and
  are retained for 14 days by default.
- A worker crash leaves its job pending. Another worker reclaims it after ten
  minutes. The source file is never uploaded again.

Do not run `docker compose down -v`, delete the data directories, or expose
database ports. Test a restore quarterly. Back up source files independently
when retention policy requires them to survive a primary-disk loss.

## Operational guardrails

- Keep at least 100 GB free on the source volume.
- Alert at 70%, 80%, and 90% storage use.
- Keep two concurrent uploads and four workers initially; tune only from
  measured CPU, disk latency, and queue depth.
- Retain raw logs only for the approved period, then delete them through a
  controlled retention job after confirming required aggregates and backups.
- Treat query strings as potentially sensitive. Add parameter masking rules
  before accepting logs containing tokens, email addresses, or user IDs.
- Rotate team passwords, database passwords, Redis passwords, and TLS account
  access on a documented schedule.
- Patch the host and rebuild images monthly, after testing in staging.

## Release gates before company rollout

- Company owner approves hostname, TLS, user list, and retention period.
- Security reviews the internet boundary and verifies only ports 80/443.
- A 25 GB representative CDN file and a 25 GB origin file complete within the
  agreed service-level objective.
- Power-loss, worker-kill, disk-full, malformed ZIP, duplicate upload, excessive
  requests, and backup-restore exercises pass.
- At least one administrator owns incident response and capacity monitoring.
