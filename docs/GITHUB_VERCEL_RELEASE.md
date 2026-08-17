# Private GitHub and Vercel release

## Architecture

Vercel hosts the Next.js interface. It does not process or store the log files.
The browser sends resumable chunks directly to the secured production API, and
workers process files on company-controlled storage. PostgreSQL and Redis stay
on the private backend network.

Required addresses:

- UI: the protected Vercel deployment URL
- API: an HTTPS backend URL such as `https://logs-api.example.com`

Set `NEXT_PUBLIC_API_URL` in Vercel to the HTTPS API address. Add the Vercel
deployment URL to backend `ALLOWED_ORIGINS` and the API hostname to
`TRUSTED_HOSTS`. Never place a database password, Redis password, API secret,
or service-account key in a `NEXT_PUBLIC_*` variable.

## GitHub

1. Create a **private** repository.
2. Push only the tracked source. The repository exclusions prevent raw logs,
   ZIPs, `.env` files, database data, backups, secrets, and the PRD from being
   committed.
3. Require pull requests and the `quality` workflow before merging to `main`.
4. Enable secret scanning, push protection, Dependabot alerts, and two-factor
   authentication for every collaborator.

## Vercel

1. Import the private GitHub repository and set Root Directory to `apps/web`.
2. Set `NEXT_PUBLIC_API_URL` to the secured backend URL for Production and
   Preview.
3. Enable Vercel Authentication under Deployment Protection and add only the
   approved team members. On a free Hobby account, share the protected preview
   deployment—not the unprotected production domain.
4. Deploy, sign in as an approved member, and test a small controlled file.
5. Confirm an unauthorized browser cannot view the interface or call the API.

Vercel Functions have a 4.5 MB request-body limit. Large upload traffic must
never be rewritten or proxied through a Vercel API route.
