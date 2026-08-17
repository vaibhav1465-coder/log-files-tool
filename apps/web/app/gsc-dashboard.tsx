"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type Property = { id:string; publication:string; site_url:string; last_sync_at?:string|null; last_sync_status:string; last_error?:string|null; quota_daily_limit:number; quota_used_today:number };
type Dashboard = { property:Property; performance:{clicks:number;impressions:number;ctr:number|null;performing_urls:number;start_date?:string|null;end_date?:string|null}; sitemaps:{path:string;warnings:number;errors:number;last_downloaded?:string|null}[]; inspections:{id:string;inspection_url:string;status:string;verdict?:string|null;coverage_state?:string|null;last_crawl_time?:string|null;error_message?:string|null}[]; inspection_cohorts:{inspected_indexed:number;inspected_not_indexed:number;pending:number}; caveat:string };

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function GscDashboard() {
  const [properties,setProperties]=useState<Property[]>([]);
  const [selected,setSelected]=useState<string>("");
  const [dashboard,setDashboard]=useState<Dashboard|null>(null);
  const [publication,setPublication]=useState("Financial Express");
  const [siteUrl,setSiteUrl]=useState("sc-domain:financialexpress.com");
  const [inspectionUrls,setInspectionUrls]=useState("");
  const [message,setMessage]=useState<string|null>(null);

  const loadProperties=useCallback(async()=>{const response=await fetch(`${apiUrl}/api/v1/gsc/properties`,{cache:"no-store"});if(response.ok){const data=await response.json() as Property[];setProperties(data);if(!selected&&data[0])setSelected(data[0].id);}},[selected]);
  const loadDashboard=useCallback(async(id:string)=>{if(!id)return;const response=await fetch(`${apiUrl}/api/v1/gsc/properties/${id}/dashboard`,{cache:"no-store"});if(response.ok)setDashboard(await response.json() as Dashboard);},[]);
  useEffect(()=>{loadProperties().catch(()=>setMessage("Connector service is unavailable"));},[loadProperties]);
  useEffect(()=>{loadDashboard(selected).catch(()=>setMessage("Dashboard is unavailable"));},[loadDashboard,selected]);

  async function createProperty(event:FormEvent){event.preventDefault();const response=await fetch(`${apiUrl}/api/v1/gsc/properties`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({publication,site_url:siteUrl})});setMessage(response.ok?"Property saved. Add the service account in Search Console, then sync.":"Property could not be saved");await loadProperties();}
  async function sync(){const response=await fetch(`${apiUrl}/api/v1/gsc/properties/${selected}/sync`,{method:"POST"});setMessage(response.ok?"GSC sync queued":"Sync could not be queued");}
  async function inspect(){const urls=inspectionUrls.split(/[\n,]/).map(value=>value.trim()).filter(Boolean);const response=await fetch(`${apiUrl}/api/v1/gsc/properties/${selected}/inspections`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({urls})});if(response.ok){const body=await response.json();setMessage(`${body.queued.length} URLs queued; ${body.rejected.length} rejected`);setInspectionUrls("");await loadDashboard(selected);}else setMessage("URLs could not be queued");}

  return <section className="gscPanel" id="indexing">
    <div className="sectionHeading"><div><p className="eyebrow">INDEXING & CRAWLING</p><h2>Google Search Console evidence</h2></div>{dashboard&&<span className={`connectorState ${dashboard.property.last_sync_status}`}>{dashboard.property.last_sync_status.replaceAll("_"," ")}</span>}</div>
    {message&&<div className="resultBanner passed"><strong>Connector update</strong><span>{message}</span></div>}
    {!properties.length?<form className="connectorSetup" onSubmit={createProperty}><h3>Configure the first property</h3><label>Publication<select value={publication} onChange={event=>setPublication(event.target.value)}><option>Financial Express</option><option>Indian Express</option><option>Jansatta</option><option>Loksatta</option></select></label><label>GSC property<input value={siteUrl} onChange={event=>setSiteUrl(event.target.value)} placeholder="sc-domain:example.com"/></label><button>Save connector</button><p>Credentials are read from the protected server environment and are never stored in the browser.</p></form>:
    <><div className="connectorBar"><select value={selected} onChange={event=>setSelected(event.target.value)}>{properties.map(property=><option value={property.id} key={property.id}>{property.publication} · {property.site_url}</option>)}</select><button onClick={sync}>Sync last 28 days</button><span>{dashboard?.property.last_sync_at?`Last sync ${new Date(dashboard.property.last_sync_at).toLocaleString()}`:"Connector pending"}</span></div>
    {dashboard&&<><div className="gscMetrics"><article><span>Clicks</span><strong>{dashboard.performance.clicks.toLocaleString()}</strong></article><article><span>Impressions</span><strong>{dashboard.performance.impressions.toLocaleString()}</strong></article><article><span>Performing URLs</span><strong>{dashboard.performance.performing_urls.toLocaleString()}</strong></article><article><span>Inspected/indexed</span><strong>{dashboard.inspection_cohorts.inspected_indexed.toLocaleString()}</strong></article><article><span>Inspected/not indexed</span><strong>{dashboard.inspection_cohorts.inspected_not_indexed.toLocaleString()}</strong></article><article><span>Quota remaining</span><strong>{Math.max(0,dashboard.property.quota_daily_limit-dashboard.property.quota_used_today).toLocaleString()}</strong></article></div><div className="evidenceCaveat">{dashboard.caveat}</div>
    <div className="gscColumns"><div><h3>URL inspection queue</h3><textarea value={inspectionUrls} onChange={event=>setInspectionUrls(event.target.value)} placeholder="Paste one approved URL per line"/><button onClick={inspect} disabled={!inspectionUrls.trim()}>Queue inspections</button><div className="inspectionList">{dashboard.inspections.slice(0,10).map(item=><div key={item.id}><span title={item.inspection_url}>{item.inspection_url}</span><strong>{item.status}</strong><small>{item.coverage_state||item.error_message||"Awaiting evidence"}</small></div>)}{!dashboard.inspections.length&&<p>No URLs inspected yet.</p>}</div></div><div><h3>Sitemap evidence</h3><div className="sitemapList">{dashboard.sitemaps.map(item=><div key={item.path}><span title={item.path}>{item.path}</span><strong>{item.errors||0} errors</strong><small>{item.warnings||0} warnings</small></div>)}{!dashboard.sitemaps.length&&<p>No sitemap evidence synced.</p>}</div></div></div></>}</>}
  </section>;
}
