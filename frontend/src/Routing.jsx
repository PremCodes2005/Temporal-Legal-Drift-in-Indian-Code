import { useId, useState } from "react";

// rag-answer-v6 routing: which Act the question was read as, the choice the user must make, and records from the monitored sources.
// Every value is read from the stored analysis (routing, latest_records); nothing is decided here.
const ACT_ROUTES = ["act_identified", "act_comparison", "amendment_mismatch"];
const actLabel = (act) => `${act.name}${act.year && !act.name.includes(act.year) ? ` ${act.year}` : ""}`;
const when = (value) => (value ? String(value).slice(0, 16).replace("T", " ") + (String(value).length > 10 ? " UTC" : "") : "not stated");

// "Interpreted as: <Act>" with a way to answer from another Act instead.
export function InterpretedAs({ routing, acts = [], onAct, busy }) {
  const [open, setOpen] = useState(false);
  const [choice, setChoice] = useState("");
  const pickId = useId();
  if (!routing || !ACT_ROUTES.includes(routing.route) || !routing.interpreted_acts?.length) return null;
  const chosen = routing.reason_code === "USER_SELECTED_ACT";
  return <div className="interpreted-as" role="note">
    <p><span className="section-kicker">{chosen ? "Act you chose" : "Interpreted as"}</span>
      <strong>{routing.interpreted_acts.map(actLabel).join(routing.route === "act_comparison" ? " and " : " · ")}</strong>
      {acts.length > 0 && <button type="button" className="link-button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        {open ? "Cancel" : "Not this Act?"}</button>}</p>
    {open && <form className="act-correction" onSubmit={(event) => { event.preventDefault(); if (choice) { setOpen(false); onAct(choice); } }}>
      <label htmlFor={pickId}>Answer the same question from</label>
      <select id={pickId} value={choice} onChange={(event) => setChoice(event.target.value)}>
        <option value="">Choose an Act…</option>
        {acts.map((act) => <option key={act.entry_id} value={act.entry_id}>{act.name}</option>)}
      </select>
      <button type="submit" className="secondary-button" disabled={busy || !choice}>Use this Act</button>
    </form>}
  </div>;
}

const CHOICE_TITLES = {
  act_ambiguous: "Which Act do you mean?",
  several_acts: "Choose one Act",
  act_not_found: "Did you mean one of these?",
  general_no_act: "Choose an Act to answer from",
  amendment_mismatch: "Acts it is recorded as amending",
};

// The Acts the user can pick; one click re-asks the same question from that Act.
export function ActChoices({ routing, onAct, busy }) {
  if (!routing?.choices?.length || !CHOICE_TITLES[routing.route]) return null;
  return <article className="act-choices" aria-labelledby="act-choices-heading">
    <h3 id="act-choices-heading">{CHOICE_TITLES[routing.route]}</h3>
    <ul>{routing.choices.map((act) => <li key={act.entry_id}>
      <button type="button" className="secondary-button" disabled={busy} onClick={() => onAct(act.entry_id)}>{actLabel(act)}</button></li>)}</ul>
    <p className="panel-note">Your question is kept as you asked it; only the Act it is answered from changes.</p>
  </article>;
}

// Where to look next for an Act that is not in the corpus, and any live record found for it (listed, not summarised).
export function NotFoundSources({ routing }) {
  if (routing?.route !== "act_not_found") return null;
  return <article className="not-found-sources" aria-label="Where to search">
    {routing.live_discoveries?.length > 0 && <ul className="live-discoveries">{routing.live_discoveries.map((item) => <li key={item.title}>
      <strong>{item.title}</strong> · found on {item.source}; not in the local corpus, so not summarised{item.url && <> · <a href={item.url} target="_blank" rel="noreferrer">Open record ↗</a></>}</li>)}</ul>}
    <p className="link-row">{(routing.links || []).map((link) => <a key={link.url} className="official-link" href={link.url} target="_blank" rel="noreferrer">{link.label} ↗</a>)}</p>
  </article>;
}

const KIND_TONE = { act_amendment: "supported", commencement_notification: "limited", unverified_candidate: "limited", other_notice: "none" };

// The latest records observed in the monitored sources, with each source's last successful check.
export function LatestRecords({ feed }) {
  if (!feed) return null;
  return <article className="latest-records" aria-labelledby="latest-heading">
    <span className="section-kicker">Monitored sources · read from the saved checks, nothing fetched for this question</span>
    <h3 id="latest-heading">{feed.items.length ? `Latest ${feed.items.length === 1 ? "record" : `${feed.items.length} records`} observed` : "No records observed"}</h3>
    <ul className="source-checks">{feed.sources.map((source) => <li key={source.source_key} className={source.state === "OK" ? "ok" : "problem"}>
      <strong>{source.source}</strong>: last successful check {when(source.last_success_at)}{source.state !== "OK" && <> · <span className="status-tag limited">{source.state.toLowerCase().replaceAll("_", " ")}</span> {source.detail}</>}</li>)}</ul>
    {feed.items.length > 0 && <ol className="record-list">{feed.items.map((item) => <li key={`${item.source_key}:${item.title}:${item.discovered_at}`}>
      <div className="record-title">{item.official_url ? <a href={item.official_url} target="_blank" rel="noreferrer">{item.title} ↗</a> : <strong>{item.title}</strong>}</div>
      <span className={`status-tag ${KIND_TONE[item.record_kind] || "none"}`}>{item.record_kind_label}</span>
      <dl className="record-facts">
        <div><dt>Source</dt><dd>{item.source}</dd></div>
        <div><dt>Published</dt><dd>{item.published || "not stated"}</dd></div>
        <div><dt>Discovered</dt><dd>{when(item.discovered_at)}</dd></div>
        <div><dt>Status</dt><dd>{item.status_label || item.status}</dd></div>
      </dl></li>)}</ol>}
    <p className="panel-note">{feed.scope} {feed.note}</p>
  </article>;
}
