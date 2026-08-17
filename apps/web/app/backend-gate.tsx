"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";

type GateState = "checking" | "connected" | "setup";

const configuredApiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export default function BackendGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<GateState>("checking");
  const [detail, setDetail] = useState("Checking analysis service…");

  const checkBackend = useCallback(async () => {
    if (!configuredApiUrl) {
      setDetail("No shared analysis server is connected to this Vercel deployment.");
      setState("setup");
      return;
    }

    setState("checking");
    setDetail("Checking analysis service…");
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 6000);
    try {
      const response = await fetch(`${configuredApiUrl}/api/v1/health`, {
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`Health check returned ${response.status}`);
      setState("connected");
    } catch {
      setDetail("The configured analysis server is currently unreachable. Start it, then retry.");
      setState("setup");
    } finally {
      window.clearTimeout(timeout);
    }
  }, []);

  useEffect(() => {
    void checkBackend();
  }, [checkBackend]);

  if (state === "connected") return <>{children}</>;

  if (state === "checking") {
    return <section className="launcherState" aria-live="polite"><span className="loader" />{detail}</section>;
  }

  return (
    <section className="setupPanel" id="setup" aria-labelledby="setup-title">
      <div className="setupIntro">
        <p className="eyebrow">TEAM SETUP · PRIVATE PROCESSING</p>
        <h2 id="setup-title">Run the analysis engine with Docker</h2>
        <p>{detail}</p>
        <div className="privacyNote">
          <strong>Your source logs stay on the Docker host.</strong>
          <span>Vercel hosts this launcher only. It does not receive, store, or analyze log files.</span>
        </div>
      </div>

      <div className="requirementGrid">
        <article><span>01</span><h3>Docker</h3><p>Install Docker Desktop on Windows/macOS, or Docker Engine with Compose on Linux.</p></article>
        <article><span>02</span><h3>Storage</h3><p>Use 100 GB+ for normal work. For files up to 500 GB, keep at least 600 GB free; 1 TB NVMe is recommended.</p></article>
        <article><span>03</span><h3>Memory</h3><p>Use at least 16 GB RAM and assign 8 GB or more to Docker for dependable large-file processing.</p></article>
      </div>

      <div className="setupSteps">
        <div>
          <p className="eyebrow">START IN POWERSHELL</p>
          <ol>
            <li>Start Docker Desktop and wait until its engine is ready.</li>
            <li>Run these commands in PowerShell.</li>
            <li>Open the local address shown below.</li>
          </ol>
        </div>
        <div className="commandBlock" aria-label="Docker setup commands">
          <code>git clone https://github.com/vaibhav1465-coder/log-files-tool.git</code>
          <code>Set-Location "log-files-tool"</code>
          <code>docker compose up -d --build</code>
          <a href="http://localhost:3001">Open http://localhost:3001</a>
        </div>
      </div>

      <div className="setupActions">
        <a className="secondaryAction" href="https://github.com/vaibhav1465-coder/log-files-tool" target="_blank" rel="noreferrer">View source and setup guide</a>
        {configuredApiUrl ? <button type="button" onClick={() => void checkBackend()}>Retry shared server</button> : null}
      </div>
      <p className="setupFootnote">Each local installation has its own database and analysis history. Closing the browser is safe; use <code>docker compose stop</code> to preserve services and <code>docker compose up -d</code> to resume.</p>
    </section>
  );
}
