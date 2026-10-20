import { useEffect, useState } from "react";
import ComparisonPanel from "./ComparisonPanel";
import { EvidenceList } from "./Determinations";
import { ClausePair } from "./Fingerprint";
import { ScoreExplanation } from "./ResultInsights";
import { DriftPanel } from "./SharedPanels";

// The standalone "Drift explanation" (#drift) and "Score calculation" (#calculation) pages, after the v0.13.0 design
// (commit 6db1c49). Both read the SAME stored analysis as the assistant; every number comes from the API, nothing is
// recomputed here. Scores shown: legal-change-fingerprint-v1.2 (wording and rule drift) and the tlds-v1 combined indicator.
export const OPERATION = { ADDED: "added", REMOVED: "removed", CHANGED: "changed", UNCHANGED: "unchanged", ABSENT: "not present", UNCERTAIN: "uncertain" };
export const DIAGNOSTIC_NOTE = "Change diagnostics; wording, rule and situation change are measured separately: not legal correctness, not a confidence probability, not materiality and not risk.";
export const fieldLabel = (row) => row.label || row.field.replaceAll("_", " ");
export const quoted = (values) => (values?.length ? values.map((value) => `“${value}”`).join(" / ") : "—");
const ROLE = {
  current_consolidated_text: "current consolidated text", substitution_footnote: "India Code footnote", reconstructed_earlier_wording: "earlier wording reconstructed from the footnote",
  amendment_instruction: "amendment instruction", before_fragment: "before fragment derived from the instruction", after_fragment: "after fragment derived from the instruction",
  act_text_excerpt: "Act text excerpt",
};
// Three readable levels over the method's own provisional bands (names and ranges come from the stored analysis).
const LEVELS = [["low", "Low", ["Very low", "Low"], "Little measured movement. Still read the rule fields: a small edit can change a deadline or a duty."],
  ["medium", "Moderate", ["Moderate"], "A noticeable change; review the cited clauses carefully."],
  ["high", "High", ["High", "Very high"], "Substantial movement; it still needs legal and applicability review."]];

export function EmptyState({ title, children }) {
  return <div className="empty-state" role="status"><strong>{title}</strong><p>{children}</p></div>;
}

export function EvidenceButtons({ ids, onEvidence, label = "Evidence" }) {
  if (!ids?.length) return null;
  return <p className="evidence-chips">{label}: {ids.map((id) => <button key={id} type="button" onClick={() => onEvidence(id)} aria-label={`Show evidence ${id}`}>{id}</button>)}</p>;
}

export function NoChangeScores({ analysis }) {
  if (!analysis.question_frame?.asks_about_versions) {
    return <EmptyState title="No change to explain">This question asks about the law as written, so no two versions are compared and no change scores exist.</EmptyState>;
  }
  return <EmptyState title="The change could not be measured">{analysis.fingerprint?.wording_drift?.reason || analysis.comparison?.support_reason
    || "No supported before/after versions were found."} Nothing is scored, so no number is shown.</EmptyState>;
}

export function ProvisionDetails({ analysis }) {
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

// Where one side of the compared clause comes from: document, page/line, verbatim or derived, and text quality.
function SideSource({ analysis, side, onEvidence }) {
  const id = analysis.comparison?.[side]?.evidence_id;
  const item = (analysis.evidence || []).find((row) => row.evidence_id === id);
  if (!item) return <p className="panel-note">Source: not recorded for this side.</p>;
  return <p className="side-source">
    <strong>{item.act_name}</strong>{item.page ? ` · page ${item.page}` : ""}{item.line ? `, line ${item.line}` : ""} · {ROLE[item.role] || item.role?.replaceAll("_", " ")}
    {" · "}{item.verbatim === false ? <span className="kind-badge">Derived, not verbatim</span> : "verbatim"}
    {item.text_reliability === "UNRELIABLE_TEXT_LAYER" && <span className="evidence-warning"> Unreliable text layer: check the PDF.</span>}
    {" "}<button type="button" className="link-button" onClick={() => onEvidence(item.evidence_id)} aria-label={`Show evidence ${item.evidence_id}`}>{item.evidence_id}</button>
    {item.pdf_url && <> · <a href={item.pdf_url} target="_blank" rel="noreferrer">PDF{item.page ? ` p. ${item.page}` : ""} ↗</a></>}
  </p>;
}

function PageHeader({ analysis, kicker, title, children, onAssistant }) {
  return <div className="section-header page-intro"><span className="section-kicker">{kicker} · analysis {analysis.analysis_id}</span><h2>{title}</h2>
    <p><strong>Question:</strong> {analysis.query}</p>{children}
    <p><button type="button" className="link-button" onClick={() => onAssistant()}>← Back to the answer</button></p></div>;
}

// ---------- #drift ----------
export function DriftExplanationPage({ analysis, highlight, onField, onEvidence, onAssistant, onCalculation, onPage }) {
  const fp = analysis.fingerprint || {};
  const wording = fp.wording_drift, rule = fp.rule_drift, outcome = fp.outcome_drift, tlds = fp.tlds;
  const header = <PageHeader analysis={analysis} kicker="Drift explanation" title="What the drift score means" onAssistant={onAssistant}>
    <p>These measures describe movement between two versions of one clause. They do not by themselves prove legal materiality or correctness.</p></PageHeader>;
  if (!analysis.question_frame?.asks_about_versions || wording?.value == null) {
    return <section className="page-section drift-page">{header}<NoChangeScores analysis={analysis} /><EvidenceList evidence={analysis.evidence} /></section>;
  }
  const changed = (rule?.details?.fields || []).filter((row) => row.contribution);
  const legal = tlds?.components?.legal_effect;
  const hidden = tlds?.value != null && legal?.value >= 0.5 && ["Very low", "Low"].includes(tlds.band);
  const bands = tlds?.bands || [];
  const range = (names) => {
    const index = bands.findIndex(([, name]) => name === names[0]);
    const last = bands.findIndex(([, name]) => name === names[names.length - 1]);
    if (index < 0 || last < 0) return null;
    return `${bands[index][0]}–${last + 1 < bands.length ? (bands[last + 1][0] - 0.1).toFixed(1) : 100}`;  // bands apply to the value rounded to 0.1
  };
  const tiles = [
    ["Wording drift", wording.label, "How much of the clause's surface wording moved (lexical and feature-hash measures)."],
    ["Rule drift", rule?.label || "Not scored", rule?.value != null ? "Weighted sum of the legal-rule fields that changed." : rule?.reason],
    ...(legal ? [["Legal-effect drift", legal.value != null ? legal.value.toFixed(2) : "Missing", legal.details?.level || legal.reason]] : []),
    ...(tlds && tlds.state !== "NOT_APPLICABLE" ? [["Combined indicator (TLDS)", tlds.value != null ? tlds.value.toFixed(1) : "Incomplete",
      tlds.value != null ? "0.2 × textual + 0.3 × semantic + 0.4 × legal effect + 0.1 × rule structure, on a 0–100 scale." : `Missing: ${tlds.missing_components.join(", ").replaceAll("_", " ")}.`, tlds.band]] : []),
  ];
  return <section className="page-section drift-page">
    {header}
    {bands.length > 0 && <div className="level-guide" aria-label="How to read the combined indicator">
      {LEVELS.map(([tone, name, members, text]) => <article key={tone} className={tone}><strong>{name}</strong>
        <b>{range(members)} · {members.join(" and ")}</b><p>{text}</p></article>)}
    </div>}
    {bands.length > 0 && <p className="panel-note">{tlds.bands_note} Bands apply to the combined indicator only.</p>}
    <article className="drift-breakdown" aria-labelledby="drift-classification"><span className="section-kicker">Calculated classification</span>
      <h3 id="drift-classification">{tlds?.value != null ? `${tlds.band} combined drift (${tlds.label})` : "Combined indicator incomplete: read the separate measures"}</h3>
      <div className="drift-score-grid">{tiles.map(([label, value, detail, band]) => <div key={label}><span>{label}</span><strong>{value}</strong>
        {band && <b className={`level-pill ${LEVELS.find(([, , members]) => members.includes(band))?.[0] || "low"}`}>{band}</b>}<p>{detail}</p></div>)}</div>
      {hidden && <p className="warning-note" role="note"><strong>Read legal effect on its own.</strong><span>The combined score is {tlds.band.toLowerCase()}, but legal-effect drift is {legal.value.toFixed(2)}. {legal.reason}</span></p>}
      {(fp.reading || []).filter((item) => item.kind === "disagreement").map((item) => <p key={item.text} className="warning-note" role="note"><strong>Wording and rule disagree.</strong><span>{item.text}</span></p>)}
      <p className="panel-note">{DIAGNOSTIC_NOTE} <button type="button" className="link-button" onClick={onCalculation}>See the worked calculation →</button>
        {onPage && <button type="button" className="link-button" onClick={() => onPage("comparison")}>View detailed clause comparison →</button>}</p>
    </article>
    <ClausePair details={wording.details} highlight={highlight}
      sources={{ before: <SideSource analysis={analysis} side="before" onEvidence={onEvidence} />, after: <SideSource analysis={analysis} side="after" onEvidence={onEvidence} /> }} />
    <article className="difference-evidence" aria-labelledby="drift-changes"><span className="section-kicker">Detected change</span><h3 id="drift-changes">How the two clauses differ</h3>
      <ul className="span-list">{(wording.details?.spans || []).map((span, index) => <li key={index}>
        {span.operation === "added" ? <>Inserted <ins>{span.after_text}</ins></> : span.operation === "removed" ? <>Removed <del>{span.before_text}</del></>
          : <><del>{span.before_text}</del> → <ins>{span.after_text}</ins></>}</li>)}</ul>
      {changed.length > 0 ? <ul className="field-list">{changed.map((row) => <li key={row.field}>
        <strong>{fieldLabel(row)}</strong> {OPERATION[row.operation] || row.operation}: {quoted(row.before)} → {quoted(row.after)}
        {row.why && <span className="field-why">Why it matters: it {row.why}.</span>}
        <button type="button" className="link-button" onClick={() => onField(row)}>Show these words in the clause</button></li>)}</ul>
        : <p className="limit-note"><strong>No rule field scored.</strong> {rule?.reason}</p>}
      {(rule?.details?.structural_changes || []).length > 0 && <p className="panel-note">Structure: {rule.details.structural_changes.map((item) => item.value).join("; ")}. A list item or Explanation changes what the rule covers.</p>}
      <p className="panel-note"><strong>Your situation (separate):</strong> {outcome?.value != null ? outcome.summary
        : outcome?.limit?.kind === "facts" ? <>it depends on your facts. <button type="button" className="link-button" onClick={() => onAssistant("scenario")}>Check your situation</button></> : outcome?.reason}</p>
    </article>
    <ProvisionDetails analysis={analysis} />
    <EvidenceList evidence={analysis.evidence} />
  </section>;
}

// ---------- #calculation ----------
const PARTS = [["textual", "Textual (T)"], ["semantic", "Semantic stand-in (S)"], ["legal_effect", "Legal effect (L)"], ["rule_structure", "Rule structure (R)"]];
const NAME = Object.fromEntries(PARTS);
const WEIGHTING = { default: "Current weights", equal: "Equal weights", legal_heavy: "Legal-effect heavy", wording_heavy: "Wording heavy" };
const pct = (value) => (value == null ? "missing" : value.toFixed(3));

// The combined indicator, worked through: each component's value × weight = points, the inputs behind it, why the weights are
// what they are, and how much the band depends on them. Every number comes from the stored analysis or the versioned method file.
function CombinedWeights({ tlds, wording, rule, method, onEvidence, onField }) {
  const legal = tlds.components?.legal_effect;
  const hidden = tlds.value != null && legal?.value >= 0.5 && ["Very low", "Low"].includes(tlds.band);
  const split = tlds.disagreement;
  const changed = (rule?.details?.fields || []).filter((row) => row.contribution);
  const inputs = {
    textual: <EvidenceButtons ids={wording.evidence_ids} onEvidence={onEvidence} label="Whole clauses from" />,
    semantic: <EvidenceButtons ids={wording.evidence_ids} onEvidence={onEvidence} label="Whole clauses from" />,
    legal_effect: changed.length ? changed.map((row) => <button key={row.field} type="button" className="link-button" onClick={() => onField(row)}
      aria-label={`Show the words behind legal effect: ${fieldLabel(row)}`}>{fieldLabel(row)}</button>) : <span>No rule field scored</span>,
    rule_structure: (() => { const d = tlds.components?.rule_structure?.details || {};
      return d.added || d.removed ? <span>{(d.removed || []).length} removed · {(d.added || []).length} added · {d.shared} unchanged elements</span> : <span>—</span>; })(),
  };
  return <article className="calculation-card" aria-labelledby="calc-tlds"><span className="section-kicker">Combined indicator · {tlds.version}</span>
    <h3 id="calc-tlds">{tlds.value != null ? `Why the combined score is ${tlds.value.toFixed(1)} (${tlds.band})` : "Why there is no combined score"}</h3>
    {split?.strong && <p className="warning-note" role="note"><strong>The components disagree.</strong><span>{NAME[split.highest]} is {tlds.components[split.highest].value.toFixed(2)} but {NAME[split.lowest]} is {tlds.components[split.lowest].value.toFixed(2)}.
      The combined score is a weighted sum, so it sits between them; read each component rather than the total alone.</span></p>}
    {hidden && <p className="warning-note" role="note"><strong>Read legal effect on its own.</strong><span>The combined score is {tlds.band.toLowerCase()}, but legal-effect drift is {legal.value.toFixed(2)}. {legal.reason}</span></p>}
    <p className="formula-display">{tlds.formula}</p>
    <div className="table-scroll" role="region" aria-label="Combined score worked calculation" tabIndex={0}><table className="fp-table weights-table">
      <caption>Each component: value × weight × 100 = points</caption>
      <thead><tr><th scope="col">Component</th><th scope="col">What it measures</th><th scope="col">Value (0–1)</th><th scope="col">Weight</th><th scope="col">Points</th><th scope="col">Inputs from</th></tr></thead>
      <tbody>{PARTS.map(([key, label]) => { const part = tlds.components?.[key] || {}; const points = tlds.contributions?.[key];
        return <tr key={key} className={part.value == null ? "missing" : ""}><th scope="row">{label}</th>
          <td>{method?.components?.[key]?.measures || part.reason}</td><td>{pct(part.value)}</td><td>{tlds.weights?.[key]}</td>
          <td>{part.value == null ? "not counted" : points != null ? points.toFixed(1) : "not recorded"}</td><td>{inputs[key]}</td></tr>; })}</tbody>
      {tlds.calculation && <tfoot><tr><th scope="row">Total</th><td colSpan={5}><code>{tlds.value != null ? "" : "Partial, not comparable with complete scores: "}{tlds.calculation}</code></td></tr></tfoot>}
    </table></div>
    {!tlds.contributions && <p className="panel-note">This stored analysis predates tlds-v1.1, so its points per component were not recorded; the total and each value above are as stored.</p>}
    {tlds.value == null && <p className="limit-note"><strong>Incomplete: no combined score.</strong> Missing: {tlds.missing_components.map((m) => NAME[m] || m).join(", ")}.
      A missing component is never counted as 0, so the total is withheld; any partial value is shown separately and must not be compared with complete scores.</p>}
    <details className="fold" open={false}><summary>Why the weights are 0.2, 0.3, 0.4 and 0.1</summary>
      {method?.components ? <><p>{method.weights_status}</p>
        <ul>{PARTS.map(([key, label]) => <li key={key}><strong>{label}:</strong> {method.components[key]?.why_this_weight}</li>)}</ul></>
        : <p className="panel-note">{method === false ? "The method description could not be loaded." : "Loading the method description…"}</p>}
    </details>
    {method?.sensitivity && <details className="fold sensitivity"><summary>How much the band depends on the weights</summary>
      <p>{method.sensitivity.finding}</p>
      <div className="table-scroll" role="region" aria-label="Weight sensitivity on held-out changes" tabIndex={0}><table className="fp-table">
        <caption>{method.sensitivity.complete} held-out changes with a complete score, under four weightings (T / S / L / R)</caption>
        <thead><tr><th scope="col">Weighting</th><th scope="col">Weights</th><th scope="col">Bands</th><th scope="col">Material legal effect but Low</th><th scope="col">Order vs current (Spearman)</th></tr></thead>
        <tbody>{Object.entries(method.sensitivity.weightings).map(([name, row]) => <tr key={name}><th scope="row">{WEIGHTING[name] || name}</th>
          <td>{PARTS.map(([key]) => row.weights[key]).join(" / ")}</td><td>{Object.entries(row.bands).map(([band, n]) => `${band} ${n}`).join(", ")}</td>
          <td>{row.legal_effect_material_but_band_low}</td><td>{row.spearman_vs_default}</td></tr>)}</tbody></table></div>
      <p className="panel-note">Source: <code>{method.sensitivity.source}</code>. The weights were not changed to improve these numbers.</p>
    </details>}
    <p className="panel-note"><strong>What this score is not:</strong> it is not legal accuracy, not the materiality of the amendment, not compliance risk and not a probability.
      It measures how much two versions of one clause differ, using choices that have not been validated against expert labels. {tlds.bands_note}</p>
  </article>;
}

function Row({ name, inputs, formula, calculation, value, children }) {
  return <div className="calculation-row"><div><strong>{name}</strong>{inputs && <span>{inputs}</span>}{formula && <code>{formula}</code>}
    {calculation && <code>Worked: {calculation}</code>}{children}</div><b>{value}</b></div>;
}

function Clause({ analysis, side, details, onEvidence }) {
  return <article aria-label={`Compared ${side} clause`}><strong>{side === "before" ? "Before clause compared" : "After clause compared"}</strong>
    <h3>{details[`${side}_kind`]}</h3>
    <p className="clause-text">{details[`${side}_clause`]}</p>
    <SideSource analysis={analysis} side={side} onEvidence={onEvidence} />
    {details.clause_sha256?.[side] && <p className="panel-note">SHA-256 of the scored text: <code>{details.clause_sha256[side].slice(0, 16)}…</code></p>}
  </article>;
}

export function ScoreCalculationPage({ analysis, onField, onEvidence, onAssistant, request }) {
  const [method, setMethod] = useState(null);  // the method as configured, with the held-out sensitivity (GET /api/methods/tlds)
  useEffect(() => { request?.("/api/methods/tlds").then(setMethod).catch(() => setMethod(false)); }, [request]);
  const fp = analysis.fingerprint || {};
  const wording = fp.wording_drift, rule = fp.rule_drift, outcome = fp.outcome_drift, tlds = fp.tlds;
  const header = <PageHeader analysis={analysis} kicker="Score calculation" title="How these percentages were calculated" onAssistant={onAssistant}>
    <p>You supplied only this question. The backend selected the provision by Act and section identity and compared the two clauses below; no before/after passage was typed in.
      Every number is read from the stored analysis ({fp.version}{tlds ? `, ${tlds.version}` : ""}); this page computes nothing.</p></PageHeader>;
  if (!analysis.question_frame?.asks_about_versions || wording?.value == null) {
    return <section className="page-section calculation-page">{header}<NoChangeScores analysis={analysis} /></section>;
  }
  const w = wording.details || {};
  const rows = rule?.details?.fields || [];
  const controlled = outcome?.details?.controlled_scenarios;
  return <section className="page-section calculation-page">
    {header}
    <div className="calculation-sources">
      <Clause analysis={analysis} side="before" details={w} onEvidence={onEvidence} />
      <Clause analysis={analysis} side="after" details={w} onEvidence={onEvidence} />
    </div>
    <article className="calculation-card"><span className="section-kicker">Why these clauses</span>
      <h3>Question → Act and section → {analysis.comparison?.support_class === "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION" ? "footnote reconstruction" : "corroborated amendment"}</h3>
      <p>{analysis.comparison?.support_reason}</p>
      <p className="panel-note">The whole aligned clause is compared, not a search excerpt. Normalised first: {(w.normalisation || []).join("; ")}. Generic and Specific modes use the same clauses and numbers.</p>
    </article>
    <article className="calculation-card" aria-labelledby="calc-values"><span className="section-kicker">Backend values and formulas</span><h3 id="calc-values">The separate measures</h3>
      <div className="calculation-rows">
        <Row name={`Wording drift · ${wording.method}`} value={wording.label}
          inputs={w.inputs ? `lexical drift ${w.inputs.lexical_drift_percent}% · feature-vector drift ${w.inputs.feature_vector_drift_percent}% (deterministic token hashes, not a pretrained semantic model)` : (w.flag === "IDENTICAL" ? "identical text" : "formatting, punctuation or spelling only")}
          formula={w.formula} calculation={w.calculation} />
        <Row name={`Rule drift · ${rule?.method}`} value={rule?.label || "Not scored"} formula={rule?.details?.formula} calculation={rule?.details?.calculation}
          inputs={rule?.value == null ? rule?.reason : "Each changed rule field adds its weight; see the table below."} />
      </div>
      <div className="table-scroll" role="region" aria-label="Rule field table" tabIndex={0}><table className="fp-table"><caption>Each rule field, its weight and what it adds</caption>
        <thead><tr><th scope="col">Field</th><th scope="col">Before</th><th scope="col">After</th><th scope="col">Change</th><th scope="col">Weight</th><th scope="col">Adds</th><th scope="col"><span className="sr-only">Evidence</span></th></tr></thead>
        <tbody>{rows.map((row) => <tr key={row.field} className={row.contribution ? "contributes" : ""}><th scope="row">{fieldLabel(row)}</th>
          <td>{quoted(row.before)}</td><td>{quoted(row.after)}</td><td>{OPERATION[row.operation] || row.operation}</td><td>{row.weight}</td><td>{row.contribution}</td>
          <td>{(row.before_spans?.length || row.after_spans?.length) ? <button type="button" className="link-button" onClick={() => onField(row)} aria-label={`Show the words for ${fieldLabel(row)}`}>Show</button> : null}</td></tr>)}</tbody>
      </table></div>
      <p className="panel-note">Weights: <code>{rule?.details?.weights_config}</code>.{rule?.details?.lower_bound ? " Uncertain fields are excluded, so the total is a lower bound." : ""}</p>
      <EvidenceButtons ids={wording.evidence_ids} onEvidence={onEvidence} label="Scored from" />
    </article>
    {tlds && tlds.state !== "NOT_APPLICABLE" && <CombinedWeights tlds={tlds} wording={wording} rule={rule} method={method} onEvidence={onEvidence} onField={onField} />}
    <article className="calculation-card" aria-labelledby="calc-outcome"><span className="section-kicker">Your situation (separate)</span><h3 id="calc-outcome">Outcome drift: {outcome?.label || "—"}</h3>
      {outcome?.details?.evaluated?.length > 0 ? <div className="table-scroll" role="region" aria-label="Facts under each version" tabIndex={0}><table className="fp-table"><caption>Your stated facts under each version</caption>
        <thead><tr><th scope="col">Rule field</th><th scope="col">Your fact</th><th scope="col">Before</th><th scope="col">After</th><th scope="col">Flips?</th></tr></thead>
        <tbody>{outcome.details.evaluated.map((row, index) => <tr key={index}><th scope="row">{row.field.replaceAll("_", " ")}</th><td>{row.decisive_fact}</td>
          <td>{row.before_answer}</td><td>{row.after_answer}</td><td>{row.changed ? "Yes" : "No"}</td></tr>)}</tbody></table></div>
        : <p>{outcome?.value == null ? outcome?.reason : outcome?.summary}</p>}
      {outcome?.details?.assumptions?.length > 0 && <p className="panel-note"><strong>Stated assumptions:</strong> {outcome.details.assumptions.join("; ")}.</p>}
      {controlled && <p className="panel-note"><strong>Hypothetical boundary values (not your facts):</strong> {controlled.flips} of {controlled.evaluated} generated
        {" "}{controlled.field.replaceAll("_", " ")} values ({controlled.values_tested.join(", ")} {controlled.unit}) flip = {controlled.percent}%. {controlled.definition}.</p>}
      <p className="panel-note">Not part of any drift score above. Outcome change is not risk.</p>
    </article>
    {analysis.metrics && <details className="legacy-diagnostic"><summary>Legacy diagnostic (drift-metrics-v3): superseded, not the combined indicator</summary>
      <p className="panel-note">{analysis.metrics.legacy_diagnostic?.note} It is computed on amendment fragments and kept only for comparison with earlier releases.</p>
      <DriftPanel metrics={analysis.metrics} legacy /><ScoreExplanation metrics={analysis.metrics} /></details>}
    <p className="research-note">These calculations measure text and rule-field movement between two versions. They are not probabilities, legal correctness scores or legal advice. Legal validation: UNVERIFIED.</p>
  </section>;
}

// ---------- #comparison ----------
const SUPPORTED = new Set(["GRAPH_TRANSITION_FRAGMENTS", "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION"]);
const SUPPORT_STATUS = {
  GRAPH_TRANSITION_FRAGMENTS: "Corroborated amendment fragments from the temporal graph (not complete historical sections)",
  CONSOLIDATED_FOOTNOTE_RECONSTRUCTION: "Earlier wording reconstructed from India Code's own footnote (derived, not verbatim)",
};

// The stored comparison record, side by side, with where each side comes from. Nothing is recalculated here.
export function ComparisonPage({ analysis, onField, onEvidence, onAssistant, onPage }) {
  const comparison = analysis.comparison || {};
  const supported = SUPPORTED.has(comparison.support_class);
  const rule = analysis.fingerprint?.rule_drift;
  const changed = (rule?.details?.fields || []).filter((row) => row.contribution);
  const links = <p className="page-links"><button type="button" className="link-button" onClick={() => onPage("drift")}>Drift explanation →</button>
    <button type="button" className="link-button" onClick={() => onPage("calculation")}>Score calculation →</button></p>;
  if (!supported) {
    const reasons = comparison.abstention_reasons || [];
    return <section className="page-section comparison-page">
      <PageHeader analysis={analysis} kicker="Clause comparison" title="No before and after to compare" onAssistant={onAssistant} />
      <article className="calculation-card" aria-labelledby="no-pair"><span className="section-kicker">Why there is no comparison</span>
        <h3 id="no-pair">{analysis.question_frame?.asks_about_versions ? "No supported pair of versions was found" : "This question is not about a change"}</h3>
        <p>{analysis.version_evidence?.reason || comparison.support_reason || "The question asks about the law as written, so no two versions are compared."}</p>
        {reasons.length > 0 && <p className="panel-note">Recorded reasons: {reasons.map((code) => code.toLowerCase().replaceAll("_", " ")).join("; ")}.</p>}
        <p className="panel-note">Two excerpts that are not shown to be versions of the same provision are never presented as before and after.</p>
      </article>
      <EvidenceList evidence={analysis.evidence} />
    </section>;
  }
  return <section className="page-section comparison-page">
    <PageHeader analysis={analysis} kicker="Clause comparison" title="Before and after, side by side" onAssistant={onAssistant}>{links}</PageHeader>
    <ProvisionDetails analysis={analysis} />
    <p className="selection-note"><strong>Evidence status:</strong> {SUPPORT_STATUS[comparison.support_class]}
      {analysis.version_evidence?.relation_verification ? ` · amendment relation: ${analysis.version_evidence.relation_verification.replaceAll("_", " ").toLowerCase()}` : ""} · legal validation: unverified.</p>
    <ComparisonPanel comparison={comparison} full />
    <article className="calculation-card" aria-labelledby="rule-changes"><span className="section-kicker">Legal-rule fields</span><h3 id="rule-changes">What changed in the legal instruction</h3>
      {changed.length > 0 ? <ul className="field-list">{changed.map((row) => <li key={row.field}>
        <strong>{fieldLabel(row)}</strong> {OPERATION[row.operation] || row.operation}: {quoted(row.before)} → {quoted(row.after)}
        {row.why && <span className="field-why">Why it matters: it {row.why}.</span>}
        <button type="button" className="link-button" onClick={() => onField(row)}>Show these words in the clause</button></li>)}</ul>
        : <p>{rule?.reason || "No rule field was scored for this change."}</p>}
    </article>
    <EvidenceList evidence={analysis.evidence} />
    {links}
  </section>;
}
