import { useState } from "react";

// rag-answer-v2 presentation: direct answer, four independent determinations, scenario facts and evidence.
// Everything shown comes from the API response; nothing is computed in the browser.

const STATE_TEXT = {
  DETERMINED: "Determined",
  PROVISIONAL: "Provisional",
  CONDITIONAL: "Conditional",
  NEEDS_FACTS: "Needs your facts",
  INSUFFICIENT_EVIDENCE: "Not enough evidence",
  OUT_OF_SCOPE: "Not applicable",
};
const TITLES = { textual_drift: "Textual drift", materiality: "Materiality", answer_change: "Answer change", risk: "Risk" };
const KIND_TEXT = { derived: "Derived text", inference: "Inference", limitation: "Limitation" };
const ROLE_TEXT = {
  amendment_instruction: "Amendment instruction (verbatim)",
  before_fragment: "Before fragment (derived from the instruction)",
  after_fragment: "After fragment (derived from the instruction)",
  current_consolidated_text: "Current consolidated text (verbatim)",
  substitution_footnote: "India Code footnote (verbatim)",
  reconstructed_earlier_wording: "Reconstructed earlier wording (derived)",
  act_text_excerpt: "Act text excerpt (verbatim)",
};

export function DirectAnswer({ answer }) {
  return <article className="answer-card v2" aria-labelledby="direct-answer-heading">
    <span className="section-kicker" id="direct-answer-heading">Answer</span>
    <p className="direct-answer">{answer.direct_answer}</p>
    {(answer.sections || []).map((section) => <section className={`answer-part ${section.kind}`} key={section.id} aria-label={section.title}>
      <h3>{section.title}{KIND_TEXT[section.kind] && <span className="kind-badge">{KIND_TEXT[section.kind]}</span>}</h3>
      {section.label && <p className="part-label">{section.label}</p>}
      <p>{section.text}</p>
      {section.evidence_ids?.length > 0 && <p className="evidence-chips">Evidence: {section.evidence_ids.map((id) => <a key={id} href={`#evidence-${id}`} aria-label={`Evidence ${id}`}>{id}</a>)}</p>}
    </section>)}
    {answer.answer_limitations?.length > 0 && <ul className="answer-limits">{answer.answer_limitations.map((item) => <li key={item}>{item}</li>)}</ul>}
  </article>;
}

export function DeterminationCards({ determinations }) {
  return <section className="determinations" aria-label="Four separate determinations">
    {Object.keys(TITLES).map((key) => <DeterminationCard key={key} name={key} value={determinations[key]} />)}
  </section>;
}

function DeterminationCard({ name, value }) {
  if (!value) return null;
  const details = value.details || {};
  return <article className={`determination state-${value.state.toLowerCase()}`}>
    <header><h3>{TITLES[name]}</h3><span className="state-badge">{STATE_TEXT[value.state] || value.state}</span></header>
    <strong className="determination-value">{value.label || "—"}</strong>
    <p>{value.summary}</p>
    <p className="determination-reason">{value.reason}</p>
    {(value.method || value.evidence_ids?.length > 0 || Object.keys(details).length > 0) && <details>
      <summary>Method and evidence</summary>
      <dl>
        {value.method && <><dt>Method</dt><dd>{value.method}</dd></>}
        <dt>Review status</dt><dd>{value.review_status.replaceAll("_", " ").toLowerCase()}; legal validation unverified</dd>
        {value.evidence_ids?.length > 0 && <><dt>Evidence</dt><dd>{value.evidence_ids.map((id) => <a key={id} href={`#evidence-${id}`}>{id} </a>)}</dd></>}
        {details.rule_a && <><dt>Rule A</dt><dd>{details.rule_a.label || "abstains"} — {details.rule_a.rationale}</dd></>}
        {details.rule_b && <><dt>Rule B</dt><dd>{details.rule_b.label || "abstains"} — {details.rule_b.rationale}</dd></>}
        {details.llm_assessment && <><dt>LLM assessment</dt><dd>{details.llm_assessment.label || "none"} ({details.llm_assessment.model}) — {details.llm_assessment.rationale}</dd></>}
        {details.is_gold === false && <><dt>Status</dt><dd>Machine triage (silver), not an expert or gold label</dd></>}
        {details.rule_id && <><dt>Obligation rule</dt><dd>{details.rule_id} ({details.provision_version})</dd></>}
        {details.reasoning_trace?.length > 0 && <><dt>Trace</dt><dd>{details.reasoning_trace.join(" ")}</dd></>}
        {details.outcomes && <><dt>Both versions</dt><dd>{details.outcomes.map((o) => `${o.date}: ${o.risk_flag ? "does not meet" : "meets"} the rule`).join("; ")}</dd></>}
      </dl>
    </details>}
  </article>;
}

// The minimal facts the backend asked for, merged across determinations; unknowns stay blank.
export function ScenarioForm({ determinations, scenario, onSubmit, busy }) {
  const needs = [];
  for (const value of Object.values(determinations || {})) {
    for (const need of value?.needs || []) if (need.kind !== "text" && !needs.some((item) => item.key === need.key)) needs.push(need);
  }
  const initial = { ...(scenario || {}), facts: { ...(scenario?.facts || {}) } };
  const [draft, setDraft] = useState(initial);
  if (!needs.length) return null;
  const get = (key) => (key.startsWith("facts.") ? draft.facts?.[key.slice(6)] : draft[key]);
  const set = (key, value) => setDraft((current) => key.startsWith("facts.")
    ? { ...current, facts: { ...current.facts, [key.slice(6)]: value } } : { ...current, [key]: value });
  const submit = (event) => {
    event.preventDefault();
    const facts = Object.fromEntries(Object.entries(draft.facts || {}).filter(([, value]) => value !== "" && value !== undefined && value !== null));
    const clean = Object.fromEntries(Object.entries(draft).filter(([key, value]) => key !== "facts" && value !== "" && value !== undefined && value !== null));
    onSubmit({ ...clean, facts });
  };
  return <form className="scenario-form" onSubmit={submit} aria-labelledby="scenario-heading">
    <h3 id="scenario-heading">Add your situation</h3>
    <p className="panel-note">Only the facts you enter are used. Leave anything you don't know blank; it will not be assumed.</p>
    <div className="scenario-grid">{needs.map((need) => {
      const id = `scenario-${need.key.replace(".", "-")}`;
      if (need.kind === "boolean") {
        const value = get(need.key);
        return <label key={need.key} htmlFor={id}>{need.label}
          <select id={id} value={value === true ? "yes" : value === false ? "no" : ""} onChange={(e) => set(need.key, e.target.value === "" ? "" : e.target.value === "yes")}>
            <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
          </select></label>;
      }
      if (need.kind === "choice" || (need.kind === "date" && need.options?.length)) {
        return <label key={need.key} htmlFor={id}>{need.label}
          {need.kind === "date"
            // A text field, not type="date": Chrome's date picker adds a focus stop with no visible focus ring.
            ? <input id={id} type="text" inputMode="numeric" pattern="\d{4}-\d{2}-\d{2}" placeholder="YYYY-MM-DD" value={get(need.key) || ""} onChange={(e) => set(need.key, e.target.value)} aria-describedby={`${id}-hint`} />
            : <select id={id} value={get(need.key) || ""} onChange={(e) => set(need.key, e.target.value)}>
              <option value="">Unknown</option>{need.options.map((option) => <option key={option} value={option}>{option.replaceAll("_", " ")}</option>)}
            </select>}
          {need.kind === "date" && <small id={`${id}-hint`}>Format YYYY-MM-DD. Modelled dates: {need.options.join(", ")}</small>}
        </label>;
      }
      return <label key={need.key} htmlFor={id}>{need.label}<input id={id} type="text" placeholder={need.kind === "date" ? "YYYY-MM-DD" : undefined} value={get(need.key) || ""} onChange={(e) => set(need.key, e.target.value)} /></label>;
    })}</div>
    <button className="send-button" type="submit" disabled={busy}>{busy ? "Re-running…" : "Re-run with these facts"}</button>
  </form>;
}

export function EvidenceList({ evidence }) {
  if (!evidence?.length) return null;
  return <article className="panel evidence-list" aria-labelledby="evidence-heading">
    <span className="section-kicker">Sources</span><h3 id="evidence-heading">Evidence</h3>
    <ol>{evidence.map((item) => <li key={item.evidence_id} id={`evidence-${item.evidence_id}`} tabIndex={-1}>
      <strong>{item.evidence_id}</strong> {ROLE_TEXT[item.role] || item.role}{item.verbatim === false && <span className="kind-badge">Derived</span>}
      <span className="evidence-meta">{item.act_name}{item.page ? ` · page ${item.page}` : ""}{item.line ? `, line ${item.line}` : ""}</span>
      {item.text && <q>{item.text.length > 320 ? `${item.text.slice(0, 319)}…` : item.text}</q>}
      <span className="source-links">
        {item.pdf_url && <a href={item.pdf_url} target="_blank" rel="noreferrer">Open source PDF at page {item.page} ↗</a>}
        {item.official_url && <a href={item.official_url} target="_blank" rel="noreferrer">Official record ↗</a>}
      </span>
      {item.text_reliability === "UNRELIABLE_TEXT_LAYER" && <span className="evidence-warning">Unreliable text layer: check the PDF.</span>}
    </li>)}</ol>
  </article>;
}
