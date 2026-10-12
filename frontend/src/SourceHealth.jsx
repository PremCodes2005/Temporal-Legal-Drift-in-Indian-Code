import { useEffect, useState } from "react";

// Scheduled ingestion status; distinct from live query-time lookup.
export default function SourceHealth({ request }) {
  const [health, setHealth] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { request("/api/sources/health").then(setHealth).catch(() => setFailed(true)); }, [request]);
  if (failed) return <p className="panel-note" role="status">Scheduled source-monitoring status is unavailable.</p>;
  if (!health) return <p className="panel-note" role="status">Checking scheduled source monitoring…</p>;
  const line = (key, label) => {
    const source = health.sources.find((item) => item.source_key === key);
    if (!source) return null;
    if (!source.last_success_at) return `${label}: not yet checked by the daily job${source.last_status ? ` (last attempt: ${source.last_status.toLowerCase().replaceAll("_", " ")})` : ""}`;
    return `${label}: last checked ${new Date(source.last_success_at).toLocaleString()}${source.scheduled_ingestion_healthy ? "" : " — overdue"}`;
  };
  const parts = [line("india_code", "India Code"), line("egazette", "e-Gazette")].filter(Boolean);
  return <p className="source-health" role="status"><strong>Scheduled ingestion (stored in UTC):</strong> {parts.join(" · ")} · {health.review_queue_pending} new document(s) awaiting review</p>;
}
