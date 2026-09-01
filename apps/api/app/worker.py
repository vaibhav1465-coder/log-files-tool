import json
import shutil
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from redis import Redis

from .config import get_settings
from .db import connection, initialize_database
from .intake import iter_analysis_lines
from .processing import aggregate_lines
from .gsc import GscClient
from .queue import GROUP, STREAM
from .source_stream import open_source_stream


def update_run(run_id: str, **values) -> None:
    assignments = ", ".join(f"{key}=%({key})s" for key in values)
    with connection() as conn:
        conn.execute(f"UPDATE analysis_runs SET {assignments} WHERE id=%(run_id)s", {**values, "run_id": run_id})


def process_run(run_id: str, heartbeat=lambda: None) -> None:
    settings = get_settings()
    with connection() as conn:
        run = conn.execute("SELECT status,analysis_limit_bytes FROM analysis_runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
        if not run or run["status"] in {"completed", "cancelled"}:
            return
        files = conn.execute("SELECT * FROM source_files WHERE run_id=%s AND upload_complete ORDER BY created_at", (run_id,)).fetchall()
        if not files:
            raise RuntimeError("Run has no completed source file")
        # SQLite is the staging store. Reset before retry for idempotency.
        conn.execute("DELETE FROM status_aggregates WHERE run_id=%s", (run_id,))
        conn.execute("DELETE FROM url_aggregates WHERE run_id=%s", (run_id,))
        conn.execute("UPDATE analysis_runs SET status='processing',phase='streaming_parse',progress_percent=NULL,processed_lines=0,accepted_lines=0,rejected_lines=0,started_at=COALESCE(started_at,NOW()),completed_at=NULL,error_code=NULL,error_message=NULL WHERE id=%s", (run_id,))
    total_processed = total_accepted = total_rejected = 0
    all_status: dict[int, dict] = {}
    try:
        scratch_root = Path(settings.storage_root)

        def guard_resources() -> None:
            free = shutil.disk_usage(scratch_root).free
            if free < settings.storage_reserve_bytes:
                raise OSError(f"Processing stopped safely: {free} bytes free is below the {settings.storage_reserve_bytes} byte reserve")
            heartbeat()

        guard_resources()

        def store_url_batch(rows: list[dict]) -> None:
            with connection() as conn:
                with conn.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO url_aggregates (run_id,normalized_url,status_code,request_count,first_seen,last_seen,response_bytes,googlebot_request_count,googlebot_first_seen,googlebot_last_seen) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (run_id,normalized_url,status_code) DO UPDATE SET request_count=url_aggregates.request_count+EXCLUDED.request_count, first_seen=LEAST(url_aggregates.first_seen,EXCLUDED.first_seen), last_seen=GREATEST(url_aggregates.last_seen,EXCLUDED.last_seen), response_bytes=COALESCE(url_aggregates.response_bytes,0)+COALESCE(EXCLUDED.response_bytes,0), googlebot_request_count=url_aggregates.googlebot_request_count+EXCLUDED.googlebot_request_count, googlebot_first_seen=LEAST(url_aggregates.googlebot_first_seen,EXCLUDED.googlebot_first_seen), googlebot_last_seen=GREATEST(url_aggregates.googlebot_last_seen,EXCLUDED.googlebot_last_seen)",
                        [(run_id, row["normalized_url"], row["status_code"], row["request_count"], row["first_seen"], row["last_seen"], row["response_bytes"], row["googlebot_request_count"], row["googlebot_first_seen"], row["googlebot_last_seen"]) for row in rows],
                    )

        for source in files:
            with open_source_stream(settings, source["stored_path"]) as stream:
                byte_limit = None if source["stored_path"].startswith("s3://") else run["analysis_limit_bytes"]
                lines, _ = iter_analysis_lines(stream, source["original_name"], max_bytes=byte_limit, source_size_bytes=source["size_bytes"])
                def progress(count: int) -> None:
                    update_run(run_id, processed_lines=total_processed + count)
                summary = aggregate_lines(
                    lines, progress, store_url_batch, scratch_root,
                    resource_guard=guard_resources,
                    progress_interval=settings.processing_progress_interval_lines,
                    sink_batch_rows=settings.processing_sqlite_batch_rows,
                    sqlite_cache_mib=settings.processing_sqlite_cache_mib,
                )
            total_processed += summary.processed_lines
            total_accepted += summary.accepted_lines
            total_rejected += summary.rejected_lines
        update_run(run_id, status="aggregating", phase="finalizing", processed_lines=total_processed, accepted_lines=total_accepted, rejected_lines=total_rejected)
        with connection() as conn:
            conn.execute("DELETE FROM status_aggregates WHERE run_id=%s", (run_id,))
            conn.execute("INSERT INTO status_aggregates (run_id,status_code,request_count,unique_url_count,response_bytes) SELECT run_id,status_code,SUM(request_count),COUNT(*),SUM(response_bytes) FROM url_aggregates WHERE run_id=%s GROUP BY run_id,status_code", (run_id,))
            conn.execute("UPDATE analysis_runs SET status='completed', phase='completed', progress_percent=100, evidence_state=CASE WHEN processed_lines > 0 AND accepted_lines::numeric/processed_lines >= 0.95 THEN 'passed' ELSE 'partial' END, completed_at=NOW() WHERE id=%s", (run_id,))
    except Exception as exc:
        update_run(run_id, status="failed", phase="failed", error_code=type(exc).__name__, error_message=str(exc)[:1000])


def sync_gsc_property(property_id: str) -> None:
    with connection() as conn:
        prop = conn.execute("SELECT * FROM gsc_properties WHERE id=%s", (property_id,)).fetchone()
        conn.execute("UPDATE gsc_properties SET last_sync_status='running',last_error=NULL WHERE id=%s", (property_id,))
    try:
        client = GscClient()
        end_date = date.today() - timedelta(days=2)
        start_date = end_date - timedelta(days=27)
        performance = client.search_performance(prop["site_url"], start_date, end_date)
        sitemaps = client.list_sitemaps(prop["site_url"])
        with connection() as conn:
            for row in performance:
                keys = row.get("keys", [])
                if len(keys) < 2:
                    continue
                conn.execute("INSERT INTO gsc_daily_performance (property_id,data_date,page,clicks,impressions,ctr,position) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (property_id,data_date,page) DO UPDATE SET clicks=EXCLUDED.clicks,impressions=EXCLUDED.impressions,ctr=EXCLUDED.ctr,position=EXCLUDED.position,extracted_at=NOW()", (property_id, keys[0], keys[1], row.get("clicks",0), row.get("impressions",0), row.get("ctr",0), row.get("position",0)))
            for sitemap in sitemaps:
                conn.execute("INSERT INTO gsc_sitemaps (property_id,path,last_submitted,last_downloaded,is_pending,warnings,errors,contents) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT (property_id,path) DO UPDATE SET last_submitted=EXCLUDED.last_submitted,last_downloaded=EXCLUDED.last_downloaded,is_pending=EXCLUDED.is_pending,warnings=EXCLUDED.warnings,errors=EXCLUDED.errors,contents=EXCLUDED.contents,extracted_at=NOW()", (property_id, sitemap.get("path"), sitemap.get("lastSubmitted"), sitemap.get("lastDownloaded"), sitemap.get("isPending"), sitemap.get("warnings"), sitemap.get("errors"), json.dumps(sitemap.get("contents",[]))))
            conn.execute("UPDATE gsc_properties SET last_sync_at=NOW(),last_sync_status='healthy',last_error=NULL,updated_at=NOW() WHERE id=%s", (property_id,))
    except Exception as exc:
        with connection() as conn:
            conn.execute("UPDATE gsc_properties SET last_sync_status='failed',last_error=%s,updated_at=NOW() WHERE id=%s", (str(exc)[:1000], property_id))


def inspect_gsc_url(inspection_id: str) -> None:
    with connection() as conn:
        item = conn.execute("SELECT i.*,p.site_url FROM gsc_inspections i JOIN gsc_properties p ON p.id=i.property_id WHERE i.id=%s", (inspection_id,)).fetchone()
        if not item:
            return
        prop = conn.execute("SELECT * FROM gsc_properties WHERE id=%s FOR UPDATE", (item["property_id"],)).fetchone()
        used = 0 if prop["quota_date"] != date.today() else prop["quota_used_today"]
        if used >= prop["quota_daily_limit"]:
            conn.execute("UPDATE gsc_inspections SET status='quota_deferred' WHERE id=%s", (inspection_id,))
            return
        conn.execute("UPDATE gsc_properties SET quota_used_today=%s,quota_date=CURRENT_DATE WHERE id=%s", (used + 1, item["property_id"]))
        conn.execute("UPDATE gsc_inspections SET status='running' WHERE id=%s", (inspection_id,))
    try:
        result = GscClient().inspect_url(item["site_url"], item["inspection_url"])
        index = result.get("indexStatusResult", {})
        with connection() as conn:
            conn.execute("UPDATE gsc_inspections SET status='completed',verdict=%s,coverage_state=%s,indexing_state=%s,page_fetch_state=%s,robots_txt_state=%s,last_crawl_time=%s,google_canonical=%s,user_canonical=%s,raw_result=%s::jsonb,completed_at=NOW() WHERE id=%s", (index.get("verdict"), index.get("coverageState"), index.get("indexingState"), index.get("pageFetchState"), index.get("robotsTxtState"), index.get("lastCrawlTime"), index.get("googleCanonical"), index.get("userCanonical"), json.dumps(result), inspection_id))
    except Exception as exc:
        with connection() as conn:
            conn.execute("UPDATE gsc_inspections SET status='failed',error_message=%s WHERE id=%s", (str(exc)[:1000], inspection_id))


def main() -> None:
    initialize_database()
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    consumer = f"worker-{uuid4()}"
    try:
        redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise
    while True:
        claimed = redis.xautoclaim(STREAM, GROUP, consumer, min_idle_time=600_000, start_id="0-0", count=1)
        messages = claimed[1] if claimed and len(claimed) > 1 else []
        if not messages:
            batch = redis.xreadgroup(GROUP, consumer, {STREAM: ">"}, count=1, block=30_000)
            messages = batch[0][1] if batch else []
        if not messages:
            continue
        message_id, fields = messages[0]
        job = json.loads(fields["payload"])
        # Lock by logical target so duplicate messages cannot run concurrently.
        target = job.get("run_id") or job.get("property_id") or job.get("inspection_id") or message_id
        lock_key = f"express:job-lock:{job.get('type', 'analysis')}:{target}"
        if not redis.set(lock_key, consumer, nx=True, ex=900):
            continue
        try:
            heartbeat = lambda: redis.expire(lock_key, 900)
            if job.get("type") == "gsc_sync":
                sync_gsc_property(job["property_id"])
            elif job.get("type") == "gsc_inspection":
                inspect_gsc_url(job["inspection_id"])
            else:
                process_run(job["run_id"], heartbeat)
            redis.xack(STREAM, GROUP, message_id)
        finally:
            if redis.get(lock_key) == consumer:
                redis.delete(lock_key)


if __name__ == "__main__":
    main()
