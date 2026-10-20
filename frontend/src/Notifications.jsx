import { useCallback, useEffect, useRef, useState } from "react";

// Latest documents discovered by the scheduled source monitoring (GET /api/sources/notifications, source-notifications-v2).
// Refreshing only re-reads the stored monitoring ledger: it never starts a source check, which stays at most once per 24 hours.
// Records are keyed by official id + content hash. Read marks and the set of records already known stay in this browser only.
export const REFRESH_MS = 5 * 60 * 1000;
const SEEN_KEY = "tldrift:seen-discoveries";
const KNOWN_KEY = "tldrift:known-discoveries";
const SOURCE_STATE = { OK: "Checked recently", STALE: "Not checked recently", FAILED: "Last check failed", NEVER_SUCCEEDED: "Never checked successfully" };

function readList(key) {
  try { const value = JSON.parse(window.localStorage.getItem(key) || "null"); return Array.isArray(value) ? value : null; } catch { return null; }
}
function saveList(key, ids) {
  try { window.localStorage.setItem(key, JSON.stringify(ids)); } catch { /* storage unavailable: read marks are a convenience */ }
}
export const readSeen = () => readList(SEEN_KEY) || [];
export const saveSeen = (ids) => saveList(SEEN_KEY, ids);
const when = (value) => (value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }) + " UTC" : "not recorded");
const records = (data) => [...(data?.latest || []), ...(data?.older || [])];

export function useDiscoveries(request) {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const [loadedAt, setLoadedAt] = useState(null);
  const [fresh, setFresh] = useState([]);  // records that appeared since this browser last looked
  const load = useCallback(() => request("/api/sources/notifications").then((value) => {
    const keys = records(value).map((row) => row.key);
    const known = readList(KNOWN_KEY);
    if (known) {
      const added = records(value).filter((row) => !known.includes(row.key));
      if (added.length) setFresh(added);
    }
    saveList(KNOWN_KEY, [...new Set([...(known || []), ...keys])]);  // the first visit records what exists without alerting
    setData(value); setFailed(false); setLoadedAt(new Date().toISOString());
  }).catch(() => setFailed(true)), [request]);
  useEffect(() => {
    load();
    const timer = window.setInterval(load, REFRESH_MS);
    const onFocus = () => { if (document.visibilityState !== "hidden") load(); };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onFocus);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", onFocus); document.removeEventListener("visibilitychange", onFocus); };
  }, [load]);
  return { data, failed, loadedAt, fresh, dismiss: () => setFresh([]) };
}

// A quiet, dismissible message when a refresh finds records this browser has not seen before.
export function DiscoveryAlert({ fresh, onOpen, onDismiss }) {
  if (!fresh.length) return null;
  return <div className="discovery-alert" role="status">
    <span>{fresh.length === 1 ? `New in the monitored sources: ${fresh[0].title}` : `${fresh.length} new documents in the monitored sources`}. Not yet reviewed.</span>
    <button type="button" className="link-button" onClick={onOpen}>Show</button>
    <button type="button" className="link-button" onClick={onDismiss} aria-label="Dismiss the new-document message">Dismiss</button>
  </div>;
}

function Record({ row, seen, onSeen }) {
  const unread = !seen.includes(row.key);
  return <li className={unread ? "unread" : ""}>
    {unread && <span className="new-dot" aria-label="Unread">New</span>}
    <strong>{row.title}</strong>
    <span className={`status-tag category-${String(row.category || "").toLowerCase()}`}>{row.category_label}</span>
    <span className="record-status">{row.status_label}</span>
    <dl>
      <div><dt>Source</dt><dd>{row.source}</dd></div>
      <div><dt>Published</dt><dd>{row.published || "not stated"}</dd></div>
      <div><dt>Discovered</dt><dd>{when(row.discovered_at)}</dd></div>
    </dl>
    {row.candidate_targets?.length > 0 && <p className="panel-note">Machine extraction names {row.candidate_targets.join(", ")}; this relationship is not verified.</p>}
    {row.same_document_ids?.length > 0 && <p className="panel-note">The same file is also listed as {row.same_document_ids.join(", ")}.</p>}
    <p className="discovery-links">{row.official_url ? <a href={row.official_url} target="_blank" rel="noreferrer">Official record ↗</a> : <span>No official link recorded</span>}
      {unread && <button type="button" className="link-button" onClick={() => onSeen([...new Set([...seen, row.key])])}>Mark as read</button>}</p>
  </li>;
}

export default function Notifications({ data, failed, loadedAt, open, onClose, seen, onSeen }) {
  const heading = useRef(null);
  useEffect(() => { if (open) heading.current?.focus(); }, [open]);
  if (!open) return null;
  const all = records(data);
  const offline = typeof navigator !== "undefined" && navigator.onLine === false;
  return <aside id="discoveries-panel" className="discoveries" aria-labelledby="discoveries-heading" onKeyDown={(event) => event.key === "Escape" && onClose()}>
    <header><div><span className="section-kicker">Monitored sources</span><h2 id="discoveries-heading" ref={heading} tabIndex={-1}>Latest discovered in monitored sources</h2></div>
      <button type="button" className="link-button" onClick={onClose} aria-label="Close latest discoveries">Close</button></header>
    {(failed || offline) && data && <p className="limit-note" role="status">{offline ? "You appear to be offline." : "The list could not be refreshed."} Showing the list loaded at {when(loadedAt)}.</p>}
    {!data ? <p className={failed ? "limit-note" : "panel-note"} role="status">{failed ? (offline ? "You appear to be offline, so the discovery list could not be loaded." : "The discovery list could not be loaded. Nothing is shown rather than an incomplete list.") : "Loading the monitoring record…"}</p>
      : <>
        <p className="panel-note">{data.scope} {data.note} This list re-reads the stored record every few minutes; it never starts a new source check.</p>
        <ul className="source-states" aria-label="Source status">{data.sources.map((row) => <li key={row.source_key} className={`state-${row.state.toLowerCase()}`}>
          <strong>{row.source}</strong> <span className="status-tag">{SOURCE_STATE[row.state] || row.state}</span>
          <small>{row.detail} Last successful check: {when(row.last_success_at)}. Last attempt: {when(row.last_attempt_at)}.</small></li>)}</ul>
        <dl className="category-legend" aria-label="What each label means">{(data.categories || []).map((row) => <div key={row.category}>
          <dt><span className={`status-tag category-${row.category.toLowerCase()}`}>{row.label}</span> {row.count}</dt><dd>{row.note}</dd></div>)}</dl>
        {all.length === 0 ? <p className="empty-state" role="status">No downloaded documents are recorded from the monitored sources.</p>
          : <><p className="discoveries-actions"><span>{all.filter((row) => !seen.includes(row.key)).length} unread of {data.total}</span>
            <button type="button" className="link-button" onClick={() => onSeen([...new Set([...seen, ...all.map((row) => row.key)])])}>Mark all as read</button></p>
          <h3 className="list-heading" id="latest-heading">{data.latest.length === 1 ? "The latest record" : `The latest ${data.latest.length} records`}{data.latest.length < 5 ? " (all that exist)" : ""}</h3>
          <ol className="discovery-list" aria-labelledby="latest-heading">{data.latest.map((row) => <Record key={row.key} row={row} seen={seen} onSeen={onSeen} />)}</ol>
          {data.older.length > 0 && <details className="fold"><summary>{data.older.length} older record{data.older.length === 1 ? "" : "s"}</summary>
            <ol className="discovery-list">{data.older.map((row) => <Record key={row.key} row={row} seen={seen} onSeen={onSeen} />)}</ol></details>}</>}
        {data.failed?.length > 0 && <details className="fold"><summary>{data.failed.length} download{data.failed.length === 1 ? "" : "s"} that failed</summary>
          <ul className="listed">{data.failed.map((row) => <li key={row.key}>{row.title} · {row.source} · {when(row.discovered_at)}</li>)}</ul></details>}
        {data.listed_total > 0 && <details className="fold"><summary>{data.listed_total} other listing{data.listed_total === 1 ? "" : "s"} seen but not downloaded</summary>
          <ul className="listed">{data.listed.slice(0, 8).map((row) => <li key={row.key}>{row.title} · {row.source} · {when(row.discovered_at)}
            {row.official_url && <> · <a href={row.official_url} target="_blank" rel="noreferrer">Official record ↗</a></>}</li>)}</ul></details>}
      </>}
  </aside>;
}
