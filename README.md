# Express Intelligence OS — Financial Express pilot

A private, evidence-first log analysis tool for a small Financial Express operations team.

## Pilot architecture

- The application runs on one ARM64 EC2 host with a 100 GB encrypted EBS volume.
- Users connect through the company VPN and open the internal application.
- Users choose an approved Financial Express source, UTC date, and hour range.
- The backend uses the EC2 instance role; no AWS access keys are accepted or stored.
- Source gzip objects are streamed from S3 and are not retained on disk.
- PostgreSQL stores run metadata and aggregated evidence. Redis coordinates one worker.
- Source buckets are treated as read-only. The application contains no S3 write or delete operation.

The public repository contains no bucket names, prefixes, account identifiers, credentials, VPN profiles, or server keys. Those values belong only in the server's private environment file.

## User workflow

1. Connect to the company VPN.
2. Open the internal application address supplied by the administrator.
3. Sign in with the named pilot account.
4. Choose Financial Express CloudFront or Akamai.
5. Select a UTC date and hour range.
6. Check the file count and size.
7. Start one analysis and monitor it in the Analysis Library.
8. Review the evidence dashboard or export filtered CSV evidence.

Users do not upload files, use the AWS console, enter bucket paths, or run AWS commands.

## Pilot limits

- Financial Express only.
- Five to six named users.
- One active processing run.
- Up to 5,000 objects and 20 GB compressed source data per run.
- At least 20 GB of local disk remains reserved.
- Production browser uploads are disabled.
- CloudFront and gzip parsing is covered by automated regression tests.

## Development

The development stack remains Docker Compose based:

```powershell
docker compose up --build
```

Run API tests:

```powershell
python -m unittest discover -s apps/api/tests
```

Build the web application:

```powershell
Set-Location apps/web
pnpm install --frozen-lockfile
pnpm run build
```

Private server preparation and verification are documented in `docs/PRIVATE_EC2_PILOT.md`.
