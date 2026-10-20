import { useEffect, useRef, useState } from "react";

// Latest items discovered by the scheduled source monitoring (GET /api/sources/notifications, source-notifications-v1).
// Read-only: the panel never triggers a check. "Read" marks are kept in this browser only.
const SEEN_KEY = "tldrift:seen-discoveries";
const SOURCE_STATE = { OK: "Checked recently", STALE: "Not checked recently", FAILED: "Last check failed", NEVER_SUCCEEDED: "Never checked successfully" };

export function readSeen() {
  try { const value = JSON.parse(window.localStorage.getItem(SEEN_KEY) || "[]"); return Array.isArray(value) ? value : []; } catch { return []; }
}
export function saveSeen(ids) {
  try { window.localStorage.setItem(SEEN_KEY, JSON.stringify(ids)); } catch { /* storage unavailable: read marks are a convenience */ }
}
const when = (value) => (value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }) + " UTC" : "not recorded");

export function useDiscoveries(request) {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { request("/api/sources/notifications").then(setData).catch(() => setFailed(true)); }, [request]);
  return { data, failed };
}

export default function Notifications({ data, failed, open, onClose, seen, onSeen }) {
  const heading = useRef(null);
  useEffect(() => { if (open) heading.current?.focus(); }, [open]);
  if (!open) return null;
  const items = data?.items || [];
  const markAll = () => onSeen([...new Set([...seen, ...items.map((row) => row.id)])]);
  const markOne = (id) => onSeen([...new Set([...seen, id])]);
  return <aside id="discoveries-panel" className="discoveries" aria-labelledby="discoveries-heading" onKeyDown={(event) => event.key === "Escape" && onClose()}>
    <header><div><span className="section-kicker">Monitored sources</span><h2 id="discoveries-heading" ref={heading} tabIndex={-1}>Latest discovered in monitored sources</h2></div>
      <button type="button" className="link-button" onClick={onClose} aria-label="Close latest discoveries">Close</button></header>
    {failed ? <p className="limit-note" role="status">The discovery list could not be loaded. Nothing is shown rather than an incomplete list.</p>
      : !data ? <p className="panel-note" role="status">Loading the monitoring record…</p>
      : <>
        <p className="panel-note">{data.scope} {data.note}</p>
        <ul className="source-states" aria-label="Source status">{data.sources.map((row) => <li key={row.source_key} className={`state-${row.state.toLowerCase()}`}>
          <strong>{row.source}</strong> <span className="status-tag">{SOURCE_STATE[row.state] || row.state}</span><small>{row.detail} Last success: {when(row.last_success_at)}. Last attempt: {when(row.last_attempt_at)}.</small></li>)}</ul>
        {items.length === 0 ? <p className="empty-state" role="status">No new documents are recorded from the monitored sources.</p>
          : <><p className="discoveries-actions"><span>{items.filter((row) => !seen.includes(row.id)).length} unread of {data.total}</span>
            <button type="button" className="link-button" onClick={markAll}>Mark all as read</button></p>
          <ol className="discovery-list">{items.map((row) => { const unread = !seen.includes(row.id);
            return <li key={row.id} className={unread ? "unread" : ""}>
              {unread && <span className="new-dot" aria-label="Unread">New</span>}
              <strong>{row.title}</strong>
              <span className="status-tag">{row.status_label}</span>
              <dl>
                <div><dt>Source</dt><dd>{row.source}</dd></div>
                <div><dt>Published</dt><dd>{row.published || "not stated"}</dd></div>
                <div><dt>Discovered</dt><dd>{when(row.discovered_at)}</dd></div>
              </dl>
              {row.candidate_targets.length > 0 && <p className="panel-note">Machine extraction names {row.candidate_targets.join(", ")}; this relationship is not verified.</p>}
              <p className="discovery-links">{row.official_url ? <a href={row.official_url} target="_blank" rel="noreferrer">Official record ↗</a> : <span>No official link recorded</span>}
                {unread && <button type="button" className="link-button" onClick={() => markOne(row.id)}>Mark as read</button>}</p>
            </li>; })}</ol></>}
        {data.listed_total > 0 && <details className="fold"><summary>{data.listed_total} other listing{data.listed_total === 1 ? "" : "s"} seen but not downloaded</summary>
          <ul className="listed">{data.listed.slice(0, 8).map((row) => <li key={row.id}>{row.title} · {row.source} · {when(row.discovered_at)}
            {row.official_url && <> · <a href={row.official_url} target="_blank" rel="noreferrer">Official record ↗</a></>}</li>)}</ul></details>}
      </>}
  </aside>;
}
