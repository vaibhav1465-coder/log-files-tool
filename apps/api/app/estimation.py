from dataclasses import dataclass


DEFAULT_BYTES_PER_SECOND = {"cdn": 5 * 1024 * 1024, "origin": 3 * 1024 * 1024}


@dataclass(frozen=True)
class AnalysisEstimate:
    low_seconds: int
    likely_seconds: int
    high_seconds: int


def estimate_seconds(source_type: str, analysis_bytes: int, observed_bytes_per_second: float | None = None) -> AnalysisEstimate:
    throughput = observed_bytes_per_second or DEFAULT_BYTES_PER_SECOND[source_type]
    throughput = max(1.0, throughput)
    likely = max(60, round(analysis_bytes / throughput))
    return AnalysisEstimate(max(30, round(likely * 0.7)), likely, max(likely, round(likely * 1.8)))


def observed_throughput(conn, source_type: str) -> float | None:
    row = conn.execute(
        """SELECT SUM(LEAST(f.size_bytes,COALESCE(r.analysis_limit_bytes,f.size_bytes)))::float /
                  NULLIF(SUM(EXTRACT(EPOCH FROM (r.completed_at-r.started_at))),0) value
           FROM analysis_runs r JOIN source_files f ON f.run_id=r.id
           WHERE r.source_type=%s AND r.status='completed' AND r.started_at IS NOT NULL
             AND r.completed_at>r.started_at AND r.created_at>NOW()-INTERVAL '90 days'""",
        (source_type,),
    ).fetchone()
    value = row["value"] if row else None
    return float(value) if value and value > 0 else None