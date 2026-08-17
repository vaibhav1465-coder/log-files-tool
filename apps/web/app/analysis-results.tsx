"use client";

import { useCallback, useEffect, useState } from "react";

type StatusMetric = { status_code: number; request_count: number; unique_url_count: number; response_bytes: number | null };
type Metrics = {
  run_id: string; evidence_state: string; processed_lines: number; accepted_lines: number; rejected_lines: number; acceptance_rate: number | null;
  crawl: { googlebot_hits: number; unique_googlebot_urls: number; recrawled_urls: number; repeat_hit_count: number; average_revisit_seconds: number | null; median_revisit_seconds: number | null; p75_revisit_seconds: number | null; p95_revisit_seconds: number | null; evidence_label: string };
  statuses: StatusMetric[];
};
type UrlItem = { normalized_url: string; status_code: number; request_count: number; first_seen: string; last_seen: string; response_bytes: number | null; googlebot_request_count: number };
type UrlPage = { total: number; page: number; page_size: number; items: UrlItem[] };

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function duration(seconds: number | null) {
  if (seconds === null) return "Not calculated";
  if (seconds >= 86400) return `${(seconds / 86400).toFixed(1)} days`;
  if (seconds >= 3600) return `${(seconds / 3600).toFixed(1)} hours`;
  return `${Math.round(seconds / 60)} min`;
}

export default function AnalysisResults() {
  const [runId, setRunId] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [urls, setUrls] = useState<UrlPage | null>(null);
  const [status, setStatus] = useState<string>("");
  const [googlebotOnly, setGooglebotOnly] = useState(false);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (selected: string, selectedStatus = status, botOnly = googlebotOnly, query = search, requestedPage = page) => {
    try {
      const params = new URLSearchParams({ page_size: "50", page: String(requestedPage) });
      if (selectedStatus) params.set("status", selectedStatus);
      if (botOnly) params.set("googlebot_only", "true");
      if (query) params.set("search", query);
      const [metricResponse, urlResponse] = await Promise.all([
        fetch(`${apiUrl}/api/v1/runs/${selected}/metrics`, { cache: "no-store" }),
        fetch(`${apiUrl}/api/v1/runs/${selected}/urls?${params}`, { cache: "no-store" }),
      ]);
      if (!metricResponse.ok || !urlResponse.ok) throw new Error("Run evidence could not be loaded");
      setMetrics(await metricResponse.json() as Metrics);
      setUrls(await urlResponse.json() as UrlPage);
      setPage(requestedPage);
      setError(null);
      document.getElementById("results")?.scrollIntoView({ behavior: "smooth" });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Run evidence could not be loaded");
    }
  }, [googlebotOnly, page, search, status]);

  useEffect(() => {
    const select = (event: Event) => {
      const selected = (event as CustomEvent<string>).detail;
      setRunId(selected); setStatus(""); setGooglebotOnly(false); setSearch(""); setPage(1); load(selected, "", false, "", 1);
    };
    window.addEventListener("analysis-run-selected", select);
    return () => window.removeEventListener("analysis-run-selected", select);
  }, [load]);

  if (!runId) return <section className="resultsPanel" id="results"><div className="emptyLibrary"><strong>Select a completed run</strong><span>Use View results in the Analysis Library to open its evidence.</span></div></section>;
  if (error) return <section className="resultsPanel" id="results"><div className="resultBanner failed"><strong>Evidence unavailable</strong><span>{error}</span></div></section>;
  if (!metrics || !urls) return <section className="resultsPanel" id="results"><div className="emptyLibrary"><strong>Loading evidence…</strong></div></section>;

  const cards = [
    ["Googlebot hits", metrics.crawl.googlebot_hits.toLocaleString()],
    ["Unique crawled URLs", metrics.crawl.unique_googlebot_urls.toLocaleString()],
    ["Recrawled URLs", metrics.crawl.recrawled_urls.toLocaleString()],
    ["Repeat hits", metrics.crawl.repeat_hit_count.toLocaleString()],
    ["Median revisit", duration(metrics.crawl.median_revisit_seconds)],
    ["P95 revisit", duration(metrics.crawl.p95_revisit_seconds)],
  ];

  const exportParams = new URLSearchParams();
  if (status) exportParams.set("status", status);
  if (googlebotOnly) exportParams.set("googlebot_only", "true");

  return (
    <section className="resultsPanel" id="results">
      <div className="sectionHeading"><div><p className="eyebrow">RUN {runId.slice(0, 8)} · EVIDENCE RESULTS</p><h2>Crawl and response evidence</h2></div><span className="devBadge">{metrics.evidence_state}</span></div>
      <div className="qualityStrip"><span><strong>{metrics.processed_lines.toLocaleString()}</strong> processed</span><span><strong>{metrics.accepted_lines.toLocaleString()}</strong> accepted</span><span><strong>{metrics.rejected_lines.toLocaleString()}</strong> rejected</span><span><strong>{metrics.acceptance_rate === null ? "Not calculated" : `${(metrics.acceptance_rate * 100).toFixed(2)}%`}</strong> acceptance</span></div>
      <div className="metricCards">{cards.map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong></article>)}</div>
      <p className="methodNote">Bot identity: {metrics.crawl.evidence_label}. Average revisit duration is weighted across observed repeat intervals; median and percentiles describe each recrawled URL&apos;s mean interval. URLs without repeat evidence are excluded.</p>

      <div className="statusHeading"><h3>HTTP response evidence</h3><span>{metrics.statuses.length} observed statuses</span></div>
      <div className="statusCards">{metrics.statuses.map((item) => <button className={status === String(item.status_code) ? "selected" : ""} key={item.status_code} onClick={() => { const next = status === String(item.status_code) ? "" : String(item.status_code); setStatus(next); load(runId, next, googlebotOnly, search, 1); }}><strong>{item.status_code}</strong><span>{item.request_count.toLocaleString()} requests</span><small>{item.unique_url_count.toLocaleString()} URLs</small></button>)}</div>

      <div className="evidenceToolbar">
        <input aria-label="Search URL evidence" placeholder="Search URLs" value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") load(runId); }} />
        <label><input type="checkbox" checked={googlebotOnly} onChange={(event) => { setGooglebotOnly(event.target.checked); load(runId, status, event.target.checked, search, 1); }} /> Googlebot only</label>
        <button onClick={() => load(runId, status, googlebotOnly, search, 1)}>Apply filters</button>
        <a href={`${apiUrl}/api/v1/runs/${runId}/exports/urls.csv?${exportParams}`} download>Download CSV</a>
      </div>
      <div className="urlTable">
        <div className="urlRow urlHeader"><span>URL</span><span>Status</span><span>Requests</span><span>Googlebot</span><span>First seen</span><span>Last seen</span></div>
        {urls.items.map((item) => <div className="urlRow" key={`${item.normalized_url}-${item.status_code}`}><span title={item.normalized_url}>{item.normalized_url}</span><span>{item.status_code}</span><span>{item.request_count.toLocaleString()}</span><span>{item.googlebot_request_count.toLocaleString()}</span><span>{new Date(item.first_seen).toLocaleString()}</span><span>{new Date(item.last_seen).toLocaleString()}</span></div>)}
        {!urls.items.length && <div className="noRows">No URL evidence matches these filters.</div>}
      </div>
      <div className="pagination"><p>Showing {urls.items.length.toLocaleString()} of {urls.total.toLocaleString()} URL/status records.</p><div><button disabled={page <= 1} onClick={() => load(runId, status, googlebotOnly, search, page - 1)}>Previous</button><span>Page {page}</span><button disabled={page * urls.page_size >= urls.total} onClick={() => load(runId, status, googlebotOnly, search, page + 1)}>Next</button></div></div>
    </section>
  );
}
