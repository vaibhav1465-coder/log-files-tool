import NewAnalysis from "./new-analysis";
import AnalysisLibrary from "./analysis-library";
import AnalysisResults from "./analysis-results";
import AdminOperations from "./admin-operations";
import BackendGate from "./backend-gate";

const modules = [
  { title: "New analysis", detail: "Choose Financial Express CDN logs by UTC date and hour", state: "Active" },
  { title: "Analysis library", detail: "Track queued, running and completed evidence", state: "Active" },
  { title: "Usage & capacity", detail: "Monitor runs, disk reserve and processing health", state: "Active" },
];

export default function Home() {
  return <main>
    <aside><div className="brandMark">EI</div><div><strong>Express Intelligence</strong><span>Financial Express pilot</span></div>
      <nav aria-label="Primary navigation"><a className="active" href="#overview">Overview</a><a href="#new-analysis">New analysis</a><a href="#library">Analysis library</a><a href="#admin">Usage & capacity</a></nav>
    </aside>
    <section className="content" id="overview">
      <header><div><p className="eyebrow">FINANCIAL EXPRESS · LOG OPERATIONS</p><h1>Private log intelligence, without AWS complexity.</h1><p className="lead">Choose a source and time period. The service reads approved logs and produces evidence-backed results.</p></div><div className="status"><i /> VPN protected</div></header>
      <div className="notice"><strong>Read-only AWS access</strong><span>The tool cannot upload, overwrite or delete source logs. One analysis runs at a time.</span></div>
      <div className="grid" id="analysis">{modules.map(module=><article key={module.title}><span className="pill">{module.state}</span><h2>{module.title}</h2><p>{module.detail}</p><a className="cardAction" href={module.title==="New analysis"?"#new-analysis":module.title==="Analysis library"?"#library":"#admin"}>Open</a></article>)}</div>
      <section className="evidence"><div><p className="eyebrow">PILOT SAFEGUARDS</p><h2>Designed for the provided server</h2></div><dl><div><dt>Sources</dt><dd>Financial Express only</dd></div><div><dt>Access</dt><dd>VPN and named login</dd></div><div><dt>Processing</dt><dd>One streaming job</dd></div><div><dt>Storage</dt><dd>20 GB disk reserve</dd></div></dl></section>
      <BackendGate><NewAnalysis/><AnalysisLibrary/><AnalysisResults/><AdminOperations/></BackendGate>
    </section>
  </main>;
}
