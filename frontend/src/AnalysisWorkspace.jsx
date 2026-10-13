import { Fragment, useRef, useState } from "react";
import ComparisonPanel from "./ComparisonPanel";
import { DeterminationCard, DirectAnswer, EvidenceList, FactsForm } from "./Determinations";
import { ClausePair } from "./Fingerprint";
import { GenerationNotice, ScoreExplanation } from "./ResultInsights";
import { DriftPanel, VerificationPanel } from "./SharedPanels";

// One stored analysis (rag-answer-v4/v5), six views. Every view reads the SAME object; nothing is recomputed here,
// and the active view lives in the URL so links, refresh and back/forward keep it.
export const TABS = [
  { id: "answer", label: "Answer" },
  { id: "evidence", label: "Compare Evidence" },
  { id: "drift", label: "Drift Explanation" },
  { id: "calculation", label: "Score Calculation" },
  { id: "scenario", label: "Scenario & Impact" },
  { id: "sources", label: "Sources & Review" },
];
const VERSION_CLASSES = new Set(["GRAPH_TRANSITION_FRAGMENTS", "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION"]);
const OPERATION = { ADDED: "added", REMOVED: "removed", CHANGED: "changed", UNCHANGED: "unchanged", ABSENT: "not present", UNCERTAIN: "uncertain" };
const DIAGNOSTIC_NOTE = "Change diagnostics; wording, rule and situation change are measured separately: not legal correctness, not a confidence probability, not materiality and not risk.";

const fieldLabel = (row) => row.label || row.field.replaceAll("_", " ");
const quoted = (values) => (values?.length ? values.map((value) => `“${value}”`).join(" / ") : "—");

export default function AnalysisWorkspace({ analysis, tab: controlledTab, onTab, onScenario = () => {}, busy = false, onReview }) {
  const [localTab, setLocalTab] = useState("answer");
  const [highlight, setHighlight] = useState(null);
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
  const showEvidence = (id) => { setHighlight(null); select("evidence", id); };
  // A rule field's own spans, marked in the whole-clause comparison.
  const showField = (row) => {
    setHighlight({ label: fieldLabel(row), before: row.before_spans || [], after: row.after_spans || [] });
    select("evidence");
    window.setTimeout(() => document.getElementById("clause-pair-heading")?.focus(), 0);
  };
  const views = {
    answer: <AnswerView analysis={analysis} onEvidence={showEvidence} onTab={select} />,
    evidence: <EvidenceView analysis={analysis} highlight={highlight} />,
    drift: <DriftView analysis={analysis} onEvidence={showEvidence} onField={showField} onTab={select} />,
    calculation: <CalculationView analysis={analysis} onEvidence={showEvidence} onField={showField} />,
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

function EmptyState({ title, children }) {
  return <div className="empty-state" role="status"><strong>{title}</strong><p>{children}</p></div>;
}

function EvidenceButtons({ ids, onEvidence, label = "Evidence" }) {
  if (!ids?.length) return null;
  return <p className="evidence-chips">{label}: {ids.map((id) => <button key={id} type="button" onClick={() => onEvidence(id)} aria-label={`Show evidence ${id}`}>{id}</button>)}</p>;
}

// ---------- Answer: the answer first; only supported results that answer the question ----------
function AnswerView({ analysis, onEvidence, onTab }) {
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
      <p className="answer-links"><button type="button" className="link-button" onClick={() => onTab("drift")}>Explore the change</button>
        <button type="button" className="link-button" onClick={() => onTab("calculation")}>How the scores are calculated</button></p>
    </section>}
    {sources.length > 0 && <p className="answer-sources"><strong>Sources:</strong> {sources.map((item) =>
      <a key={item.evidence_id} href={item.pdf_url || item.official_url} target="_blank" rel="noreferrer">{item.evidence_id} · {item.act_name}{item.page ? `, p. ${item.page}` : ""} ↗</a>)}</p>}
    {missing.length > 0 && <p className="check-situation"><button type="button" className="secondary-button" onClick={() => onTab("scenario")}>Check your situation</button>
      <span>{missing.length} fact{missing.length === 1 ? "" : "s"} decide whether this changes for you.</span></p>}
  </div>;
}

// ---------- Compare Evidence ----------
function ProvisionDetails({ analysis }) {
  const v = analysis.version_evidence || {};
  const c = analysis.comparison || {};
  const rows = [
    ["Act", c.after?.act_name || c.before?.act_name],
    ["Provision", (v.provision_path || c.provision_path || "").replace("section:", "Section ")],
    ["Operation", (v.operation || c.operation || "").toLowerCase()],
    ["Amending Act", v.amending_entry || (v.footnote_act ? `Act ${v.footnote_act.number} of ${v.footnote_act.year} (from the footnote)` : null)],
    ["How the versions were obtained", c.support_reason],
    ["Commencement", v.effective_date ? `${v.effective_date} (Act-wide)` : v.footnote_stated_date ? `footnote states ${v.footnote_stated_date}; not verified as commencement` : null],
    ["Amendment relation", v.relation_verification ? v.relation_verification.replaceAll("_", " ").toLowerCase() : null],
  ].filter(([, value]) => value);
  if (!rows.length) return null;
  return <article className="panel provision-details"><span className="section-kicker">Provision and versions</span>
    <dl>{rows.map(([term, value]) => <div key={term}><dt>{term}</dt><dd>{value}</dd></div>)}</dl></article>;
}

function EvidenceView({ analysis, highlight }) {
  const wording = analysis.fingerprint?.wording_drift;
  const supported = VERSION_CLASSES.has(analysis.comparison?.support_class);
  return <div className="view-stack">
    {supported && <ProvisionDetails analysis={analysis} />}
    {wording?.details?.before_clause && <ClausePair details={wording.details} highlight={highlight} />}
    {supported ? <ComparisonPanel comparison={analysis.comparison} /> : <EmptyState title="No before/after comparison for this question">
      {analysis.comparison?.support_reason || "The question is answered from the law as written; no versions are compared."}</EmptyState>}
    <EvidenceList evidence={analysis.evidence} />
  </div>;
}

// ---------- Drift Explanation ----------
function NoChangeScores({ analysis }) {
  if (!analysis.question_frame?.asks_about_versions) {
    return <EmptyState title="No change to explain">This question asks about the law as written, so no two versions are compared and no change scores exist.</EmptyState>;
  }
  return <EmptyState title="The change could not be measured">{analysis.fingerprint?.wording_drift?.reason || analysis.comparison?.support_reason
    || "No supported before/after versions were found."} Nothing is scored, so no number is shown.</EmptyState>;
}

function DriftView({ analysis, onEvidence, onField, onTab }) {
  const fp = analysis.fingerprint;
  const wording = fp?.wording_drift, rule = fp?.rule_drift, outcome = fp?.outcome_drift;
  if (!analysis.question_frame?.asks_about_versions || wording?.value == null) return <NoChangeScores analysis={analysis} />;
  const spans = wording.details?.spans || [];
  const changed = (rule?.details?.fields || []).filter((row) => row.contribution);
  const structural = rule?.details?.structural_changes || [];
  const disagreement = (fp.reading || []).filter((item) => item.kind === "disagreement");
  return <div className="view-stack drift-view">
    <header className="view-intro"><span className="section-kicker">Drift explanation</span><h3>What changed in this provision, and why it matters</h3>
      <p className="panel-note">{DIAGNOSTIC_NOTE}</p></header>
    {disagreement.map((item) => <p key={item.text} className="warning-note" role="note"><strong>Read the two measures together.</strong><span>{item.text}</span></p>)}
    <section className="panel" aria-labelledby="drift-wording"><span className="section-kicker">1 · Wording change</span>
      <h3 id="drift-wording">Which exact words changed <span className="value-pill">{wording.label}</span></h3>
      <ul className="span-list">{spans.map((span, index) => <li key={index}>
        {span.operation === "added" ? <>Inserted <ins>{span.after_text}</ins></> : span.operation === "removed" ? <>Removed <del>{span.before_text}</del></>
          : <><del>{span.before_text}</del> → <ins>{span.after_text}</ins></>}</li>)}</ul>
      <EvidenceButtons ids={wording.evidence_ids} onEvidence={onEvidence} label="Cited spans" />
    </section>
    <section className="panel" aria-labelledby="drift-rule"><span className="section-kicker">2 · Legal-rule change</span>
      <h3 id="drift-rule">What changed in the legal instruction <span className="value-pill">{rule?.label || "—"}</span></h3>
      {changed.length > 0 ? <ul className="field-list">{changed.map((row) => <li key={row.field}>
        <strong>{fieldLabel(row)}</strong> {OPERATION[row.operation] || row.operation}: {quoted(row.before)} → {quoted(row.after)}
        {row.why && <span className="field-why">Why it matters: it {row.why}.</span>}
        <button type="button" className="link-button" onClick={() => onField(row)}>Show these words in the clause</button></li>)}</ul>
        : <p>{rule?.reason}</p>}
      {structural.length > 0 && <p className="panel-note">Structure: {structural.map((item) => item.value).join("; ")}. A list item or Explanation changes what the rule covers; words inside it are not counted as new duties.</p>}
      <EvidenceButtons ids={rule?.evidence_ids} onEvidence={onEvidence} label="Cited spans" />
    </section>
    <CombinedScore tlds={fp.tlds} onEvidence={onEvidence} />
    <section className="panel" aria-labelledby="drift-outcome"><span className="section-kicker">{fp.tlds && fp.tlds.state !== "NOT_APPLICABLE" ? "4" : "3"} · Your situation (separate)</span>
      <h3 id="drift-outcome">Does it change the answer for you?</h3>
      {outcome?.value != null ? <p>{outcome.summary}</p>
        : outcome?.limit?.kind === "facts" ? <p>That depends on facts about your situation; it is assessed separately. <button type="button" className="link-button" onClick={() => onTab("scenario")}>Check your situation</button></p>
          : <p>{outcome?.reason}</p>}
    </section>
  </div>;
}

const TLDS_PARTS = [["textual", "Textual drift (T)"], ["semantic", "Semantic drift (S, word-overlap stand-in)"], ["legal_effect", "Legal-effect drift (L)"], ["rule_structure", "Rule-structure drift (R)"]];

// tlds-v1: the four components stay visible beside the composite; stored records without it simply omit the section.
function CombinedScore({ tlds, onEvidence }) {
  if (!tlds || tlds.state === "NOT_APPLICABLE") return null;
  const legal = tlds.components?.legal_effect;
  const hidden = tlds.value != null && legal?.value >= 0.5 && ["Very low", "Low"].includes(tlds.band);
  return <section className="panel" aria-labelledby="drift-tlds"><span className="section-kicker">3 · Combined indicator · {tlds.version}</span>
    <h3 id="drift-tlds">Hybrid drift score (TLDS) <span className="value-pill">{tlds.label}</span></h3>
    {hidden && <p className="warning-note" role="note"><strong>Read legal effect on its own.</strong><span>The combined score is {tlds.band.toLowerCase()}, but legal-effect drift is {legal.value.toFixed(2)}. {legal.reason}</span></p>}
    {tlds.value == null && <p className="limit-note"><strong>No complete score.</strong> Missing: {tlds.missing_components.join(", ").replaceAll("_", " ")}.
      {tlds.partial_label ? ` A ${tlds.partial_label} is recorded separately.` : ""}</p>}
    <dl className="calc-list">{TLDS_PARTS.map(([key, label]) => { const part = tlds.components?.[key] || {};
      return <Fragment key={key}><dt>{label}</dt><dd>{part.value != null ? <strong>{part.value.toFixed(3)}</strong> : "missing"} · {part.reason}</dd></Fragment>; })}
      {tlds.calculation && <><dt>Worked calculation</dt><dd><code>{tlds.calculation}</code></dd></>}
      <dt>Weights</dt><dd>{TLDS_PARTS.map(([key]) => `${key.replaceAll("_", " ")} ${tlds.weights?.[key]}`).join(" · ")} (<code>{tlds.config}</code>)</dd>
    </dl>
    <p className="panel-note">{tlds.note} {tlds.bands_note}</p>
    <EvidenceButtons ids={tlds.evidence_ids} onEvidence={onEvidence} label="Scored from" />
  </section>;
}

// ---------- Score Calculation ----------
function CalculationView({ analysis, onEvidence, onField }) {
  const fp = analysis.fingerprint;
  const wording = fp?.wording_drift, rule = fp?.rule_drift, outcome = fp?.outcome_drift;
  if (!analysis.question_frame?.asks_about_versions || wording?.value == null) return <NoChangeScores analysis={analysis} />;
  const w = wording.details || {};
  const rows = (rule?.details?.fields || []);
  const controlled = outcome?.details?.controlled_scenarios;
  return <div className="view-stack calculation-view">
    <header className="view-intro"><span className="section-kicker">Score calculation</span><h3>Inputs, formulas and contributions</h3>
      <p className="panel-note">Every number is read from stored analysis {analysis.analysis_id} ({fp.version}); the browser computes nothing. {DIAGNOSTIC_NOTE}</p></header>
    <section className="panel calc-card" aria-labelledby="calc-wording"><span className="section-kicker">Wording drift · {wording.method}</span>
      <h3 id="calc-wording">Wording drift = <span className="value-pill">{wording.label}</span></h3>
      <dl className="calc-list">
        {w.inputs && <><dt>Inputs</dt><dd>lexical drift {w.inputs.lexical_drift_percent}% · feature-vector drift {w.inputs.feature_vector_drift_percent}% (deterministic token hashes, not a semantic model)</dd></>}
        {w.formula && <><dt>Formula</dt><dd><code>{w.formula}</code></dd></>}
        {w.calculation && <><dt>Worked calculation</dt><dd><code>{w.calculation}</code></dd></>}
        {w.flag && <><dt>Result</dt><dd>{w.flag === "IDENTICAL" ? "identical text" : "formatting, punctuation or spelling only"}</dd></>}
        <dt>Compared</dt><dd>whole before clause ({w.before_kind}) and whole after clause ({w.after_kind}); {(w.spans || []).length} changed span(s)</dd>
        {w.normalisation?.length > 0 && <><dt>Normalised first</dt><dd>{w.normalisation.join("; ")}</dd></>}
      </dl>
      <EvidenceButtons ids={wording.evidence_ids} onEvidence={onEvidence} label="Scored from" />
    </section>
    <section className="panel calc-card" aria-labelledby="calc-rule"><span className="section-kicker">Rule drift · {rule?.method}</span>
      <h3 id="calc-rule">Rule drift = <span className="value-pill">{rule?.label || "—"}</span></h3>
      {rule?.value == null && <p className="limit-note"><strong>No score is shown.</strong> {rule?.reason}</p>}
      <div className="table-scroll" role="region" aria-label="Rule field table" tabIndex={0}><table className="fp-table"><caption>Each rule field, its weight and what it adds</caption>
        <thead><tr><th scope="col">Field</th><th scope="col">Before</th><th scope="col">After</th><th scope="col">Change</th><th scope="col">Weight</th><th scope="col">Adds</th><th scope="col"><span className="sr-only">Evidence</span></th></tr></thead>
        <tbody>{rows.map((row) => <tr key={row.field} className={row.contribution ? "contributes" : ""}><th scope="row">{fieldLabel(row)}</th>
          <td>{quoted(row.before)}</td><td>{quoted(row.after)}</td><td>{OPERATION[row.operation] || row.operation}</td><td>{row.weight}</td><td>{row.contribution}</td>
          <td>{(row.before_spans?.length || row.after_spans?.length) ? <button type="button" className="link-button" onClick={() => onField(row)} aria-label={`Show the words for ${fieldLabel(row)}`}>Show</button> : null}</td></tr>)}</tbody>
        {rule?.value != null && <tfoot><tr><th scope="row" colSpan={5}>Total ({rule.details.formula})</th><td colSpan={2}><strong>{rule.details.calculation}</strong></td></tr></tfoot>}
      </table></div>
      <p className="panel-note">Weights: <code>{rule?.details?.weights_config}</code>. Independent of how many words changed and of the materiality label.
        {rule?.details?.lower_bound ? " Uncertain fields are excluded, so the total is a lower bound." : ""}</p>
      <EvidenceButtons ids={rule?.evidence_ids} onEvidence={onEvidence} label="Scored from" />
    </section>
    <section className="panel calc-card" aria-labelledby="calc-outcome"><span className="section-kicker">Outcome drift · {outcome?.method}</span>
      <h3 id="calc-outcome">Outcome drift = <span className="value-pill">{outcome?.label || "—"}</span></h3>
      {outcome?.details?.evaluated?.length > 0 ? <table className="fp-table"><caption>Your stated facts under each version</caption>
        <thead><tr><th scope="col">Rule field</th><th scope="col">Your fact</th><th scope="col">Before</th><th scope="col">After</th><th scope="col">Flips?</th></tr></thead>
        <tbody>{outcome.details.evaluated.map((row, index) => <tr key={index}><th scope="row">{row.field.replaceAll("_", " ")}</th><td>{row.decisive_fact}</td>
          <td>{row.before_answer}</td><td>{row.after_answer}</td><td>{row.changed ? "Yes" : "No"}</td></tr>)}</tbody></table>
        : <p>{outcome?.value == null ? `No outcome value: ${outcome?.reason}` : outcome?.summary}</p>}
      {outcome?.details?.assumptions?.length > 0 && <p className="panel-note"><strong>Stated assumptions:</strong> {outcome.details.assumptions.join("; ")}.</p>}
      {controlled && <p className="panel-note"><strong>Hypothetical boundary values (not your facts):</strong> {controlled.flips} of {controlled.evaluated} generated
        {" "}{controlled.field.replaceAll("_", " ")} values ({controlled.values_tested.join(", ")} {controlled.unit}) flip = {controlled.percent}%. {controlled.definition}.</p>}
      {outcome?.details?.compat_percent_definition && <p className="panel-note">{outcome.details.compat_percent_definition}. Outcome drift is not risk.</p>}
    </section>
    {analysis.metrics && <details className="legacy-diagnostic"><summary>Legacy diagnostic (drift-metrics-v3), not used above</summary>
      <p className="panel-note">{analysis.metrics.legacy_diagnostic?.note}</p><DriftPanel metrics={analysis.metrics} legacy /><ScoreExplanation metrics={analysis.metrics} /></details>}
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
