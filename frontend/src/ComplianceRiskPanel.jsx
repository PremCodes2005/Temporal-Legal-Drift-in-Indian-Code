import { useEffect, useState } from "react";

export default function ComplianceRiskPanel({ request }) {
  const [catalog, setCatalog] = useState(null);
  const [scenario, setScenario] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    request("/api/risk/catalog").then((value) => {
      setCatalog(value);
      setScenario(value.conditional_demonstrations[0]?.scenario || value.scenarios[0]?.scenario);
    }).catch((failure) => setError(failure.message));
  }, [request]);
  const update = (key, value) => { setScenario((old) => ({ ...old, [key]: value })); setResult(null); };
  const rows = catalog ? [...catalog.conditional_demonstrations, ...catalog.scenarios] : [];
  const submit = async (event) => {
    event.preventDefault(); setError(""); setResult(null); setBusy(true);
    try { setResult(await request("/api/risk/assess", { method: "POST", body: scenario })); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  };
  return <section className="page-section">
    <div className="hero"><span className="section-kicker">Scenario-based assessment</span><h2>Check an obligation against your facts.</h2>
      <p>Risk depends on the applicable obligation and its consequence. Textual drift percentages do not enter this calculation.</p>
      <p>The Section 19 examples use stated research assumptions. The other imported templates need scenario facts and supported obligation models before a risk can be assessed.</p>
    </div>
    {error && <div className="form-error" role="alert">{error}</div>}
    {!scenario && !error && <p role="status">Loading scenario models…</p>}
    {scenario && <form className="panel risk-form" onSubmit={submit}>
      <label htmlFor="risk-example">Starting scenario</label>
      <select id="risk-example" disabled={busy} value={scenario.scenario_id} onChange={(event) => { setScenario(structuredClone(rows.find((r) => r.scenario.scenario_id === event.target.value).scenario)); setResult(null); }}>
        {rows.map((row) => <option key={row.scenario.scenario_id} value={row.scenario.scenario_id}>{row.scenario.scenario_id.includes("demo_") ? `Section 19 — ${row.scenario.reference_date} (conditional example)` : `${row.scenario.applicable_provision} — template ${row.scenario.scenario_id.slice(-6)}`}</option>)}
      </select>
      <div className="risk-fields">{["organization_type", "industry", "jurisdiction", "activity", "reference_date", "applicable_provision"].map((key) => <label key={key}>{key.replaceAll("_", " ")}<input disabled={busy} type={key === "reference_date" ? "date" : "text"} required={key === "reference_date"} value={scenario[key] || ""} onChange={(event) => update(key, event.target.value || null)} /></label>)}
        <label>Exposure description<input disabled={busy} value={scenario.exposure.description || ""} onChange={(event) => update("exposure", { ...scenario.exposure, description: event.target.value || null })} /></label>
        <label>Exposure amount (optional; not a calculated loss)<input disabled={busy} type="number" min="0" step="any" value={scenario.exposure.amount ?? ""} onChange={(event) => update("exposure", { ...scenario.exposure, amount: event.target.value === "" ? null : Number(event.target.value) })} /></label>
      </div>
      <fieldset disabled={busy}><legend>Scenario facts</legend>{Object.entries(scenario.facts).map(([key, value]) => <label className="risk-fact" key={key}>
        {typeof value === "boolean" ? <input type="checkbox" checked={value} onChange={(event) => update("facts", { ...scenario.facts, [key]: event.target.checked })} /> : <input value={value ?? ""} onChange={(event) => update("facts", { ...scenario.facts, [key]: event.target.value || null })} />}{key.replaceAll("_", " ")}
      </label>)}{!Object.keys(scenario.facts).length && <p>No facts were authored in this source template. The engine will identify the evidence gap.</p>}</fieldset>
      <button className="send-button" type="submit" disabled={busy}>{busy ? "Assessing…" : "Assess scenario"}</button>
    </form>}
    {catalog && <details className="panel risk-result"><summary>How risk levels are assigned</summary><dl>{Object.entries(catalog.risk_levels).map(([level, meaning]) => <div key={level}><dt><strong>{level}</strong></dt><dd>{meaning}</dd></div>)}</dl><p>Unknown means evidence is insufficient. It is not the None category.</p></details>}
    {result && <div className="panel risk-result" aria-live="polite">
      <h2>{result.risk_level === null ? "Risk cannot yet be determined" : `${result.risk_level === "None" ? "No adverse consequence detected" : `${result.risk_level} operational risk`}`}</h2>
      <p>{result.status.replaceAll("_", " ")} · Urgency: {result.urgency.toLowerCase()}</p>
      <p><strong>Selected version:</strong> {result.provision_version || "Unresolved"}</p>
      <p><strong>Obligation:</strong> {result.obligation || "No supported obligation established"}</p>
      <p><strong>Consequence:</strong> {result.consequence || "Unresolved"}</p>
      <p><strong>Materiality:</strong> {result.materiality || "Unassessed"} · <strong>Escalation:</strong> {result.escalation_required ? "Required" : "Not required"}</p>
      <h3>How the result was reached</h3><ol>{result.reasoning_trace.map((line, i) => <li key={i}>{line}</li>)}</ol>
      <h3>Assumptions and missing information</h3><ul>{result.uncertainty.map((reason) => <li key={reason}>{reason.replaceAll("_", " ")}</li>)}</ul>
      {result.evidence.map((item) => <details key={item.evidence_id}><summary>{item.role} evidence · {item.locator}</summary><blockquote>{item.quote}</blockquote><small>Source: {item.source_id}</small></details>)}
      <p>Conditional research assessment; legal interpretation has not been independently validated.</p>
      <a href="https://indiacode.gov.in/" target="_blank" rel="noreferrer">Visit India Code for further information ↗</a>
    </div>}
  </section>;
}
