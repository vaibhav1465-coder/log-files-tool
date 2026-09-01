from __future__ import annotations

import hashlib
from datetime import date
from pathlib import PurePosixPath
from uuid import uuid4

import boto3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .config import get_settings
from .db import connection
from .estimation import estimate_seconds, observed_throughput
from .intake import SAMPLE_LINES, iter_preflight_lines
from .parser import preflight
from .queue import enqueue_job
from .remote_sources import RemoteSourceError, discover_objects, get_source, source_catalog


router = APIRouter(prefix="/api/v1", tags=["private-sources"])


class RemoteSelection(BaseModel):
    source_id: str
    day: date
    start_hour_utc: int = Field(ge=0, le=23)
    end_hour_utc: int = Field(ge=1, le=24)


class RemoteEstimate(BaseModel):
    source_id: str
    day: date
    start_hour_utc: int
    end_hour_utc: int
    file_count: int
    total_bytes: int
    files: list[dict]


def _objects(payload: RemoteSelection):
    settings = get_settings()
    source = get_source(settings, payload.source_id)
    return source, discover_objects(
        boto3.client("s3"),
        source,
        payload.day,
        payload.start_hour_utc,
        payload.end_hour_utc,
        max_objects=settings.remote_max_objects,
        max_total_bytes=settings.remote_max_total_bytes,
        max_scanned_keys=settings.remote_max_scanned_keys,
    )


@router.get("/remote-sources")
def list_remote_sources() -> list[dict[str, str]]:
    return source_catalog(get_settings())


@router.post("/remote-runs/estimate", response_model=RemoteEstimate)
def estimate_remote_run(payload: RemoteSelection) -> RemoteEstimate:
    try:
        _, objects = _objects(payload)
    except RemoteSourceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RemoteEstimate(
        **payload.model_dump(),
        file_count=len(objects),
        total_bytes=sum(item.size_bytes for item in objects),
        files=[item.public_metadata() for item in objects[:100]],
    )


@router.post("/remote-runs", status_code=202)
def create_remote_run(payload: RemoteSelection) -> dict:
    settings = get_settings()
    try:
        source, objects = _objects(payload)
    except RemoteSourceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    s3 = boto3.client("s3")
    first = objects[0]
    response = s3.get_object(Bucket=first.bucket, Key=first.key)
    body = response["Body"]
    try:
        lines, _ = iter_preflight_lines(body, PurePosixPath(first.key).name)
        sample = preflight(lines, limit=SAMPLE_LINES)
    finally:
        body.close()
    if sample.evidence_state != "passed" or sample.profile != "cdn_access":
        raise HTTPException(status_code=422, detail="Selected source did not pass the CDN log quality gate.")

    run_id = uuid4()
    total_bytes = sum(item.size_bytes for item in objects)
    with connection() as conn:
        active = conn.execute(
            "SELECT COUNT(*) count FROM analysis_runs WHERE status IN ('queued','processing','aggregating')"
        ).fetchone()["count"]
        if active >= settings.remote_max_active_runs:
            raise HTTPException(status_code=409, detail="The analysis server is busy. Retry after the active run finishes.")
        estimate = estimate_seconds("cdn", total_bytes, observed_throughput(conn, "cdn"))
        conn.execute(
            "INSERT INTO analysis_runs (id,publication,source_type,status,phase,progress_percent,evidence_state,analysis_limit_bytes,eta_low_seconds,eta_likely_seconds,eta_high_seconds) VALUES (%s,'Financial Express','cdn','queued','queued',NULL,'passed',%s,%s,%s,%s)",
            (run_id, total_bytes, estimate.low_seconds, estimate.likely_seconds, estimate.high_seconds),
        )
        for item in objects:
            uri_hash = hashlib.sha256(item.uri.encode()).hexdigest()
            conn.execute(
                "INSERT INTO source_files (id,run_id,original_name,stored_path,size_bytes,sha256,source_type,upload_offset,expected_size,upload_complete) VALUES (%s,%s,%s,%s,%s,%s,'cdn',%s,%s,TRUE)",
                (uuid4(), run_id, PurePosixPath(item.key).name, item.uri, item.size_bytes, uri_hash, item.size_bytes, item.size_bytes),
            )
        conn.execute(
            "INSERT INTO audit_events (id,actor,action,target_type,target_id,result,detail) VALUES (%s,'authenticated-team-user','remote_analysis_created','analysis_run',%s,'accepted',%s::jsonb)",
            (uuid4(), str(run_id), __import__("json").dumps({
                "source_id": source.id,
                "day": payload.day.isoformat(),
                "start_hour_utc": payload.start_hour_utc,
                "end_hour_utc": payload.end_hour_utc,
                "file_count": len(objects),
                "total_bytes": total_bytes,
            })),
        )
    enqueue_job({"run_id": str(run_id)})
    return {
        "id": str(run_id),
        "status": "queued",
        "file_count": len(objects),
        "total_bytes": total_bytes,
        "eta_low_seconds": estimate.low_seconds,
        "eta_likely_seconds": estimate.likely_seconds,
        "eta_high_seconds": estimate.high_seconds,
    }
