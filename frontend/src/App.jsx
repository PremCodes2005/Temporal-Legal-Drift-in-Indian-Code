import { useEffect, useMemo, useRef, useState } from "react";

const sections = [
  { id: "compare", number: "01", label: "Compare amendments" },
  { id: "corpus", number: "02", label: "Browse legal PDFs" },
  { id: "method", number: "03", label: "How it works" },
];

export default function App() {
  const [section, setSection] = useState("compare");
  const [menuOpen, setMenuOpen] = useState(false);
  const [corpus, setCorpus] = useState(null);
  const [corpusError, setCorpusError] = useState("");

  useEffect(() => {
    api("/api/corpus").then(setCorpus).catch((error) => setCorpusError(error.message));
  }, []);

  const navigate = (nextSection) => {
    setSection(nextSection);
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <aside className={`sidebar ${menuOpen ? "open" : ""}`} aria-label="Primary navigation">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">TL</div>
          <div><strong>Temporal Legal Drift</strong><span>Indian Code comparison</span></div>
        </div>
        <nav className="nav-list">
          {sections.map((item) => (
            <button key={item.id} className={`nav-item ${section === item.id ? "active" : ""}`} onClick={() => navigate(item.id)}>
              <span>{item.number}</span>{item.label}
            </button>
          ))}
        </nav>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <button className="menu-toggle" aria-label="Open navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}>☰</button>
          <div><p className="eyebrow">Versioned Indian law</p><h1>{sections.find((item) => item.id === section)?.label}</h1></div>
        </header>
        <main id="main-content" tabIndex="-1">
          {section === "compare" && <ComparisonWorkspace />}
          {section === "corpus" && <CorpusBrowser corpus={corpus} error={corpusError} />}
          {section === "method" && <Method />}
        </main>
      </div>
    </div>
  );
}

function ComparisonWorkspace() {
  const formRef = useRef(null);
  const [preFile, setPreFile] = useState(null);
  const [postFile, setPostFile] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    if (!preFile || !postFile) return setError("Choose both the pre-amendment and post-amendment PDFs.");
    if (![preFile, postFile].every((file) => file.name.toLowerCase().endsWith(".pdf"))) return setError("Both selected files must be PDF documents.");
    if ([preFile, postFile].some((file) => file.size > 20 * 1024 * 1024)) return setError("Each PDF must be 20 MB or smaller.");
    const values = new FormData(event.currentTarget);
    setBusy(true);
    setResult(null);
    try {
      const comparison = await api("/api/compare", {
        method: "POST",
        body: {
          pre_filename: preFile.name,
          pre_content_base64: await fileToBase64(preFile),
          post_filename: postFile.name,
          post_content_base64: await fileToBase64(postFile),
          question: values.get("question"),
          facts: values.get("facts") || "",
          pre_date: values.get("pre_date") || null,
          post_date: values.get("post_date") || null,
        },
      });
      setResult(comparison);
      window.setTimeout(() => document.getElementById("analysis-results")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    formRef.current?.reset();
    setPreFile(null);
    setPostFile(null);
    setResult(null);
    setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <section className="page-section active" aria-labelledby="compare-heading">
      <div className="section-header intro">
        <span className="section-kicker">Pre-amendment ↔ post-amendment</span>
        <h2 id="compare-heading">Find out what changed—and whether it changes the answer.</h2>
        <p>Upload two text-based legal PDFs, ask one question, and optionally add scenario facts. The result separates wording changes from material legal changes and scenario-specific compliance effects.</p>
      </div>

      <form ref={formRef} className="panel comparison-form" onSubmit={submit}>
        <div className="upload-grid">
          <PdfUpload id="pre-file" title="Pre-amendment PDF" subtitle="Choose the earlier legal version" file={preFile} onChange={setPreFile} />
          <div className="version-arrow" aria-hidden="true">↓</div>
          <PdfUpload id="post-file" title="Post-amendment PDF" subtitle="Choose the amended legal version" file={postFile} onChange={setPostFile} after />
        </div>
        <div className="question-grid">
          <label className="field full"><span>What legal or compliance question should be tested? *</span><textarea name="question" required rows="3" maxLength="4000" placeholder="Example: Is a document submitted on day 12 compliant with the applicable deadline?" /></label>
          <label className="field full"><span>Scenario facts <small>optional, but needed to determine whether the compliance outcome changes</small></span><textarea name="facts" rows="3" maxLength="8000" placeholder="Example: The company submitted the required document on day 12." /></label>
          <label className="field"><span>Pre-amendment reference date <small>optional</small></span><input name="pre_date" type="date" /></label>
          <label className="field"><span>Post-amendment reference date <small>optional</small></span><input name="post_date" type="date" /></label>
        </div>
        {error && <div className="form-error" role="alert"><strong>Comparison could not be completed.</strong><span>{error}</span></div>}
        <div className="form-footer"><p>Maximum 20 MB per PDF. Files are analysed for this request and are not added to the project corpus.</p><button type="submit" className="primary-button" disabled={busy}>{busy ? "Analysing…" : "Analyse legal drift"}</button></div>
      </form>

      {busy && <section className="loading-panel" aria-live="polite"><span className="spinner" aria-hidden="true" /><div><strong>Comparing legal versions…</strong><p>Extracting text, locating operative changes and testing the supplied facts.</p></div></section>}
      {result && <AnalysisResults result={result} onReset={reset} />}
    </section>
  );
}

function PdfUpload({ id, title, subtitle, file, onChange, after = false }) {
  return (
    <label className={`pdf-drop ${file ? "selected" : ""}`}>
      <input id={id} type="file" accept="application/pdf,.pdf" required onChange={(event) => onChange(event.target.files?.[0] || null)} />
      <span className={`document-icon ${after ? "after" : ""}`} aria-hidden="true">PDF</span>
      <span className="upload-copy"><strong>{title}</strong><small>{subtitle}</small><em>{file ? `${file.name} · ${formatBytes(file.size)}` : "No file selected"}</em></span>
      <span className="choose-button">Choose file</span>
    </label>
  );
}

function AnalysisResults({ result, onReset }) {
  const classification = result.classification;
  const metrics = result.metrics;
  const outcomeChanged = result.compliance.outcome_changed;
  const metricCards = [
    [classification.text_changed ? "Yes" : "No", "Text changed", `${metrics.text_change_percent}% of extracted tokens differ`],
    [classification.legal_rule_changed ? "Yes" : "No", "Legal rule changed", `${classification.materiality} materiality`],
    [outcomeChanged === null ? "Unknown" : outcomeChanged ? "Yes" : "No", "Answer changed", outcomeChanged === null ? "Add facts for a scenario-specific result" : "Based on the supplied facts"],
    [`${metrics.question_relevance_percent}%`, "Question relevance", `${metrics.changed_term_count} changed terms detected`],
  ];
  return (
    <section id="analysis-results" className="results" aria-labelledby="results-heading">
      <div className="result-heading"><div><span className="section-kicker">Comparison result</span><h2 id="results-heading">Legal drift analysis</h2></div><button className="secondary-button" type="button" onClick={onReset}>Start new comparison</button></div>
      <article className={`summary-card ${classification.materiality.toLowerCase()}`}><div><span className="result-label">{classification.materiality} materiality</span><h3>{result.summary}</h3><p>{classification.materiality_reason}</p></div><div className="score-ring"><strong>{metrics.drift_score}</strong><span>/ 100 drift</span></div></article>
      {result.temporal_interpretation?.evidence_order_corrected && <article className="temporal-note"><strong>Document roles corrected</strong><p>{result.temporal_interpretation.note}</p></article>}
      <div className="metric-grid">{metricCards.map(([value, label, note]) => <article className="metric-card" key={label}><span>{label}</span><strong>{value}</strong><p>{note}</p></article>)}</div>
      <div className="content-grid equal">
        <article className="panel"><span className="section-kicker">What changed</span><h3>Detected legal changes</h3><ChangeList result={result} /></article>
        <article className="panel"><span className="section-kicker">Answer to your question</span><h3>Compliance consequence</h3><Compliance result={result.compliance} /></article>
      </div>
      <div className="evidence-grid"><EvidenceCard label="Before evidence" filename={result.documents.evidence_before?.filename || result.documents.pre.filename} excerpts={result.evidence.before} /><EvidenceCard label="After evidence" filename={result.documents.evidence_after?.filename || result.documents.post.filename} excerpts={result.evidence.after} after /></div>
      <article className="score-note"><strong>How to read the drift score</strong><p>{result.interpretation.drift_score}</p><small>{result.interpretation.review_note}</small></article>
    </section>
  );
}

function ChangeList({ result }) {
  const rows = [
    ...result.numeric_changes.map((item, index) => ({ key: `numeric-${index}`, label: "Numeric threshold", value: <>{item.before} {item.unit} <b>→</b> {item.after} {item.unit}</> })),
    ...result.classification.change_types.filter((item) => item !== "numeric threshold").map((item) => ({ key: item, label: "Legal cue", value: titleCase(item) })),
  ];
  if (result.classification.obligation_type_stable) rows.push({ key: "stable", label: "Obligation type", value: "Remains the same", stable: true });
  if (!rows.length) return <p className="muted">No change was detected in the extracted text.</p>;
  return <div className="change-list">{rows.map((row) => <div key={row.key} className={`change-row ${row.stable ? "stable" : ""}`}><span>{row.label}</span><strong>{row.value}</strong></div>)}</div>;
}

function Compliance({ result }) {
  return <><div className="answer-pair"><div><span>Before</span><strong className={`answer ${result.pre_answer}`}>{titleCase(result.pre_answer)}</strong></div><span className="answer-arrow">→</span><div><span>After</span><strong className={`answer ${result.post_answer}`}>{titleCase(result.post_answer)}</strong></div></div><p className="consequence-reason">{result.reason}</p></>;
}

function EvidenceCard({ label, filename, excerpts, after = false }) {
  return <article className={`evidence-card ${after ? "after" : "before"}`}><span className="section-kicker">{label}</span><h3>{filename}</h3>{excerpts.length ? excerpts.map((text, index) => <blockquote key={index}>{text}</blockquote>) : <p className="muted">No changed excerpt was identified in this version.</p>}</article>;
}

function CorpusBrowser({ corpus, error }) {
  const [query, setQuery] = useState("");
  const entries = useMemo(() => corpus?.entries.filter((item) => [item.entry_id, item.official_identifier, item.research_role].some((value) => String(value || "").toLowerCase().includes(query.trim().toLowerCase()))) || [], [corpus, query]);
  return <section className="page-section active" aria-labelledby="corpus-heading"><div className="section-header split"><div><span className="section-kicker">Downloaded legal sources</span><h2 id="corpus-heading">Browse local Indian legal PDFs</h2><p>Open the readable PDFs already included in the project corpus.</p></div><label className="search-field"><span className="sr-only">Search corpus</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search Acts or identifiers" /></label></div>{corpus && <div className="inline-stats"><div><span>Readable PDFs</span><strong>{corpus.entry_count}</strong></div><div><span>Extracted blocks</span><strong>{formatNumber(corpus.total_normalized_blocks)}</strong></div><div><span>Local size</span><strong>{formatBytes(corpus.total_bytes)}</strong></div></div>}<div className="table-shell"><table><thead><tr><th>Legal instrument</th><th>Identifier</th><th>Extracted blocks</th><th>Document</th></tr></thead><tbody>{error ? <tr><td colSpan="4" className="empty-state">{error}</td></tr> : !corpus ? <tr><td colSpan="4" className="empty-state">Loading legal documents…</td></tr> : entries.length ? entries.map((item) => <tr key={item.entry_id}><td><strong>{titleCase(item.entry_id)}</strong><small>{item.research_role || ""}</small></td><td>{item.official_identifier || "—"}</td><td>{formatNumber(item.normalized_blocks || 0)}</td><td>{item.pdf_available ? <a className="document-link" href={item.pdf_url} target="_blank" rel="noreferrer">Open PDF ↗</a> : "Unavailable"}</td></tr>) : <tr><td colSpan="4" className="empty-state">No legal documents match the search.</td></tr>}</tbody></table></div></section>;
}

function Method() {
  return <section className="page-section active" aria-labelledby="method-heading"><div className="section-header"><div><span className="section-kicker">Simple interpretation</span><h2 id="method-heading">How the comparison works</h2><p>Each result answers three different questions. They should not be collapsed into one label.</p></div></div><div className="method-grid"><MethodCard number="1" title="Did the wording change?">Measures the textual difference between the two extracted PDF versions.</MethodCard><MethodCard number="2" title="Did the legal rule change?">Checks duties, permissions, prohibitions, scope, penalties and numeric thresholds.</MethodCard><MethodCard number="3" title="Does the answer change?">Applies the detected rule change to the facts supplied with the question.</MethodCard></div><article className="example-panel"><span className="section-kicker">Example</span><h3>A deadline changes from 10 days to 15 days</h3><p>The duty to submit remains the same, but the legal deadline is different. This is a material numeric-threshold change. A filing on day 12 is late under the earlier version and on time under the amended version; a filing on day 8 remains compliant under both.</p></article></section>;
}

function MethodCard({ number, title, children }) { return <article className="method-card"><span>{number}</span><h3>{title}</h3><p>{children}</p></article>; }

async function api(path, options = {}) {
  const init = { method: options.method || "GET", headers: { Accept: "application/json" } };
  if (options.body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(options.body); }
  const response = await fetch(path, init);
  let value;
  try { value = await response.json(); } catch { throw new Error(`Server returned ${response.status}`); }
  if (!response.ok) throw new Error(value.error || `Request failed with ${response.status}`);
  return value;
}

function fileToBase64(file) { return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(",", 2)[1]); reader.onerror = () => reject(new Error("The selected PDF could not be read.")); reader.readAsDataURL(file); }); }
function titleCase(value) { return String(value || "").replaceAll("_", " ").replaceAll("-", " ").split(/\s+/).map((item) => item.charAt(0).toUpperCase() + item.slice(1)).join(" "); }
function formatNumber(value) { return Number(value || 0).toLocaleString("en-IN"); }
function formatBytes(value) { const bytes = Number(value || 0); if (bytes < 1024) return `${bytes} B`; if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`; return `${(bytes / 1024 ** 2).toFixed(1)} MB`; }
