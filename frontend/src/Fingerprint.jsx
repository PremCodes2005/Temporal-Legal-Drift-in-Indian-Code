// Legal Change Fingerprint (legal-change-fingerprint-v1): three separate measures, shown together and never averaged.
// Every number comes from the API response; the browser only displays it.

const STATE_TEXT = {
  DETERMINED: "Determined", PROVISIONAL: "Provisional", CONDITIONAL: "Conditional",
  NEEDS_FACTS: "Needs your facts", INSUFFICIENT_EVIDENCE: "Not enough evidence", OUT_OF_SCOPE: "Not applicable",
};
const OP_TEXT = { ADDED: "Added", REMOVED: "Removed", CHANGED: "Changed", UNCHANGED: "Unchanged", ABSENT: "Not present", UNCERTAIN: "Uncertain" };

function Card({ title, question, component, children }) {
  return <article className={`fingerprint-card state-${component.state.toLowerCase()}`} aria-labelledby={`fp-${title}`}>
    <header><h3 id={`fp-${title}`}>{title}</h3><span className="state-badge">{STATE_TEXT[component.state] || component.state}</span></header>
    <p className="fp-question">{question}</p>
    <strong className="fp-value">{component.label || "—"}</strong>
    <p>{component.summary}</p>
    <p className="fp-reason">{component.reason}</p>
    {component.next_action && <p className="fp-next"><strong>Next:</strong> {component.next_action}</p>}
    {children}
  </article>;
}

export function LegalChangeFingerprint({ fingerprint, legacy }) {
  if (!fingerprint) return null;
  const { wording_drift: wording, rule_drift: rule, outcome_drift: outcome } = fingerprint;
  return <section className="fingerprint" aria-labelledby="fingerprint-heading">
    <div className="fingerprint-heading"><span className="section-kicker">Legal Change Fingerprint</span>
      <h2 id="fingerprint-heading">Three separate measures of this change</h2>
      <p className="panel-note">{fingerprint.note}</p></div>
    <div className="fingerprint-grid">
      <Card title="Wording drift" question="How much did the clause's words change?" component={wording}>
        {wording.details?.spans && <WordingDetails details={wording.details} legacy={legacy} />}
      </Card>
      <Card title="Rule drift" question="What changed in the legal instruction?" component={rule}>
        {rule.details?.fields && <RuleDetails details={rule.details} />}
      </Card>
      <Card title="Outcome drift" question="Does the answer change for your scenario?" component={outcome}>
        {(outcome.details?.evaluated?.length > 0 || outcome.details?.controlled_scenarios) && <OutcomeDetails details={outcome.details} />}
      </Card>
    </div>
  </section>;
}

function WordingDetails({ details, legacy }) {
  return <details className="fp-details">
    <summary>How wording drift was calculated</summary>
    {details.formula && <p><strong>Formula:</strong> {details.formula}{details.calculation ? ` = ${details.calculation.split(" = ").pop()}%` : ""}</p>}
    {details.calculation && <p><strong>Calculation:</strong> {details.calculation}</p>}
    {details.flag && <p><strong>Result:</strong> {details.flag === "IDENTICAL" ? "identical text" : "formatting, punctuation or spelling only"}</p>}
    <p><strong>Before clause:</strong> {details.before_kind}. <strong>After clause:</strong> {details.after_kind}.</p>
    <p className="panel-note">Feature-vector drift uses deterministic token hashes, not a pretrained semantic model. Normalised before scoring: {(details.normalisation || []).join("; ")}.</p>
    {details.spans.length > 0 && <table className="fp-table"><caption>Exact changed spans</caption>
      <thead><tr><th scope="col">Change</th><th scope="col">Before</th><th scope="col">After</th></tr></thead>
      <tbody>{details.spans.map((span, index) => <tr key={index}><th scope="row">{span.operation}</th>
        <td>{span.before_text ? <del>{span.before_text}</del> : "—"}</td><td>{span.after_text ? <ins>{span.after_text}</ins> : "—"}</td></tr>)}</tbody></table>}
    {legacy && <div className="fp-legacy">{legacy}</div>}
  </details>;
}

function RuleDetails({ details }) {
  const rows = details.fields.filter((row) => row.operation !== "ABSENT");
  return <details className="fp-details">
    <summary>Rule delta and score</summary>
    <p><strong>Score:</strong> {details.formula}: {details.calculation}{details.lower_bound ? " (lower bound: some changes are not captured by a supported field)" : ""}.</p>
    {rows.length > 0 ? <table className="fp-table"><caption>Rule fields found in the changed sentences</caption>
      <thead><tr><th scope="col">Field</th><th scope="col">Before</th><th scope="col">After</th><th scope="col">Change</th><th scope="col">Weight</th><th scope="col">Adds</th></tr></thead>
      <tbody>{rows.map((row) => <tr key={row.field}><th scope="row">{row.field.replaceAll("_", " ")}</th>
        <td>{row.before.join("; ") || "—"}</td><td>{row.after.join("; ") || "—"}</td>
        <td>{OP_TEXT[row.operation] || row.operation}{row.status === "LLM_PROPOSED_VALIDATED" ? " (model-proposed, verified)" : ""}</td>
        <td>{row.weight}</td><td>{row.contribution}</td></tr>)}</tbody></table>
      : <p>No rule fields appear in the changed sentences.</p>}
    <p className="panel-note">Weights: {details.weights_config}. Not based on text length or the materiality label. Model proposals: {details.llm_proposal?.status?.replaceAll("_", " ").toLowerCase()}.</p>
  </details>;
}

function OutcomeDetails({ details }) {
  const controlled = details.controlled_scenarios;
  return <details className="fp-details">
    <summary>Facts applied to both versions</summary>
    {details.evaluated?.length > 0 && <table className="fp-table"><caption>Your facts under each version</caption>
      <thead><tr><th scope="col">Rule field</th><th scope="col">Decisive fact</th><th scope="col">Before</th><th scope="col">After</th><th scope="col">Flips?</th></tr></thead>
      <tbody>{details.evaluated.map((row, index) => <tr key={index}><th scope="row">{row.field.replaceAll("_", " ")}</th><td>{row.decisive_fact}</td>
        <td>{row.before_answer}</td><td>{row.after_answer}</td><td>{row.changed ? "Yes" : "No"}</td></tr>)}</tbody></table>}
    {details.not_evaluable?.length > 0 && <p><strong>Not evaluated:</strong> {details.not_evaluable.join("; ")}.</p>}
    {controlled && <p><strong>Controlled scenarios:</strong> {controlled.flips} of {controlled.evaluated} generated {controlled.field.replaceAll("_", " ")} values ({controlled.values_tested.join(", ")} {controlled.unit}) flip = {controlled.percent}%. {controlled.definition}.</p>}
    <p className="panel-note">{details.compat_percent_definition} Outcome drift is not risk.</p>
  </details>;
}
