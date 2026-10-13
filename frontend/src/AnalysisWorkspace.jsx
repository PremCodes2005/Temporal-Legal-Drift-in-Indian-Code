import { useRef, useState } from "react";
import ComparisonPanel from "./ComparisonPanel";
import { DeterminationCard, DirectAnswer, EvidenceList, FactsForm } from "./Determinations";
import { DIAGNOSTIC_NOTE, EmptyState, ProvisionDetails } from "./ExplanationPages";
import { ClausePair } from "./Fingerprint";
import { GenerationNotice } from "./ResultInsights";
import { VerificationPanel } from "./SharedPanels";

// One stored analysis (rag-answer-v4/v5) in four views. Drift explanation and Score calculation are separate sidebar pages
// (#drift, #calculation) of the same analysis. Every view reads the SAME object; nothing is recomputed here.
export const TABS = [
  { id: "answer", label: "Answer" },
  { id: "evidence", label: "Compare Evidence" },
  { id: "scenario", label: "Scenario & Impact" },
  { id: "sources", label: "Sources & Review" },
];
const VERSION_CLASSES = new Set(["GRAPH_TRANSITION_FRAGMENTS", "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION"]);

export default function AnalysisWorkspace({ analysis, tab: controlledTab, onTab, onPage = () => {}, onScenario = () => {}, busy = false, onReview }) {
  const [localTab, setLocalTab] = useState("answer");
  const tab = controlledTab || localTab;
  const tabRefs = useRef({});
  const select = (id, focusEvidence) => {
    (onTab || setLocalTab)(id);
    if (focusEvidence) window.setTimeout(() => document.getElementById(`evidence-${focusEvidence}`)?.focus(), 0);
  };
  const onKey = (event) => {
    const index = TABS.findIndex((item) => item.id === tab);
    const next = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: TABS.length - 1 }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const target = TABS[(next + TABS.length) % TABS.length];
    select(target.id);
    tabRefs.current[target.id]?.focus();
  };
  const showEvidence = (id) => select("evidence", id);
  const views = {
    answer: <AnswerView analysis={analysis} onEvidence={showEvidence} onTab={select} onPage={onPage} />,
    evidence: <EvidenceView analysis={analysis} />,
    scenario: <ScenarioView analysis={analysis} onScenario={onScenario} busy={busy} onEvidence={showEvidence} />,
    sources: <SourcesView analysis={analysis} onReview={onReview} />,
  };
  return <section id="rag-result" className="results analysis" aria-label="Analysis">
    <div className="result-heading"><div><span className="section-kicker">Analysis {analysis.analysis_id}</span>
      <h2>{analysis.question_frame?.asks_about_versions ? "Version comparison" : "Answer"}</h2></div>
      <div className="mode-badge">{analysis.mode === "generic" ? "Generic" : "Specific"} mode</div></div>
    <p className="analysis-query"><strong>Question:</strong> {analysis.query}</p>
    <div role="tablist" aria-label="Analysis views" className="analysis-tabs" onKeyDown={onKey}>
      {TABS.map((item) => <button key={item.id} id={`tab-${item.id}`} role="tab" type="button" ref={(el) => { tabRefs.current[item.id] = el; }}
        aria-selected={tab === item.id} aria-controls={`panel-${item.id}`} tabIndex={tab === item.id ? 0 : -1}
        className={tab === item.id ? "active" : ""} onClick={() => select(item.id)}>{item.label}</button>)}
    </div>
    <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="analysis-panel" tabIndex={0}>{views[tab] || views.answer}</div>
  </section>;
}

// ---------- Answer: the answer first; only supported results that answer the question ----------
function AnswerView({ analysis, onEvidence, onTab, onPage }) {
  const fp = analysis.fingerprint || {};
  const versions = analysis.question_frame?.asks_about_versions;
  const scored = versions ? [["Wording change", fp.wording_drift], ["Rule change", fp.rule_drift]].filter(([, item]) => item?.value != null) : [];
  const outcome = versions && fp.outcome_drift?.value != null ? fp.outcome_drift : null;
  const timing = analysis.determinations?.applicability;
  const applies = analysis.scenario?.reference_date && ["DETERMINED", "CONDITIONAL"].includes(timing?.state) && timing?.label ? timing : null;
  const missing = (analysis.scenario_request?.fields || []).filter((row) => row.group === "core" && (row.value === null || row.value === undefined));
  const sources = (analysis.evidence || []).filter((item) => item.pdf_url || item.official_url).slice(0, 3);
  return <div className="answer-view">
    <GenerationNotice method={analysis.answer.generation_method} warning={analysis.answer.generation_warning} />
    <DirectAnswer answer={analysis.answer} onEvidence={onEvidence} showLimits={false} />
    {(scored.length > 0 || outcome || applies) && <section className="change-glance" aria-labelledby="glance-heading">
      <h3 id="glance-heading" className="sr-only">The change at a glance</h3>
      <ul>
        {scored.map(([name, item]) => <li key={name}><span>{name}</span><strong>{item.label}</strong></li>)}
        {outcome && <li><span>For your facts</span><strong>{outcome.label}</strong></li>}
        {applies && <li><span>Wording for your date</span><strong>{applies.label}</strong></li>}
      </ul>
      <p className="panel-note">{DIAGNOSTIC_NOTE}</p>
      <p className="answer-links"><button type="button" className="link-button" onClick={() => onPage("drift")}>Drift explanation →</button>
        <button type="button" className="link-button" onClick={() => onPage("calculation")}>Score calculation →</button></p>
    </section>}
    {sources.length > 0 && <p className="answer-sources"><strong>Sources:</strong> {sources.map((item) =>
      <a key={item.evidence_id} href={item.pdf_url || item.official_url} target="_blank" rel="noreferrer">{item.evidence_id} · {item.act_name}{item.page ? `, p. ${item.page}` : ""} ↗</a>)}</p>}
    {missing.length > 0 && <p className="check-situation"><button type="button" className="secondary-button" onClick={() => onTab("scenario")}>Check your situation</button>
      <span>{missing.length} fact{missing.length === 1 ? "" : "s"} decide whether this changes for you.</span></p>}
  </div>;
}

// ---------- Compare Evidence ----------
function EvidenceView({ analysis }) {
  const wording = analysis.fingerprint?.wording_drift;
  const supported = VERSION_CLASSES.has(analysis.comparison?.support_class);
  return <div className="view-stack">
    {supported && <ProvisionDetails analysis={analysis} />}
    {wording?.details?.before_clause && <ClausePair details={wording.details} />}
    {supported ? <ComparisonPanel comparison={analysis.comparison} /> : <EmptyState title="No before/after comparison for this question">
      {analysis.comparison?.support_reason || "The question is answered from the law as written; no versions are compared."}</EmptyState>}
    <EvidenceList evidence={analysis.evidence} />
  </div>;
}

// ---------- Scenario & Impact ----------
function ScenarioView({ analysis, onScenario, busy, onEvidence }) {
  const d = analysis.determinations || {};
  const outcome = analysis.fingerprint?.outcome_drift;
  const relevant = (item) => item && item.state !== "OUT_OF_SCOPE";
  return <div className="view-stack">
    <FactsForm request={analysis.scenario_request} onSubmit={onScenario} busy={busy} />
    <section className="determinations" aria-label="Impact on your situation">
      {relevant(d.applicability) && <DeterminationCard name="applicability" title="Which wording applies" value={d.applicability} onEvidence={onEvidence} />}
      {relevant(outcome) && <DeterminationCard name="outcome" title="Does your answer change" value={outcome} onEvidence={onEvidence} />}
      {relevant(d.risk) && <DeterminationCard name="risk" title="Conditional compliance risk" value={d.risk} onEvidence={onEvidence} />}
    </section>
    {!relevant(d.risk) && d.risk && <p className="panel-note">No modelled compliance obligation covers this provision, so no risk is assessed.</p>}
    <p className="panel-note">Outcome change is not risk, and neither depends on wording or rule drift. Facts you leave blank are never assumed.</p>
  </div>;
}

// ---------- Sources & Review ----------
function SourcesView({ analysis, onReview }) {
  const evidence = analysis.evidence || [];
  const unreliable = evidence.filter((item) => item.text_reliability === "UNRELIABLE_TEXT_LAYER");
  const derived = evidence.filter((item) => item.verbatim === false);
  const uncertainty = Object.entries(analysis.fingerprint || {}).flatMap(([name, item]) => (item?.uncertainty || []).map((u) => `${name.replace("_", " ")}: ${u.replaceAll("_", " ")}`));
  return <div className="view-stack">
    {analysis.determinations?.materiality && <section className="determinations single" aria-label="Materiality">
      <DeterminationCard name="materiality" title="Materiality of the amendment (machine triage)" value={analysis.determinations.materiality} /></section>}
    {(analysis.source_fidelity_warnings || []).map((item) => <div className="warning-note" role="alert" key={item.entry_id || item.warning}>
      <strong>Source text unreliable: {item.entry_id}</strong><span>{item.detail || item.warning}</span></div>)}
    {evidence.length > 0 && <article className="panel"><span className="section-kicker">Provenance and text quality</span><h3>Source documents</h3>
      <p className="panel-note">{evidence.length - derived.length} verbatim, {derived.length} derived (reconstructed or fragment) excerpt(s); {unreliable.length} with an unreliable text layer.</p>
      <table className="fp-table"><caption className="sr-only">Evidence provenance</caption>
        <thead><tr><th scope="col">ID</th><th scope="col">What it is</th><th scope="col">Act</th><th scope="col">Page / line</th><th scope="col">Text</th><th scope="col">Source hash</th></tr></thead>
        <tbody>{evidence.map((item) => <tr key={item.evidence_id}><th scope="row">{item.evidence_id}</th><td>{item.role?.replaceAll("_", " ")}</td><td>{item.act_name}</td>
          <td>{item.page ?? "—"}{item.line ? ` / ${item.line}` : ""}</td><td>{item.verbatim ? "verbatim" : "derived"}{item.text_reliability === "UNRELIABLE_TEXT_LAYER" ? " · unreliable" : ""}</td>
          <td><code>{item.source_sha256 ? item.source_sha256.slice(0, 12) + "…" : "—"}</code></td></tr>)}</tbody></table></article>}
    {analysis.verification && <VerificationPanel verification={analysis.verification} />}
    <article className="panel"><span className="section-kicker">Uncertainty, review and limitations</span><h3>What this analysis cannot tell you</h3>
      <ul>{[...(analysis.answer?.answer_limitations || []), ...(analysis.limitations || [])].filter((v, i, a) => a.indexOf(v) === i).map((item) => <li key={item}>{item}</li>)}</ul>
      {uncertainty.length > 0 && <p className="panel-note"><strong>Flagged uncertainty:</strong> {uncertainty.join("; ")}.</p>}
      <p><strong>Review state:</strong> not reviewed by a qualified legal expert. Legal validation: UNVERIFIED.</p>
      {onReview && <button type="button" className="link-button" onClick={onReview}>Open case trace & review</button>}
    </article>
    {analysis.source_guidance && <article className="source-guidance"><div><span className="section-kicker">Authoritative source</span><h3>Verify the complete legal text</h3>
      <p>{analysis.source_guidance.message}</p></div><a href={analysis.source_guidance.url} target="_blank" rel="noreferrer">{analysis.source_guidance.label} ↗</a></article>}
  </div>;
}
