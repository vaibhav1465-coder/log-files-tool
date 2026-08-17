# Security policy

## Reporting

Do not open a public issue for a suspected vulnerability or exposed log data.
Report it privately to the Indian Express engineering/security owner assigned
to this deployment. Include the affected URL, request ID, time, and impact;
never attach production logs or credentials.

## Deployment requirements

- Keep the GitHub repository private.
- Never commit `.env`, `deploy/secrets`, database dumps, source logs, or GSC keys.
- Protect the Vercel deployment with Vercel Authentication and allow only
  approved team members.
- The browser must upload large files directly to the secured backend/object
  store. Never proxy log bodies through a Vercel Function.
- Expose only HTTPS. PostgreSQL and Redis must remain private.
- Rotate credentials immediately after suspected disclosure.
- Keep daily backups and test restoration quarterly.

## Supported versions

Only the latest deployed commit is supported. Apply dependency and base-image
updates through a tested pull request before production rollout.
