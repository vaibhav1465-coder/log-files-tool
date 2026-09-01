from datetime import datetime, timezone
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import StreamingResponse

from .auth import router as auth_router
from .config import get_settings
from .intake import MAX_FILES_PER_BATCH, SAMPLE_LINES, IntakeFailure, iter_preflight_lines
from .db import connection, initialize_database
from .exports import csv_lines
from .estimation import estimate_seconds, observed_throughput
from .models import BatchPreflightResponse, CrawlMetrics, FilePreflightResult, GscPropertyCreate, HealthResponse, InspectionRequest, RunDetail, RunMetricsResponse, RunSummary, UploadSession, UploadSessionCreate, UrlEvidencePage
from .parser import preflight
from .storage import ensure_capacity, finalize_upload, store_upload, upload_target
from .security import SecurityMiddleware
from .queue import enqueue_job
from .remote_api import router as remote_router
from redis import Redis

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(SecurityMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.accepted_hosts)
app.include_router(remote_router)
app.include_router(auth_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Upload-Offset", "X-API-Key", "X-Request-ID"],
)


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        service=settings.app_name,
        status="ok",
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
    )


@app.post("/api/v1/uploads", response_model=UploadSession, status_code=201)
def create_upload_session(payload: UploadSessionCreate) -> UploadSession:
    filename = Path(payload.filename).name.strip()
    if not filename:
        raise HTTPException(status_code=422, detail="filename is required")
    if payload.size_bytes > settings.max_file_bytes:
        raise HTTPException(status_code=413, detail=f"Maximum source size is {settings.max_file_bytes} bytes")
    analysis_limit = payload.analysis_limit_bytes or payload.size_bytes
    if analysis_limit > payload.size_bytes:
        raise HTTPException(status_code=422, detail="analysis_limit_bytes cannot exceed size_bytes")
    try:
        ensure_capacity(payload.size_bytes)
    except OSError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc
    run_id, file_id = uuid4(), uuid4()
    target = upload_target(run_id, file_id, filename)
    with connection() as conn:
        stale = conn.execute("SELECT r.id,f.stored_path FROM analysis_runs r JOIN source_files f ON f.run_id=r.id WHERE r.status='uploading' AND ((f.upload_offset=0 AND r.created_at < NOW()-INTERVAL '10 minutes') OR f.upload_updated_at < NOW()-INTERVAL '6 hours') FOR UPDATE").fetchall()
        for item in stale:
            conn.execute("UPDATE analysis_runs SET status='cancelled',phase='upload_expired',error_code='UPLOAD_EXPIRED',error_message='Inactive upload session expired' WHERE id=%s", (item["id"],))
            _remove_partial_upload(item["stored_path"])
        active = conn.execute("SELECT id FROM analysis_runs WHERE status='uploading' ORDER BY created_at").fetchall()
        if len(active) >= settings.max_active_uploads:
            raise HTTPException(status_code=409, detail=f"Upload capacity reached ({settings.max_active_uploads} active); retry later")
        estimate = estimate_seconds(payload.source_type, analysis_limit, observed_throughput(conn, payload.source_type))
        conn.execute("INSERT INTO analysis_runs (id,publication,source_type,status,phase,progress_percent,analysis_limit_bytes,eta_low_seconds,eta_likely_seconds,eta_high_seconds) VALUES (%s,%s,%s,'uploading','upload',0,%s,%s,%s,%s)", (run_id, payload.publication.strip(), payload.source_type, analysis_limit, estimate.low_seconds, estimate.likely_seconds, estimate.high_seconds))
        conn.execute("INSERT INTO source_files (id,run_id,original_name,stored_path,size_bytes,sha256,source_type,upload_offset,expected_size,upload_complete) VALUES (%s,%s,%s,%s,0,'',%s,0,%s,FALSE)", (file_id, run_id, filename, str(target), payload.source_type, payload.size_bytes))
    return UploadSession(run_id=str(run_id), file_id=str(file_id), filename=filename, expected_size=payload.size_bytes, upload_offset=0, status="uploading", analysis_limit_bytes=analysis_limit, eta_low_seconds=estimate.low_seconds, eta_likely_seconds=estimate.likely_seconds, eta_high_seconds=estimate.high_seconds)


@app.get("/api/v1/uploads/{run_id}", response_model=UploadSession)
def get_upload_session(run_id: str) -> UploadSession:
    with connection() as conn:
        row = conn.execute("SELECT r.id run_id,f.id file_id,f.original_name filename,f.expected_size,f.upload_offset,r.status,r.analysis_limit_bytes,r.eta_low_seconds,r.eta_likely_seconds,r.eta_high_seconds FROM analysis_runs r JOIN source_files f ON f.run_id=r.id WHERE r.id=%s", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Upload session not found")
    return UploadSession(**row)


@app.put("/api/v1/uploads/{run_id}/chunk", response_model=UploadSession)
async def upload_chunk(run_id: str, request: Request, upload_offset: int = Header(..., alias="Upload-Offset")) -> UploadSession:
    declared_length = int(request.headers.get("content-length", "0") or 0)
    if declared_length > settings.max_chunk_bytes:
        raise HTTPException(status_code=413, detail=f"Chunk limit is {settings.max_chunk_bytes} bytes")
    with connection() as conn:
        row = conn.execute("SELECT r.status,r.analysis_limit_bytes,r.eta_low_seconds,r.eta_likely_seconds,r.eta_high_seconds,f.* FROM analysis_runs r JOIN source_files f ON f.run_id=r.id WHERE r.id=%s FOR UPDATE OF f", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Upload session not found")
        if row["status"] != "uploading" or row["upload_complete"]:
            raise HTTPException(status_code=409, detail="Upload is not active")
        if upload_offset != row["upload_offset"]:
            raise HTTPException(status_code=409, detail={"expected_offset": row["upload_offset"]})
        target = Path(row["stored_path"])
        written = 0
        with target.open("ab", buffering=0) as output:
            async for chunk in request.stream():
                if written + len(chunk) > settings.max_chunk_bytes:
                    raise HTTPException(status_code=413, detail=f"Chunk limit is {settings.max_chunk_bytes} bytes")
                if row["upload_offset"] + written + len(chunk) > row["expected_size"]:
                    raise HTTPException(status_code=413, detail="Chunk exceeds declared file size")
                output.write(chunk)
                written += len(chunk)
            output.flush()
            os.fsync(output.fileno())
        next_offset = row["upload_offset"] + written
        percent = round(next_offset / row["expected_size"] * 100, 2)
        conn.execute("UPDATE source_files SET upload_offset=%s,size_bytes=%s,upload_updated_at=NOW() WHERE id=%s", (next_offset, next_offset, row["id"]))
        conn.execute("UPDATE analysis_runs SET progress_percent=%s WHERE id=%s", (percent, run_id))
    return UploadSession(run_id=run_id, file_id=str(row["id"]), filename=row["original_name"], expected_size=row["expected_size"], upload_offset=next_offset, status="uploading", analysis_limit_bytes=row["analysis_limit_bytes"], eta_low_seconds=row["eta_low_seconds"], eta_likely_seconds=row["eta_likely_seconds"], eta_high_seconds=row["eta_high_seconds"])


def _remove_partial_upload(stored_path: str) -> None:
    root = Path(settings.storage_root).resolve()
    target = Path(stored_path).resolve()
    if target != root and root in target.parents:
        target.unlink(missing_ok=True)
        try:
            target.parent.rmdir()
        except OSError:
            pass


@app.get("/api/v1/active-upload", response_model=UploadSession | None)
def get_active_upload() -> UploadSession | None:
    with connection() as conn:
        row = conn.execute("SELECT r.id run_id,f.id file_id,f.original_name filename,f.expected_size,f.upload_offset,r.status,r.analysis_limit_bytes,r.eta_low_seconds,r.eta_likely_seconds,r.eta_high_seconds FROM analysis_runs r JOIN source_files f ON f.run_id=r.id WHERE r.status='uploading' ORDER BY r.created_at LIMIT 1").fetchone()
    return UploadSession(**row) if row else None


@app.delete("/api/v1/uploads/{run_id}", status_code=204)
def cancel_upload(run_id: str) -> None:
    with connection() as conn:
        row = conn.execute("SELECT r.status,f.stored_path FROM analysis_runs r JOIN source_files f ON f.run_id=r.id WHERE r.id=%s FOR UPDATE", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Upload session not found")
        if row["status"] != "uploading":
            raise HTTPException(status_code=409, detail="Only an active upload can be cancelled")
        conn.execute("UPDATE analysis_runs SET status='cancelled',phase='upload_cancelled',error_code='USER_CANCELLED',error_message='Upload cancelled before analysis' WHERE id=%s", (run_id,))
    _remove_partial_upload(row["stored_path"])


@app.post("/api/v1/uploads/{run_id}/complete", response_model=RunSummary, status_code=202)
def complete_upload(run_id: str) -> RunSummary:
    with connection() as conn:
        row = conn.execute("SELECT r.source_type,r.status,f.* FROM analysis_runs r JOIN source_files f ON f.run_id=r.id WHERE r.id=%s FOR UPDATE OF f", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Upload session not found")
        if row["upload_complete"]:
            return get_run(run_id)
        conn.execute("UPDATE analysis_runs SET status='verifying',phase='checksum',progress_percent=NULL WHERE id=%s", (run_id,))
    try:
        stored = finalize_upload(Path(row["stored_path"]), row["expected_size"])
        with stored.path.open("rb") as stream:
            lines, _ = iter_preflight_lines(stream, row["original_name"])
            result = preflight(lines, limit=SAMPLE_LINES)
        expected_profile = "cdn_access" if row["source_type"] == "cdn" else "origin_jsonl"
        if result.evidence_state != "passed" or result.profile != expected_profile:
            with connection() as conn:
                conn.execute("UPDATE source_files SET stored_path=%s,size_bytes=%s,sha256=%s,upload_complete=TRUE WHERE id=%s", (str(stored.path), stored.size_bytes, stored.sha256, row["id"]))
                conn.execute("UPDATE analysis_runs SET status='failed',phase='preflight_failed',evidence_state='mapping_required',error_code='MAPPING_REQUIRED',error_message=%s WHERE id=%s", (f"Detected {result.profile}; acceptance {result.acceptance_rate}", run_id))
            return get_run(run_id)
        with connection() as conn:
            conn.execute("UPDATE source_files SET stored_path=%s,size_bytes=%s,sha256=%s,upload_complete=TRUE WHERE id=%s", (str(stored.path), stored.size_bytes, stored.sha256, row["id"]))
            conn.execute("UPDATE analysis_runs SET status='queued',phase='queued',progress_percent=NULL,evidence_state='passed' WHERE id=%s", (run_id,))
        enqueue_job({"run_id": run_id})
        return get_run(run_id)
    except (ValueError, IntakeFailure) as exc:
        with connection() as conn:
            conn.execute("UPDATE analysis_runs SET status='failed',phase='verification_failed',error_code=%s,error_message=%s WHERE id=%s", (type(exc).__name__, str(exc)[:1000], run_id))
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/preflight", response_model=BatchPreflightResponse)
async def run_preflight(
    source_type: str = Form(...),
    files: list[UploadFile] = File(...),
) -> BatchPreflightResponse:
    if source_type not in {"cdn", "origin"}:
        raise HTTPException(status_code=422, detail="source_type must be cdn or origin")
    if not files or len(files) > MAX_FILES_PER_BATCH:
        raise HTTPException(status_code=422, detail=f"Select between 1 and {MAX_FILES_PER_BATCH} files")

    results: list[FilePreflightResult] = []
    accepted_total = processed_total = 0
    for upload in files:
        filename = upload.filename or "unnamed"
        upload.file.seek(0, 2)
        size = upload.file.tell()
        upload.file.seek(0)
        try:
            lines, archive_entries = iter_preflight_lines(upload.file, filename)
            result = preflight(lines, limit=SAMPLE_LINES)
            expected_profile = "cdn_access" if source_type == "cdn" else "origin_jsonl"
            if result.profile != expected_profile and result.profile != "unknown":
                result.evidence_state = "mapping_required"
            accepted_total += result.accepted_lines
            processed_total += result.processed_lines
            results.append(FilePreflightResult(
                filename=filename,
                source_type=source_type,
                compressed_bytes=size,
                archive_entries=archive_entries,
                result=result,
            ))
        except IntakeFailure as exc:
            results.append(FilePreflightResult(
                filename=filename,
                source_type=source_type,
                compressed_bytes=size,
                error_code=exc.code,
                error_message=exc.message,
            ))
        finally:
            await upload.close()

    states = [item.result.evidence_state if item.result else "mapping_required" for item in results]
    quality_gate = "no_data" if not processed_total else ("passed" if all(s == "passed" for s in states) else "mapping_required")
    return BatchPreflightResponse(
        files=results,
        quality_gate=quality_gate,
        accepted_lines=accepted_total,
        processed_lines=processed_total,
    )


@app.post("/api/v1/runs", response_model=RunSummary, status_code=202)
async def create_run(
    publication: str = Form(...),
    source_type: str = Form(...),
    files: list[UploadFile] = File(...),
) -> RunSummary:
    publication = publication.strip()
    if not publication:
        raise HTTPException(status_code=422, detail="publication is required")
    if source_type not in {"cdn", "origin"}:
        raise HTTPException(status_code=422, detail="source_type must be cdn or origin")
    if not files or len(files) > MAX_FILES_PER_BATCH:
        raise HTTPException(status_code=422, detail=f"Select between 1 and {MAX_FILES_PER_BATCH} files")

    run_id = uuid4()
    with connection() as conn:
        conn.execute(
            "INSERT INTO analysis_runs (id,publication,source_type,status,phase) VALUES (%s,%s,%s,'queued','upload_complete')",
            (run_id, publication, source_type),
        )
    for upload in files:
        file_id = uuid4()
        try:
            stored = await store_upload(run_id, file_id, upload)
            with connection() as conn:
                conn.execute(
                    "INSERT INTO source_files (id,run_id,original_name,stored_path,size_bytes,sha256,source_type) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (file_id, run_id, upload.filename or "unnamed", str(stored.path), stored.size_bytes, stored.sha256, source_type),
                )
        finally:
            await upload.close()
    enqueue_job({"run_id": str(run_id)})
    return get_run(str(run_id))


@app.get("/api/v1/runs", response_model=list[RunSummary])
def list_runs(publication: str | None = None, limit: int = 50) -> list[RunSummary]:
    limit = min(max(limit, 1), 100)
    with connection() as conn:
        if publication:
            rows = conn.execute("SELECT * FROM analysis_runs WHERE publication=%s ORDER BY created_at DESC LIMIT %s", (publication, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM analysis_runs ORDER BY created_at DESC LIMIT %s", (limit,)).fetchall()
    return [RunSummary(**row) for row in rows]


@app.get("/api/v1/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str) -> RunDetail:
    with connection() as conn:
        run = conn.execute("SELECT * FROM analysis_runs WHERE id=%s", (run_id,)).fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        files = conn.execute("SELECT id,original_name,size_bytes,sha256,source_type,created_at FROM source_files WHERE run_id=%s ORDER BY created_at", (run_id,)).fetchall()
        statuses = conn.execute("SELECT status_code,request_count,unique_url_count,response_bytes FROM status_aggregates WHERE run_id=%s ORDER BY status_code", (run_id,)).fetchall()
    return RunDetail(**run, source_files=files, status_aggregates=statuses)


@app.get("/api/v1/runs/{run_id}/metrics", response_model=RunMetricsResponse)
def get_run_metrics(run_id: str) -> RunMetricsResponse:
    with connection() as conn:
        run = conn.execute("SELECT * FROM analysis_runs WHERE id=%s", (run_id,)).fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        crawl = conn.execute(
            """
            WITH bot_urls AS (
              SELECT normalized_url, SUM(googlebot_request_count) hits,
                     MIN(googlebot_first_seen) first_seen, MAX(googlebot_last_seen) last_seen
              FROM url_aggregates WHERE run_id=%s AND googlebot_request_count > 0 GROUP BY normalized_url
            ), intervals AS (
              SELECT EXTRACT(EPOCH FROM (last_seen-first_seen))/NULLIF(hits-1,0) duration
              FROM bot_urls WHERE hits > 1 AND first_seen IS NOT NULL AND last_seen IS NOT NULL
            )
            SELECT COALESCE(SUM(hits),0)::bigint googlebot_hits,
                   COUNT(*)::bigint unique_googlebot_urls,
                   COUNT(*) FILTER (WHERE hits > 1)::bigint recrawled_urls,
                   COALESCE(SUM(GREATEST(hits-1,0)),0)::bigint repeat_hit_count,
                   (SELECT SUM(EXTRACT(EPOCH FROM (last_seen-first_seen)))/NULLIF(SUM(hits-1),0) FROM bot_urls WHERE hits > 1) average_revisit_seconds,
                   (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY duration) FROM intervals) median_revisit_seconds,
                   (SELECT percentile_cont(0.75) WITHIN GROUP (ORDER BY duration) FROM intervals) p75_revisit_seconds,
                   (SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY duration) FROM intervals) p95_revisit_seconds
            FROM bot_urls
            """,
            (run_id,),
        ).fetchone()
        statuses = conn.execute("SELECT status_code,request_count,unique_url_count,response_bytes FROM status_aggregates WHERE run_id=%s ORDER BY status_code", (run_id,)).fetchall()
    acceptance = run["accepted_lines"] / run["processed_lines"] if run["processed_lines"] else None
    return RunMetricsResponse(
        run_id=str(run["id"]), evidence_state=run["evidence_state"], processed_lines=run["processed_lines"],
        accepted_lines=run["accepted_lines"], rejected_lines=run["rejected_lines"], acceptance_rate=acceptance,
        crawl=CrawlMetrics(**crawl), statuses=statuses,
    )


@app.get("/api/v1/runs/{run_id}/urls", response_model=UrlEvidencePage)
def get_url_evidence(run_id: str, status: int | None = None, googlebot_only: bool = False, search: str | None = None, page: int = 1, page_size: int = 50) -> UrlEvidencePage:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    clauses = ["run_id=%s"]
    params: list[object] = [run_id]
    if status is not None:
        if status < 100 or status > 599:
            raise HTTPException(status_code=422, detail="status must be between 100 and 599")
        clauses.append("status_code=%s"); params.append(status)
    if googlebot_only:
        clauses.append("googlebot_request_count > 0")
    if search:
        clauses.append("normalized_url ILIKE %s"); params.append(f"%{search[:200]}%")
    where = " AND ".join(clauses)
    with connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) count FROM url_aggregates WHERE {where}", params).fetchone()["count"]
        items = conn.execute(
            f"SELECT normalized_url,status_code,request_count,first_seen,last_seen,response_bytes,googlebot_request_count,googlebot_first_seen,googlebot_last_seen FROM url_aggregates WHERE {where} ORDER BY request_count DESC, normalized_url LIMIT %s OFFSET %s",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
    return UrlEvidencePage(run_id=run_id, total=total, page=page, page_size=page_size, items=items)


@app.get("/api/v1/runs/{run_id}/exports/urls.csv")
def export_urls(run_id: str, status: int | None = None, googlebot_only: bool = False) -> StreamingResponse:
    if status is not None and (status < 100 or status > 599):
        raise HTTPException(status_code=422, detail="status must be between 100 and 599")
    with connection() as conn:
        run = conn.execute("SELECT id,publication,source_type,evidence_state FROM analysis_runs WHERE id=%s", (run_id,)).fetchone()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    def rows():
        clauses = ["run_id=%s"]
        params: list[object] = [run_id]
        if status is not None:
            clauses.append("status_code=%s"); params.append(status)
        if googlebot_only:
            clauses.append("googlebot_request_count > 0")
        with connection() as conn:
            with conn.cursor(name=f"export_{str(run_id).replace('-', '')[:16]}") as cursor:
                cursor.execute(f"SELECT normalized_url,status_code,request_count,googlebot_request_count,first_seen,last_seen,response_bytes FROM url_aggregates WHERE {' AND '.join(clauses)} ORDER BY status_code,normalized_url", params)
                for record in cursor:
                    yield {"run_id": str(run["id"]), "publication": run["publication"], "source_type": run["source_type"], "url": record["normalized_url"], "status": record["status_code"], "request_count": record["request_count"], "googlebot_request_count": record["googlebot_request_count"], "first_seen": record["first_seen"], "last_seen": record["last_seen"], "response_bytes": record["response_bytes"], "evidence_quality": run["evidence_state"]}

    filename = f"run-{str(run_id)[:8]}-{status or 'all'}-urls.csv"
    return StreamingResponse(csv_lines(rows()), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def audit(actor: str, action: str, target_type: str, target_id: str | None, result: str, detail: dict | None = None) -> None:
    with connection() as conn:
        conn.execute("INSERT INTO audit_events (id,actor,action,target_type,target_id,result,detail) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)", (uuid4(), actor, action, target_type, target_id, result, json.dumps(detail or {})))


@app.get("/api/v1/gsc/properties")
def list_gsc_properties() -> list[dict]:
    with connection() as conn:
        return conn.execute("SELECT id,publication,site_url,timezone,enabled,last_sync_at,last_sync_status,last_error,quota_daily_limit,quota_used_today,quota_date FROM gsc_properties ORDER BY publication").fetchall()


@app.post("/api/v1/gsc/properties", status_code=201)
def create_gsc_property(payload: GscPropertyCreate, actor: str = "development-admin") -> dict:
    site_url = payload.site_url.strip()
    if not (site_url.startswith("sc-domain:") or site_url.startswith("https://") or site_url.startswith("http://")):
        raise HTTPException(status_code=422, detail="Use a Search Console domain or URL-prefix property")
    property_id = uuid4()
    try:
        with connection() as conn:
            row = conn.execute("INSERT INTO gsc_properties (id,publication,site_url,timezone) VALUES (%s,%s,%s,%s) RETURNING *", (property_id, payload.publication.strip(), site_url, payload.timezone)).fetchone()
        audit(actor, "gsc.property.create", "gsc_property", str(property_id), "success", {"publication": payload.publication, "site_url": site_url})
        return row
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Publication or property already exists") from exc


@app.post("/api/v1/gsc/properties/{property_id}/sync", status_code=202)
def queue_gsc_sync(property_id: str, actor: str = "development-admin") -> dict:
    with connection() as conn:
        exists = conn.execute("SELECT 1 FROM gsc_properties WHERE id=%s AND enabled", (property_id,)).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="GSC property not found")
    enqueue_job({"type": "gsc_sync", "property_id": property_id})
    audit(actor, "gsc.sync.queue", "gsc_property", property_id, "success")
    return {"property_id": property_id, "status": "queued"}


@app.post("/api/v1/gsc/properties/{property_id}/inspections", status_code=202)
def queue_inspections(property_id: str, payload: InspectionRequest, actor: str = "development-user") -> dict:
    with connection() as conn:
        prop = conn.execute("SELECT * FROM gsc_properties WHERE id=%s AND enabled", (property_id,)).fetchone()
    if not prop:
        raise HTTPException(status_code=404, detail="GSC property not found")
    expected_domain = prop["site_url"].removeprefix("sc-domain:").lower() if prop["site_url"].startswith("sc-domain:") else (urlparse(prop["site_url"]).hostname or "").lower()
    queued: list[str] = []
    rejected: list[dict] = []
    for value in dict.fromkeys(payload.urls):
        parsed = urlparse(value.strip())
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or not host or not (host == expected_domain or host.endswith(f".{expected_domain}")):
            rejected.append({"url": value, "reason": "HOST_NOT_OWNED"})
            continue
        inspection_id = uuid4()
        with connection() as conn:
            conn.execute("INSERT INTO gsc_inspections (id,property_id,inspection_url) VALUES (%s,%s,%s)", (inspection_id, property_id, value.strip()))
        enqueue_job({"type": "gsc_inspection", "inspection_id": str(inspection_id)})
        queued.append(str(inspection_id))
    audit(actor, "gsc.inspection.queue", "gsc_property", property_id, "success", {"queued": len(queued), "rejected": len(rejected)})
    return {"queued": queued, "rejected": rejected}


@app.get("/api/v1/gsc/properties/{property_id}/dashboard")
def gsc_dashboard(property_id: str) -> dict:
    with connection() as conn:
        prop = conn.execute("SELECT * FROM gsc_properties WHERE id=%s", (property_id,)).fetchone()
        if not prop:
            raise HTTPException(status_code=404, detail="GSC property not found")
        totals = conn.execute("SELECT COALESCE(SUM(clicks),0) clicks,COALESCE(SUM(impressions),0) impressions,CASE WHEN SUM(impressions)>0 THEN SUM(clicks)/SUM(impressions) ELSE NULL END ctr,COUNT(DISTINCT page) performing_urls,MIN(data_date) start_date,MAX(data_date) end_date FROM gsc_daily_performance WHERE property_id=%s", (property_id,)).fetchone()
        sitemaps = conn.execute("SELECT path,last_submitted,last_downloaded,is_pending,warnings,errors,contents,extracted_at FROM gsc_sitemaps WHERE property_id=%s ORDER BY path", (property_id,)).fetchall()
        inspections = conn.execute("SELECT id,inspection_url,status,verdict,coverage_state,indexing_state,page_fetch_state,last_crawl_time,completed_at,error_message FROM gsc_inspections WHERE property_id=%s ORDER BY requested_at DESC LIMIT 100", (property_id,)).fetchall()
        cohorts = conn.execute("SELECT COUNT(*) FILTER (WHERE status='completed' AND verdict='PASS') inspected_indexed,COUNT(*) FILTER (WHERE status='completed' AND verdict IS DISTINCT FROM 'PASS') inspected_not_indexed,COUNT(*) FILTER (WHERE status IN ('scheduled','running','quota_deferred')) pending FROM gsc_inspections WHERE property_id=%s", (property_id,)).fetchone()
    return {"property": prop, "performance": totals, "sitemaps": sitemaps, "inspections": inspections, "inspection_cohorts": cohorts, "caveat": "Search Analytics performance rows and sampled URL Inspection results are not a complete index inventory."}


@app.get("/api/v1/admin/audit")
def list_audit_events(limit: int = 100) -> list[dict]:
    with connection() as conn:
        return conn.execute("SELECT actor,action,target_type,target_id,result,detail,created_at FROM audit_events ORDER BY created_at DESC LIMIT %s", (min(max(limit,1),500),)).fetchall()


@app.get("/api/v1/admin/capacity")
def capacity_status() -> dict:
    disk = shutil.disk_usage(settings.storage_root)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        pending = redis.xpending("express:jobs", "express-workers")
    except Exception:
        pending = {"pending": 0}
    with connection() as conn:
        runs = conn.execute("SELECT status,COUNT(*) count FROM analysis_runs GROUP BY status ORDER BY status").fetchall()
        sources = conn.execute("SELECT COALESCE(SUM(size_bytes),0) bytes,COUNT(*) files FROM source_files WHERE upload_complete").fetchone()
    return {
        "storage": {"total_bytes": disk.total, "used_bytes": disk.used, "free_bytes": disk.free, "reserve_bytes": settings.storage_reserve_bytes, "source_bytes": sources["bytes"], "source_files": sources["files"]},
        "jobs": {"stream_length": redis.xlen("express:jobs"), "pending": pending.get("pending", 0)},
        "runs": runs,
        "limits": {"max_file_bytes": settings.max_file_bytes, "max_active_uploads": settings.max_active_uploads, "max_chunk_bytes": settings.max_chunk_bytes},
    }
