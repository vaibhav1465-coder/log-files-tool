"use client";

import { useCallback, useEffect, useState } from "react";

type Run = {
  id: string;
  publication: string;
  source_type: string;
  status: string;
  phase: string;
  progress_percent: number | null;
  evidence_state: string;
  processed_lines: number;
  accepted_lines: number;
  rejected_lines: number;
  created_at: string;
  completed_at?: string | null;
  error_message?: string | null;
  remote_source_id?:string|null; created_by_email?:string|null; selected_day?:string|null; start_hour_utc?:number|null; end_hour_utc?:number|null; selected_bytes?:number|null; estimated_transfer_cost_usd?:number|null;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const activeStates = new Set(["uploading", "queued", "verifying", "processing", "aggregating", "cancelling"]);

export default function AnalysisLibrary() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await fetch(`${apiUrl}/api/v1/runs?limit=25`, { cache: "no-store" });
      if (!response.ok) throw new Error("Library is unavailable");
      setRuns(await response.json() as Run[]);
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Library is unavailable");
    }
  }, []);

  useEffect(() => {
    load();
    const refresh = () => load();
    window.addEventListener("analysis-run-created", refresh);
    const timer = window.setInterval(load, 5000);
    return () => { window.removeEventListener("analysis-run-created", refresh); window.clearInterval(timer); };
  }, [load]);

  async function cancel(run:Run){
    if(!window.confirm(`Cancel analysis ${run.id.slice(0,8)}? Completed evidence will remain in history.`))return;
    try{const response=await fetch(`${apiUrl}/api/v1/runs/${run.id}/cancel`,{method:"POST",credentials:"include"});const body=await response.json().catch(()=>({detail:"Cancellation failed"}));if(!response.ok)throw new Error(body.detail??"Cancellation failed");await load();}catch(reason){setError(reason instanceof Error?reason.message:"Cancellation failed");}
  }

  const formatBytes=(value?:number|null)=>value===null||value===undefined?"Size unavailable":`${(value/1024**3).toFixed(2)} GB`;
  const scope=(run:Run)=>run.selected_day&&run.start_hour_utc!==null&&run.start_hour_utc!==undefined&&run.end_hour_utc!==null&&run.end_hour_utc!==undefined?`${run.selected_day} · ${String(run.start_hour_utc).padStart(2,"0")}:00–${String(run.end_hour_utc).padStart(2,"0")}:00 UTC`:"Legacy run";

  return (
    <section className="libraryPanel" id="library">
      <div className="sectionHeading">
        <div><p className="eyebrow">ANALYSIS LIBRARY</p><h2>Immutable run history</h2></div>
        <button className="refreshButton" onClick={load}>Refresh</button>
      </div>
      {error && <div className="resultBanner failed"><strong>Library unavailable</strong><span>{error}</span></div>}
      {!error && runs.length === 0 && <div className="emptyLibrary"><strong>No analysis runs yet</strong><span>A run appears here immediately after it is queued.</span></div>}
      {runs.length > 0 && (
        <div className="runTable" role="table" aria-label="Analysis runs">
          <div className="runRow runHeader" role="row"><span>Run</span><span>Publication</span><span>Evidence</span><span>Progress</span><span>Rows</span><span>Created</span><span>Action</span></div>
          {runs.map((run) => (
            <div className="runRow" role="row" key={run.id}>
              <span><strong>{run.id.slice(0, 8)}</strong><small>{run.remote_source_id??run.source_type.toUpperCase()} · {scope(run)}</small></span>
              <span>{run.publication}</span>
              <span><i className={`runState ${run.status}`} />{run.status}</span>
              <span>{run.progress_percent === null ? run.phase.replaceAll("_", " ") : `${run.progress_percent}%`}</span>
              <span>{run.processed_lines ? run.processed_lines.toLocaleString() : "Not calculated"}</span>
              <span>{new Date(run.created_at).toLocaleString()}<small>{formatBytes(run.selected_bytes)} · est. ${(run.estimated_transfer_cost_usd??0).toFixed(4)} USD</small></span>
              <span>{activeStates.has(run.status)?<button className="viewRun" disabled={run.status==="cancelling"} onClick={()=>cancel(run)}>{run.status==="cancelling"?"Cancelling…":"Cancel"}</button>:<button className="viewRun" disabled={run.status !== "completed"} onClick={() => window.dispatchEvent(new CustomEvent("analysis-run-selected", { detail: run.id }))}>View results</button>}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
