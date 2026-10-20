import { useEffect, useMemo, useRef, useState } from "react";
import ComparisonPanel from "./ComparisonPanel";
import { GenerationNotice, IndicatorStrip, ScoreExplanation, VersionStatus } from "./ResultInsights";
import { DeterminationCards, DirectAnswer, EvidenceList, ScenarioForm } from "./Determinations";
import { LegalChangeFingerprint } from "./Fingerprint";
import SourceHealth from "./SourceHealth";
import ComplianceRiskPanel from "./ComplianceRiskPanel";
import { DriftPanel, VerificationPanel, percent } from "./SharedPanels";
import AssistantResult from "./AssistantResult";
import { ComparisonPage, DriftExplanationPage, ScoreCalculationPage } from "./ExplanationPages";
import Notifications, { DiscoveryAlert, readSeen, saveSeen, useDiscoveries } from "./Notifications";
import FAQ from "./faq.json";

// Addresses of one stored analysis: #assistant/<id>, #drift/<id>, #calculation/<id>, #comparison/<id>. Plain #assistant, #drift,
// #calculation or #comparison reopen the analysis last shown. Older links (#analysis/<id>[/<view>], v0.14–v0.17) open the matching page.
const ANALYSIS_PAGES = ["assistant", "drift", "calculation", "comparison"];
const VIEW_PAGES = ["drift", "calculation", "comparison"];
// Smooth scrolling only when the reader has not asked for reduced motion.
export const scrollBehavior = () => (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");
const ANALYSIS_ID = /^an_[0-9a-f]{24}$/;
function parseRoute(hash) {
  const parts = hash.slice(1).split("?")[0].split("/");
  const id = ANALYSIS_ID.test(parts[1] || "") ? parts[1] : null;
  if (parts[0] === "analysis" && id) {
    const view = parts[2] === "scores" ? "calculation" : parts[2];
    return { section: VIEW_PAGES.includes(view) ? view : "assistant", analysisId: id };
  }
  return { section: parts[0] || "assistant", analysisId: ANALYSIS_PAGES.includes(parts[0]) ? id : null };
}
const pageHash = (page, id) => (ANALYSIS_PAGES.includes(page) && id ? `#${page}/${id}` : `#${page}`);

// Pages reached from an answer or an old link, not from the sidebar. "review" is the retired Case trace & review screen.
const PAGE_TITLES = { comparison: "Clause comparison", review: "Case trace & review (retired)" };
const sections = [
  { id: "assistant", number: "01", label: "Legal drift assistant" },
  { id: "drift", number: "02", label: "Drift explanation" },
  { id: "calculation", number: "03", label: "Score calculation" },
  { id: "corpus", number: "04", label: "Document repository" },
  { id: "method", number: "05", label: "How it works" },
  { id: "faq", number: "06", label: "Recent changes FAQ" },
  { id: "risk", number: "07", label: "Compliance risk" },
];
const KNOWN = new Set([...sections.map((item) => item.id), ...Object.keys(PAGE_TITLES)]);

// Recently asked questions stay in this browser only (question, mode and Act; never scenario facts or chosen sections).
const HISTORY_KEY = "tldrift:recent-questions";
const HISTORY_SIZE = 5;
export function readHistory() {
  try { const value = JSON.parse(window.localStorage.getItem(HISTORY_KEY) || "[]"); return Array.isArray(value) ? value.filter((row) => typeof row?.query === "string") : []; }
  catch { return []; }
}
const sameQuestion = (a, b) => a.query.trim().toLowerCase().replace(/\s+/g, " ") === b.query.trim().toLowerCase().replace(/\s+/g, " ");
export function remember(history, entry) {
  const next = [entry, ...history.filter((row) => !sameQuestion(row, entry))].slice(0, HISTORY_SIZE);
  try { window.localStorage.setItem(HISTORY_KEY, JSON.stringify(next)); } catch { /* storage unavailable: history is a convenience */ }
  return next;
}
// Follow-ups are built from the Act and sections the last answer returned; they are suggestions, not promised scores.
export function followUps(result) {
  const act = result?.question_frame?.principal?.name;
  if (!act) return [];
  const found = result.version_evidence?.section_candidates;
  if (found) {
    return found.candidates.filter((row) => row.status === "SUPPORTED").slice(0, 2)
      .map((row) => `Compare section ${row.section} of the ${act} before and after the ${row.amendment_year ? `${row.amendment_year} ` : ""}amendment.`);
  }
  return result.question_frame?.asks_about_versions ? [`What changed in the ${act}?`] : [];
}

export default function App() {
  const route = useMemo(() => parseRoute(window.location.hash), []);
  // Shareable question link: #assistant?q=<question> asks once on load.
  // Read once: the link is replaced by #assistant after loading, and must not then look like "no question".
  const [linkedQuestion] = useState(() => new URLSearchParams(window.location.hash.split("?")[1] || "").get("q")?.slice(0, 4000) || "");
  const [section, setSection] = useState(() => KNOWN.has(route.section) ? route.section : "assistant");
  const [analysisError, setAnalysisError] = useState("");
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [highlight, setHighlight] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [corpus, setCorpus] = useState(null);
  const [status, setStatus] = useState(null);
  const [loadError, setLoadError] = useState("");
  // A question to place in the box: { text, run, id }. run=true asks it once (FAQ cards, #assistant?q= links).
  const [starter, setStarter] = useState(() => (linkedQuestion ? { text: linkedQuestion, run: true, id: "link" } : null));
  const [history, setHistory] = useState(readHistory);
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
    if (!id || !ANALYSIS_ID.test(id)) return;
    setLoadingAnalysis(true);
    api(`/api/analyses/${id}`).then(setLastResult).catch((error) => setAnalysisError(`The linked analysis could not be loaded: ${error.message}`))
      .finally(() => setLoadingAnalysis(false));
  }, [route.analysisId, linkedQuestion]);

  // A #assistant?q= link asks once: its history entry is replaced so Back never re-asks it.
  useEffect(() => { if (linkedQuestion) window.history.replaceState(null, "", "#assistant"); }, [linkedQuestion]);

  const currentId = useRef(null);
  currentId.current = lastResult?.analysis_id || null;
  // Plain #drift / #calculation reopen the analysis last shown, whether asked here or opened from a link.
  useEffect(() => {
    if (lastResult?.analysis_id) try { window.sessionStorage.setItem("tldrift:last-analysis", lastResult.analysis_id); } catch { /* storage unavailable */ }
  }, [lastResult]);

  // Back/forward between pages of the same analysis switches the page; another analysis or a question link re-opens from the stored record.
  useEffect(() => {
    const onNavigate = () => {
      const next = parseRoute(window.location.hash);
      if (next.analysisId && next.analysisId !== currentId.current || /[?&]q=/.test(window.location.hash)) { window.location.reload(); return; }
      if (KNOWN.has(next.section)) setSection(next.section);
    };
    window.addEventListener("popstate", onNavigate);
    window.addEventListener("hashchange", onNavigate);
    return () => { window.removeEventListener("popstate", onNavigate); window.removeEventListener("hashchange", onNavigate); };
  }, []);

  const showResult = (value) => {
    setLastResult(value); setHighlight(null); setSection("assistant");
    if (value?.analysis_id) window.history.pushState(null, "", `#assistant/${value.analysis_id}`);
  };

  const navigate = (next) => {
    setMenuOpen(false); window.scrollTo({ top: 0, behavior: scrollBehavior() });
    setSection(next);
    window.history.pushState(null, "", pageHash(next, lastResult?.analysis_id));
  };
  // Evidence and rule-field links from either page open the Drift explanation page at the cited item.
  const openEvidence = (id) => {
    if (section !== "drift") navigate("drift");
    window.setTimeout(() => document.getElementById(`evidence-${id}`)?.focus(), 0);
  };
  const openField = (row) => {
    setHighlight({ label: row.label || row.field.replaceAll("_", " "), before: row.before_spans || [], after: row.after_spans || [] });
    if (section !== "drift") navigate("drift");
    window.setTimeout(() => document.getElementById("clause-pair-heading")?.focus(), 0);
  };
  const toAssistant = () => navigate("assistant");
  const activeNav = section;
  const pageProps = { analysis: lastResult, onEvidence: openEvidence, onField: openField, onAssistant: toAssistant, onPage: navigate, request: api };
  const discoveries = useDiscoveries(api);
  const [seen, setSeen] = useState(readSeen);
  const [panelOpen, setPanelOpen] = useState(false);
  const toggle = useRef(null);
  const unread = [...(discoveries.data?.latest || []), ...(discoveries.data?.older || [])].filter((row) => !seen.includes(row.key)).length;
  const markSeen = (ids) => { saveSeen(ids); setSeen(ids); };
  const closePanel = () => { setPanelOpen(false); toggle.current?.focus(); };

  // An FAQ card asks its question once; the previous answer is cleared so it cannot replace the question shown.
  const askFromFaq = (question) => {
    setLastResult(null); setHighlight(null);
    setStarter({ text: question, run: true, id: Date.now() });
    setSection("assistant"); setMenuOpen(false);
    window.history.pushState(null, "", "#assistant");
    window.scrollTo({ top: 0, behavior: scrollBehavior() });
  };
  // A section chosen from a list re-asks the same question, so only the question itself is remembered.
  const recordQuestion = (value, section) => {
    if (value?.analysis_id && !section) setHistory((rows) => remember(rows, { query: value.query, mode: value.mode, act: value.question_frame?.principal?.name || null }));
  };
  const clearHistory = () => { try { window.localStorage.removeItem(HISTORY_KEY); } catch { /* storage unavailable */ } setHistory([]); };

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <aside className={`sidebar ${menuOpen ? "open" : ""}`} aria-label="Primary navigation">
      <div className="brand"><div className="brand-mark">TL</div><div><strong>Temporal Legal Drift</strong><span>Indian Code RAG assistant</span></div></div>
      <nav className="nav-list">{sections.map((item) => <button key={item.id} type="button" aria-current={activeNav === item.id ? "page" : undefined} className={`nav-item ${activeNav === item.id ? "active" : ""}`} onClick={() => navigate(item.id)}><span>{item.number}</span>{item.label}</button>)}</nav>
      <a className="official-link side-link" href="https://indiacode.gov.in/" target="_blank" rel="noreferrer">India Code official website ↗</a>
    </aside>
    <div className={`workspace ${panelOpen ? "panel-open" : ""}`}>
      <header className="topbar"><button className="menu-toggle" onClick={() => setMenuOpen((open) => !open)} aria-label="Open navigation">☰</button><div><p className="eyebrow">Versioned Indian law</p><h1>{sections.find((item) => item.id === activeNav)?.label || PAGE_TITLES[activeNav]}</h1></div>
        <button ref={toggle} type="button" className="discoveries-toggle" aria-expanded={panelOpen} aria-controls="discoveries-panel" onClick={() => setPanelOpen((open) => !open)}
          aria-label={`Latest discoveries${unread > 0 ? `, ${unread} unread` : ""}`}>
          <span className="long">Latest discoveries</span><span className="short" aria-hidden="true">Discoveries</span>{unread > 0 && <span className="count" aria-hidden="true">{unread}</span>}</button></header>
      <Notifications {...discoveries} open={panelOpen} onClose={closePanel} seen={seen} onSeen={markSeen} />
      <DiscoveryAlert fresh={discoveries.fresh} onOpen={() => { discoveries.dismiss(); setPanelOpen(true); }} onDismiss={discoveries.dismiss} />
      <main id="main-content">
        {section === "assistant" && <AssistantWorkspace status={status} error={loadError || analysisError} starter={starter}
          result={lastResult} onResult={showResult} onPage={navigate} onEvidence={openEvidence}
          history={history} onAsked={recordQuestion} onClearHistory={clearHistory} />}
        {VIEW_PAGES.includes(section) && (lastResult?.analysis_id
          ? section === "drift" ? <DriftExplanationPage {...pageProps} highlight={highlight} onCalculation={() => navigate("calculation")} />
            : section === "comparison" ? <ComparisonPage {...pageProps} /> : <ScoreCalculationPage {...pageProps} />
          : <section className="page-section"><div className="section-header"><span className="section-kicker">{{ drift: "Drift explanation", calculation: "Score calculation", comparison: "Clause comparison" }[section]}</span>
            <h2>{loadingAnalysis ? "Loading the analysis…" : "Ask a comparison question first."}</h2>
            <p>{analysisError || { drift: "This page explains what the drift scores of the current analysis mean, with the before and after clauses and their sources.",
              calculation: "This page shows the exact inputs, formulas and worked calculation of the current analysis.",
              comparison: "This page shows the compared clauses of the current analysis side by side, with their sources." }[section]} General questions have no change scores.</p></div>
            <button className="send-button" type="button" onClick={() => navigate("assistant")}>Open legal drift assistant <span>→</span></button></section>)}
        {section === "corpus" && <CorpusBrowser corpus={corpus} error={loadError} status={status} />}
        {section === "method" && <Method />}
        {section === "faq" && <RecentChangesFaq onAsk={askFromFaq} />}
        {section === "risk" && <ComplianceRiskPanel request={api} />}
        {section === "review" && <section className="page-section"><div className="section-header"><span className="section-kicker">Retired page</span>
          <h2>Case trace & review is no longer part of this app</h2>
          <p>Case runs, their review history and the review ledger are kept unchanged for research and reproducibility; they are no longer shown here.
            New documents from the monitored sources are listed under Latest discoveries, and every answer shows its own sources and review state.</p></div>
          <button className="send-button" type="button" onClick={() => navigate("assistant")}>Open legal drift assistant <span>→</span></button></section>}
      </main>
    </div>
  </div>;
}

function AssistantWorkspace({ status, error: statusError, starter, result, onResult, onPage, onEvidence, history = [], onAsked = () => {}, onClearHistory }) {
  const [query, setQuery] = useState(starter?.text || result?.query || "");
  const [mode, setMode] = useState("specific");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const handled = useRef(null);  // the starter already placed; survives StrictMode's effect replay, so a question runs once
  const input = useRef(null);
  const pending = starter && handled.current !== starter.id;

  // A loaded or linked analysis shows its own question and mode, unless a newer question (FAQ, link) is about to replace it.
  useEffect(() => { if (result?.query && !pending) { setQuery(result.query); if (result.mode) setMode(result.mode); } }, [result]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!pending) return;
    handled.current = starter.id;
    setQuery(starter.text);
    if (starter.run) submit(null, starter.text); else input.current?.focus();
  }, [starter]);  // eslint-disable-line react-hooks/exhaustive-deps

  const prefill = (text) => { setQuery(text); input.current?.focus(); };
  const submit = async (event, text = query, scenario = null, runMode = mode, section = null) => {
    event?.preventDefault(); setError("");
    if (!text.trim()) return setError("Enter a question about the indexed Indian legal documents.");
    setBusy(true);
    try {
      const value = await api("/api/rag/query", { method: "POST", body: { query: text.trim(), mode: runMode, ...(scenario ? { scenario } : {}), ...(section ? { section } : {}) } });
      onResult(value);
      if (!scenario) onAsked(value, section);
      window.setTimeout(() => document.getElementById("rag-result")?.scrollIntoView?.({ behavior: scrollBehavior(), block: "start" }), 0);
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  // As in v0.13.0, the full question area (status, scheduled ingestion, suggestions) stays above every answer.
  return <section className="page-section">
    <div className="hero">
      <span className="section-kicker">Single-prompt legal research</span>
      <h2>Ask what changed in Indian law.</h2>
      <p>The assistant checks the live India Code repository and uses the local evidence cache for reproducible amendment comparisons and traceable source anchors.</p>
      <RepositoryStatus status={status} error={statusError} />
      <SourceHealth request={api} />
      <form className="prompt-panel" onSubmit={submit}>
        <label htmlFor="legal-query" className="sr-only">Legal research question</label>
        <textarea id="legal-query" ref={input} rows="4" maxLength="4000" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ask a question, for example: What changed in the IT Act amendment regarding data privacy?" />
        <div className="prompt-actions">
          <div className="mode-switch" role="group" aria-label="Analysis mode">
            <button type="button" aria-pressed={mode === "specific"} className={mode === "specific" ? "active" : ""} onClick={() => setMode("specific")}><strong>Specific</strong><small>Clause-level analysis</small></button>
            <button type="button" aria-pressed={mode === "generic"} className={mode === "generic" ? "active" : ""} onClick={() => setMode("generic")}><strong>Generic</strong><small>High-level overview</small></button>
          </div>
          <button className="send-button" type="submit" disabled={busy || !query.trim()}>{busy ? "Searching…" : "Analyse"}<span aria-hidden="true">→</span></button>
        </div>
      </form>
      <p className="jump-row"><button type="button" className="link-button" onClick={() => { const area = document.getElementById("question-chips");
        area?.scrollIntoView?.({ behavior: scrollBehavior(), block: "center" }); area?.focus(); }}>Recently asked and suggested questions ↓</button></p>
      <QuestionChips history={history} followUps={followUps(result)} onPick={prefill} onClear={onClearHistory} />
      {error && <div className="form-error" role="alert"><strong>Analysis could not be completed.</strong><span>{error}</span></div>}
    </div>
    {busy && <div className="loading-panel"><span className="spinner"/><div><strong>Retrieving versioned legal evidence…</strong><p>Classifying the question, matching documents and validating the response context.</p></div></div>}
    {result && (result.analysis_id
      ? <AssistantResult analysis={result} onPage={onPage} onEvidence={onEvidence} busy={busy}
          onSection={(section) => submit(null, result.query, null, result.mode, section)} />
      : <RagResult result={result} onExplain={() => onPage?.("calculation")} busy={busy} onScenario={(scenario) => submit(null, result.query, scenario)} />)}
  </section>;
}

// "Recently asked" (this browser), "Suggested follow-ups" (from the last answer) and verified starter examples. A chip only fills the box.
function QuestionChips({ history, followUps: next, onPick, onClear }) {
  const chips = (items, label) => items.map((text) => <button key={label + text} type="button" onClick={() => onPick(text)}>{text}</button>);
  return <div className="question-chips" id="question-chips" tabIndex={-1} role="region" aria-label="Recently asked and suggested questions">
    {history.length > 0 && <div className="suggestions" role="group" aria-label="Recently asked"><span>Recently asked</span>
      {chips(history.map((row) => row.query), "recent")}
      <button type="button" className="clear-history" onClick={onClear}>Clear history</button></div>}
    {next.length > 0 && <div className="suggestions" role="group" aria-label="Suggested follow-ups"><span>Suggested follow-ups</span>{chips(next, "next")}</div>}
    <div className="suggestions" role="group" aria-label="Try asking"><span>Try asking</span>{chips(FAQ.starters, "starter")}</div>
    {next.length > 0 && <p className="panel-note">Follow-ups are built from your last answer; a comparison appears only if the evidence supports it.</p>}
  </div>;
}

function RepositoryStatus({ status, error }) {
  return <div className={`repository-status ${error ? "error" : ""}`}>
    <span className="status-dot" />
    <div><strong>{error ? "Repository unavailable" : status?.ready ? "India Code connection ready" : "Preparing legal repository"}</strong><small>{error || (status ? `Live India Code lookup · ${formatNumber(status.document_count)} cached documents · ${formatNumber(status.chunk_count)} searchable chunks` : "Connecting to India Code and the local evidence cache…")}</small></div>
    {status && <span className="status-badge">Live + cached</span>}
  </div>;
}

export function RagResult({ result, onExplain, onScenario = () => {}, busy = false }) {
  if (result.analysis_id) return <AssistantResult analysis={result} onScenario={onScenario} busy={busy} />;
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


function RecentChangesFaq({ onAsk }) {
  const kinds = { act: "Shows the sections you can compare", section: "Opens a clause comparison" };
  return <section className="page-section"><div className="section-header"><span className="section-kicker">Frequently asked questions</span>
    <h2>Questions about amended Acts in this corpus</h2>
    <p>Each question was checked against the evidence held here: it either lists the sections of an Act that can be compared, or opens a comparison of one section.
      This corpus is a research sample, not complete or up-to-date India Code coverage.</p></div>
    <div className="faq-grid">{FAQ.questions.map((item) => <article className="faq-card" key={item.question}><span>{item.topic}</span><h3>{item.question}</h3>
      <p className="panel-note">{kinds[item.kind]}</p>
      <button type="button" onClick={() => onAsk(item.question)}>Ask this question <b aria-hidden="true">→</b></button></article>)}</div>
    <article className="source-guidance"><div><span className="section-kicker">Official source</span><h3>Check the latest official text</h3><p>Whether a change applies depends on publication, commencement and applicability evidence. Confirm the complete record on India Code.</p></div><a href="https://indiacode.gov.in/" target="_blank" rel="noreferrer">Visit India Code ↗</a></article></section>;
}

async function api(path, options = {}) { const init = { method: options.method || "GET", headers: { Accept: "application/json" } }; if (options.body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(options.body); } const response = await fetch(path, init); let value; try { value = await response.json(); } catch { throw new Error(`Server returned ${response.status}`); } if (!response.ok) throw new Error(value.error || `Request failed with ${response.status}`); return value; }
function titleCase(value) { return String(value || "").replaceAll("_", " ").replaceAll("-", " ").split(/\s+/).map((item) => item.charAt(0).toUpperCase() + item.slice(1)).join(" "); }
function formatNumber(value) { return Number(value || 0).toLocaleString("en-IN"); }
