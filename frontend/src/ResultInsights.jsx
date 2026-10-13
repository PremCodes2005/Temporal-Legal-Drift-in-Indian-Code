// Response-specific status, separate indicators and the score explanation.
// Every value shown here comes from the current API response; nothing is recomputed in the browser.

const PAIRING_TEXT = {
  GRAPH_TRANSITION_FRAGMENTS: "Amendment fragments from a machine-checked transition (not complete sections).",
  CONSOLIDATED_FOOTNOTE_RECONSTRUCTION: "Earlier wording reconstructed from India Code's footnote; current consolidated text on the right.",
  UNALIGNED_EXCERPTS: "Only excerpts: the two texts are not shown to be the same provision.",
  AMBIGUOUS_CANDIDATES: "Several amendments could match; none is chosen.",
};
const TEMPORAL_TEXT = {
  EFFECTIVE_DATE_EVIDENCED: "Effective date evidenced (Act-wide basis)",
  FOOTNOTE_STATED_DATE_UNVERIFIED: "Date printed in the India Code footnote (unverified)",
  UNRESOLVED: "Effective date unresolved",
};

export function GenerationNotice({ method }) {
  const text = method === "grounded_composition"
    ? "Answer composed directly from the cited evidence; no language model was used."
    : String(method || "").startsWith("extractive")
    ? "Extractive evidence summary: quoted from retrieved sources, not a language-model conclusion."
    : method === "llm_grounded" ? "Language-model answer constrained to the retrieved evidence; verify it against the cited source."
      : "No answer could be generated from the available evidence.";
  return <p className="generation-method" role="status">{text}</p>;
}

export function VersionStatus({ comparison, metrics }) {
  if (!comparison || comparison.support_class === "NOT_A_COMPARISON") {
    return <p className="version-status" role="note"><strong>Legal-version status:</strong> not a version comparison. The answer summarises the retrieved document; no before/after versions were identified.</p>;
  }
  const temporal = metrics?.reliability?.temporal_certainty;
  const warnings = [];
  if (comparison.support_class === "GRAPH_TRANSITION_FRAGMENTS") warnings.push("Only amendment fragments are available, not complete historical sections.");
  if (comparison.support_class === "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION") warnings.push("The 'after' text is the current consolidated version; it is not proven to be the text in force on a particular past date.");
  if (["UNALIGNED_EXCERPTS", "AMBIGUOUS_CANDIDATES"].includes(comparison.support_class)) warnings.push("Evidence is incomplete, so no change is asserted and no score is given.");
  return <div className="version-status" role="note">
    <p><strong>Legal-version status:</strong> {PAIRING_TEXT[comparison.support_class] || comparison.support_class}{temporal ? ` ${TEMPORAL_TEXT[temporal.status] || temporal.status}${temporal.date ? `: ${temporal.date}` : ""}.` : ""}</p>
    {warnings.map((text) => <p className="version-warning" key={text}>{text}</p>)}
  </div>;
}

export function IndicatorStrip({ metrics, comparison }) {
  const drift = metrics?.overall_drift_percent;
  const tiles = [
    ["Textual drift", drift == null ? "Unavailable" : `${drift}%`, drift == null ? "No aligned pair to measure." : "How much the compared wording moved (not legal significance)."],
    ["Materiality", comparison?.materiality_status === "NOT_ASSESSED_IN_QUERY_FLOW" || !comparison ? "Not assessed" : comparison.materiality_status, "Legal significance is triaged separately and needs review."],
    ["Answer change", "Not determined", "Whether your situation is answered differently needs the applicable version and your facts."],
    ["Risk", "Not assessed", "Use the compliance-risk view with scenario facts; drift is never a risk input."],
  ];
  return <section className="indicator-strip" aria-label="Separate indicators">{tiles.map(([label, value, help]) =>
    <div className="indicator" key={label}><span>{label}</span><strong>{value}</strong><small>{help}</small></div>)}</section>;
}

export function ScoreExplanation({ metrics }) {
  if (!metrics?.calculation_trace || metrics.overall_drift_percent == null) return null;
  const trace = metrics.calculation_trace;
  const basis = metrics.score_basis || {};
  const rows = [
    ["Vector (feature-hash)", metrics.semantic_drift_percent, `${trace.semantic.formula}; cosine similarity ${trace.semantic.cosine_similarity_percent}%`, trace.overall.weighted_square_contributions.semantic],
    ["Lexical", metrics.lexical_drift_percent, `${trace.lexical.formula}; Jaccard ${trace.lexical.jaccard_similarity_percent}%, sequence ${trace.lexical.sequence_similarity_percent}%`, trace.overall.weighted_square_contributions.lexical],
    ["Conceptual", metrics.conceptual_drift_percent, `${metrics.conceptual_method}: cues before [${(trace.conceptual.pre_legal_cues || []).join(", ")}], after [${(trace.conceptual.post_legal_cues || []).join(", ")}]`, trace.overall.weighted_square_contributions.conceptual],
  ];
  return <details className="score-explanation">
    <summary>How this score was calculated</summary>
    <p className="panel-note">Contract {metrics.metrics_contract_version}. Computed from the exact excerpts below for this response only.</p>
    <table><caption className="sr-only">Score components</caption><thead><tr><th scope="col">Component</th><th scope="col">Score</th><th scope="col">Inputs and formula</th><th scope="col">Weighted square</th></tr></thead>
      <tbody>{rows.map(([name, value, detail, contribution]) => <tr key={name}><th scope="row">{name}</th><td>{value}%</td><td>{detail}</td><td>{contribution}</td></tr>)}</tbody></table>
    <p><strong>Overall:</strong> {trace.overall.formula} = √{trace.overall.sum_of_weighted_squares} = {metrics.overall_drift_percent}%.</p>
    {metrics.component_disagreement && <p className="calculation-warning" role="alert">The components disagree by {metrics.component_spread_percent} points; read each one separately rather than the overall figure.</p>}
    {metrics.reliability && <p><strong>Reliability (not part of the score):</strong> pairing {metrics.reliability.pairing}; evidence {metrics.reliability.evidence_coverage}; date {metrics.reliability.temporal_certainty?.status}; retrieval relevance {metrics.reliability.retrieval_relevance}.</p>}
    {metrics.question_relevance && <p><strong>Does this answer your question?</strong> {metrics.question_relevance.status.replaceAll("_", " ").toLowerCase()}. {metrics.question_relevance.explanation}</p>}
    <div className="excerpt-pair"><blockquote><strong>Before (as compared)</strong><span>{basis.pre_excerpt}</span></blockquote><blockquote><strong>After (as compared)</strong><span>{basis.post_excerpt}</span></blockquote></div>
  </details>;
}
