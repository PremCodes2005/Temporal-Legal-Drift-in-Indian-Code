import { useEffect, useMemo, useState } from "react";

const sections = [
  { id: "assistant", number: "01", label: "Legal drift assistant" },
  { id: "corpus", number: "02", label: "Document repository" },
  { id: "method", number: "03", label: "How it works" },
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

  useEffect(() => {
    Promise.all([api("/api/corpus"), api("/api/rag/status")])
      .then(([corpusData, statusData]) => { setCorpus(corpusData); setStatus(statusData); })
      .catch((error) => setLoadError(error.message));
  }, []);

  const navigate = (next) => {
    setSection(next); setMenuOpen(false); window.scrollTo({ top: 0, behavior: "smooth" });
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
        {section === "assistant" && <AssistantWorkspace status={status} error={loadError} />}
        {section === "corpus" && <CorpusBrowser corpus={corpus} error={loadError} status={status} />}
        {section === "method" && <Method />}
      </main>
    </div>
  </div>;
}

function AssistantWorkspace({ status, error: statusError }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("specific");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault(); setError(""); setResult(null);
    if (!query.trim()) return setError("Enter a question about the indexed Indian legal documents.");
    setBusy(true);
    try {
      const value = await api("/api/rag/query", { method: "POST", body: { query: query.trim(), mode } });
      setResult(value);
      window.setTimeout(() => document.getElementById("rag-result")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  return <section className="page-section">
    <div className="hero">
      <span className="section-kicker">Single-prompt legal research</span>
      <h2>Ask what changed in Indian law.</h2>
      <p>The assistant searches the local versioned corpus, retrieves relevant amendment evidence and explains the change with traceable source anchors.</p>
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
    {result && <RagResult result={result} />}
  </section>;
}

function RepositoryStatus({ status, error }) {
  return <div className={`repository-status ${error ? "error" : ""}`}>
    <span className="status-dot" />
    <div><strong>{error ? "Repository unavailable" : status?.ready ? "Document repository ready" : "Preparing document repository"}</strong><small>{error || (status ? `${formatNumber(status.document_count)} documents · ${formatNumber(status.chunk_count)} searchable chunks · Hybrid retrieval` : "Building the local legal index…")}</small></div>
    {status && <span className="status-badge">Auto-ingestion on</span>}
  </div>;
}

function RagResult({ result }) {
  const answer = result.answer;
  const metrics = result.metrics;
  return <section id="rag-result" className="results">
    <div className="result-heading"><div><span className="section-kicker">Grounded response</span><h2>{titleCase(result.intent)}</h2></div><div className="mode-badge">{titleCase(result.mode)} mode</div></div>
    <article className="answer-card">
      <AnswerSection label="Pre-amendment baseline" text={answer.pre_amendment_baseline} tone="before" />
      <div className="answer-divider" />
      <AnswerSection label="Post-amendment revision" text={answer.post_amendment_revision} tone="after" />
      <div className="difference-summary"><span className="section-kicker">Key differences summary</span><ul>{answer.key_differences.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
    </article>
    {metrics ? <DriftPanel metrics={metrics} /> : <article className="empty-analysis"><strong>Drift metrics unavailable</strong><p>A supported pre/post evidence pair was not found for this query.</p></article>}
    <div className="result-columns">
      <VerificationPanel verification={result.verification} />
      <EvidencePanel citations={result.citations} retrieval={result.retrieval} />
    </div>
    {answer.generation_warning && <div className="warning-note">{answer.generation_warning}. The displayed response uses the evidence-only fallback.</div>}
    <article className="source-guidance"><div><span className="section-kicker">Authoritative source</span><h3>Verify the complete legal text</h3><p>{result.source_guidance.message}</p></div><a href={result.source_guidance.url} target="_blank" rel="noreferrer">{result.source_guidance.label} ↗</a></article>
    <p className="research-note">Scores describe retrieved-text movement and evidence alignment; they are not probabilities or legal advice.</p>
  </section>;
}

function AnswerSection({ label, text, tone }) { return <section className={`answer-section ${tone}`}><div className="answer-label"><span>{tone === "before" ? "B" : "A"}</span><strong>{label}</strong></div><p>{text}</p></section>; }

function DriftPanel({ metrics }) {
  const rows = [
    { label: "Semantic drift", value: metrics.semantic_drift_percent, tone: "blue", help: "Meaning-level distance between retrieved version embeddings." },
    { label: "Lexical / textual shift", value: metrics.lexical_drift_percent, tone: "green", help: "Token and sequence changes in the paired excerpts." },
    { label: "Conceptual / legal intent shift", value: metrics.conceptual_drift_percent, tone: "purple", help: metrics.conceptual_method === "llm_judge" ? "Evidence-bound LLM judgment of operative legal change." : "Deterministic legal-cue proxy; no LLM judgment was available." },
    { label: "Retrieval & extraction alignment", value: metrics.alignment_accuracy_percent, tone: "gold", help: "Retrieval confidence, metadata coverage and paired evidence completeness." },
  ];
  return <article className="analytics-panel"><div className="analytics-heading"><div><span className="section-kicker">Drift score breakdown</span><h3>How far the retrieved versions moved</h3></div><div className="overall-score"><strong>{metrics.overall_drift_percent}%</strong><span>weighted drift</span></div></div><div className="metric-bars">{rows.map((row) => <div className="metric-row" key={row.label}><div><strong>{row.label}</strong><span>{row.help}</span></div><div className="bar-line"><div className={`bar-fill ${row.tone}`} style={{ width: `${Math.max(0, Math.min(100, row.value))}%` }} /></div><b>{row.value}%</b></div>)}</div></article>;
}

function VerificationPanel({ verification }) { return <article className="panel compact"><span className="section-kicker">Objective verification</span><h3>{verification.passed ? "Alignment checks passed" : "Review required"}</h3><div className="check-list">{verification.checks.map((check) => <div key={check.id} className={check.passed ? "pass" : "fail"}><span>{check.passed ? "✓" : "!"}</span>{check.label}</div>)}</div><p className="panel-note">{verification.note}</p></article>; }

function EvidencePanel({ citations, retrieval }) { return <article className="panel compact"><span className="section-kicker">Retrieved evidence</span><h3>{citations.length} source anchor{citations.length === 1 ? "" : "s"}</h3>{citations.length ? <div className="citation-list">{citations.map((item) => <a key={item.chunk_id} href={item.source_url || item.official_portal_url} target="_blank" rel="noreferrer"><span>{item.label === "pre" ? "Baseline" : "Revision"} · {item.source_anchor || "Document"}</span><strong>{item.act_name}</strong><small>{item.version} · {item.official_identifier}</small></a>)}</div> : <p className="panel-note">No local citation was available.</p>}<p className="panel-note">Pair status: {titleCase(retrieval.pair_status)}</p></article>; }

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

async function api(path, options = {}) { const init = { method: options.method || "GET", headers: { Accept: "application/json" } }; if (options.body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(options.body); } const response = await fetch(path, init); let value; try { value = await response.json(); } catch { throw new Error(`Server returned ${response.status}`); } if (!response.ok) throw new Error(value.error || `Request failed with ${response.status}`); return value; }
function titleCase(value) { return String(value || "").replaceAll("_", " ").replaceAll("-", " ").split(/\s+/).map((item) => item.charAt(0).toUpperCase() + item.slice(1)).join(" "); }
function formatNumber(value) { return Number(value || 0).toLocaleString("en-IN"); }
