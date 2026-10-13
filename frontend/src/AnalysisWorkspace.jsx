import { useRef, useState } from "react";
import ComparisonPanel from "./ComparisonPanel";
import { DeterminationCard, DirectAnswer, EvidenceList, FactsForm } from "./Determinations";
import { ClausePair, FingerprintStrip, LegalChangeFingerprint } from "./Fingerprint";
import { GenerationNotice, ScoreExplanation } from "./ResultInsights";
import { DriftPanel, VerificationPanel } from "./SharedPanels";

// One analysis (rag-answer-v4), five focused views. Every view reads the SAME stored analysis object;
// nothing is recomputed here, and the active tab lives in the URL so links and refreshes keep it.
export const TABS = [
  { id: "answer", label: "Answer" },
  { id: "evidence", label: "Compare & Evidence" },
  { id: "scores", label: "Scores & Method" },
  { id: "scenario", label: "Scenario & Impact" },
  { id: "sources", label: "Sources & Review" },
];
const VERSION_CLASSES = new Set(["GRAPH_TRANSITION_FRAGMENTS", "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION"]);

export default function AnalysisWorkspace({ analysis, tab: controlledTab, onTab, onScenario = () => {}, busy = false, onReview }) {
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
  const supported = VERSION_CLASSES.has(analysis.comparison?.support_class);
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
    <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="analysis-panel" tabIndex={0}>
      {tab === "answer" && <AnswerView analysis={analysis} onEvidence={showEvidence} onTab={select} onScenario={onScenario} busy={busy} />}
      {tab === "evidence" && <EvidenceView analysis={analysis} supported={supported} />}
      {tab === "scores" && <ScoresView analysis={analysis} onEvidence={showEvidence} />}
      {tab === "scenario" && <ScenarioView analysis={analysis} onScenario={onScenario} busy={busy} onEvidence={showEvidence} />}
      {tab === "sources" && <SourcesView analysis={analysis} onReview={onReview} />}
    </div>
  </section>;
}

// The single most useful next step, chosen from backend fields in a fixed order.
function nextAction(analysis) {
  const core = (analysis.scenario_request?.fields || []).filter((row) => row.group === "core" && (row.value === null || row.value === undefined));
  if (core.length) return { text: `Add ${core.length} fact${core.length === 1 ? "" : "s"} to see whether the answer changes for your situation.`, tab: "scenario" };
  const blocked = Object.values(analysis.fingerprint || {}).find((item) => item?.limit?.kind === "evidence");
  if (blocked) return { text: blocked.limit.action.label + ".", tab: "sources" };
  const method = Object.values(analysis.fingerprint || {}).find((item) => item?.limit?.kind === "method");
  if (method) return { text: method.summary, tab: "scores" };
  const limit = analysis.answer?.answer_limitations?.[0];
  return limit ? { text: limit, tab: "sources" } : null;
}

function AnswerView({ analysis, onEvidence, onTab, onScenario, busy }) {
  const action = nextAction(analysis);
  const coreFields = (analysis.scenario_request?.fields || []).filter((row) => row.group === "core");
  return <div className="answer-layout">
    <div className="answer-main">
      <GenerationNotice method={analysis.answer.generation_method} />
      <DirectAnswer answer={analysis.answer} onEvidence={onEvidence} showLimits={false} />
      {analysis.question_frame?.asks_about_versions && <FingerprintStrip fingerprint={analysis.fingerprint}
        materiality={analysis.determinations?.materiality} onOpen={() => onTab("scores")} />}
      {action && <div className="next-action" role="note"><strong>Next step:</strong> {action.text}{" "}
        <button type="button" className="link-button" onClick={() => onTab(action.tab)}>Open {labelOf(action.tab)}</button></div>}
    </div>
    {coreFields.length > 0 && <aside className="answer-side" aria-label="Your situation">
      <FactsForm request={analysis.scenario_request} onSubmit={onScenario} busy={busy} compact />
    </aside>}
  </div>;
}

const labelOf = (id) => TABS.find((item) => item.id === id)?.label;

function EmptyState({ title, children }) {
  return <div className="empty-state" role="status"><strong>{title}</strong><p>{children}</p></div>;
}

function EvidenceView({ analysis, supported }) {
  const wording = analysis.fingerprint?.wording_drift;
  return <div className="view-stack">
    {supported ? <ComparisonPanel comparison={analysis.comparison} /> : <EmptyState title="No before/after comparison for this question">
      {analysis.comparison?.support_reason || "The question is answered from the law as written; no versions are compared."}</EmptyState>}
    {wording?.details?.before_clause && <ClausePair details={wording.details} />}
    <EvidenceList evidence={analysis.evidence} />
  </div>;
}

function ScoresView({ analysis, onEvidence }) {
  const fp = analysis.fingerprint;
  if (!analysis.question_frame?.asks_about_versions) {
    return <EmptyState title="No change scores for this question">Scores compare two versions of one provision; this question asks about the law as written.</EmptyState>;
  }
  const wording = fp?.wording_drift, rule = fp?.rule_drift;
  const conflict = wording?.value != null && rule?.value != null && ((wording.value < 10 && rule.value >= 25) || (wording.value >= 30 && rule.value === 0));
  return <div className="view-stack">
    {conflict && <p className="warning-note" role="note"><strong>The measures disagree, and that is informative.</strong>
      <span>{wording.value < 10 ? "Few words changed, but the legal instruction changed." : "Many words changed, but no rule field changed."} They are reported separately and never averaged.</span></p>}
    <LegalChangeFingerprint fingerprint={fp} onEvidence={onEvidence} open
      legacy={analysis.metrics && <><p className="panel-note"><strong>Legacy diagnostic (drift-metrics-v3).</strong> {analysis.metrics.legacy_diagnostic?.note}</p>
        <DriftPanel metrics={analysis.metrics} legacy /><ScoreExplanation metrics={analysis.metrics} /></>} />
  </div>;
}

function ScenarioView({ analysis, onScenario, busy, onEvidence }) {
  const d = analysis.determinations || {};
  const outcome = analysis.fingerprint?.outcome_drift;
  return <div className="view-stack">
    <FactsForm request={analysis.scenario_request} onSubmit={onScenario} busy={busy} />
    <section className="determinations" aria-label="Impact on your situation">
      {d.applicability && <DeterminationCard name="applicability" title="Which wording applies" value={d.applicability} onEvidence={onEvidence} />}
      {outcome && <DeterminationCard name="outcome" title="Does your answer change" value={outcome} onEvidence={onEvidence} />}
      {d.risk && <DeterminationCard name="risk" title="Conditional risk" value={d.risk} onEvidence={onEvidence} />}
    </section>
    <p className="panel-note">Outcome change is not risk, and neither depends on wording or rule drift.</p>
  </div>;
}

function SourcesView({ analysis, onReview }) {
  const evidence = analysis.evidence || [];
  return <div className="view-stack">
    {analysis.determinations?.materiality && <section className="determinations single" aria-label="Materiality">
      <DeterminationCard name="materiality" title="Materiality of the amendment" value={analysis.determinations.materiality} /></section>}
    {(analysis.source_fidelity_warnings || []).map((item) => <div className="warning-note" role="alert" key={item.entry_id}>
      <strong>Source text unreliable: {item.entry_id}</strong><span>{item.detail}</span></div>)}
    {evidence.length > 0 && <article className="panel"><span className="section-kicker">Provenance</span><h3>Source documents</h3>
      <table className="fp-table"><caption className="sr-only">Evidence provenance</caption>
        <thead><tr><th scope="col">ID</th><th scope="col">What it is</th><th scope="col">Act</th><th scope="col">Page / line</th><th scope="col">Text</th><th scope="col">Source hash</th></tr></thead>
        <tbody>{evidence.map((item) => <tr key={item.evidence_id}><th scope="row">{item.evidence_id}</th><td>{item.role?.replaceAll("_", " ")}</td><td>{item.act_name}</td>
          <td>{item.page ?? "—"}{item.line ? ` / ${item.line}` : ""}</td><td>{item.verbatim ? "verbatim" : "derived"}{item.text_reliability === "UNRELIABLE_TEXT_LAYER" ? " · unreliable" : ""}</td>
          <td><code>{item.source_sha256 ? item.source_sha256.slice(0, 12) + "…" : "—"}</code></td></tr>)}</tbody></table></article>}
    {analysis.verification && <VerificationPanel verification={analysis.verification} />}
    <article className="panel"><span className="section-kicker">Limitations</span><h3>What this analysis cannot tell you</h3>
      <ul>{[...(analysis.answer?.answer_limitations || []), ...(analysis.limitations || [])].filter((v, i, a) => a.indexOf(v) === i).map((item) => <li key={item}>{item}</li>)}</ul>
      <p><strong>Review state:</strong> not reviewed by a qualified legal expert. Legal validation: UNVERIFIED.</p>
      {onReview && <button type="button" className="link-button" onClick={onReview}>Open case trace & review</button>}
    </article>
    {analysis.source_guidance && <article className="source-guidance"><div><span className="section-kicker">Authoritative source</span><h3>Verify the complete legal text</h3>
      <p>{analysis.source_guidance.message}</p></div><a href={analysis.source_guidance.url} target="_blank" rel="noreferrer">{analysis.source_guidance.label} ↗</a></article>}
  </div>;
}
