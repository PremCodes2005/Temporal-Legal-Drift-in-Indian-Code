// Panels shared by the assistant views and the legacy result view.

// Unavailable values are shown as such, never as zero.
export function percent(value) { return value == null ? "Unavailable" : `${value}%`; }

export function DriftPanel({ metrics, legacy = false }) {
  const rows = [
    { label: "Vector drift (feature-hash)", value: metrics.semantic_drift_percent, tone: "blue", help: "Cosine distance between deterministic 256-dimension token-hash vectors; not a trained meaning model." },
    { label: "Lexical / textual shift", value: metrics.lexical_drift_percent, tone: "green", help: "Token and sequence changes in the paired excerpts." },
    { label: "Conceptual / legal intent shift", value: metrics.conceptual_drift_percent, tone: "purple", help: metrics.conceptual_method === "llm_judge" ? "Evidence-bound LLM judgment of operative legal change." : "Deterministic legal-cue proxy; no LLM judgment was available." },
    { label: "Evidence-alignment quality", value: metrics.evidence_alignment_quality_percent ?? metrics.alignment_accuracy_percent, tone: "gold", help: "Retrieval confidence, metadata coverage and paired-evidence completeness. Not answer accuracy or a probability." },
  ];
  return <article className="analytics-panel"><div className="analytics-heading"><div><span className="section-kicker">Drift score breakdown</span><h3>How far the retrieved versions moved</h3></div><div className="overall-score"><strong>{percent(metrics.overall_drift_percent)}</strong><span>{legacy ? "legacy overall (diagnostic)" : "weighted RMS drift"}</span></div></div><div className="metric-bars">{rows.map((row) => <div className="metric-row" key={row.label}><div><strong>{row.label}</strong><span>{row.help}</span></div><div className="bar-line"><div className={`bar-fill ${row.tone}`} style={{ width: `${row.value == null ? 0 : Math.max(0, Math.min(100, row.value))}%` }} /></div><b>{percent(row.value)}</b></div>)}</div>{Object.values(metrics.unavailable_reasons || {}).map((reason) => <p className="panel-note" key={reason}>Unavailable: {reason}.</p>)}{metrics.component_disagreement && <p className="panel-note">The component scores strongly disagree. Review each score and its cited evidence separately; the overall score must not be interpreted as ordinary averaging.</p>}</article>;
}

export function VerificationPanel({ verification }) { return <article className="panel compact"><span className="section-kicker">Objective verification</span><h3>{verification.passed ? "Alignment checks passed" : "Review required"}</h3><div className="check-list">{verification.checks.map((check) => <div key={check.id} className={check.passed ? "pass" : "fail"}><span>{check.passed ? "✓" : "!"}</span>{check.label}</div>)}</div><p className="panel-note">{verification.note}</p></article>; }
