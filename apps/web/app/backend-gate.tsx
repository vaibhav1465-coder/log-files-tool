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
        <article><span>01</span><h3>Docker</h3><p>Install Docker Desktop on Windows. Docker includes the Compose command used by this product.</p><a href="https://www.docker.com/products/docker-desktop/" target="_blank" rel="noreferrer">Download Docker Desktop</a></article>
        <article><span>02</span><h3>Storage</h3><p>Use 100 GB+ for normal work. For files up to 500 GB, keep at least 600 GB free; 1 TB NVMe is recommended.</p></article>
        <article><span>03</span><h3>Git and memory</h3><p>Install Git for the first download. Use at least 16 GB RAM and assign 8 GB or more to Docker.</p><a href="https://git-scm.com/download/win" target="_blank" rel="noreferrer">Download Git for Windows</a></article>
      </div>

      <div className="readinessBox">
        <div><strong>Before you begin</strong><span>Docker Desktop must show “Engine running”.</span></div>
        <div><strong>Quick readiness check</strong><code>docker info</code><span>If this fails, open Docker Desktop and wait before continuing.</span></div>
        <div><strong>Local data location</strong><code>D:\\Express Intelligence OS</code><span>Uploads, database files, results and exports remain on the local D: drive.</span></div>
      </div>

      <div className="setupSteps">
        <div>
          <p className="eyebrow">FIRST-TIME SETUP</p>
          <ol>
            <li>Install Docker Desktop and Git using the links above.</li>
            <li>Start Docker Desktop and wait for the engine.</li>
            <li>Open PowerShell and run each command once.</li>
          </ol>
        </div>
        <div className="commandBlock" aria-label="Docker setup commands">
          <code>Set-Location "D:\\"</code>
          <code>git clone https://github.com/vaibhav1465-coder/log-files-tool.git</code>
          <code>Set-Location "D:\\log-files-tool"</code>
          <code>docker compose up -d --build</code>
          <a href="http://localhost:3001">Open http://localhost:3001</a>
        </div>
      </div>

      <div className="dailyOperations">
        <p className="eyebrow">EVERYDAY COMMANDS</p>
        <div className="operationGrid">
          <article><h3>Start or resume</h3><p>Open Docker Desktop, then run:</p><code>Set-Location "D:\\log-files-tool"</code><code>docker compose up -d</code></article>
          <article><h3>Check status</h3><p>Confirm all services are running:</p><code>docker compose ps</code><code>docker compose logs --tail 50</code></article>
          <article><h3>Stop safely</h3><p>Finish or pause work before shutdown:</p><code>docker compose stop</code><small>Never use <b>docker compose down -v</b>; it deletes stored database volumes.</small></article>
        </div>
      </div>

      <div className="alternatives">
        <p className="eyebrow">OTHER WAYS TO RUN</p>
        <ul>
          <li><strong>Shared team server:</strong> best for centrally shared history and very large daily files. It needs an India-region server, HTTPS, access controls and large storage.</li>
          <li><strong>Docker Engine on Linux:</strong> suitable for an always-on server and uses the same Compose stack.</li>
          <li><strong>Podman:</strong> may run Compose-compatible containers, but this product is not yet acceptance-tested on Podman.</li>
          <li><strong>Native Windows desktop edition:</strong> planned as a future alternative. It is not available today because the engine requires PostgreSQL, Redis and background workers.</li>
          <li><strong>Vercel only:</strong> cannot analyze or store large logs. Vercel hosts this guide and interface; processing happens on Docker or the shared server.</li>
        </ul>
      </div>

      <div className="setupActions">
        <a className="secondaryAction" href="https://github.com/vaibhav1465-coder/log-files-tool" target="_blank" rel="noreferrer">View source and setup guide</a>
        {configuredApiUrl ? <button type="button" onClick={() => void checkBackend()}>Retry shared server</button> : null}
      </div>
      <p className="setupFootnote">Each local installation has its own database and analysis history. Closing the browser does not delete a run. Keep Docker running while an analysis is active; stopping the laptop interrupts processing, and archive parsing may restart from the beginning when resumed.</p>
    </section>
  );
}
