from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


EvidenceState = Literal["passed", "mapping_required", "partial", "no_data"]


class HealthResponse(BaseModel):
    service: str
    status: Literal["ok"]
    environment: str
    timestamp: datetime


class RejectionSummary(BaseModel):
    reason: str
    count: int


class PreflightResult(BaseModel):
    profile: Literal["cdn_access", "origin_jsonl", "unknown"]
    processed_lines: int
    accepted_lines: int
    rejected_lines: int
    ambiguous_lines: int = 0
    acceptance_rate: float | None = Field(default=None, description="Null when no lines were processed")
    timestamp_parse_rate: float | None = None
    valid_status_rate: float | None = None
    evidence_state: EvidenceState
    rejection_reasons: list[RejectionSummary]
    observed_statuses: dict[int, int]
    observed_time_start: datetime | None = None
    observed_time_end: datetime | None = None


class FilePreflightResult(BaseModel):
    filename: str
    source_type: Literal["cdn", "origin"]
    compressed_bytes: int
    archive_entries: int = 1
    result: PreflightResult | None = None
    error_code: str | None = None
    error_message: str | None = None


class BatchPreflightResponse(BaseModel):
    files: list[FilePreflightResult]
    quality_gate: EvidenceState
    accepted_lines: int
    processed_lines: int


class RunSummary(BaseModel):
    id: UUID
    publication: str
    source_type: Literal["cdn", "origin"]
    status: str
    analysis_limit_bytes: int | None = None
    eta_low_seconds: int | None = None
    eta_likely_seconds: int | None = None
    eta_high_seconds: int | None = None
    phase: str
    progress_percent: float | None
    evidence_state: EvidenceState
    processed_lines: int
    accepted_lines: int
    rejected_lines: int
    created_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class RunDetail(RunSummary):
    source_files: list[dict]
    status_aggregates: list[dict]


class CrawlMetrics(BaseModel):
    googlebot_hits: int
    unique_googlebot_urls: int
    recrawled_urls: int
    repeat_hit_count: int
    average_revisit_seconds: float | None
    median_revisit_seconds: float | None
    p75_revisit_seconds: float | None
    p95_revisit_seconds: float | None
    evidence_label: str = "User-agent identified; not IP verified"


class RunMetricsResponse(BaseModel):
    run_id: str
    evidence_state: EvidenceState
    processed_lines: int
    accepted_lines: int
    rejected_lines: int
    acceptance_rate: float | None
    crawl: CrawlMetrics
    statuses: list[dict]


class UrlEvidencePage(BaseModel):
    run_id: str
    total: int
    page: int
    page_size: int
    items: list[dict]


class GscPropertyCreate(BaseModel):
    publication: str
    site_url: str
    timezone: str = "Asia/Kolkata"


class InspectionRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=1000)


class UploadSessionCreate(BaseModel):
    publication: str
    source_type: Literal["cdn", "origin"]
    filename: str
    size_bytes: int = Field(gt=0)
    analysis_limit_bytes: int | None = Field(default=None, gt=0)


class UploadSession(BaseModel):
    run_id: UUID
    file_id: UUID
    filename: str
    expected_size: int
    upload_offset: int
    status: str
    analysis_limit_bytes: int | None = None
    eta_low_seconds: int | None = None
    eta_likely_seconds: int | None = None
    eta_high_seconds: int | None = None
