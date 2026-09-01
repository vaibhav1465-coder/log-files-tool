"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type RemoteSource = { id: string; label: string; provider: string; timezone: string };
type Estimate = { source_id:string; day:string; start_hour_utc:number; end_hour_utc:number; file_count:number; total_bytes:number; estimated_transfer_cost_usd:number; files:Array<{filename:string;size_bytes:number;last_modified?:string}> };
type QueuedRun = { id:string; status:string; file_count:number; total_bytes:number; eta_likely_seconds?:number; estimated_transfer_cost_usd:number };
const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

function formatBytes(bytes:number){if(!bytes)return"0 B";const units=["B","KB","MB","GB"];const index=Math.min(Math.floor(Math.log(bytes)/Math.log(1024)),units.length-1);return `${(bytes/1024**index).toFixed(index?1:0)} ${units[index]}`;}
function formatDuration(seconds?:number){if(!seconds)return"Pending first measurement";if(seconds<60)return`${seconds}s`;if(seconds<3600)return`${Math.ceil(seconds/60)} min`;return`${(seconds/3600).toFixed(1)} hr`;}
async function requestJson(path:string,init?:RequestInit){const response=await fetch(`${apiUrl}${path}`,{cache:"no-store",...init});if(!response.ok){let detail=`Request failed (${response.status})`;try{const body=await response.json();detail=typeof body.detail==="string"?body.detail:JSON.stringify(body.detail);}catch{}throw new Error(detail);}return response.json();}

export default function NewAnalysis(){
  const yesterday=useMemo(()=>new Date(Date.now()-86400000).toISOString().slice(0,10),[]);
  const [sources,setSources]=useState<RemoteSource[]>([]);
  const [sourceId,setSourceId]=useState("");
  const [day,setDay]=useState(yesterday);
  const [startHour,setStartHour]=useState(0);
  const [endHour,setEndHour]=useState(1);
  const [estimate,setEstimate]=useState<Estimate|null>(null);
  const [run,setRun]=useState<QueuedRun|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);

  useEffect(()=>{void requestJson("/api/v1/remote-sources").then((items:RemoteSource[])=>{setSources(items);setSourceId(items[0]?.id??"");}).catch(cause=>setError(cause instanceof Error?cause.message:"Sources unavailable"));},[]);

  const payload={source_id:sourceId,day,start_hour_utc:startHour,end_hour_utc:endHour};
  async function checkSelection(){setBusy(true);setError(null);setEstimate(null);setRun(null);try{setEstimate(await requestJson("/api/v1/remote-runs/estimate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}));}catch(cause){setError(cause instanceof Error?cause.message:"Could not check this period");}finally{setBusy(false);}}
  async function submit(event:FormEvent){event.preventDefault();if(!estimate||busy)return;setBusy(true);setError(null);try{const queued=await requestJson("/api/v1/remote-runs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}) as QueuedRun;setRun(queued);setEstimate(null);window.dispatchEvent(new CustomEvent("analysis-run-created"));}catch(cause){setError(cause instanceof Error?cause.message:"Analysis could not start");}finally{setBusy(false);}}

  return <section className="analysisPanel" id="new-analysis">
    <div className="sectionHeading"><div><p className="eyebrow">FINANCIAL EXPRESS · PRIVATE AWS LOGS</p><h2>Start a log analysis</h2></div><span className="devBadge">VPN only</span></div>
    <form onSubmit={submit}>
      <fieldset><legend>1. Choose the log source</legend>
        <select className="publicationSelect" value={sourceId} onChange={event=>{setSourceId(event.target.value);setEstimate(null);}} disabled={busy||!sources.length}>
          {sources.map(source=><option key={source.id} value={source.id}>{source.label}</option>)}
        </select>
        {!sources.length&&!error?<p>Loading approved sources…</p>:null}
      </fieldset>
      <fieldset><legend>2. Choose date and UTC hours</legend>
        <div className="scopeChoices">
          <label><span>Date</span><input type="date" value={day} max={yesterday} onChange={event=>{setDay(event.target.value);setEstimate(null);}} disabled={busy}/></label>
          <label><span>From</span><select value={startHour} onChange={event=>{const value=Number(event.target.value);setStartHour(value);setEndHour(Math.max(value+1,endHour));setEstimate(null);}} disabled={busy}>{Array.from({length:24},(_,hour)=><option key={hour} value={hour}>{String(hour).padStart(2,"0")}:00 UTC</option>)}</select></label>
          <label><span>To</span><select value={endHour} onChange={event=>{setEndHour(Number(event.target.value));setEstimate(null);}} disabled={busy}>{Array.from({length:24-startHour},(_,index)=>startHour+index+1).map(hour=><option key={hour} value={hour}>{String(hour).padStart(2,"0")}:00 UTC</option>)}</select></label>
        </div>
        <small>UTC is used because both log sources are stored by UTC hour. IST is UTC +5:30.</small>
      </fieldset>
      {!estimate&&!run?<div className="formActions"><p>The tool checks file count and size before processing. Source buckets remain read-only.</p><button type="button" className="primaryButton" onClick={checkSelection} disabled={!sourceId||!day||busy}>{busy?"Checking…":"Check selected period"}</button></div>:null}
      {estimate?<div className="estimateCard"><strong>{estimate.file_count} files · {formatBytes(estimate.total_bytes)} · est. ${estimate.estimated_transfer_cost_usd.toFixed(4)}</strong><span>Estimated transfer at $0.09/GB · Approved for one sequential analysis job</span><p>No files are copied permanently. Gzip content is streamed from AWS and temporary processing data is cleaned automatically.</p><button className="primaryButton" disabled={busy}>{busy?"Starting…":"Start analysis"}</button></div>:null}
      {run?<div className="resultBanner passed"><strong>Analysis queued</strong><span>Run {run.id.slice(0,8)} · {sources.find(item=>item.id===sourceId)?.label??sourceId} · {day} · {String(startHour).padStart(2,"0")}:00–{String(endHour).padStart(2,"0")}:00 UTC · {run.file_count} files · expected time {formatDuration(run.eta_likely_seconds)}. You may close this page.</span></div>:null}
      {error?<div className="resultBanner failed"><strong>Unable to continue safely</strong><span>{error}</span></div>:null}
    </form>
  </section>;
}
