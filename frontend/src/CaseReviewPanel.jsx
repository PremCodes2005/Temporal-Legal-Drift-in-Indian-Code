import { useCallback, useEffect, useState } from "react";

const STAGE_LABELS = {
  source: "Authoritative source",
  graph: "Provision version",
  applicability: "Applies to this date?",
  materiality: "Materiality (machine triage)",
  risk: "Conditional risk",
  explanation: "Explanation check",
};
const STATUS_TEXT = {
  OK: "Supported",
  UNRESOLVED: "Unresolved",
  NOT_REQUESTED: "Not requested",
  FAILED: "Failed",
  SKIPPED_UPSTREAM_FAILURE: "Skipped",
  INVALID: "Invalid",
};
const ACTIONS = [
  ["ACKNOWLEDGE", "Acknowledge (I checked the evidence)"],
  ["REQUEST_CHANGES", "Request changes"],
  ["ESCALATE", "Escalate to a qualified legal reviewer"],
  ["RECORD_OPINION", "Record an opinion"],
];
const EMPTY_CASE = { case_id: "", act: "", section: "", reference_date: "" };

export default function CaseReviewPanel({ request, initialRunId = null }) {
  const [runs, setRuns] = useState(null);
  const [reviewers, setReviewers] = useState([]);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(EMPTY_CASE);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => request("/api/runs").then((value) => setRuns(value.runs)).catch((failure) => setError(failure.message)), [request]);
  useEffect(() => {
    load();
    request("/api/reviewers").then((value) => setReviewers(value.reviewers)).catch((failure) => setError(failure.message));
  }, [load, request]);

  const open = useCallback(async (id) => {
    setError(""); setBusy(true);
    try { setSelected(await request(`/api/runs/${id}`)); window.history.replaceState(null, "", `#review/${id}`); }
    catch (failure) { setError(failure.message); } finally { setBusy(false); }
  }, [request]);
  useEffect(() => { if (initialRunId) open(initialRunId); }, [initialRunId, open]);
  const runCase = async (event) => {
    event.preventDefault(); setError(""); setBusy(true);
    try { const value = await request("/api/runs", { method: "POST", body: form }); setSelected(value); load(); }
    catch (failure) { setError(failure.message); } finally { setBusy(false); }
  };

  return <section className="page-section">
    <div className="section-header"><span className="section-kicker">Case trace and review</span><h2>Follow one question from source to review.</h2>
      <p>Each run records the source, provision version, applicability, materiality, risk and explanation stages. Recording a review is an audit entry, <strong>not legal approval</strong>.</p></div>
    {error && <div className="form-error" role="alert">{error}</div>}
    <div className="review-layout">
      <div>
        <form className="panel review-form" onSubmit={runCase} aria-label="Run a new case">
          <h3>Run a case</h3>
          {[["case_id", "Case name", "text"], ["act", "Act (corpus id)", "text"], ["section", "Section", "text"], ["reference_date", "Reference date", "date"]].map(([key, label, type]) =>
            <label key={key}>{label}<input required type={type} disabled={busy} value={form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} /></label>)}
          <button className="send-button" type="submit" disabled={busy}>{busy ? "Running…" : "Run case"}</button>
        </form>
        <article className="panel"><h3>Recorded runs</h3>
          {runs === null && !error && <p role="status">Loading runs…</p>}
          {runs?.length === 0 && <p className="panel-note">No runs recorded yet.</p>}
          {runs?.length > 0 && <ul className="run-list">{runs.map((run) => <li key={run.correlation_id}><button type="button" onClick={() => open(run.correlation_id)} aria-current={selected?.record.correlation_id === run.correlation_id}>
            <strong>{run.case.case_id}</strong><small>{run.case.act} s.{run.case.section} · {run.case.reference_date}</small><span className="state-pill">{run.review_state.replaceAll("_", " ").toLowerCase()}</span></button></li>)}</ul>}
        </article>
      </div>
      <div>{selected ? <RunDetail detail={selected} reviewers={reviewers} request={request} onUpdated={(value) => { setSelected(value); load(); }} /> : <article className="empty-analysis"><strong>No case selected</strong><p>Run a case or open a recorded run to see its trace.</p></article>}</div>
    </div>
  </section>;
}

function RunDetail({ detail, reviewers, request, onUpdated }) {
  const { record, review_state: state, review_history: history, ledger_integrity_errors: ledgerErrors } = detail;
  const explanation = record.stages.explanation?.output;
  const [review, setReview] = useState({ action: "ACKNOWLEDGE", reviewer_id: reviewers[0]?.reviewer_id || "", reason: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setReview((old) => ({ ...old, reviewer_id: old.reviewer_id || reviewers[0]?.reviewer_id || "" })); }, [reviewers]);
  const submit = async (event) => {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      const value = await request("/api/reviews", { method: "POST", body: { ...review, subject_id: record.correlation_id, expected_prior_state: state } });
      setReview({ ...review, reason: "" }); onUpdated(value.run);
    } catch (failure) { setError(failure.message); } finally { setBusy(false); }
  };
  return <article className="panel run-detail" aria-live="polite">
    <span className="section-kicker">{record.correlation_id}</span>
    <h3>{record.case.question || `${record.case.act} section ${record.case.section} on ${record.case.reference_date}`}</h3>
    <p className="state-banner">Review state: <strong>{state.replaceAll("_", " ").toLowerCase()}</strong> · Legal validation: <strong>unverified</strong></p>
    {explanation ? <section aria-label="Short answer"><h4>Short answer</h4><ul className="claim-list">{explanation.claims.map((claim, index) => <li key={index}>{claim.text}</li>)}</ul>
      {explanation.uncertainty.length > 0 && <div className="warning-note"><strong>What cannot be determined</strong><span>{explanation.uncertainty.map((item) => item.replaceAll("_", " ")).join("; ")}</span></div>}</section>
      : <div className="warning-note" role="alert"><strong>No explanation</strong><span>An upstream stage failed; the case is escalated.</span></div>}
    <h4>Stage trace</h4>
    <ol className="stage-list">{Object.keys(STAGE_LABELS).filter((name) => record.stages[name]).map((name) => [name, record.stages[name]]).map(([name, stage]) => <li key={name} className={`stage ${stage.status.toLowerCase()}`}><span>{STAGE_LABELS[name] || name}</span><strong>{STATUS_TEXT[stage.status] || stage.status}</strong>{stage.error && <small>{stage.error}</small>}</li>)}</ol>
    {explanation?.citations.length > 0 && <><h4>Evidence</h4><ul className="evidence-list">{explanation.citations.map((item) => <li key={item.anchor_id}><span>{item.role.replaceAll("_", " ")}{item.page ? ` · page ${item.page}, line ${item.line}` : item.locator ? ` · ${item.locator}` : ""}</span><q>{item.quote}</q>{item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">Open source ↗</a>}</li>)}</ul></>}
    <h4>Review</h4>
    <p className="panel-note">Registered reviewers here are not qualified legal reviewers. An entry records who checked what and why; it never makes the answer legally final.</p>
    {ledgerErrors.length > 0 && <div className="form-error" role="alert">Review ledger integrity check failed; new reviews are blocked.</div>}
    {error && <div className="form-error" role="alert">{error}</div>}
    <form className="review-form" onSubmit={submit}>
      <label>Reviewer<select required disabled={busy} value={review.reviewer_id} onChange={(event) => setReview({ ...review, reviewer_id: event.target.value })}>{reviewers.map((item) => <option key={item.reviewer_id} value={item.reviewer_id}>{item.display_name} ({item.role.replaceAll("_", " ")})</option>)}</select></label>
      <label>Action<select disabled={busy} value={review.action} onChange={(event) => setReview({ ...review, action: event.target.value })}>{ACTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Reason (required, 10–2000 characters)<textarea required minLength={10} maxLength={2000} disabled={busy} value={review.reason} onChange={(event) => setReview({ ...review, reason: event.target.value })} /></label>
      <button className="send-button" type="submit" disabled={busy || ledgerErrors.length > 0}>{busy ? "Recording…" : "Record review"}</button>
    </form>
    <h4>Audit trail</h4>
    {history.length === 0 ? <p className="panel-note">No review entries yet.</p> : <ol className="audit-list">{history.map((entry) => <li key={entry.entry_sha256}><strong>{entry.prior_state.replaceAll("_", " ").toLowerCase()} → {entry.new_state.replaceAll("_", " ").toLowerCase()}</strong><span>{entry.reviewer_id} ({entry.reviewer_role.replaceAll("_", " ")}) · {entry.recorded_at}</span><p>{entry.reason}</p></li>)}</ol>}
  </article>;
}
