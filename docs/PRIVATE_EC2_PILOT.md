# Private EC2 pilot runbook

This runbook deliberately excludes real bucket names, prefixes, IP addresses, usernames, passwords, PEM contents, VPN profiles, and account identifiers.

## Release gates

Do not deploy until all of the following are true:

- All credentials shared outside the approved password channel have been rotated.
- The feature pull request passes API tests and the web build.
- Security review has no unresolved high or critical finding.
- The EC2 role has only the approved S3 list/read actions and prefixes.
- The EC2 security group exposes the application port only to the approved VPN CIDR.
- SSH is restricted to the approved administrative VPN path.
- The EBS volume is encrypted.
- No public IP or public DNS route is required by the application.
- The private environment file is owned by root and mode 600.
- A rollback copy of the current application metadata exists.

## Private configuration

Create the production environment file on the server, never in Git. Populate the private application host, PostgreSQL and Redis service secrets, and the two approved Financial Express bucket/prefix pairs. Use a 20 GB per-run remote byte limit, a 20 GB disk reserve, one worker, and one active run.

The application reads AWS credentials only from the attached EC2 role.

## Named users

Create one gateway account per approved pilot user. Store only Caddy password hashes in the server-only secrets file. Never commit or send plaintext passwords through chat.

## Read-only preflight

Run `deploy/preflight-private-pilot.sh` from the repository directory. It checks architecture, disk reserve, required tools, private configuration permissions, role availability, allowlisted prefix visibility, and Compose validity. It does not download an object or mutate AWS.

## Deployment sequence

1. Record the current commit and container state.
2. Build the ARM64 containers from the reviewed commit.
3. Start PostgreSQL and Redis.
4. Run schema migrations through API startup.
5. Start one worker, API, frontend, and gateway.
6. Confirm that PostgreSQL, Redis, and the API have no host ports.
7. Confirm that only the internal gateway port is listening.
8. Run health, authentication, source catalog, estimate, and one small historical-hour analysis.
9. Verify that no source object was written, deleted, copied to Vercel, or retained locally.
10. Record the deployment commit, operator, time, and verification results in the private operational log.

## Storage operations

- Maintain at least 20 GB free disk.
- Source bytes shown in the UI are remote evidence volume, not local disk usage.
- Scratch databases are removed after each aggregation.
- Keep three days of database backups during the one-month pilot.
- Stop new runs if disk reserve, database health, or Redis coordination is unavailable.

## Rollback

Stop the new containers, restore the previous reviewed commit and metadata backup, then start the previous stack. Never delete volumes during rollback.
