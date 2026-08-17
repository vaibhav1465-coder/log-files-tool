"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";

type SourceType = "cdn" | "origin";
type UploadSession = { run_id:string; file_id:string; filename:string; expected_size:number; upload_offset:number; status:string };
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const CHUNK_SIZE = 16 * 1024 * 1024;
const MAX_FILE_SIZE = 25_000_000_000;

function formatBytes(bytes:number){if(!bytes)return"0 B";const units=["B","KB","MB","GB"];const index=Math.min(Math.floor(Math.log(bytes)/Math.log(1024)),units.length-1);return `${(bytes/1024**index).toFixed(index?1:0)} ${units[index]}`;}

async function requestJson(url:string,init?:RequestInit){const response=await fetch(url,init);if(!response.ok){let detail=`Request failed (${response.status})`;try{const body=await response.json();detail=typeof body.detail==="string"?body.detail:JSON.stringify(body.detail);}catch{}throw new Error(detail);}return response.json();}

export default function NewAnalysis(){
  const [publication,setPublication]=useState("Financial Express");
  const [sourceType,setSourceType]=useState<SourceType>("cdn");
  const [file,setFile]=useState<File|null>(null);
  const [progress,setProgress]=useState(0);
  const [phase,setPhase]=useState("Ready");
  const [error,setError]=useState<string|null>(null);
  const [busy,setBusy]=useState(false);
  const [runId,setRunId]=useState<string|null>(null);
  const [activeUpload,setActiveUpload]=useState<UploadSession|null>(null);

  async function refreshActive(){try{setActiveUpload(await requestJson(`${apiUrl}/api/v1/active-upload`) as UploadSession|null);}catch{setActiveUpload(null);}}
  useEffect(()=>{refreshActive();},[]);

  async function cancelActive(){if(!activeUpload)return;setBusy(true);setError(null);try{const response=await fetch(`${apiUrl}/api/v1/uploads/${activeUpload.run_id}`,{method:"DELETE"});if(!response.ok)throw new Error("Active upload could not be cancelled");setActiveUpload(null);setPhase("Ready");}catch(cause){setError(cause instanceof Error?cause.message:"Cancellation failed");}finally{setBusy(false);}}

  function selectFile(event:ChangeEvent<HTMLInputElement>){const selected=event.target.files?.[0]??null;setError(null);setRunId(null);setProgress(0);if(selected&&selected.size>MAX_FILE_SIZE){setFile(null);setError("The maximum supported file size is 25 GB.");event.target.value="";return;}setFile(selected);}

  async function uploadChunk(session:UploadSession,blob:Blob,offset:number){let lastError:unknown;for(let attempt=1;attempt<=3;attempt++){try{return await requestJson(`${apiUrl}/api/v1/uploads/${session.run_id}/chunk`,{method:"PUT",headers:{"Upload-Offset":String(offset),"Content-Type":"application/octet-stream"},body:blob});}catch(cause){lastError=cause;try{const current=await requestJson(`${apiUrl}/api/v1/uploads/${session.run_id}`) as UploadSession;if(current.upload_offset>offset)return current;}catch{}if(attempt<3)await new Promise(resolve=>setTimeout(resolve,attempt*1000));}}throw lastError;}

  async function submit(event:FormEvent){event.preventDefault();if(!file||busy)return;setBusy(true);setError(null);setProgress(0);try{
    setPhase("Creating upload session");
    let session=await requestJson(`${apiUrl}/api/v1/uploads`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({publication,source_type:sourceType,filename:file.name,size_bytes:file.size})}) as UploadSession;
    setRunId(session.run_id);
    while(session.upload_offset<file.size){const start=session.upload_offset;const end=Math.min(start+CHUNK_SIZE,file.size);setPhase(`Uploading ${formatBytes(start)} of ${formatBytes(file.size)}`);session=await uploadChunk(session,file.slice(start,end),start) as UploadSession;setProgress(session.upload_offset/file.size*100);}
    setPhase("Verifying checksum and sample mapping");
    await requestJson(`${apiUrl}/api/v1/uploads/${session.run_id}/complete`,{method:"POST"});
    setPhase("Queued for full analysis");setProgress(100);setActiveUpload(null);window.dispatchEvent(new CustomEvent("analysis-run-created"));
  }catch(cause){setError(cause instanceof Error?cause.message:"Upload failed");setPhase("Upload stopped");}finally{setBusy(false);}}

  return <section className="analysisPanel" id="new-analysis"><div className="sectionHeading"><div><p className="eyebrow">NEW ANALYSIS · RESUMABLE INTAKE</p><h2>Upload one evidence file</h2></div><span className="devBadge">Up to 25 GB</span></div>
    <form onSubmit={submit}>
      {activeUpload&&<div className="activeUpload"><div><strong>One upload is already active</strong><span>{activeUpload.filename} · {formatBytes(activeUpload.upload_offset)} of {formatBytes(activeUpload.expected_size)}</span></div><button type="button" onClick={cancelActive} disabled={busy}>Cancel active upload</button></div>}
      <fieldset><legend>1. Select publication</legend><select className="publicationSelect" value={publication} onChange={event=>setPublication(event.target.value)} disabled={busy}><option>Financial Express</option><option>Indian Express</option><option>Jansatta</option><option>Loksatta</option></select></fieldset>
      <fieldset><legend>2. Choose evidence source</legend><div className="sourceChoices">{(["cdn","origin"] as SourceType[]).map(source=><label className={sourceType===source?"selected":""} key={source}><input type="radio" checked={sourceType===source} onChange={()=>setSourceType(source)} disabled={busy}/><strong>{source==="cdn"?"CDN logs":"Origin logs"}</strong><span>{source==="cdn"?"Apache-style access records":"Newline-delimited JSON records"}</span></label>)}</div></fieldset>
      <fieldset><legend>3. Select one file</legend><label className="dropZone"><input type="file" accept=".zip,.log,.json,.jsonl,.txt" onChange={selectFile} disabled={busy}/><strong>{file?file.name:"Choose one log file or ZIP archive"}</strong><span>{file?`${formatBytes(file.size)} · stored directly on D:`:"One file per analysis run; maximum 25 GB"}</span></label></fieldset>
      {(busy||progress>0)&&<div className="uploadProgress"><div><span style={{width:`${progress}%`}}/></div><p><strong>{phase}</strong><span>{progress.toFixed(1)}%</span></p></div>}
      {error&&<div className="resultBanner failed"><strong>Upload not completed</strong><span>{error}</span></div>}
      {runId&&progress===100&&!error&&<div className="resultBanner passed"><strong>Analysis queued</strong><span>Run {runId.slice(0,8)} will continue if the browser is closed.</span></div>}
      <div className="formActions"><p>The same stored file is used for preflight and full analysis. It is never uploaded twice.</p><button className="primaryButton" disabled={!file||busy||!!activeUpload}>{busy?"Uploading…":"Upload and analyze"}</button></div>
    </form>
  </section>;
}
