import NewAnalysis from "./new-analysis";
import AnalysisLibrary from "./analysis-library";
import AnalysisResults from "./analysis-results";
import GscDashboard from "./gsc-dashboard";
import AdminOperations from "./admin-operations";

const modules = [
  { title: "New analysis", detail: "Resumable CDN and origin log intake with evidence checks", state: "Active" },
  { title: "Analysis library", detail: "Persistent runs, source evidence and reusable exports", state: "Active" },
  { title: "Indexing & crawling", detail: "GSC evidence and quota-aware URL inspection", state: "Optional" },
];

export default function Home() {
  return (
    <main>
      <aside>
        <div className="brandMark">EI</div>
        <div>
          <strong>Express Intelligence</strong>
          <span>Evidence OS</span>
        </div>
        <nav aria-label="Primary navigation">
          <a className="active" href="#overview">Overview</a>
          <a href="#new-analysis">New analysis</a>
          <a href="#library">Analysis library</a>
          <a href="#indexing">Indexing & crawling</a>
          <a href="#admin">Admin</a>
        </nav>
      </aside>
      <section className="content" id="overview">
        <header>
          <div>
            <p className="eyebrow">EXPRESS GROUP · LOG OPERATIONS</p>
            <h1>Log intelligence, grounded in evidence.</h1>
            <p className="lead">No uploaded evidence means no metric, conclusion or recommendation.</p>
          </div>
          <div className="status"><i /> Analysis services active</div>
        </header>

        <div className="notice">
          <strong>Production safeguards</strong>
          <span>Durable uploads, evidence-quality gates, protected capacity and recoverable background jobs.</span>
        </div>

        <div className="grid" id="analysis">
          {modules.map((module) => (
            <article key={module.title}>
              <span className="pill">{module.state}</span>
              <h2>{module.title}</h2>
              <p>{module.detail}</p>
              {module.title === "New analysis" ? <a className="cardAction" href="#new-analysis">Start analysis</a> : <a className="cardAction" href={module.title === "Analysis library"?"#library":"#indexing"}>Open module</a>}
            </article>
          ))}
        </div>

        <section className="evidence">
          <div>
            <p className="eyebrow">DETECTED INPUTS</p>
            <h2>Initial parser coverage</h2>
          </div>
          <dl>
            <div><dt>CDN</dt><dd>Apache-style access logs</dd></div>
            <div><dt>Origin</dt><dd>Newline-delimited JSON</dd></div>
            <div><dt>Processing</dt><dd>Streaming, archive-safe</dd></div>
            <div><dt>Invalid status</dt><dd>Rejected outside 100–599</dd></div>
          </dl>
        </section>
        <NewAnalysis />
        <AnalysisLibrary />
        <AnalysisResults />
        <GscDashboard />
        <AdminOperations />
      </section>
    </main>
  );
}
