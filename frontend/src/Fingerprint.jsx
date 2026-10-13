import { Fragment } from "react";

// Legal Change Fingerprint (legal-change-fingerprint-v1): three separate measures, shown together and never averaged.
// Every number comes from the API response; the browser only displays it.

const STATE_TEXT = {
  DETERMINED: "Determined", PROVISIONAL: "Provisional", CONDITIONAL: "Conditional",
  NEEDS_FACTS: "Needs your facts", INSUFFICIENT_EVIDENCE: "Not enough evidence", OUT_OF_SCOPE: "Not applicable",
};
const OP_TEXT = { ADDED: "Added", REMOVED: "Removed", CHANGED: "Changed", UNCHANGED: "Unchanged", ABSENT: "Not present", UNCERTAIN: "Uncertain" };

function EvidenceButtons({ ids, onEvidence }) {
  if (!ids?.length || !onEvidence) return null;
  return <p className="evidence-chips">Scored from: {ids.map((id) => <button key={id} type="button" onClick={() => onEvidence(id)} aria-label={`Show evidence ${id}`}>{id}</button>)}</p>;
}

function Card({ title, question, component, children, onEvidence }) {
  return <article className={`fingerprint-card state-${component.state.toLowerCase()}`} aria-labelledby={`fp-${title}`}>
    <header><h3 id={`fp-${title}`}>{title}</h3><span className="state-badge">{STATE_TEXT[component.state] || component.state}</span></header>
    <p className="fp-question">{question}</p>
    <strong className="fp-value">{component.label || "—"}</strong>
    <p>{component.summary}</p>
    <p className="fp-reason">{component.reason}</p>
    {component.next_action && <p className="fp-next"><strong>Next:</strong> {component.next_action}</p>}
    <EvidenceButtons ids={component.value != null ? component.evidence_ids : []} onEvidence={onEvidence} />
    {children}
  </article>;
}

export function LegalChangeFingerprint({ fingerprint, legacy, onEvidence, open = false }) {
  if (!fingerprint) return null;
  const { wording_drift: wording, rule_drift: rule, outcome_drift: outcome } = fingerprint;
  return <section className="fingerprint" aria-labelledby="fingerprint-heading">
    <div className="fingerprint-heading"><span className="section-kicker">Legal Change Fingerprint</span>
      <h2 id="fingerprint-heading">Three separate measures of this change</h2>
      <p className="panel-note">{fingerprint.note}</p></div>
    <div className="fingerprint-grid">
      <Card title="Wording drift" question="Which exact words changed?" component={wording} onEvidence={onEvidence}>
        {wording.details?.spans && <WordingDetails details={wording.details} legacy={legacy} open={open} />}
      </Card>
      <Card title="Rule drift" question="Which obligation, deadline, amount or actor changed?" component={rule} onEvidence={onEvidence}>
        {rule.details?.fields && <RuleDetails details={rule.details} open={open} />}
      </Card>
      <Card title="Outcome drift" question="Does this change the answer for your facts?" component={outcome} onEvidence={onEvidence}>
        {(outcome.details?.evaluated?.length > 0 || outcome.details?.controlled_scenarios) && <OutcomeDetails details={outcome.details} open={open} />}
      </Card>
    </div>
  </section>;
}

function WordingDetails({ details, legacy, open }) {
  return <details className="fp-details" open={open}>
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
    {details.before_clause && <ClausePair details={details} />}
    {legacy && <div className="fp-legacy">{legacy}</div>}
  </details>;
}

function RuleDetails({ details, open }) {
  const rows = details.fields.filter((row) => row.operation !== "ABSENT");
  return <details className="fp-details" open={open}>
    <summary>Rule delta and score</summary>
    {details.unscored_reason ? <p><strong>No score:</strong> the changed words are not one of the supported rule fields, so no number is given.</p>
      : <p><strong>Score:</strong> {details.formula}: {details.calculation}{details.lower_bound ? " (some changes are not captured by a supported field)" : ""}.</p>}
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

function OutcomeDetails({ details, open }) {
  const controlled = details.controlled_scenarios;
  return <details className="fp-details" open={open}>
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

// The exact clauses that were scored: changed spans at their recorded offsets, and optionally one rule field's spans <mark>ed.
export function ClausePair({ details, highlight, sources }) {
  const render = (text, side) => {
    const ranges = (details.spans || []).map((span) => [...span[`${side}_offsets`], "diff"])
      .concat((highlight?.[side] || []).map(([start, end]) => [start, end, "mark"])).filter(([start, end]) => end > start);
    const cuts = [...new Set([0, text.length, ...ranges.flatMap(([start, end]) => [start, end])])].filter((n) => n >= 0 && n <= text.length).sort((x, y) => x - y);
    const out = []; let group = null;
    cuts.slice(0, -1).forEach((start, index) => {
      const end = cuts[index + 1];
      const piece = text.slice(start, end);
      const within = (kind) => ranges.some(([a, b, k]) => k === kind && a <= start && end <= b);
      const node = <Fragment key={start}>{within("diff") ? (side === "before" ? <del>{piece}</del> : <ins>{piece}</ins>) : piece}</Fragment>;
      if (within("mark")) { if (!group) { group = []; out.push(<mark key={`m${start}`}>{group}</mark>); } group.push(node); }  // one continuous highlight
      else { group = null; out.push(node); }
    });
    return out;
  };
  return <article className="panel clause-pair" aria-labelledby="clause-pair-heading">
    <span className="section-kicker">Scored text</span><h3 id="clause-pair-heading" tabIndex={-1}>Whole clauses compared, changed words marked</h3>
    {highlight?.label && <p className="highlight-note" role="status">Highlighted: the words behind <strong>{highlight.label}</strong>.</p>}
    <div className="compare-grid">
      <section aria-label="Clause before"><h4>Before</h4><p className="panel-note">{details.before_kind}</p><p className="compare-text">{render(details.before_clause, "before")}</p>{sources?.before}</section>
      <section aria-label="Clause after"><h4>After</h4><p className="panel-note">{details.after_kind}</p><p className="compare-text">{render(details.after_clause, "after")}</p>{sources?.after}</section>
    </div>
  </article>;
}
