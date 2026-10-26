import ComparisonPanel from "./ComparisonPanel";
import { DeterminationCard, DirectAnswer } from "./Determinations";
import { DIAGNOSTIC_NOTE } from "./ExplanationPages";
import { GenerationNotice, VersionStatus } from "./ResultInsights";
import { VerificationPanel } from "./SharedPanels";
import { ActChoices, InterpretedAs, LatestRecords, NotFoundSources } from "./Routing";

// The assistant page's answer for one stored analysis (rag-answer-v4/v5), in the single-page order of v0.13.0 (commit 6db1c49):
// answer, path to the explanation pages, pre/post comparison. Evidence ids open their cards on the Drift explanation page;
// review details are folded away.
// Every value is read from the stored analysis; nothing is recomputed here.
const HEADINGS = { act_choice: "Choose an Act", act_not_found: "Act not found in the corpus", latest_records: "Latest records",
  scope_guidance: "Outside this assistant's scope", act_comparison: "Comparison of Acts" };

export default function AssistantResult({ analysis, onPage = () => {}, onEvidence = () => {}, onSection = () => {}, onAct = () => {}, acts = [], busy = false }) {
  const fp = analysis.fingerprint || {};
  const routing = analysis.routing;
  const versions = analysis.question_frame?.asks_about_versions && routing?.route !== "act_comparison";
  const scored = versions ? [["Wording drift", fp.wording_drift], ["Rule drift", fp.rule_drift]].filter(([, item]) => item?.value != null) : [];
  const combined = versions && fp.tlds?.value != null ? fp.tlds : null;
  const found = analysis.version_evidence?.section_candidates;
  return <section id="rag-result" className="results" aria-labelledby="result-title">
    <div className="result-heading"><div><span className="section-kicker">Grounded response · analysis {analysis.analysis_id}</span>
      <h2 id="result-title">{HEADINGS[routing?.response_type] || (versions ? "Version comparison" : "Answer")}</h2></div>
      <div className="mode-badge">{analysis.mode === "generic" ? "Generic" : "Specific"} mode</div></div>
    <InterpretedAs routing={routing} acts={acts} onAct={onAct} busy={busy} />
    {analysis.selection?.section && <p className="selection-note">Section chosen from the list: <strong>section {analysis.selection.section}</strong> of the {analysis.selection.act_name}.
      Your question is kept as you asked it.</p>}
    {/* With the chooser shown, the answer's plain-text list of the same sections would repeat it. */}
    <DirectAnswer answer={found ? { ...analysis.answer, sections: (analysis.answer.sections || []).filter((part) => part.id !== "candidates") } : analysis.answer}
      onEvidence={onEvidence} showLimits={false}
      note={versions && <VersionStatus comparison={analysis.comparison} metrics={analysis.metrics} scope={analysis.comparison?.support_class !== "NOT_A_COMPARISON"} />}
      footer={<GenerationNotice method={analysis.answer.generation_method} warning={analysis.answer.generation_warning} />} />
    {found && <SectionChooser found={found} onSection={onSection} busy={busy} />}
    <ActChoices routing={routing} onAct={onAct} busy={busy} />
    <NotFoundSources routing={routing} />
    <LatestRecords feed={analysis.latest_records} />
    {analysis.scenario && <p className="panel-note">Using your facts: {Object.entries({ ...analysis.scenario, ...(analysis.scenario.facts || {}) })
      .filter(([key, value]) => key !== "facts" && value !== null && value !== "")
      .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value === true ? "yes" : value === false ? "no" : String(value).replaceAll("_", " ")}`).join("; ")}.</p>}
    {versions && !found && <ChangePath scored={scored} combined={combined} analysis={analysis} onPage={onPage} />}
    <ComparisonPanel comparison={analysis.comparison} scope={!versions} />
    {(analysis.source_fidelity_warnings || []).map((item) => <div className="warning-note" role="alert" key={item.entry_id || item.warning}>
      <strong>Source text unreliable: {item.entry_id}</strong><span>{item.detail || item.warning} Treat quoted wording from this source as unverified.</span></div>)}
    <Review analysis={analysis} />
    {analysis.source_guidance && <article className="source-guidance"><div><span className="section-kicker">Authoritative source</span><h3>Verify the complete legal text</h3>
      <p>{analysis.source_guidance.message}</p></div><a href={analysis.source_guidance.url} target="_blank" rel="noreferrer">{analysis.source_guidance.label} ↗</a></article>}
  </section>;
}

// A compact score line and the two explanation pages; values appear only when they were scored.
function ChangePath({ scored, combined, analysis, onPage }) {
  return <article className="change-path" aria-labelledby="change-path-heading">
    <span className="section-kicker">The change, measured</span>
    <h3 id="change-path-heading" className="sr-only">The change, measured</h3>
    {scored.length || combined ? <ul className="change-glance-list">
      {scored.map(([name, item]) => <li key={name}><span>{name}</span><strong>{item.label}</strong></li>)}
      {combined && <li><span>Combined indicator</span><strong>{combined.label}</strong></li>}
    </ul> : <p>No change score: {analysis.fingerprint?.wording_drift?.reason || analysis.comparison?.support_reason || "no supported before/after versions."}</p>}
    <p className="panel-note">{DIAGNOSTIC_NOTE}</p>
    {["GRAPH_TRANSITION_FRAGMENTS", "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION"].includes(analysis.comparison?.support_class) &&
      <button className="explain-drift-button" type="button" onClick={() => onPage("comparison")}>View detailed clause comparison <span aria-hidden="true">→</span></button>}
    <button className="explain-drift-button" type="button" onClick={() => onPage("drift")}>Explain the change with the cited clauses <span aria-hidden="true">→</span></button>
    <button className="explain-drift-button" type="button" onClick={() => onPage("calculation")}>See how the scores are calculated <span aria-hidden="true">→</span></button>
  </article>;
}

const STATUS = {
  SUPPORTED: ["supported", "Before/after available"],
  SEVERAL_CHANGES: ["limited", "Several changes recorded"],
  NOT_CORROBORATED: ["limited", "Change recorded, not corroborated"],
  TEXT_UNRELIABLE: ["limited", "Source text unreliable"],
  NO_RECORDED_CHANGE: ["none", "Mentions your topic; no recorded change"],
};

// An Act-only question: the sections that can be compared, why each is listed, and where the evidence is. One click compares.
function SectionChooser({ found, onSection, busy }) {
  const supported = found.counts.SUPPORTED || 0;
  return <article className="section-chooser" aria-labelledby="chooser-heading">
    <span className="section-kicker">Choose a section</span>
    <h3 id="chooser-heading">{found.candidates.length ? `Sections of the ${found.act_name} you can open` : "No section to compare"}</h3>
    <p className="panel-note">{supported} section{supported === 1 ? "" : "s"} with a before/after comparison{found.amendment_year ? ` for the ${found.amendment_year} amendment` : ""}
      {found.candidates.length < found.checked_sections ? `; showing the ${found.candidates.length} most relevant` : ""}. {found.note}</p>
    {found.candidates.length > 0 && <ul className="chooser-list">{found.candidates.map((row) => {
      const [tone, label] = STATUS[row.status] || ["none", row.status];
      return <li key={row.section} className={`chooser-item ${tone}`}>
        <div className="chooser-main">
          <strong>Section {row.section}{row.heading ? ` · ${row.heading}` : ""}</strong>
          <span className={`status-tag ${tone}`}>{label}</span>
          <p>{row.why}</p>
          <small>{[row.amendment, row.footnote_stated_date && `footnote states effect from ${row.footnote_stated_date} (not verified)`, row.effective_date && `in force ${row.effective_date}`].filter(Boolean).join(" · ")}
            {row.source?.pdf_url && <> · <a href={row.source.pdf_url} target="_blank" rel="noreferrer">Source PDF{row.source.page ? ` p. ${row.source.page}` : ""} ↗</a></>}</small>
        </div>
        <button type="button" className={row.status === "SUPPORTED" ? "send-button" : "secondary-button"} disabled={busy} onClick={() => onSection(row.section)}
          aria-label={row.status === "SUPPORTED" ? `Compare section ${row.section}` : `See why section ${row.section} cannot be compared`}>
          {row.status === "SUPPORTED" ? "Compare" : "See why"}</button>
      </li>;
    })}</ul>}
  </article>;
}

function Review({ analysis }) {
  const evidence = analysis.evidence || [];
  const derived = evidence.filter((item) => item.verbatim === false).length;
  const unreliable = evidence.filter((item) => item.text_reliability === "UNRELIABLE_TEXT_LAYER").length;
  const uncertainty = Object.entries(analysis.fingerprint || {}).flatMap(([name, item]) => (item?.uncertainty || []).map((u) => `${name.replace("_", " ")}: ${u.replaceAll("_", " ")}`));
  const limits = [...(analysis.answer?.answer_limitations || []), ...(analysis.limitations || [])].filter((v, i, a) => a.indexOf(v) === i);
  return <details className="fold review">
    <summary>Sources, quality and review</summary>
    {analysis.determinations?.materiality && <section className="determinations single" aria-label="Materiality">
      <DeterminationCard name="materiality" title="Materiality of the amendment (machine triage)" value={analysis.determinations.materiality} /></section>}
    {evidence.length > 0 && <><p className="panel-note">{evidence.length - derived} verbatim and {derived} derived (reconstructed or fragment) excerpt(s); {unreliable} with an unreliable text layer.</p>
      <div className="table-scroll" role="region" aria-label="Evidence provenance" tabIndex={0}><table className="fp-table"><caption className="sr-only">Evidence provenance</caption>
        <thead><tr><th scope="col">ID</th><th scope="col">What it is</th><th scope="col">Act</th><th scope="col">Page / line</th><th scope="col">Text</th><th scope="col">Source hash</th></tr></thead>
        <tbody>{evidence.map((item) => <tr key={item.evidence_id}><th scope="row">{item.evidence_id}</th><td>{item.role?.replaceAll("_", " ")}</td><td>{item.act_name}</td>
          <td>{item.page ?? "—"}{item.line ? ` / ${item.line}` : ""}</td><td>{item.verbatim ? "verbatim" : "derived"}{item.text_reliability === "UNRELIABLE_TEXT_LAYER" ? " · unreliable" : ""}</td>
          <td><code>{item.source_sha256 ? item.source_sha256.slice(0, 12) + "…" : "—"}</code></td></tr>)}</tbody></table></div></>}
    {analysis.verification && <VerificationPanel verification={analysis.verification} />}
    {limits.length > 0 && <ul>{limits.map((item) => <li key={item}>{item}</li>)}</ul>}
    {uncertainty.length > 0 && <p className="panel-note"><strong>Flagged uncertainty:</strong> {uncertainty.join("; ")}.</p>}
    <p><strong>Review state:</strong> not reviewed by a qualified legal expert. Legal validation: UNVERIFIED.</p>
  </details>;
}
