import { useEffect, useMemo, useState } from "react";

const sections = [
  { id: "assistant", number: "01", label: "Legal drift assistant" },
  { id: "corpus", number: "02", label: "Document repository" },
  { id: "drift", number: "03", label: "Drift explanation" },
  { id: "calculation", number: "04", label: "Score calculation" },
  { id: "method", number: "05", label: "How it works" },
  { id: "faq", number: "06", label: "Recent changes FAQ" },
];

const suggestions = [
  "What changed in the IT Act amendment regarding data privacy?",
  "Compare Section 19 before and after the IT Amendment Act, 2008.",
  "What penalties were introduced for privacy violations in the IT Act?",
];

export default function App() {
  const [section, setSection] = useState("assistant");
  const [menuOpen, setMenuOpen] = useState(false);
  const [corpus, setCorpus] = useState(null);
  const [status, setStatus] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [starterQuery, setStarterQuery] = useState("");
  const [lastResult, setLastResult] = useState(() => {
    try { return JSON.parse(window.sessionStorage.getItem("tldrift:last-result")) || null; }
    catch { return null; }
  });

  useEffect(() => {
    Promise.all([api("/api/corpus"), api("/api/rag/status")])
      .then(([corpusData, statusData]) => { setCorpus(corpusData); setStatus(statusData); })
      .catch((error) => setLoadError(error.message));
  }, []);

  useEffect(() => {
    if (lastResult) window.sessionStorage.setItem("tldrift:last-result", JSON.stringify(lastResult));
  }, [lastResult]);

  const navigate = (next) => {
    setSection(next); setMenuOpen(false); window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const askFromFaq = (question) => {
    setStarterQuery(question); setSection("assistant"); setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <aside className={`sidebar ${menuOpen ? "open" : ""}`} aria-label="Primary navigation">
      <div className="brand"><div className="brand-mark">TL</div><div><strong>Temporal Legal Drift</strong><span>Indian Code RAG assistant</span></div></div>
      <nav className="nav-list">{sections.map((item) => <button key={item.id} className={`nav-item ${section === item.id ? "active" : ""}`} onClick={() => navigate(item.id)}><span>{item.number}</span>{item.label}</button>)}</nav>
      <a className="official-link side-link" href="https://indiacode.gov.in/" target="_blank" rel="noreferrer">India Code official website ↗</a>
    </aside>
    <div className="workspace">
      <header className="topbar"><button className="menu-toggle" onClick={() => setMenuOpen((open) => !open)} aria-label="Open navigation">☰</button><div><p className="eyebrow">Versioned Indian law</p><h1>{sections.find((item) => item.id === section)?.label}</h1></div></header>
      <main id="main-content">
        {section === "assistant" && <AssistantWorkspace status={status} error={loadError} starterQuery={starterQuery} result={lastResult} onResult={setLastResult} onExplain={() => navigate("drift")} />}
        {section === "corpus" && <CorpusBrowser corpus={corpus} error={loadError} status={status} />}
        {section === "drift" && <DriftExplanation result={lastResult} onAnalyse={() => navigate("assistant")} />}
        {section === "calculation" && <ScoreCalculation result={lastResult} onAnalyse={() => navigate("assistant")} />}
        {section === "method" && <Method />}
        {section === "faq" && <RecentChangesFaq onAsk={askFromFaq} />}
      </main>
    </div>
  </div>;
}

function AssistantWorkspace({ status, error: statusError, starterQuery, result, onResult, onExplain }) {
  const [query, setQuery] = useState(starterQuery || "");
  const [mode, setMode] = useState("specific");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { if (starterQuery) setQuery(starterQuery); }, [starterQuery]);

  const submit = async (event) => {
    event.preventDefault(); setError(""); onResult(null);
    if (!query.trim()) return setError("Enter a question about the indexed Indian legal documents.");
    setBusy(true);
    try {
      const value = await api("/api/rag/query", { method: "POST", body: { query: query.trim(), mode } });
      onResult(value);
      window.setTimeout(() => document.getElementById("rag-result")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  return <section className="page-section">
    <div className="hero">
      <span className="section-kicker">Single-prompt legal research</span>
      <h2>Ask what changed in Indian law.</h2>
      <p>The assistant checks the live India Code repository and uses the local evidence cache for reproducible amendment comparisons and traceable source anchors.</p>
      <RepositoryStatus status={status} error={statusError} />
      <form className="prompt-panel" onSubmit={submit}>
        <label htmlFor="legal-query" className="sr-only">Legal research question</label>
        <textarea id="legal-query" rows="4" maxLength="4000" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ask a question, for example: What changed in the IT Act amendment regarding data privacy?" />
        <div className="prompt-actions">
          <div className="mode-switch" role="group" aria-label="Analysis mode">
            <button type="button" className={mode === "specific" ? "active" : ""} onClick={() => setMode("specific")}><strong>Specific</strong><small>Clause-level analysis</small></button>
            <button type="button" className={mode === "generic" ? "active" : ""} onClick={() => setMode("generic")}><strong>Generic</strong><small>High-level overview</small></button>
          </div>
          <button className="send-button" type="submit" disabled={busy || !query.trim()}>{busy ? "Searching…" : "Analyse"}<span aria-hidden="true">→</span></button>
        </div>
      </form>
      <div className="suggestions"><span>Try asking</span>{suggestions.map((item) => <button key={item} type="button" onClick={() => setQuery(item)}>{item}</button>)}</div>
      {error && <div className="form-error" role="alert"><strong>Analysis could not be completed.</strong><span>{error}</span></div>}
    </div>
    {busy && <div className="loading-panel"><span className="spinner"/><div><strong>Retrieving versioned legal evidence…</strong><p>Classifying the question, matching documents and validating the response context.</p></div></div>}
    {result && <RagResult result={result} onExplain={onExplain} />}
  </section>;
}

function RepositoryStatus({ status, error }) {
  return <div className={`repository-status ${error ? "error" : ""}`}>
    <span className="status-dot" />
    <div><strong>{error ? "Repository unavailable" : status?.ready ? "India Code connection ready" : "Preparing legal repository"}</strong><small>{error || (status ? `Live India Code lookup · ${formatNumber(status.document_count)} cached documents · ${formatNumber(status.chunk_count)} searchable chunks` : "Connecting to India Code and the local evidence cache…")}</small></div>
    {status && <span className="status-badge">Live + cached</span>}
  </div>;
}

function RagResult({ result, onExplain }) {
  const answer = result.answer;
  const metrics = result.metrics;
  const isSummary = answer.answer_type === "single_document_summary";
  return <section id="rag-result" className="results">
    <div className="result-heading"><div><span className="section-kicker">Grounded response</span><h2>{titleCase(result.intent)}</h2></div><div className="mode-badge">{titleCase(result.mode)} mode</div></div>
    <article className="answer-card">
      {isSummary ? <AnswerSection label="Short answer" text={answer.short_answer || answer.post_amendment_revision} tone="summary" /> : <><AnswerSection label="Pre-amendment baseline" text={answer.pre_amendment_baseline} tone="before" /><div className="answer-divider" /><AnswerSection label="Post-amendment revision" text={answer.post_amendment_revision} tone="after" /></>}
      <div className="difference-summary"><span className="section-kicker">{isSummary ? "Key points" : "Key differences summary"}</span><ul>{answer.key_differences.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
    </article>
    {metrics ? <><DriftPanel metrics={metrics} /><button className="explain-drift-button" type="button" onClick={onExplain}>Explain these scores with PDF evidence <span>→</span></button></> : <article className="empty-analysis"><strong>{isSummary ? "Document summary" : "Drift metrics unavailable"}</strong><p>{isSummary ? "Drift scores are shown only when the question asks for a comparison and a supported pre/post evidence pair is available." : "A supported pre/post evidence pair was not found for this query."}</p></article>}
    <div className="result-columns">
      <VerificationPanel verification={result.verification} />
      <EvidencePanel citations={result.citations} retrieval={result.retrieval} />
    </div>
    {answer.generation_warning && <div className="warning-note">{answer.generation_warning}. The displayed response uses the evidence-only fallback.</div>}
    <article className="source-guidance"><div><span className="section-kicker">Authoritative source</span><h3>Verify the complete legal text</h3><p>{result.source_guidance.message}</p></div><a href={result.source_guidance.url} target="_blank" rel="noreferrer">{result.source_guidance.label} ↗</a></article>
    <p className="research-note">Scores describe retrieved-text movement and evidence alignment; they are not probabilities or legal advice.</p>
  </section>;
}

function AnswerSection({ label, text, tone }) { return <section className={`answer-section ${tone}`}><div className="answer-label"><span>{tone === "before" ? "B" : tone === "after" ? "A" : "S"}</span><strong>{label}</strong></div><p>{text}</p></section>; }

function DriftPanel({ metrics }) {
  const rows = [
    { label: "Semantic drift", value: metrics.semantic_drift_percent, tone: "blue", help: "Meaning-level distance between retrieved version embeddings." },
    { label: "Lexical / textual shift", value: metrics.lexical_drift_percent, tone: "green", help: "Token and sequence changes in the paired excerpts." },
    { label: "Conceptual / legal intent shift", value: metrics.conceptual_drift_percent, tone: "purple", help: metrics.conceptual_method === "llm_judge" ? "Evidence-bound LLM judgment of operative legal change." : "Deterministic legal-cue proxy; no LLM judgment was available." },
    { label: "Retrieval & extraction alignment", value: metrics.alignment_accuracy_percent, tone: "gold", help: "Retrieval confidence, metadata coverage and paired evidence completeness." },
  ];
  return <article className="analytics-panel"><div className="analytics-heading"><div><span className="section-kicker">Drift score breakdown</span><h3>How far the retrieved versions moved</h3></div><div className="overall-score"><strong>{metrics.overall_drift_percent}%</strong><span>weighted RMS drift</span></div></div><div className="metric-bars">{rows.map((row) => <div className="metric-row" key={row.label}><div><strong>{row.label}</strong><span>{row.help}</span></div><div className="bar-line"><div className={`bar-fill ${row.tone}`} style={{ width: `${Math.max(0, Math.min(100, row.value))}%` }} /></div><b>{row.value}%</b></div>)}</div>{metrics.component_disagreement && <p className="panel-note">The component scores strongly disagree. Review each score and its cited evidence separately; the overall score must not be interpreted as ordinary averaging.</p>}</article>;
}

function DriftExplanation({ result, onAnalyse }) {
  if (!result?.metrics) return <section className="page-section"><div className="section-header"><span className="section-kicker">Score interpretation</span><h2>Run a comparison to explain its drift.</h2><p>This tab uses the latest supported pre/post result. General questions and single-document answers do not produce drift scores.</p></div><button className="send-button" type="button" onClick={onAnalyse}>Open legal drift assistant <span>→</span></button></section>;

  const { metrics, retrieval, citations } = result;
  const levels = metrics.levels || {};
  const scoreRows = [
    ["Semantic drift", metrics.semantic_drift_percent, levels.semantic, "How far the deterministic vector representations moved."],
    ["Lexical shift", metrics.lexical_drift_percent, levels.lexical, "How much the words and token sequence changed."],
    ["Conceptual drift", metrics.conceptual_drift_percent, levels.conceptual, "How much the detected legal cues, numbers or model-assessed intent changed."],
    ["Overall drift", metrics.overall_drift_percent, levels.overall, "Weighted root-mean-square result: 40% semantic, 30% lexical and 30% conceptual. A strong signal is not cancelled by a weak one."],
  ];
  const preCitation = citations?.find((item) => item.label === "pre");
  const postCitation = citations?.find((item) => item.label === "post");
  return <section className="page-section drift-page">
    <div className="section-header"><span className="section-kicker">Latest comparison</span><h2>What the drift score means</h2><p>The classifications below describe movement between the two retrieved excerpts. They do not independently prove legal materiality or correctness.</p></div>
    <div className="level-guide">
      <article className="low"><strong>Low</strong><b>0–33.3%</b><p>The excerpts are mostly stable, with limited textual or conceptual movement.</p></article>
      <article className="medium"><strong>Medium</strong><b>33.4–66.6%</b><p>A noticeable change exists and the cited clauses should be reviewed carefully.</p></article>
      <article className="high"><strong>High</strong><b>66.7–100%</b><p>Substantial movement was detected; this still requires legal and applicability review.</p></article>
    </div>
    <article className="drift-breakdown"><span className="section-kicker">Calculated classification</span><h3>{levels.overall || driftLevel(metrics.overall_drift_percent)} overall drift</h3><div className="drift-score-grid">{scoreRows.map(([label, value, level, detail]) => <div key={label}><span>{label}</span><strong>{value}%</strong><b className={`level-pill ${(level || driftLevel(value)).toLowerCase()}`}>{level || driftLevel(value)}</b><p>{detail}</p></div>)}</div></article>
    <div className="evidence-comparison">
      <EvidenceExcerpt title="Before-side PDF evidence" citation={preCitation} chunk={retrieval.pre} />
      <div className="comparison-arrow" aria-hidden="true">→</div>
      <EvidenceExcerpt title="After-side PDF evidence" citation={postCitation} chunk={retrieval.post} />
    </div>
    <article className="difference-evidence"><span className="section-kicker">Detected change</span><h3>How the cited excerpts differ</h3><ul>{result.answer.key_differences.map((item, index) => <li key={index}>{item}</li>)}</ul><p>Open the cited source to inspect the complete provision, amendment operation, commencement and applicability.</p></article>
  </section>;
}

function EvidenceExcerpt({ title, citation, chunk }) {
  return <article className="evidence-excerpt"><span className="section-kicker">{title}</span><h3>{citation?.act_name || chunk?.metadata?.act_name || "Evidence unavailable"}</h3><div className="evidence-meta">{citation?.version || chunk?.metadata?.version || "Unknown version"} · {citation?.source_anchor || chunk?.metadata?.source_anchor || "No anchor"}</div><blockquote>{excerpt(chunk?.text)}</blockquote>{(citation?.source_url || citation?.official_portal_url) && <a href={citation.source_url || citation.official_portal_url} target="_blank" rel="noreferrer">Open cited source ↗</a>}</article>;
}

function ScoreCalculation({ result, onAnalyse }) {
  if (!result?.metrics) return <section className="page-section"><div className="section-header"><span className="section-kicker">Reproducible calculation</span><h2>Run a pre/post comparison first.</h2><p>This tab explains the percentages from the latest response and identifies the exact retrieved PDF pages used.</p></div><button className="send-button" type="button" onClick={onAnalyse}>Open legal drift assistant <span>→</span></button></section>;

  const { metrics, retrieval, citations, answer, query } = result;
  const hasServerTrace = Boolean(metrics.calculation_trace);
  const trace = metrics.calculation_trace || legacyCalculationTrace(metrics);
  const basis = metrics.score_basis || {};
  const preCitation = citations?.find((item) => item.label === "pre");
  const postCitation = citations?.find((item) => item.label === "post");
  const contribution = trace.overall.weighted_square_contributions;
  const rows = [
    ["Semantic drift", `${trace.semantic.cosine_similarity_percent}% similarity`, trace.semantic.formula, metrics.semantic_drift_percent],
    ["Lexical drift", `${trace.lexical.jaccard_similarity_percent}% Jaccard · ${trace.lexical.sequence_similarity_percent}% sequence`, trace.lexical.formula, metrics.lexical_drift_percent],
    ["Conceptual drift", titleCase(trace.conceptual.method), trace.conceptual.formula, metrics.conceptual_drift_percent],
    ["Evidence alignment", `${trace.alignment.average_retrieval_confidence_percent}% retrieval · ${trace.alignment.paired_evidence_completeness_percent}% evidence · ${trace.alignment.metadata_coverage_percent}% metadata`, trace.alignment.formula, metrics.alignment_accuracy_percent],
  ];
  return <section className="page-section calculation-page">
    <div className="section-header"><span className="section-kicker">Latest response audit</span><h2>How these percentages were calculated</h2><p>You supplied only this prompt: “{query}”. The backend automatically found the relevant versions and selected comparable evidence. No before/after passage was entered by the user.</p></div>
    {!hasServerTrace && <div className="calculation-warning">This result came from an older running backend. The final percentages and formulas are shown, but detailed token, cue and similarity inputs require restarting the backend and running the question again.</div>}
    <div className="calculation-sources">
      <CalculationSource label="Automatically selected before evidence" citation={preCitation} chunk={retrieval.pre} scoringExcerpt={basis.pre_excerpt} />
      <CalculationSource label="Automatically selected after evidence" citation={postCitation} chunk={retrieval.post} scoringExcerpt={basis.post_excerpt} />
    </div>
    <article className="calculation-card"><span className="section-kicker">Automatic score basis</span><h3>Prompt → retrieval → {titleCase(basis.selection_method || "query relevant evidence")}</h3><p className="panel-note">The scoring basis is fixed across Generic and Specific display modes. Those modes change answer detail, not the selected evidence or percentages.</p></article>
    <article className="calculation-card"><span className="section-kicker">Backend values and formulas</span><div className="calculation-rows">{rows.map(([name, inputs, formula, score]) => <div className="calculation-row" key={name}><div><strong>{name}</strong><span>{inputs}</span><code>{formula}</code></div><b>{score}%</b></div>)}</div></article>
    <article className="calculation-card"><span className="section-kicker">Overall weighted-RMS calculation</span><h3>Why the final score is {metrics.overall_drift_percent}%</h3><p className="formula-display">{trace.overall.formula}</p><div className="contribution-grid"><div><span>Semantic contribution</span><strong>{contribution.semantic}</strong></div><div><span>Lexical contribution</span><strong>{contribution.lexical}</strong></div><div><span>Conceptual contribution</span><strong>{contribution.conceptual}</strong></div><div><span>Sum before square root</span><strong>{trace.overall.sum_of_weighted_squares}</strong></div></div>{metrics.component_disagreement && <p className="calculation-warning">The component scores differ substantially. Weighted RMS prevents a strong change signal from being cancelled by a weak one.</p>}</article>
    <article className="calculation-card"><span className="section-kicker">Connection to the response</span><h3>Detected changes supported by those pages</h3><ul>{answer.key_differences.map((item, index) => <li key={index}>{item}</li>)}</ul><div className="cue-grid"><div><strong>Before legal cues</strong><span>{trace.conceptual.pre_legal_cues.join(", ") || "None detected"}</span><small>Numbers: {trace.conceptual.pre_numbers.join(", ") || "none"}</small></div><div><strong>After legal cues</strong><span>{trace.conceptual.post_legal_cues.join(", ") || "None detected"}</span><small>Numbers: {trace.conceptual.post_numbers.join(", ") || "none"}</small></div></div></article>
    <p className="research-note">These calculations measure retrieved-text movement and evidence alignment. They are not probabilities, legal correctness scores or legal advice.</p>
  </section>;
}

function CalculationSource({ label, citation, chunk, scoringExcerpt }) {
  const anchor = citation?.source_anchor || chunk?.metadata?.source_anchor || "No page anchor";
  const sourceUrl = citation?.source_url || citation?.official_portal_url;
  return <article><span className="section-kicker">{label}</span><h3>{citation?.act_name || chunk?.metadata?.act_name || "Evidence unavailable"}</h3><strong>{anchor}</strong><p>{excerpt(scoringExcerpt || chunk?.text, 520)}</p>{sourceUrl && <a href={sourceUrl} target="_blank" rel="noreferrer">Open cited PDF page source ↗</a>}</article>;
}

function legacyCalculationTrace(metrics) {
  const semantic = Number(metrics.semantic_drift_percent || 0);
  const lexical = Number(metrics.lexical_drift_percent || 0);
  const conceptual = Number(metrics.conceptual_drift_percent || 0);
  const contributions = {
    semantic: Number((0.4 * semantic * semantic).toFixed(2)),
    lexical: Number((0.3 * lexical * lexical).toFixed(2)),
    conceptual: Number((0.3 * conceptual * conceptual).toFixed(2)),
  };
  return {
    semantic: { cosine_similarity_percent: Number((100 - semantic).toFixed(1)), formula: "100 × (1 - cosine similarity)" },
    lexical: { jaccard_similarity_percent: "Unavailable", sequence_similarity_percent: "Unavailable", formula: "100 × (1 - (0.55 × Jaccard similarity + 0.45 × sequence similarity))" },
    conceptual: { method: metrics.conceptual_method || "Unavailable", formula: "Evidence-bound LLM score when available; otherwise deterministic legal-cue, numeric and polarity changes", pre_legal_cues: [], post_legal_cues: [], pre_numbers: [], post_numbers: [] },
    overall: { formula: "sqrt(0.40 × semantic² + 0.30 × lexical² + 0.30 × conceptual²)", weighted_square_contributions: contributions, sum_of_weighted_squares: Number(Object.values(contributions).reduce((sum, value) => sum + value, 0).toFixed(2)) },
    alignment: { average_retrieval_confidence_percent: "Unavailable", paired_evidence_completeness_percent: "Unavailable", metadata_coverage_percent: "Unavailable", formula: "0.50 × retrieval confidence + 0.30 × evidence completeness + 0.20 × metadata coverage" },
  };
}

function VerificationPanel({ verification }) { return <article className="panel compact"><span className="section-kicker">Objective verification</span><h3>{verification.passed ? "Alignment checks passed" : "Review required"}</h3><div className="check-list">{verification.checks.map((check) => <div key={check.id} className={check.passed ? "pass" : "fail"}><span>{check.passed ? "✓" : "!"}</span>{check.label}</div>)}</div><p className="panel-note">{verification.note}</p></article>; }

function EvidencePanel({ citations, retrieval }) {
  const amendments = retrieval.live_indiacode?.amendments || [];
  return <article className="panel compact"><span className="section-kicker">Retrieved evidence</span><h3>{citations.length} source anchor{citations.length === 1 ? "" : "s"}</h3>{citations.length ? <div className="citation-list">{citations.map((item) => <a key={item.chunk_id} href={item.source_url || item.official_portal_url} target="_blank" rel="noreferrer"><span>{item.label === "pre" ? "Baseline" : "Revision"} · {item.source_anchor || "Document"}</span><strong>{item.act_name}</strong><small>{item.version} · {item.official_identifier}</small></a>)}</div> : <p className="panel-note">No local citation was available.</p>}{amendments.length > 0 && <div className="live-amendments"><h4>Related India Code amendment records</h4><p>These records show amendment history. They are not treated as reconstructed pre/post text automatically.</p><div className="amendment-links">{amendments.map((item) => <a key={`${item.official_identifier}-${item.target_act}`} href={item.source_url} target="_blank" rel="noreferrer"><strong>{item.title}</strong><small>{item.target_act || "Target Act not stated"}{item.year ? ` · ${item.year}` : ""}</small></a>)}</div></div>}<p className="panel-note">Pair status: {titleCase(retrieval.pair_status)}</p></article>;
}

function CorpusBrowser({ corpus, status, error }) {
  const [query, setQuery] = useState("");
  const entries = useMemo(() => corpus?.entries.filter((item) => [item.entry_id, item.official_identifier, item.research_role].some((value) => String(value || "").toLowerCase().includes(query.toLowerCase()))) || [], [corpus, query]);
  return <section className="page-section"><div className="section-header split"><div><span className="section-kicker">Automatic ingestion</span><h2>Indexed Indian legal documents</h2><p>Local verified PDFs retain their authoritative India Code provenance and are indexed automatically for retrieval.</p></div><input className="search-input" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search the repository" /></div><RepositoryStatus status={status} error={error}/><div className="table-shell"><table><thead><tr><th>Legal instrument</th><th>Identifier</th><th>Extracted blocks</th><th>Source</th></tr></thead><tbody>{entries.map((item) => <tr key={item.entry_id}><td><strong>{titleCase(item.entry_id)}</strong><small>{item.research_role}</small></td><td>{item.official_identifier}</td><td>{formatNumber(item.normalized_blocks)}</td><td><a href={item.pdf_url} target="_blank" rel="noreferrer">Open local PDF ↗</a></td></tr>)}</tbody></table>{!entries.length && <div className="empty-state">{error || "No matching documents."}</div>}</div><a className="official-link repository-link" href="https://indiacode.gov.in/" target="_blank" rel="noreferrer">Visit India Code for further information ↗</a></section>;
}

function Method() { return <section className="page-section"><div className="section-header"><span className="section-kicker">Evidence-first pipeline</span><h2>How one question becomes a grounded comparison</h2><p>The workflow keeps retrieval confidence, legal drift and legal correctness conceptually separate.</p></div><div className="method-grid">{[
  ["1", "Classify", "Identify diff analysis, general legal QA or statutory lookup intent."],
  ["2", "Retrieve", "Search deterministic embeddings and lexical signals across indexed legal chunks."],
  ["3", "Pair", "Connect an amending instrument with its target consolidated Act when repository evidence supports it."],
  ["4", "Compare", "Calculate semantic, lexical and conceptual movement on the retrieved excerpts."],
  ["5", "Generate", "Produce a specific clause view or generic overview using only supplied evidence."],
  ["6", "Verify", "Check coverage, version pairing, citation anchors and response alignment."],
].map(([number, title, body]) => <article className="method-card" key={number}><span>{number}</span><h3>{title}</h3><p>{body}</p></article>)}</div><article className="source-guidance"><div><span className="section-kicker">Always verify</span><h3>Local retrieval is not the final legal authority</h3><p>If evidence is missing or incomplete, the assistant still directs the user to India Code for the complete text and further information.</p></div><a href="https://indiacode.gov.in/" target="_blank" rel="noreferrer">Visit India Code ↗</a></article></section>; }

const recentChangeQuestions = [
  ["Banking law", "What changed recently under the Banking Laws (Amendment) Act, 2025?"],
  ["Disaster management", "What changed in the Disaster Management (Amendment) Act, 2025?"],
  ["Competition", "What important changes were made by the Competition (Amendment) Act, 2023?"],
  ["Biological diversity", "What changed under the Biological Diversity (Amendment) Act, 2023?"],
  ["GST", "What changed in the Central Goods and Services Tax amendments of 2023?"],
  ["Wildlife", "What changed in the Wild Life (Protection) Amendment Act, 2022?"],
  ["Insolvency", "What changed across the Insolvency and Bankruptcy Code amendments from 2019 to 2021?"],
  ["Data and technology", "What are the major legal changes affecting data and technology after the Information Technology Act, 2000?"],
  ["Right to Information", "What changed in the Right to Information (Amendment) Act, 2019?"],
  ["Motor vehicles", "What changed in the Motor Vehicles (Amendment) Act, 2019?"],
  ["Aadhaar", "What changed in the Aadhaar and Other Laws (Amendment) Act, 2019?"],
  ["Child protection", "What changed in the Protection of Children from Sexual Offences (Amendment) Act, 2019?"],
];

function RecentChangesFaq({ onAsk }) {
  return <section className="page-section"><div className="section-header"><span className="section-kicker">Frequently asked questions</span><h2>What has changed recently in Indian Acts?</h2><p>Select a common question to analyse it using available India Code evidence. A drift score is shown only when a supported pre/post pair can be established.</p></div><div className="faq-grid">{recentChangeQuestions.map(([topic, question]) => <article className="faq-card" key={question}><span>{topic}</span><h3>{question}</h3><button type="button" onClick={() => onAsk(question)}>Ask the legal drift assistant <b>→</b></button></article>)}</div><article className="source-guidance"><div><span className="section-kicker">Current source</span><h3>Check the latest official text</h3><p>Recent-change answers depend on publication, commencement and applicability evidence. Confirm the complete record on India Code.</p></div><a href="https://indiacode.gov.in/" target="_blank" rel="noreferrer">Visit India Code ↗</a></article></section>;
}

async function api(path, options = {}) { const init = { method: options.method || "GET", headers: { Accept: "application/json" } }; if (options.body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(options.body); } const response = await fetch(path, init); let value; try { value = await response.json(); } catch { throw new Error(`Server returned ${response.status}`); } if (!response.ok) throw new Error(value.error || `Request failed with ${response.status}`); return value; }
function titleCase(value) { return String(value || "").replaceAll("_", " ").replaceAll("-", " ").split(/\s+/).map((item) => item.charAt(0).toUpperCase() + item.slice(1)).join(" "); }
function formatNumber(value) { return Number(value || 0).toLocaleString("en-IN"); }
function driftLevel(value) { const score = Number(value || 0); return score <= 33.3 ? "Low" : score <= 66.6 ? "Medium" : "High"; }
function excerpt(value, maximum = 900) { const text = String(value || "No excerpt was returned.").replace(/\s+/g, " ").trim(); return text.length <= maximum ? text : `${text.slice(0, maximum - 1).trim()}…`; }
