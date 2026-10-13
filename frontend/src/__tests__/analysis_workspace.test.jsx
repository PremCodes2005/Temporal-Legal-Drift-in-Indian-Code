// @vitest-environment jsdom
// rag-answer-v5 analysis workspace and the standalone #drift / #calculation pages against real backend responses (fixtures/rag_answer_v5.json, generated offline;
// "timeout" used a real local socket that never answered). One v4 record checks that v0.14 links still open.
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import AssistantResult from "../AssistantResult";
import { DriftExplanationPage, ScoreCalculationPage } from "../ExplanationPages";

const { responses } = JSON.parse(readFileSync("src/__tests__/fixtures/rag_answer_v5.json", "utf8"));
const v4 = JSON.parse(readFileSync("src/__tests__/fixtures/rag_answer_v4.json", "utf8")).responses;
const weights = Object.fromEntries(Object.entries(JSON.parse(readFileSync("../configs/metrics/rule_drift.v1.2.json", "utf8")).fields).map(([k, v]) => [k, v.weight]));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); window.sessionStorage.clear(); });
// Text a reader sees without opening a folded section.
const visible = () => { const copy = document.getElementById("rag-result").cloneNode(true); copy.querySelectorAll("details:not([open]) > :not(summary)").forEach((el) => el.remove()); return copy.textContent; };
const fold = (name) => screen.getByText(name, { selector: "summary", exact: false }).closest("details");
const scored = (analysis) => ["wording_drift", "rule_drift"].map((name) => analysis.fingerprint?.[name]).filter((item) => item?.value != null);

describe("the restored single-page assistant", () => {
  it("shows the answer, the change measured, pre/post evidence and citations on one page, with no tabs and no empty assessments", () => {
    for (const key of ["it-s19", "ibc99", "ibc240", "mv170", "dm31", "wrong-act", "ocr", "general", "timeout"]) {
      render(<AssistantResult analysis={responses[key]} />);
      expect(screen.queryByRole("tablist"), key).toBeNull();
      const text = visible();
      for (const empty of ["Cannot determine", "Needs your facts", "Not enough evidence", "Not scored", "Not applicable"]) expect(text, `${key}: ${empty}`).not.toContain(empty);
      expect([...document.querySelectorAll(".determination")].filter((el) => !el.closest("details:not([open])")).length, key).toBe(0);
      expect(screen.getByRole("article", { name: "Answer" }).textContent).toContain(responses[key].answer.direct_answer);
      if (responses[key].evidence?.length) expect(screen.getByRole("article", { name: "Evidence" })).toBeTruthy();
      cleanup();
    }
  });

  it("keeps the v0.13.0 order: answer, the change measured, clause comparison, evidence", () => {
    render(<AssistantResult analysis={responses.ibc99} />);
    const order = ["Answer", "The change, measured", "Clause comparison", "Evidence"].map((name) => screen.getByRole("article", { name }));
    for (let i = 1; i < order.length; i++) expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("lists only scored values and opens the separate explanation pages", async () => {
    const user = userEvent.setup();
    const onPage = vi.fn();
    const fp = responses.ibc99.fingerprint;
    render(<AssistantResult analysis={responses.ibc99} onPage={onPage} />);
    const path = screen.getByRole("article", { name: "The change, measured" });
    expect([...path.querySelectorAll("li")].map((li) => li.textContent)).toEqual([`Wording drift${fp.wording_drift.label}`, `Rule drift${fp.rule_drift.label}`, `Combined indicator${fp.tlds.label}`]);
    await user.click(within(path).getByRole("button", { name: /Explain the change with the cited clauses/ }));
    await user.click(within(path).getByRole("button", { name: /See how the scores are calculated/ }));
    expect(onPage.mock.calls).toEqual([["drift"], ["calculation"]]);
    cleanup();
    render(<AssistantResult analysis={responses.mv170} />);
    expect([...document.querySelectorAll(".change-glance-list li")].map((li) => li.textContent)).toEqual([`Wording drift${responses.mv170.fingerprint.wording_drift.label}`]);  // no rule or combined number
  });

  it("folds personal-situation details behind one 'Check your situation' control", async () => {
    const user = userEvent.setup();
    render(<AssistantResult analysis={responses["it-s19"]} />);
    const details = fold("Check your situation");
    expect(details.querySelector("summary").textContent).toBe("Check your situation · 3 facts decide whether this changes for you");
    expect(details.open).toBe(false);
    await user.click(details.querySelector("summary"));
    expect(details.open).toBe(true);
    expect(screen.getByRole("form", { name: "Your situation" })).toBeTruthy();
  });

  it("labels a model timeout and still answers from the evidence", () => {
    render(<AssistantResult analysis={responses.timeout} />);
    expect(screen.getAllByRole("status")[0].textContent).toMatch(/Extractive evidence summary.*TimeoutError; this answer was produced without it/);
  });

  it("re-runs with the facts that decide the outcome, and keeps irrelevant risk out", async () => {
    const user = userEvent.setup();
    const onScenario = vi.fn();
    render(<AssistantResult analysis={responses.ibc99} onScenario={onScenario} />);
    await user.click(fold("Check your situation").querySelector("summary"));
    await user.type(screen.getByLabelText(/How many days have passed/), "15");
    await user.click(screen.getByRole("button", { name: "Re-run with these facts" }));
    expect(onScenario).toHaveBeenCalledWith({ facts: { elapsed_days: 15 } });
    expect(screen.getByText(/No modelled compliance obligation covers this provision/)).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Conditional compliance risk" })).toBeNull();
  });

  it("shows a deadline flip for one scenario and not for another, with the facts used", () => {
    for (const [key, label] of [["ibc99-day15", "Changed"], ["ibc99-day25", "Unchanged"]]) {
      render(<AssistantResult analysis={responses[key]} />);
      expect(fold("Check your situation").open).toBe(true);  // a re-run with facts shows its result
      expect(within(screen.getByRole("region", { name: "Impact on your situation" })).getByText(label)).toBeTruthy();
      expect(screen.getByText(/Using your facts: elapsed days/)).toBeTruthy();
      cleanup();
    }
  });

  it("shows unreadable-source warnings openly and keeps review details folded", () => {
    render(<AssistantResult analysis={responses.ocr} />);
    expect(screen.getByRole("alert").textContent).toMatch(/Source text unreliable: it-amendment-act-2008/);
    const review = fold("Sources, quality and review");
    expect(review.open).toBe(false);
    expect(review.textContent).toMatch(/Legal validation: UNVERIFIED/);
  });

  it("marks materiality as provisional machine triage, not gold, inside the review details", async () => {
    const user = userEvent.setup();
    render(<AssistantResult analysis={responses.ibc99} />);
    await user.click(fold("Sources, quality and review").querySelector("summary"));
    const card = screen.getByRole("heading", { name: /Materiality of the amendment/ }).closest("article");
    await user.click(within(card).getByText("Method and evidence"));
    expect(within(card).getAllByText(/computed for this answer/).length).toBeGreaterThan(0);
    expect(screen.getByRole("region", { name: "Evidence provenance" })).toBeTruthy();
  });

  it("still opens a stored v4 analysis", () => {
    render(<AssistantResult analysis={v4["dm31-month18"]} />);
    expect(screen.getByRole("article", { name: "Answer" }).textContent).toContain(v4["dm31-month18"].answer.direct_answer);
  });
});

describe("standalone Drift explanation and Score calculation pages", () => {
  const handlers = () => ({ onEvidence: vi.fn(), onField: vi.fn(), onAssistant: vi.fn(), onCalculation: vi.fn() });
  const drift = (analysis, props = {}) => render(<DriftExplanationPage analysis={analysis} {...handlers()} {...props} />);
  const calc = (analysis, props = {}) => render(<ScoreCalculationPage analysis={analysis} {...handlers()} {...props} />);
  const page = () => document.querySelector(".page-section");

  it("show every score the Answer tab shows, or say why there is none", () => {
    for (const [key, analysis] of Object.entries(responses)) {
      for (const show of [drift, calc]) {
        show(analysis);
        const labels = scored(analysis).map((item) => item.label);
        for (const label of labels) expect(page().textContent, `${key}`).toContain(label);
        if (!labels.length) expect(within(page()).getByRole("status").textContent, key).toMatch(/No change to explain|could not be measured/);
        cleanup();
      }
    }
  });

  it("Drift explanation: guide, component breakdown, clauses side by side with their sources, and detected changes", () => {
    const analysis = responses.ibc99;
    drift(analysis);
    const guide = screen.getByLabelText("How to read the combined indicator");
    expect([...guide.querySelectorAll("strong")].map((el) => el.textContent)).toEqual(["Low", "Moderate", "High"]);
    expect(guide.textContent).toContain("0–29.9 · Very low and Low");
    const breakdown = screen.getByRole("article", { name: /combined drift/ });
    for (const label of ["Wording drift", "Rule drift", "Legal-effect drift", "Combined indicator (TLDS)"]) expect(breakdown.textContent).toContain(label);
    expect(breakdown.textContent).toContain(analysis.fingerprint.tlds.value.toFixed(1));
    expect(within(breakdown).getAllByRole("note")[0].textContent).toMatch(/combined score is low, but legal-effect drift is 0\.50/);
    expect(breakdown.textContent).toMatch(/Only 0\.8% of the wording changed, yet the deadline or period changed/);
    const before = screen.getByRole("region", { name: "Clause before" }), after = screen.getByRole("region", { name: "Clause after" });
    expect(after.querySelector(".compare-text").textContent).toBe(analysis.fingerprint.wording_drift.details.after_clause);
    expect(before.textContent).toMatch(/Insolvency Bankruptcy Code 2016 · page 98, line 11 · earlier wording reconstructed from the footnote · Derived, not verbatim/);
    expect(after.textContent).toMatch(/page 98, line 11 · current consolidated text · verbatim/);
    expect(within(after).getByRole("link", { name: /PDF p\. 98/ }).getAttribute("href")).toBe("/corpus/insolvency-bankruptcy-code-2016.pdf#page=98");
    const changes = screen.getByRole("article", { name: "How the two clauses differ" });
    expect(changes.textContent).toContain("“within ten days” → “within twenty-one days”");
    expect(changes.textContent).toContain("Why it matters: it changes when compliance is due.");
    expect(document.getElementById("evidence-E1")).toBeTruthy();  // clickable source list on the page
  });

  it("Drift explanation: a rule field's words are highlighted in the clauses", async () => {
    const user = userEvent.setup();
    const onField = vi.fn();
    const { rerender } = drift(responses.ibc99, { onField });
    await user.click(screen.getByRole("button", { name: "Show these words in the clause" }));
    const row = onField.mock.calls[0][0];
    expect(row.field).toBe("deadline");
    rerender(<DriftExplanationPage analysis={responses.ibc99} {...handlers()} highlight={{ label: "Deadline or period", before: row.before_spans, after: row.after_spans }} />);
    expect([...document.querySelectorAll(".clause-pair mark")].map((m) => m.textContent)).toEqual(["within ten days", "within twenty-one days"]);
  });

  it("Score calculation: inputs, formulas, rule contributions and the worked combined calculation, all from the stored analysis", () => {
    for (const key of ["ibc99", "sra", "mv173", "ibc240", "dm31"]) {
      const analysis = responses[key];
      const rule = analysis.fingerprint.rule_drift, tlds = analysis.fingerprint.tlds;
      calc(analysis);
      const rows = within(screen.getByRole("table", { name: /Each rule field/ })).getAllByRole("row").slice(1);
      expect(rows).toHaveLength(8);
      expect(rows.map((row) => Number(row.cells[5].textContent)).reduce((a, b) => a + b, 0), key).toBe(rule.value);
      for (const row of rule.details.fields) expect(row.contribution).toBe(["ADDED", "REMOVED", "CHANGED"].includes(row.operation) ? weights[row.field] : 0);
      expect(page().textContent).toContain(rule.details.calculation);
      expect(page().textContent).toContain(analysis.fingerprint.wording_drift.details.calculation);
      const card = screen.getByRole("article", { name: /Why the combined score is/ });
      expect(card.textContent).toContain(tlds.calculation);
      const recomputed = 100 * Object.entries(tlds.components).reduce((sum, [name, part]) => sum + tlds.weights[name] * part.value, 0);
      expect(tlds.calculation.endsWith(`= ${recomputed.toFixed(1)}`), key).toBe(true);  // the shown sum reproduces from the shown parts
      expect(page().textContent).toContain(analysis.fingerprint.wording_drift.details.clause_sha256.before.slice(0, 16));
      expect(page().textContent).not.toMatch(/pretrained semantic embedding|legal accuracy/i);
      cleanup();
    }
  });

  it("Score calculation: each input links to its source", async () => {
    const user = userEvent.setup();
    const onEvidence = vi.fn(), onField = vi.fn();
    calc(responses.ibc99, { onEvidence, onField });
    await user.click(within(screen.getByRole("article", { name: "Compared before clause" })).getByRole("button", { name: "Show evidence E3" }));
    expect(onEvidence).toHaveBeenCalledWith("E3");
    await user.click(screen.getByRole("button", { name: "Show the words for Deadline or period" }));
    expect(onField.mock.calls[0][0].field).toBe("deadline");
  });

  it("Score calculation: no number when a change cannot be scored, and the combined score is marked incomplete, never 0", () => {
    calc(responses.mv170);
    expect(page().textContent).toMatch(/Only a cross-reference changed \(“149” → “150”\)/);
    const card = screen.getByRole("article", { name: /Why there is no combined score/ });
    expect(card.textContent).toMatch(/Incomplete\. Missing: legal effect\. A missing component is never counted as 0/);
    expect(card.textContent).toContain("Partial, not comparable with complete scores");
  });

  it("Score calculation: Generic and Specific mode give the same numbers", () => {
    const views = [];
    for (const key of ["it-s19", "it-s19-generic"]) {
      calc(responses[key]);
      views.push(page().textContent.replace(/analysis an_[0-9a-f]+/, "").replace(/Question:.*?\?|Question:[^.]*\./, ""));
      cleanup();
    }
    expect(views[0]).toBe(views[1]);
  });

  it("Score calculation: hypothetical boundary values are labelled as not the user's facts, and the legacy score is collapsed", () => {
    calc(responses["ibc99-day25"]);
    expect(page().textContent).toContain("Hypothetical boundary values (not your facts)");
    const legacy = document.querySelector("details.legacy-diagnostic");
    expect(legacy.open).toBe(false);
    expect(legacy.querySelector("summary").textContent).toMatch(/superseded, not the combined indicator/);
  });

  it("explain unsupported pairing instead of showing a number", () => {
    drift(responses["wrong-act"]);
    expect(within(page()).getByRole("status").textContent).toMatch(/could not be measured.*Nothing is scored, so no number is shown/);
  });

  it("open a stored v4 analysis (no combined indicator) without a guide or empty sections", () => {
    drift(v4["dm31-month18"]);
    expect(screen.queryByLabelText("How to read the combined indicator")).toBeNull();
    expect(page().textContent).toContain(v4["dm31-month18"].fingerprint.rule_drift.label);
    cleanup();
    calc(v4["dm31-month18"]);
    expect(screen.queryByRole("article", { name: /combined score/ })).toBeNull();
  });
});

describe("links, history and keyboard", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (url, init) => {
      const id = String(url).match(/\/api\/analyses\/(an_[0-9a-f]{24})/)?.[1];
      const asked = String(url).includes("/api/rag/query") ? Object.values(responses).find((r) => r.query === JSON.parse(init.body).query && r.mode === JSON.parse(init.body).mode && !r.scenario) : null;
      const body = asked || (id ? Object.values(responses).find((r) => r.analysis_id === id) : String(url).includes("/api/corpus") ? { entries: [] } : String(url).includes("/api/sources/health") ? { sources: [] } : { ready: true });
      return { ok: Boolean(body), status: body ? 200 : 404, json: async () => body || { error: "Analysis not found" } };
    }));
  });

  const loaded = (analysis) => waitFor(() => expect(screen.getByText(new RegExp(`analysis ${analysis.analysis_id}`))).toBeTruthy());

  it("opens #drift/<id> and #calculation/<id> as standalone pages of that analysis, after a refresh too", async () => {
    const analysis = responses["ibc99-day15"];
    for (const page of ["drift", "calculation"]) {
      window.history.replaceState(null, "", `#${page}/${analysis.analysis_id}`);
      render(<App />);
      await loaded(analysis);
      expect(fetch).toHaveBeenCalledWith(`/api/analyses/${analysis.analysis_id}`, expect.anything());
      expect(screen.queryByRole("tablist")).toBeNull();
      expect(within(screen.getByRole("navigation")).getByRole("button", { name: page === "drift" ? /Drift explanation/ : /Score calculation/ }).getAttribute("aria-current")).toBe("page");
      cleanup();
    }
  });

  it("remembers an analysis opened from a link, so a later plain #calculation reopens it", async () => {
    const analysis = responses.sra;
    window.history.replaceState(null, "", `#drift/${analysis.analysis_id}`);
    render(<App />);
    await loaded(analysis);
    cleanup();
    window.history.replaceState(null, "", "#calculation");
    render(<App />);
    await loaded(analysis);
    expect(screen.getByRole("heading", { name: "How these percentages were calculated" })).toBeTruthy();
  });

  it("plain #drift opens the current analysis; old 'scores' and tab links open the pages", async () => {
    const analysis = responses.dm31;
    window.sessionStorage.setItem("tldrift:last-analysis", analysis.analysis_id);
    window.history.replaceState(null, "", "#drift");
    render(<App />);
    await loaded(analysis);
    expect(screen.getByRole("heading", { name: "What the drift score means" })).toBeTruthy();
    cleanup();
    for (const [hash, heading] of [["scores", "How these percentages were calculated"], ["drift", "What the drift score means"]]) {
      window.history.replaceState(null, "", `#analysis/${analysis.analysis_id}/${hash}`);
      render(<App />);
      await waitFor(() => expect(screen.getByRole("heading", { name: heading })).toBeTruthy());
      cleanup();
    }
  });

  it("switches between the assistant and both pages without losing the analysis, and back/forward retraces it", async () => {
    const user = userEvent.setup();
    const analysis = responses.ibc99;
    window.history.replaceState(null, "", `#assistant/${analysis.analysis_id}`);
    render(<App />);
    await waitFor(() => screen.getByRole("article", { name: "Answer" }));
    const nav = screen.getByRole("navigation");
    await user.click(within(nav).getByRole("button", { name: /Drift explanation/ }));
    expect(window.location.hash).toBe(`#drift/${analysis.analysis_id}`);
    await loaded(analysis);
    await user.click(within(nav).getByRole("button", { name: /Score calculation/ }));
    expect(window.location.hash).toBe(`#calculation/${analysis.analysis_id}`);
    expect(screen.getByRole("heading", { name: "How these percentages were calculated" })).toBeTruthy();
    window.history.back();
    await waitFor(() => expect(screen.getByRole("heading", { name: "What the drift score means" })).toBeTruthy());
    window.history.back();
    await waitFor(() => expect(screen.getByRole("article", { name: "Answer" })).toBeTruthy());
    window.history.forward();
    await waitFor(() => expect(screen.getByRole("heading", { name: "What the drift score means" })).toBeTruthy());
    await user.click(within(nav).getByRole("button", { name: /Legal drift assistant/ }));
    expect(window.location.hash).toBe(`#assistant/${analysis.analysis_id}`);
    expect(screen.getByLabelText("Legal research question").value).toBe(analysis.query);
    expect(screen.getByRole("article", { name: "Answer" }).textContent).toContain(analysis.answer.direct_answer);
  });

  it("links from the answer to the pages, and from a page's evidence and rule fields back to the cited words", async () => {
    const user = userEvent.setup();
    const analysis = responses.ibc99;
    window.history.replaceState(null, "", `#assistant/${analysis.analysis_id}`);
    render(<App />);
    await waitFor(() => screen.getByRole("article", { name: "Answer" }));
    await user.click(screen.getByRole("button", { name: /See how the scores are calculated/ }));
    expect(window.location.hash).toBe(`#calculation/${analysis.analysis_id}`);
    await user.click(screen.getByRole("button", { name: "Show the words for Deadline or period" }));
    await waitFor(() => expect(document.activeElement.id).toBe("clause-pair-heading"));
    expect(window.location.hash).toBe(`#drift/${analysis.analysis_id}`);
    expect([...document.querySelectorAll(".clause-pair mark")].map((m) => m.textContent)).toEqual(["within ten days", "within twenty-one days"]);
    await user.click(within(screen.getByRole("region", { name: "Clause after" })).getByRole("button", { name: "Show evidence E1" }));
    await waitFor(() => expect(document.activeElement.id).toBe("evidence-E1"));
  });

  it("shows a helpful page for the score views before any analysis exists", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(within(screen.getByRole("navigation")).getByRole("button", { name: /Score calculation/ }));
    expect(screen.getByText("Ask a comparison question first.")).toBeTruthy();
  });

  it("asks a question end to end: input, mode, answer at #assistant/<id>, then the pages and back keep it", async () => {
    const user = userEvent.setup();
    const analysis = responses["it-s19-generic"];
    window.history.replaceState(null, "", "#assistant");
    render(<App />);
    const input = screen.getByLabelText("Legal research question");
    await user.type(input, analysis.query);
    const generic = screen.getByRole("button", { name: /Generic/ });
    await user.click(generic);
    expect(generic.getAttribute("aria-pressed")).toBe("true");
    await user.click(screen.getByRole("button", { name: /Analyse/ }));
    await waitFor(() => expect(window.location.hash).toBe(`#assistant/${analysis.analysis_id}`));
    expect(screen.getByRole("article", { name: "Answer" }).textContent).toContain(analysis.answer.direct_answer);
    expect(fetch).toHaveBeenCalledWith("/api/rag/query", expect.objectContaining({ method: "POST", body: JSON.stringify({ query: analysis.query, mode: "generic" }) }));
    await user.click(screen.getByRole("button", { name: /Explain the change with the cited clauses/ }));
    expect(window.location.hash).toBe(`#drift/${analysis.analysis_id}`);
    window.history.back();
    await waitFor(() => expect(screen.getByRole("article", { name: "Answer" }).textContent).toContain(analysis.answer.direct_answer));
  });

  it("keeps the full question area above an answer: status, scheduled ingestion, labelled input and the 3 suggestions", async () => {
    const health = { sources: [{ source_key: "india_code", last_success_at: "2026-10-12T14:21:16Z", scheduled_ingestion_healthy: true },
      { source_key: "egazette", last_success_at: "2026-10-12T16:42:42Z", scheduled_ingestion_healthy: true }], review_queue_pending: 4 };
    const base = fetch.getMockImplementation();
    fetch.mockImplementation(async (url, init) => (String(url).includes("/api/sources/health") ? { ok: true, status: 200, json: async () => health } : base(url, init)));
    const analysis = responses.ibc99;
    window.history.replaceState(null, "", `#assistant/${analysis.analysis_id}`);
    render(<App />);
    await waitFor(() => screen.getByRole("article", { name: "Answer" }));
    expect(screen.getByRole("heading", { name: "Ask what changed in Indian law." })).toBeTruthy();
    await waitFor(() => expect(screen.getByText(/Scheduled ingestion \(stored in UTC\):/).parentElement.textContent)
      .toMatch(/India Code: last checked .* · e-Gazette: last checked .* · 4 new document\(s\) awaiting review/));
    expect(screen.getByLabelText("Legal research question").value).toBe(analysis.query);
    const suggestions = screen.getByText("Try asking").parentElement.querySelectorAll("button");
    expect([...suggestions].map((b) => b.textContent)).toEqual(["What changed in the IT Act amendment regarding data privacy?",
      "Compare Section 19 before and after the IT Amendment Act, 2008.", "What penalties were introduced for privacy violations in the IT Act?"]);
  });

  it("opens older #analysis/<id>/<view> links on the assistant, with the situation open for 'scenario'", async () => {
    const analysis = responses.ibc99;
    window.history.replaceState(null, "", `#analysis/${analysis.analysis_id}/scenario`);
    render(<App />);
    await waitFor(() => screen.getByRole("article", { name: "Answer" }));
    expect(fold("Check your situation").open).toBe(true);
    expect(screen.queryByRole("tablist")).toBeNull();
  });

  it("restores the assistant after a refresh of #assistant/<id> and from plain #assistant", async () => {
    const analysis = responses.dm31;
    window.history.replaceState(null, "", `#assistant/${analysis.analysis_id}`);
    render(<App />);
    await waitFor(() => expect(screen.getByRole("article", { name: "Answer" }).textContent).toContain(analysis.answer.direct_answer));
    cleanup();
    window.history.replaceState(null, "", "#assistant");
    render(<App />);
    await waitFor(() => expect(screen.getByRole("article", { name: "Answer" }).textContent).toContain(analysis.answer.direct_answer));
  });

  it("stacks dense calculation rows on narrow screens", () => {
    const css = readFileSync("src/styles.css", "utf8");
    expect(css).toMatch(/\.table-scroll\{position:relative;overflow-x:auto\}/);  // relative: the sr-only header must not escape the scroller
    expect(css).toMatch(/@media \(max-width:620px\)\{\.calc-list\{grid-template-columns:1fr\}\.table-scroll \.fp-table\{min-width:600px\}/);
    expect(css).toMatch(/\.fold>summary:focus-visible\{outline:3px solid var\(--primary\)/);
  });
});
