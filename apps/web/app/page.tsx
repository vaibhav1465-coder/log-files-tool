import AuthShell from "./auth-shell";
import WorkspaceHeader from "./workspace-header";
import ProductGuide from "./product-guide";
import NewAnalysis from "./new-analysis";
import AnalysisLibrary from "./analysis-library";
import AnalysisResults from "./analysis-results";
import AdminOperations from "./admin-operations";
import BackendGate from "./backend-gate";

export default function Home(){
 return <AuthShell><main className="workspace">
  <aside className="sidebar"><div className="brandMark">EI</div><div className="brandText"><strong>Express Intelligence</strong><span>Financial Express</span></div>
   <nav aria-label="Primary navigation"><a className="active" href="#overview">Overview</a><a href="#guide">How to use</a><a href="#new-analysis">New analysis</a><a href="#library">Analysis library</a><a href="#results">Evidence</a><a href="#admin">Administration</a></nav>
   <div className="sidebarSafety"><span>READ-ONLY SOURCE</span><p>No upload, overwrite or delete permission.</p></div>
  </aside>
  <section className="content" id="overview"><WorkspaceHeader/>
   <header className="hero"><div><p className="eyebrow">FINANCIAL EXPRESS · DELIVERY INTELLIGENCE</p><h1>Find what search engines and readers actually received.</h1><p className="lead">Select a precise UTC window, stream approved CDN logs, and turn billions of delivery events into evidence your team can act on.</p><div className="heroActions"><a href="#new-analysis">Start an analysis</a><a className="secondaryHero" href="#guide">See how it works</a></div></div><div className="heroMetric"><span>ONE-MONTH PILOT</span><strong>100 GB</strong><p>Private server capacity with a protected 20 GB reserve.</p></div></header>
   <div className="trustStrip"><span><i/>VPN protected</span><span><i/>Named sessions</span><span><i/>Read-only S3</span><span><i/>One controlled worker</span></div>
   <section className="overviewGrid"><article><span>01</span><h2>Select</h2><p>Choose CloudFront or Akamai logs by UTC date and hour.</p></article><article><span>02</span><h2>Estimate</h2><p>See file count, source size and runtime before processing.</p></article><article><span>03</span><h2>Analyze</h2><p>Stream gzip logs without retaining private source copies.</p></article><article><span>04</span><h2>Act</h2><p>Review status, URL and Googlebot evidence and export only what is needed.</p></article></section>
   <ProductGuide/>
   <BackendGate><NewAnalysis/><AnalysisLibrary/><AnalysisResults/><AdminOperations/></BackendGate>
  </section>
 </main></AuthShell>;
}
