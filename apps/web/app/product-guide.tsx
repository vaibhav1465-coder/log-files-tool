export default function ProductGuide(){
  const steps=[
    {number:"01",title:"Connect and sign in",detail:"Connect OpenVPN, open the private URL and use your Express Intelligence account. Never enter AWS credentials."},
    {number:"02",title:"Choose source and period",detail:"Select Financial Express CloudFront or Akamai, the UTC date, and the smallest hour range needed."},
    {number:"03",title:"Review the estimate",detail:"Confirm file count, source size and expected runtime. Keep experiments small to protect the one-month pilot."},
    {number:"04",title:"Run one analysis",detail:"Start the job and leave the page open or return later. Only one analysis processes at a time."},
    {number:"05",title:"Read and export evidence",detail:"Open the completed run, filter status codes and Googlebot activity, then export only the rows you need."},
  ];
  return <section className="guidePanel" id="guide">
    <div className="sectionHeading"><div><p className="eyebrow">PRODUCT GUIDE</p><h2>From source logs to usable evidence</h2></div><span className="guideTime">Typical setup · 2 minutes</span></div>
    <div className="guideSteps">{steps.map(step=><article key={step.number}><span>{step.number}</span><h3>{step.title}</h3><p>{step.detail}</p></article>)}</div>
    <div className="guideRules"><strong>Pilot rules</strong><span>Use UTC hours · Start with one hour · Do not download raw source logs · Export only evidence needed for the task · Ask an admin before adding users.</span></div>
  </section>;
}
