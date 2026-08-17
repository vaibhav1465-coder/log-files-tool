from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from .config import get_settings


SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


class GscConfigurationError(RuntimeError):
    pass


class GscClient:
    def __init__(self) -> None:
        credential_path = get_settings().google_service_account_file
        if not credential_path or not Path(credential_path).is_file():
            raise GscConfigurationError("GSC service-account credentials are not configured")
        self.credentials = service_account.Credentials.from_service_account_file(credential_path, scopes=[SCOPE])

    def token(self) -> str:
        if not self.credentials.valid:
            self.credentials.refresh(Request())
        return self.credentials.token

    def request(self, method: str, url: str, **kwargs) -> dict:
        headers = {"Authorization": f"Bearer {self.token()}"}
        with httpx.Client(timeout=60) as client:
            response = client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}

    def list_sites(self) -> list[dict]:
        return self.request("GET", "https://www.googleapis.com/webmasters/v3/sites").get("siteEntry", [])

    def search_performance(self, site_url: str, start_date: date, end_date: date) -> list[dict]:
        encoded = quote(site_url, safe="")
        rows: list[dict] = []
        start_row = 0
        while True:
            payload = {"startDate": start_date.isoformat(), "endDate": end_date.isoformat(), "dimensions": ["date", "page"], "type": "web", "aggregationType": "auto", "rowLimit": 25000, "startRow": start_row}
            batch = self.request("POST", f"https://www.googleapis.com/webmasters/v3/sites/{encoded}/searchAnalytics/query", json=payload).get("rows", [])
            rows.extend(batch)
            if len(batch) < 25000:
                break
            start_row += len(batch)
        return rows

    def list_sitemaps(self, site_url: str) -> list[dict]:
        encoded = quote(site_url, safe="")
        return self.request("GET", f"https://www.googleapis.com/webmasters/v3/sites/{encoded}/sitemaps").get("sitemap", [])

    def inspect_url(self, site_url: str, inspection_url: str) -> dict:
        return self.request("POST", "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect", json={"inspectionUrl": inspection_url, "siteUrl": site_url, "languageCode": "en-US"}).get("inspectionResult", {})
