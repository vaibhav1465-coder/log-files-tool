"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";

type GateState = "checking" | "connected" | "offline";
const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export default function BackendGate({children}:{children:ReactNode}){
  const [state,setState]=useState<GateState>("checking");
  const check=useCallback(async()=>{setState("checking");const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),6000);try{const response=await fetch(`${apiUrl}/api/v1/health`,{cache:"no-store",signal:controller.signal});setState(response.ok?"connected":"offline");}catch{setState("offline");}finally{clearTimeout(timeout);}},[]);
  useEffect(()=>{void check();},[check]);
  if(state==="connected")return <>{children}</>;
  if(state==="checking")return <section className="launcherState" aria-live="polite"><span className="loader"/>Connecting to the private analysis server…</section>;
  return <section className="setupPanel"><div className="setupIntro"><p className="eyebrow">PRIVATE SERVER UNAVAILABLE</p><h2>Connect to the company VPN</h2><p>This application can reach the analysis service only from the approved VPN. Connect OpenVPN, then retry. Do not enter AWS credentials in this application.</p></div><div className="setupActions"><button type="button" onClick={()=>void check()}>Retry connection</button></div></section>;
}
