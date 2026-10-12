const SUPPORT_TEXT = {
  GRAPH_TRANSITION_FRAGMENTS: "Before/after wording of one amendment, taken from a machine-checked transition in the temporal graph. These are fragments, not complete sections.",
  CONSOLIDATED_FOOTNOTE_RECONSTRUCTION: "Earlier wording reconstructed from India Code's own substitution footnote in the same section. Check it against the official text.",
  UNALIGNED_EXCERPTS: "The amendment instruction and the Act text are not shown to be the same provision, so they are not presented as before/after versions and no drift score is calculated.",
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
};
const TOKEN = /([A-Za-z]+|\d+(?:\.\d+)?)/;

// Mark the tokens named by changed_spans, in order, without inserting any HTML.
function markedTokens(text, spans, side) {
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

function Pane({ side, data, spans }) {
  if (!data) return null;
  return <section className="compare-pane" aria-label={ROLE_TEXT[data.role] || data.role}>
    <header><strong>{ROLE_TEXT[data.role] || data.role}</strong><span>{data.act_name || data.entry_id}{data.page ? ` · page ${data.page}` : ""}</span>
      {data.source_url && <a href={data.source_url} target="_blank" rel="noreferrer">Open source ↗</a>}</header>
    {data.compared_text ? <p className="compare-text">{markedTokens(data.compared_text, spans, side)}</p>
      : <p className="panel-note">No aligned text was compared for this side.</p>}
    <small className="panel-note">Page-region highlight unavailable: no verified PDF text coordinates for this excerpt.</small>
  </section>;
}

export default function ComparisonPanel({ comparison }) {
  if (!comparison || comparison.support_class === "NOT_A_COMPARISON") return null;
  const spans = comparison.changed_spans || [];
  return <article className="panel comparison-panel" aria-labelledby="comparison-heading">
    <span className="section-kicker">What was compared</span>
    <h3 id="comparison-heading">{comparison.support_class === "UNALIGNED_EXCERPTS" ? "Excerpts only — no aligned versions" : "Clause comparison"}</h3>
    <p>{SUPPORT_TEXT[comparison.support_class]}</p>
    {spans.length > 0 && <p className="compare-legend"><del>struck through</del> = removed wording · <ins>underlined</ins> = added wording</p>}
    <div className="compare-grid"><Pane side="before" data={comparison.before} spans={spans} /><Pane side="after" data={comparison.after} spans={spans} /></div>
    {comparison.abstention_reasons?.length > 0 && <ul className="reason-list">{comparison.abstention_reasons.map((code) => <li key={code}>{REASON_TEXT[code] || code}</li>)}</ul>}
    <p className="panel-note">Applicability to a specific date or situation and its legal consequence are not determined here. Legal validation: unverified.</p>
  </article>;
}
