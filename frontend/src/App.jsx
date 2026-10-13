import { useEffect, useMemo, useRef, useState } from "react";
import CaseReviewPanel from "./CaseReviewPanel";
import ComparisonPanel from "./ComparisonPanel";
import { GenerationNotice, IndicatorStrip, ScoreExplanation, VersionStatus } from "./ResultInsights";
import { DeterminationCards, DirectAnswer, EvidenceList, ScenarioForm } from "./Determinations";
import { LegalChangeFingerprint } from "./Fingerprint";
import SourceHealth from "./SourceHealth";
import ComplianceRiskPanel from "./ComplianceRiskPanel";
import { DriftPanel, VerificationPanel, percent } from "./SharedPanels";
import AnalysisWorkspace, { TABS } from "./AnalysisWorkspace";

// #analysis/<id>/<view> is the shareable address of one stored analysis. #drift and #calculation open those views of the
// current analysis; v0.14 links to the former "scores" view open Score Calculation.
const VIEW_SECTIONS = ["drift", "calculation"];
function parseRoute(hash) {
  const parts = hash.slice(1).split("?")[0].split("/");
  if (parts[0] === "analysis" && /^an_[0-9a-f]{24}$/.test(parts[1] || "")) {
    const view = parts[2] === "scores" ? "calculation" : parts[2];
    return { section: "assistant", analysisId: parts[1], tab: TABS.some((t) => t.id === view) ? view : "answer" };
  }
  return { section: parts[0], analysisId: null, tab: VIEW_SECTIONS.includes(parts[0]) ? parts[0] : "answer" };
}

const sections = [
  { id: "assistant", number: "01", label: "Legal drift assistant" },
  { id: "drift", number: "02", label: "Drift explanation" },
  { id: "calculation", number: "03", label: "Score calculation" },
  { id: "corpus", number: "04", label: "Document repository" },
  { id: "method", number: "05", label: "How it works" },
  { id: "faq", number: "06", label: "Recent changes FAQ" },
  { id: "risk", number: "07", label: "Compliance risk" },
  { id: "review", number: "08", label: "Case trace & review" },
];

const suggestions = [
  "What changed in the IT Act amendment regarding data privacy?",
  "Compare Section 19 before and after the IT Amendment Act, 2008.",
  "What penalties were introduced for privacy violations in the IT Act?",
];

export default function App() {
  // Deep links: #review or #review/run_<id> (validated) so a case can be shared with a reviewer.
  const initialHash = window.location.hash.slice(1).split("?")[0].split("/");
  const route = useMemo(() => parseRoute(window.location.hash), []);
  // Shareable question link: #assistant?q=<question> asks once on load.
  const linkedQuestion = new URLSearchParams(window.location.hash.split("?")[1] || "").get("q")?.slice(0, 4000) || "";
  const [section, setSection] = useState(() => sections.some((item) => item.id === route.section) ? route.section : "assistant");
  const [tab, setTab] = useState(route.tab);
  const [analysisError, setAnalysisError] = useState("");
  const initialRunId = /^run_[0-9a-f]{24}$/.test(initialHash[1] || "") ? initialHash[1] : null;
  const [menuOpen, setMenuOpen] = useState(false);
  const [corpus, setCorpus] = useState(null);
  const [status, setStatus] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [starterQuery, setStarterQuery] = useState(linkedQuestion);
  // The single source of truth for every view: the stored analysis, fetched by ID.
  const [lastResult, setLastResult] = useState(null);

  useEffect(() => {
    Promise.all([api("/api/corpus"), api("/api/rag/status")])
      .then(([corpusData, statusData]) => { setCorpus(corpusData); setStatus(statusData); })
      .catch((error) => setLoadError(error.message));
  }, []);

  useEffect(() => {
    let id = route.analysisId;
    if (!id && !linkedQuestion) { try { id = window.sessionStorage.getItem("tldrift:last-analysis"); } catch { id = null; } }
    if (!id || !/^an_[0-9a-f]{24}$/.test(id)) return;
    api(`/api/analyses/${id}`).then(setLastResult).catch((error) => setAnalysisError(`The linked analysis could not be loaded: ${error.message}`));
  }, [route.analysisId, linkedQuestion]);

  const currentId = useRef(null);
  currentId.current = lastResult?.analysis_id || null;
  // The Drift explanation / Score calculation entries are views of the current analysis once it has loaded.
  useEffect(() => {
    if (VIEW_SECTIONS.includes(section) && lastResult?.analysis_id) { setTab(section); setSection("assistant"); }
  }, [section, lastResult]);

  // Back/forward between views of the same analysis switches the view; another analysis or a question link re-opens from the stored record.
  useEffect(() => {
    const onNavigate = () => {
      const next = parseRoute(window.location.hash);
      if (next.analysisId && next.analysisId === currentId.current) { setSection("assistant"); setTab(next.tab); return; }
      if (next.analysisId || /[?&]q=/.test(window.location.hash)) { window.location.reload(); return; }
      if (sections.some((item) => item.id === next.section)) setSection(next.section);
    };
    window.addEventListener("popstate", onNavigate);
    window.addEventListener("hashchange", onNavigate);
    return () => { window.removeEventListener("popstate", onNavigate); window.removeEventListener("hashchange", onNavigate); };
  }, []);

  const showResult = (value, nextTab = "answer") => {
    setLastResult(value);
    if (value?.analysis_id) {
      setTab(nextTab);
      window.history.pushState(null, "", `#analysis/${value.analysis_id}/${nextTab}`);
      try { window.sessionStorage.setItem("tldrift:last-analysis", value.analysis_id); } catch { /* storage unavailable */ }
    }
  };
  const changeTab = (next) => {
    setTab(next);
    if (lastResult?.analysis_id) window.history.pushState(null, "", `#analysis/${lastResult.analysis_id}/${next}`);
  };

  const navigate = (next) => {
    setMenuOpen(false); window.scrollTo({ top: 0, behavior: "smooth" });
    if (VIEW_SECTIONS.includes(next) && lastResult?.analysis_id) { setSection("assistant"); changeTab(next); return; }
    setSection(next); window.history.pushState(null, "", `#${next}`);
  };
  const activeNav = section === "assistant" && VIEW_SECTIONS.includes(tab) ? tab : section;

  const askFromFaq = (question) => {
    setStarterQuery(question); setSection("assistant"); setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <aside className={`sidebar ${menuOpen ? "open" : ""}`} aria-label="Primary navigation">
      <div className="brand"><div className="brand-mark">TL</div><div><strong>Temporal Legal Drift</strong><span>Indian Code RAG assistant</span></div></div>
      <nav className="nav-list">{sections.map((item) => <button key={item.id} type="button" aria-current={activeNav === item.id ? "page" : undefined} className={`nav-item ${activeNav === item.id ? "active" : ""}`} onClick={() => navigate(item.id)}><span>{item.number}</span>{item.label}</button>)}</nav>
      <a className="official-link side-link" href="https://indiacode.gov.in/" target="_blank" rel="noreferrer">India Code official website ↗</a>
    </aside>
    <div className="workspace">
      <header className="topbar"><button className="menu-toggle" onClick={() => setMenuOpen((open) => !open)} aria-label="Open navigation">☰</button><div><p className="eyebrow">Versioned Indian law</p><h1>{sections.find((item) => item.id === activeNav)?.label}</h1></div></header>
      <main id="main-content">
        {section === "assistant" && <AssistantWorkspace status={status} error={loadError || analysisError} starterQuery={starterQuery} autoRun={Boolean(linkedQuestion)}
          result={lastResult} onResult={showResult} tab={tab} onTab={changeTab} onReview={() => navigate("review")} />}
        {VIEW_SECTIONS.includes(section) && <section className="page-section"><div className="section-header"><span className="section-kicker">{section === "drift" ? "Drift explanation" : "Score calculation"}</span>
          <h2>Ask a comparison question first.</h2><p>This view explains the {section === "drift" ? "changed words and legal-rule fields" : "inputs, formulas and contributions"} of the current analysis, with its cited evidence. General questions have no change scores.</p></div>
          <button className="send-button" type="button" onClick={() => navigate("assistant")}>Open legal drift assistant <span>→</span></button></section>}
        {section === "corpus" && <CorpusBrowser corpus={corpus} error={loadError} status={status} />}
        {section === "method" && <Method />}
        {section === "faq" && <RecentChangesFaq onAsk={askFromFaq} />}
        {section === "risk" && <ComplianceRiskPanel request={api} />}
        {section === "review" && <CaseReviewPanel request={api} initialRunId={initialRunId} />}
      </main>
    </div>
  </div>;
}

function AssistantWorkspace({ status, error: statusError, starterQuery, autoRun = false, result, onResult, tab, onTab, onReview }) {
  const [query, setQuery] = useState(starterQuery || "");
  const [mode, setMode] = useState("specific");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { if (starterQuery) setQuery(starterQuery); }, [starterQuery]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (autoRun && starterQuery) submit(null, starterQuery); }, []);

  // A loaded or linked analysis shows its own question and mode, so a re-run asks exactly the same thing.
  useEffect(() => { if (result?.query) { setQuery(result.query); if (result.mode) setMode(result.mode); } }, [result]);

  const submit = async (event, text = query, scenario = null, keepTab = null, runMode = mode) => {
    event?.preventDefault(); setError("");
    if (!text.trim()) return setError("Enter a question about the indexed Indian legal documents.");
    setBusy(true);
    try {
      const value = await api("/api/rag/query", { method: "POST", body: { query: text.trim(), mode: runMode, ...(scenario ? { scenario } : {}) } });
      onResult(value, keepTab || "answer");
      window.setTimeout(() => document.getElementById("rag-result")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  const compact = Boolean(result);
  return <section className="page-section">
    <div className={`hero ${compact ? "compact" : ""}`}>
      {!compact && <><span className="section-kicker">Single-prompt legal research</span>
      <h2>Ask what changed in Indian law.</h2>
      <p>The assistant checks the live India Code repository and uses the local evidence cache for reproducible amendment comparisons and traceable source anchors.</p>
      <RepositoryStatus status={status} error={statusError} />
      <SourceHealth request={api} /></>}
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
      {!compact && <div className="suggestions"><span>Try asking</span>{suggestions.map((item) => <button key={item} type="button" onClick={() => setQuery(item)}>{item}</button>)}</div>}
      {error && <div className="form-error" role="alert"><strong>Analysis could not be completed.</strong><span>{error}</span></div>}
    </div>
    {busy && <div className="loading-panel"><span className="spinner"/><div><strong>Retrieving versioned legal evidence…</strong><p>Classifying the question, matching documents and validating the response context.</p></div></div>}
    {result && (result.analysis_id
      ? <AnalysisWorkspace analysis={result} tab={tab} onTab={onTab} busy={busy} onReview={onReview}
          onScenario={(scenario) => submit(null, result.query, scenario, tab, result.mode)} />
      : <RagResult result={result} onExplain={() => onTab?.("calculation")} busy={busy} onScenario={(scenario) => submit(null, result.query, scenario)} />)}
  </section>;
}

function RepositoryStatus({ status, error }) {
  return <div className={`repository-status ${error ? "error" : ""}`}>
    <span className="status-dot" />
    <div><strong>{error ? "Repository unavailable" : status?.ready ? "India Code connection ready" : "Preparing legal repository"}</strong><small>{error || (status ? `Live India Code lookup · ${formatNumber(status.document_count)} cached documents · ${formatNumber(status.chunk_count)} searchable chunks` : "Connecting to India Code and the local evidence cache…")}</small></div>
    {status && <span className="status-badge">Live + cached</span>}
  </div>;
}

export function RagResult({ result, onExplain, onScenario = () => {}, busy = false }) {
  if (result.analysis_id) return <AnalysisWorkspace analysis={result} onScenario={onScenario} busy={busy} />;
  if (/^rag-answer-v[23]$/.test(result.contract_version || "")) return <RagResultV2 result={result} onExplain={onExplain} onScenario={onScenario} busy={busy} />;
  const answer = result.answer;
  const metrics = result.metrics;
  const isSummary = answer.answer_type === "single_document_summary";
  // Only aligned evidence is called a before/after version; other pairs are labelled as source excerpts.
  const pairLabels = {
    graph_aligned_amendment_fragments: ["Before (amendment-controlled fragment)", "After (amendment-controlled fragment)"],
    consolidated_footnote_reconstruction: ["Reconstructed earlier wording (from consolidated-text footnote)", "Current consolidated text"],
  }[result.retrieval?.pair_status] || ["Amendment instruction (source excerpt)", "Consolidated text (source excerpt)"];
  return <section id="rag-result" className="results">
    <div className="result-heading"><div><span className="section-kicker">Grounded response</span><h2>{titleCase(result.intent)}</h2></div><div className="mode-badge">{titleCase(result.mode)} mode</div></div>
    <GenerationNotice method={answer.generation_method} />
    <VersionStatus comparison={result.comparison} metrics={metrics} />
    <IndicatorStrip metrics={metrics} comparison={result.comparison} />
    <article className="answer-card">
      {isSummary ? <AnswerSection label="Short answer" text={answer.short_answer || answer.post_amendment_revision} tone="summary" /> : <><AnswerSection label={pairLabels[0]} text={answer.pre_amendment_baseline} tone="before" /><div className="answer-divider" /><AnswerSection label={pairLabels[1]} text={answer.post_amendment_revision} tone="after" /></>}
      <div className="difference-summary"><span className="section-kicker">{isSummary ? "Key points" : "Key differences summary"}</span><ul>{answer.key_differences.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
    </article>
    <ComparisonPanel comparison={result.comparison} />
    {metrics ? <><DriftPanel metrics={metrics} /><ScoreExplanation metrics={metrics} /><button className="explain-drift-button" type="button" onClick={onExplain}>Explain these scores with PDF evidence <span>→</span></button></> : <article className="empty-analysis"><strong>{isSummary ? "Document summary" : "Drift metrics unavailable"}</strong><p>{isSummary ? "Drift scores are shown only when the question asks for a comparison and a supported pre/post evidence pair is available." : "A supported pre/post evidence pair was not found for this query."}</p></article>}
    <div className="result-columns">
      <VerificationPanel verification={result.verification} />
      <EvidencePanel citations={result.citations} retrieval={result.retrieval} />
    </div>
    {(result.source_fidelity_warnings || []).map((item) => <div className="warning-note" role="alert" key={item.entry_id}><strong>Source text unreadable: {item.entry_id}</strong><span>{item.detail} Treat quoted wording from this source as unverified.</span></div>)}
    {answer.generation_warning && <div className="warning-note">{answer.generation_warning}. The displayed response uses the evidence-only fallback.</div>}
    <article className="source-guidance"><div><span className="section-kicker">Authoritative source</span><h3>Verify the complete legal text</h3><p>{result.source_guidance.message}</p></div><a href={result.source_guidance.url} target="_blank" rel="noreferrer">{result.source_guidance.label} ↗</a></article>
    <p className="research-note">Scores describe retrieved-text movement and evidence alignment; they are not probabilities or legal advice.</p>
  </section>;
}

const VERSION_CLASSES = new Set(["GRAPH_TRANSITION_FRAGMENTS", "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION"]);

// rag-answer-v2: answer first, then the four separate determinations, facts, clause cards and sources.
function RagResultV2({ result, onExplain, onScenario, busy }) {
  const { answer, metrics, comparison, determinations } = result;
  const supported = VERSION_CLASSES.has(comparison?.support_class);
  return <section id="rag-result" className="results">
    <div className="result-heading"><div><span className="section-kicker">Grounded response</span><h2>{result.question_frame?.asks_about_versions ? "Version comparison" : "Answer"}</h2></div><div className="mode-badge">{titleCase(result.mode)} mode</div></div>
    <GenerationNotice method={answer.generation_method} />
    {supported && <VersionStatus comparison={comparison} metrics={metrics} />}
    <DirectAnswer answer={answer} />
    {result.scenario && <p className="panel-note">Using your facts: {Object.entries({ ...result.scenario, ...(result.scenario.facts || {}) }).filter(([key, value]) => key !== "facts" && value !== null && value !== "").map(([key, value]) => `${key.replaceAll("_", " ")}: ${value === true ? "yes" : value === false ? "no" : String(value).replaceAll("_", " ")}`).join("; ")}.</p>}
    {result.fingerprint && <LegalChangeFingerprint fingerprint={result.fingerprint}
      legacy={metrics && <><p className="panel-note"><strong>Legacy diagnostic (drift-metrics-v3).</strong> {metrics.legacy_diagnostic?.note}</p><DriftPanel metrics={metrics} legacy /><ScoreExplanation metrics={metrics} /></>} />}
    <DeterminationCards determinations={determinations} />
    <ScenarioForm key={JSON.stringify(result.scenario || {}) + result.query} determinations={determinations} extraNeeds={result.fingerprint?.outcome_drift?.needs || []} scenario={result.scenario} onSubmit={onScenario} busy={busy} />
    {supported && <ComparisonPanel comparison={comparison} />}
    {metrics && !result.fingerprint && <><DriftPanel metrics={metrics} /><ScoreExplanation metrics={metrics} /><button className="explain-drift-button" type="button" onClick={onExplain}>Explain these scores with PDF evidence <span>→</span></button></>}
    <EvidenceList evidence={result.evidence} />
    <div className="result-columns"><VerificationPanel verification={result.verification} /></div>
    {(result.source_fidelity_warnings || []).map((item) => <div className="warning-note" role="alert" key={item.entry_id}><strong>Source text unreliable: {item.entry_id}</strong><span>{item.detail} Treat quoted wording from this source as unverified.</span></div>)}
    {answer.generation_warning && <div className="warning-note">{answer.generation_warning}. The displayed response uses the evidence-only fallback.</div>}
    {result.source_guidance && <article className="source-guidance"><div><span className="section-kicker">Authoritative source</span><h3>Verify the complete legal text</h3><p>{result.source_guidance.message}</p></div><a href={result.source_guidance.url} target="_blank" rel="noreferrer">{result.source_guidance.label} ↗</a></article>}
  </section>;
}

function AnswerSection({ label, text, tone }) { return <section className={`answer-section ${tone}`}><div className="answer-label"><span>{tone === "before" ? "B" : tone === "after" ? "A" : "S"}</span><strong>{label}</strong></div><p>{text}</p></section>; }

function EvidencePanel({ citations, retrieval }) {
  const amendments = retrieval.live_indiacode?.amendments || [];
  return <article className="panel compact"><span className="section-kicker">Retrieved evidence</span><h3>{citations.length} source anchor{citations.length === 1 ? "" : "s"}</h3>{citations.length ? <div className="citation-list">{citations.map((item) => <a key={item.chunk_id} href={item.source_url || item.official_portal_url} target="_blank" rel="noreferrer"><span>{item.label === "pre" ? "Amending instruction" : "Act text"} · {item.source_anchor || "Document"}</span><strong>{item.act_name}</strong><small>{item.version} · {item.official_identifier}</small></a>)}</div> : <p className="panel-note">No local citation was available.</p>}{amendments.length > 0 && <div className="live-amendments"><h4>Related India Code amendment records</h4><p>These records show amendment history. They are not treated as reconstructed pre/post text automatically.</p><div className="amendment-links">{amendments.map((item) => <a key={`${item.official_identifier}-${item.target_act}`} href={item.source_url} target="_blank" rel="noreferrer"><strong>{item.title}</strong><small>{item.target_act || "Target Act not stated"}{item.year ? ` · ${item.year}` : ""}</small></a>)}</div></div>}<p className="panel-note">Pair status: {titleCase(retrieval.pair_status)}</p></article>;
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
  ["4", "Compare", "Calculate vector (feature-hash), lexical and conceptual movement on the retrieved excerpts."],
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
