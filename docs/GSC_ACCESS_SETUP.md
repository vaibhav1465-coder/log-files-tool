# GSC access for Indian Express and Financial Express

The application cannot create or grant Search Console ownership by itself. Access must be provided by someone who is already a verified owner or sufficiently privileged user of these Search Console properties.

## Who to contact

Contact the person or team that currently manages Google Search Console for:

- `sc-domain:indianexpress.com`
- `sc-domain:financialexpress.com`

This is commonly the SEO lead, technical SEO team, web-platform team, or Google Cloud administrator. In Search Console, the current verified owner can be identified under **Settings -> Users and permissions**.

## Create the service account

1. Ask the Google Cloud administrator to create or select a company-controlled Google Cloud project.
2. Enable the **Google Search Console API** in that project.
3. Create a service account dedicated to Express Intelligence OS.
4. Create a JSON key only if the chosen runtime cannot use keyless workload identity.
5. Store the JSON outside this repository.
6. Copy the service-account email address, which ends in `iam.gserviceaccount.com`.

## Grant Search Console access

The verified owner should add that service-account email in Search Console for both properties. Read-only/restricted access is sufficient for this application because it only reads performance, sitemap, and URL Inspection evidence.

Use the exact property identifiers displayed by Search Console. Recommended domain-property values are:

```text
sc-domain:indianexpress.com
sc-domain:financialexpress.com
```

## Configure this application

Place the downloaded key in a protected local path and set:

```text
GOOGLE_SERVICE_ACCOUNT_FILE=/run/secrets/gsc-service-account.json
```

Mount that file read-only into both the API and worker containers. Never place the key inside the source tree or commit it to Git.

Start the application, open **Indexing & Crawling**, create one connector for each property, and run **Sync last 28 days**. Then inspect one controlled URL from each domain to verify access and quota accounting.
