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
// determinations-v2: textual_drift is a deprecated alias of the fingerprint's wording drift, so it is not shown twice.
const TITLES = { materiality: "Materiality", applicability: "Applicability", answer_change: "Answer change", risk: "Risk" };
const LEGACY_TITLES = { textual_drift: "Textual drift", materiality: "Materiality", answer_change: "Answer change", risk: "Risk" };
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

export function DirectAnswer({ answer, onEvidence, showLimits = true }) {
  return <article className="answer-card v2" aria-labelledby="direct-answer-heading">
    <span className="section-kicker" id="direct-answer-heading">Answer</span>
    <p className="direct-answer">{answer.direct_answer}</p>
    {(answer.sections || []).map((section) => <section className={`answer-part ${section.kind}`} key={section.id} aria-label={section.title}>
      <h3>{section.title}{KIND_TEXT[section.kind] && <span className="kind-badge">{KIND_TEXT[section.kind]}</span>}</h3>
      {section.label && <p className="part-label">{section.label}</p>}
      <p>{section.text}</p>
      {section.evidence_ids?.length > 0 && <p className="evidence-chips">Evidence: {section.evidence_ids.map((id) => onEvidence
        ? <button key={id} type="button" onClick={() => onEvidence(id)} aria-label={`Show evidence ${id}`}>{id}</button>
        : <a key={id} href={`#evidence-${id}`} aria-label={`Evidence ${id}`}>{id}</a>)}</p>}
    </section>)}
    {showLimits && answer.answer_limitations?.length > 0 && <ul className="answer-limits">{answer.answer_limitations.map((item) => <li key={item}>{item}</li>)}</ul>}
  </article>;
}

export function DeterminationCards({ determinations }) {
  const titles = determinations?.applicability ? TITLES : LEGACY_TITLES;
  return <section className="determinations" aria-label="Separate legal determinations">
    {Object.keys(titles).map((key) => <DeterminationCard key={key} name={key} title={titles[key]} value={determinations[key]} />)}
  </section>;
}

const LIMIT_TEXT = { facts: "Needs your facts", evidence: "Missing legal evidence (your facts cannot fill this)", method: "Outside what this method measures" };

export function DeterminationCard({ name, title, value, onEvidence }) {
  if (!value) return null;
  const details = value.details || {};
  return <article className={`determination state-${value.state.toLowerCase()}`}>
    <header><h3>{title || name}</h3><span className="state-badge">{STATE_TEXT[value.state] || value.state}</span></header>
    <strong className="determination-value">{value.label || "—"}</strong>
    <p>{value.summary}</p>
    <p className="determination-reason">{value.reason}</p>
    {value.limit && LIMIT_TEXT[value.limit.kind] && <p className={`limit-tag limit-${value.limit.kind}`}><strong>{LIMIT_TEXT[value.limit.kind]}.</strong> {value.limit.action?.label}</p>}
    {value.details?.evaluated?.length > 0 && <table className="fp-table"><caption>Your facts under each version</caption>
      <thead><tr><th scope="col">Rule field</th><th scope="col">Decisive fact</th><th scope="col">Before</th><th scope="col">After</th></tr></thead>
      <tbody>{value.details.evaluated.map((row, index) => <tr key={index}><th scope="row">{row.field.replaceAll("_", " ")}</th><td>{row.decisive_fact}</td><td>{row.before_answer}</td><td>{row.after_answer}</td></tr>)}</tbody></table>}
    {(value.method || value.evidence_ids?.length > 0 || Object.keys(details).length > 0) && <details>
      <summary>Method and evidence</summary>
      <dl>
        {value.method && <><dt>Method</dt><dd>{value.method}</dd></>}
        <dt>Review status</dt><dd>{(value.review_status || "unreviewed").replaceAll("_", " ").toLowerCase()}; legal validation unverified</dd>
        {value.evidence_ids?.length > 0 && <><dt>Evidence</dt><dd>{value.evidence_ids.map((id) => onEvidence
          ? <button key={id} type="button" className="link-button" onClick={() => onEvidence(id)}>{id}</button> : <a key={id} href={`#evidence-${id}`}>{id} </a>)}</dd></>}
        {details.source && <><dt>Assessment source</dt><dd>{{ FROZEN_SILVER_SET: "Frozen silver set (versioned machine triage, not gold)", ON_THE_FLY_MACHINE_TRIAGE: "Machine triage computed for this answer (not in the frozen set, not gold)" }[details.source] || details.source}</dd></>}
        {details.rule_a && <><dt>Rule A</dt><dd>{details.rule_a.label || "abstains"} — {details.rule_a.rationale}</dd></>}
        {details.rule_b && <><dt>Rule B</dt><dd>{details.rule_b.label || "abstains"} — {details.rule_b.rationale}</dd></>}
        {details.llm_assessment && <><dt>LLM assessment</dt><dd>{details.llm_assessment.label || "none"} ({details.llm_assessment.model}) — {details.llm_assessment.rationale}</dd></>}
        {details.is_gold === false && <><dt>Status</dt><dd>Machine triage (silver), not an expert or gold label</dd></>}
        {details.rule_id && <><dt>Obligation rule</dt><dd>{details.rule_id} ({details.provision_version})</dd></>}
        {details.reasoning_trace?.length > 0 && <><dt>Trace</dt><dd>{details.reasoning_trace.join(" ")}</dd></>}
        {details.outcomes && <><dt>Both versions</dt><dd>{details.outcomes.map((o) => `${o.date}: ${o.risk_flag ? "does not meet" : "meets"} the rule`).join("; ")}</dd></>}
        {details.commencement && <><dt>Commencement</dt><dd>{details.commencement.date || "unknown"} — {details.commencement.basis}</dd></>}
        {details.publication && <><dt>Publication</dt><dd>{details.publication.note}</dd></>}
      </dl>
    </details>}
  </article>;
}

// The minimal facts the backend asked for, merged across determinations; unknowns stay blank.
export function ScenarioForm({ determinations, extraNeeds = [], scenario, onSubmit, busy }) {
  const needs = [];
  for (const value of [...Object.values(determinations || {}), { needs: extraNeeds }]) {
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
    const numeric = new Set(needs.filter((need) => need.kind === "number").map((need) => need.key.slice(6)));
    const facts = Object.fromEntries(Object.entries(draft.facts || {}).filter(([, value]) => value !== "" && value !== undefined && value !== null)
      .map(([key, value]) => [key, numeric.has(key) && !Number.isNaN(Number(value)) ? Number(value) : value]));
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
      return <label key={need.key} htmlFor={id}>{need.label}<input id={id} type="text" inputMode={need.kind === "number" ? "decimal" : undefined}
        placeholder={need.kind === "date" ? "YYYY-MM-DD" : need.kind === "number" ? "a number" : undefined} value={get(need.key) ?? ""} onChange={(e) => set(need.key, e.target.value)} /></label>;
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

// Minimum facts (rag-answer-v4 scenario_request): only what unlocks something blocked by missing facts.
export function FactsForm({ request, onSubmit, busy, compact = false }) {
  const fields = (request?.fields || []).filter((row) => !compact || row.group === "core");
  const initial = Object.fromEntries((request?.fields || []).map((row) => [row.key, row.value ?? ""]));
  const [draft, setDraft] = useState(initial);
  if (!fields.length) {
    return request?.blocked_by_evidence?.length ? <p className="panel-note limit-evidence">{request.explanation}</p> : null;
  }
  const submit = (event) => {
    event.preventDefault();
    const scenario = { facts: {} };
    for (const row of request.fields) {
      const value = draft[row.key];
      if (value === "" || value === undefined || value === null) continue;
      const typed = row.kind === "number" ? Number(value) : row.kind === "boolean" ? value === true || value === "yes" : value;
      if (row.kind === "number" && Number.isNaN(typed)) continue;
      if (row.key.startsWith("facts.")) scenario.facts[row.key.slice(6)] = typed; else scenario[row.key] = typed;
    }
    onSubmit(scenario);
  };
  const field = (row) => {
    const id = `fact-${compact ? "c-" : ""}${row.key.replace(".", "-")}`;
    const value = draft[row.key];
    const set = (v) => setDraft((current) => ({ ...current, [row.key]: v }));
    const hint = <small id={`${id}-hint`}>Unlocks {row.unlocks.join(" and ")}{row.source === "question" ? " · read from your question" : ""}
      {row.kind === "date" && row.options?.length ? ` · modelled dates: ${row.options.join(", ")}` : ""}</small>;
    let control;
    if (row.kind === "boolean") {
      control = <select id={id} aria-describedby={`${id}-hint`} value={value === true ? "yes" : value === false ? "no" : value || ""} onChange={(e) => set(e.target.value)}>
        <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option></select>;
    } else if (row.kind === "choice") {
      control = <select id={id} aria-describedby={`${id}-hint`} value={value || ""} onChange={(e) => set(e.target.value)}>
        <option value="">Unknown</option>{row.options.map((o) => <option key={o} value={o}>{o.replaceAll("_", " ")}</option>)}</select>;
    } else {
      control = <input id={id} type="text" aria-describedby={`${id}-hint`} inputMode={row.kind === "number" ? "decimal" : "numeric"}
        placeholder={row.kind === "date" ? "YYYY-MM-DD" : row.kind === "number" ? "a number" : undefined} value={value ?? ""} onChange={(e) => set(e.target.value)} />;
    }
    return <label key={row.key} htmlFor={id}>{row.label}{control}{hint}</label>;
  };
  const core = fields.filter((row) => row.group === "core"), risk = fields.filter((row) => row.group === "risk");
  return <form className={`facts-form ${compact ? "compact" : ""}`} onSubmit={submit} aria-labelledby={compact ? "facts-heading-c" : "facts-heading"}>
    <h3 id={compact ? "facts-heading-c" : "facts-heading"}>Your situation</h3>
    <p className="panel-note">{request.explanation}</p>
    <div className="scenario-grid">{core.map(field)}</div>
    {risk.length > 0 && <details className="risk-facts"><summary>Also assess conditional risk (optional, {risk.length} facts)</summary>
      <div className="scenario-grid">{risk.map(field)}</div></details>}
    <button className="send-button" type="submit" disabled={busy}>{busy ? "Re-running…" : "Re-run with these facts"}</button>
  </form>;
}
