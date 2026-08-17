"use client";

import { useEffect, useState } from "react";

type AuditEvent = { actor:string; action:string; target_type:string; target_id?:string|null; result:string; detail:Record<string,unknown>; created_at:string };
type Capacity = { storage:{total_bytes:number;used_bytes:number;free_bytes:number;reserve_bytes:number;source_bytes:number;source_files:number}; jobs:{stream_length:number;pending:number}; limits:{max_file_bytes:number;max_active_uploads:number}; runs:Array<{status:string;count:number}> };
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const size=(value:number)=>new Intl.NumberFormat("en-IN",{maximumFractionDigits:1}).format(value/1_000_000_000)+" GB";

export default function AdminOperations(){
  const [events,setEvents]=useState<AuditEvent[]>([]);
  const [capacity,setCapacity]=useState<Capacity|null>(null);
  const [available,setAvailable]=useState(true);
  async function load(){
    const [auditResponse,capacityResponse]=await Promise.all([fetch(`${apiUrl}/api/v1/admin/audit?limit=50`,{cache:"no-store"}),fetch(`${apiUrl}/api/v1/admin/capacity`,{cache:"no-store"})]);
    if(!auditResponse.ok||!capacityResponse.ok){setAvailable(false);return;}
    setEvents(await auditResponse.json() as AuditEvent[]);setCapacity(await capacityResponse.json() as Capacity);setAvailable(true);
  }
  useEffect(()=>{load().catch(()=>setAvailable(false));},[]);
  const completed=capacity?.runs.find(run=>run.status==="completed")?.count??0;
  return <section className="adminPanel" id="admin">
    <div className="sectionHeading"><div><p className="eyebrow">OPERATIONS</p><h2>Capacity and audit</h2></div><button className="refreshButton" onClick={load}>Refresh status</button></div>
    <div className="adminCallout"><strong>Protected team deployment</strong><span>HTTPS access, named team credentials, rate limits, durable jobs and daily database backups are required in production.</span></div>
    {capacity&&<div className="capacityCards">
      <article><span>Source storage</span><strong>{size(capacity.storage.source_bytes)}</strong><small>{capacity.storage.source_files} retained files</small></article>
      <article><span>Disk available</span><strong>{size(capacity.storage.free_bytes)}</strong><small>{size(capacity.storage.reserve_bytes)} protected reserve</small></article>
      <article><span>Job queue</span><strong>{capacity.jobs.pending}</strong><small>{capacity.jobs.stream_length} durable records</small></article>
      <article><span>Completed runs</span><strong>{completed}</strong><small>Saved in the analysis library</small></article>
    </div>}
    {!available?<div className="resultBanner failed"><strong>Operations service unavailable</strong><span>Ask an administrator to check the application services.</span></div>:events.length?<div className="auditTable"><div className="auditRow auditHeader"><span>Time</span><span>Actor</span><span>Action</span><span>Target</span><span>Result</span></div>{events.map((event,index)=><div className="auditRow" key={`${event.created_at}-${index}`}><span>{new Date(event.created_at).toLocaleString()}</span><span>{event.actor}</span><span>{event.action}</span><span>{event.target_type}{event.target_id?` · ${event.target_id.slice(0,8)}`:""}</span><span>{event.result}</span></div>)}</div>:<div className="emptyLibrary"><strong>No operational events yet</strong><span>Upload, connector and administrative activity will appear here.</span></div>}
  </section>;
}
