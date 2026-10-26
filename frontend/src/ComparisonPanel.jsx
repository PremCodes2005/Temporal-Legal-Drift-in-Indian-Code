import { SCOPE_NOTE } from "./ResultInsights";

const SUPPORT_TEXT = {
  GRAPH_TRANSITION_FRAGMENTS: "Before/after wording of one amendment, taken from a machine-checked transition in the temporal graph. These are fragments, not complete sections.",
  CONSOLIDATED_FOOTNOTE_RECONSTRUCTION: "Earlier wording reconstructed from India Code's own substitution footnote in the same section. Check it against the official text.",
  UNALIGNED_EXCERPTS: "The amendment instruction and the Act text are not shown to be the same provision, so they are not presented as before/after versions and no drift score is calculated.",
  AMBIGUOUS_CANDIDATES: "More than one recorded amendment could match these texts, so none is chosen and no score is calculated.",
};
const VERSION_TEXT = {
  DERIVED_FROM_FOOTNOTE: "version reconstructed from the footnote",
  CURRENT_CONSOLIDATED_SECTION: "version: current consolidated text",
  AMENDMENT_CONTROLLED_FRAGMENT: "version: amendment fragment",
};
const ROLE_TEXT = {
  before_fragment: "Before (amendment fragment)",
  after_fragment: "After (amendment fragment)",
  reconstructed_earlier_wording: "Reconstructed earlier wording",
  current_consolidated_text: "Current consolidated text",
  amendment_instruction_excerpt: "Amendment instruction (excerpt)",
  available_act_text_excerpt: "Available Act text (excerpt)",
};
const REASON_TEXT = {
  PAIR_UNALIGNED: "The two excerpts are not aligned to the same provision.",
  SCORING_UNAVAILABLE: "No drift score: there is no aligned pair to measure.",
  SOURCE_TEXT_UNRELIABLE: "A cited source has an unreliable text layer; treat its wording as unverified.",
  MODEL_UNAVAILABLE: "The language model was unavailable; the answer is an extractive summary.",
  PAIR_AMBIGUOUS: "Several amendment candidates fit; none was chosen.",
};
const TOKEN = /([A-Za-z]+|\d+(?:\.\d+)?)/;

// Mark the tokens named by changed_spans, in order, without inserting any HTML.
export function markedTokens(text, spans, side) {
  const parts = String(text || "").split(TOKEN);
  const tokenIndexes = parts.map((part, index) => (index % 2 === 1 ? index : -1)).filter((index) => index >= 0);
  const marked = new Set();
  let cursor = 0;
  for (const span of spans) {
    const wanted = String(span[side] || "").split(/\s+/).filter(Boolean);
    if (!wanted.length) continue;
    for (let start = cursor; start + wanted.length <= tokenIndexes.length; start += 1) {
      if (wanted.every((word, offset) => parts[tokenIndexes[start + offset]].toLowerCase() === word.toLowerCase())) {
        wanted.forEach((_, offset) => marked.add(tokenIndexes[start + offset]));
        cursor = start + wanted.length;
        break;
      }
    }
  }
  return parts.map((part, index) => {
    if (!marked.has(index)) return part;
    return side === "before" ? <del key={index}>{part}</del> : <ins key={index}>{part}</ins>;
  });
}

function Pane({ side, data, spans, comparison }) {
  if (!data) return null;
  const derived = data.span_basis === "derived_text_not_a_verbatim_source_span";
  return <section className={`compare-pane ${derived ? "derived" : ""}`} aria-label={ROLE_TEXT[data.role] || data.role}>
    <header><strong>{ROLE_TEXT[data.role] || data.role}</strong>
      <span>{data.act_name || data.entry_id}{comparison.provision_path ? ` · ${comparison.provision_path.replace("section:", "section ")}` : ""}{data.page ? ` · page ${data.page}` : ""}</span>
      <span>{comparison.operation ? `Operation: ${comparison.operation.toLowerCase()}` : "Operation not established"}{data.document_version ? ` · ${VERSION_TEXT[data.document_version] || data.document_version.toLowerCase().replaceAll("_", " ")}` : ""}</span>
      {derived && <span className="derived-badge">Derived text — not a verbatim quote</span>}
      <span className="source-links">{data.local_pdf_url && <a href={data.local_pdf_url} target="_blank" rel="noreferrer">Open source PDF at page {data.page} ↗</a>}
        {data.source_url && <a href={data.source_url} target="_blank" rel="noreferrer">Official record ↗</a>}</span></header>
    {data.compared_text ? <p className="compare-text" tabIndex={0} aria-label={`${ROLE_TEXT[data.role] || data.role} text`}>{markedTokens(data.compared_text, spans, side)}</p>
      : <p className="panel-note">No aligned text was compared for this side.</p>}
  </section>;
}

export default function ComparisonPanel({ comparison, full = false, scope = true }) {
  if (!comparison || comparison.support_class === "NOT_A_COMPARISON") return null;
  const spans = comparison.changed_spans || [];
  return <article className={`panel comparison-panel ${full ? "full" : ""}`} aria-labelledby="comparison-heading">
    <span className="section-kicker">What was compared</span>
    <h3 id="comparison-heading">{comparison.support_class === "UNALIGNED_EXCERPTS" ? "Excerpts only — no aligned versions" : "Clause comparison"}</h3>
    <p>{SUPPORT_TEXT[comparison.support_class]}</p>
    {spans.length > 0 && <p className="compare-legend"><del>struck through</del> = removed · <ins>underlined</ins> = inserted · a struck word paired with an underlined word = changed · <span className="derived-badge">dashed border</span> = derived or uncertain text</p>}
    <div className="compare-grid"><Pane side="before" data={comparison.before} spans={spans} comparison={comparison} /><Pane side="after" data={comparison.after} spans={spans} comparison={comparison} /></div>
    <p className="panel-note">PDF links open at the cited page; a highlighted region on the page is not available (no verified PDF text coordinates).</p>
    {comparison.abstention_reasons?.length > 0 && <ul className="reason-list">{comparison.abstention_reasons.map((code) => <li key={code}>{REASON_TEXT[code] || code}</li>)}</ul>}
    {scope && <p className="panel-note">{SCOPE_NOTE}</p>}
  </article>;
}
