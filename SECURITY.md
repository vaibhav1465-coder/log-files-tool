# Security policy

## Reporting

Do not open a public issue for a vulnerability, log sample, infrastructure identifier, or exposed credential. Report it privately to the Indian Express engineering/security owner. Include only the minimum request ID, time, and impact needed to investigate.

## Non-negotiable deployment controls

- Never commit or paste production credentials, VPN profiles, PEM files, bucket names, prefixes, account identifiers, database dumps, source logs, or private environment files.
- Rotate any credential immediately after suspected disclosure and before production deployment.
- The application is reachable only through the company VPN and a security group restricted to the approved VPN network.
- Every user has a named gateway login; shared application passwords are prohibited.
- EC2 receives AWS access only from its attached instance role. Static AWS access keys are prohibited.
- The role is limited to listing approved prefixes and reading approved objects. S3 write, delete, ACL, policy, replication, and lifecycle permissions are prohibited.
- Bucket and key values come only from the server's private configuration. Client requests cannot supply them.
- Production local-upload and preflight-upload endpoints remain disabled.
- PostgreSQL and Redis have no host port and remain inside the container network.
- Source objects are streamed, never copied to the repository, Vercel, or long-term local storage.
- The worker rejects any S3 URI outside the configured bucket-and-prefix allowlist.
- Logs and audit events must not contain raw source lines, object keys, secrets, or authentication headers.
- Merge and deploy only from a reviewed pull request with passing API and web checks.

## VPN transport

The pilot gateway is bound only to the private host and is carried inside the encrypted company VPN. If DevOps later provides a trusted internal DNS name and certificate, enable HTTPS at the gateway without changing the application data path.

## Supported version

Only the latest reviewed deployment is supported. Apply dependency and base-image updates through a tested pull request.
