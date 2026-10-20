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
import { followUps, readHistory, remember } from "../App";
import FAQ from "../faq.json";
import { ComparisonPage } from "../ExplanationPages";
const recorded = JSON.parse(readFileSync("src/__tests__/fixtures/methods_and_discoveries.json", "utf8"));

const { responses } = JSON.parse(readFileSync("src/__tests__/fixtures/rag_answer_v5.json", "utf8"));
const v4 = JSON.parse(readFileSync("src/__tests__/fixtures/rag_answer_v4.json", "utf8")).responses;
const weights = Object.fromEntries(Object.entries(JSON.parse(readFileSync("../configs/metrics/rule_drift.v1.2.json", "utf8")).fields).map(([k, v]) => [k, v.weight]));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); window.sessionStorage.clear(); window.localStorage.clear(); });
// Text a reader sees without opening a folded section.
const visible = () => { const copy = document.getElementById("rag-result").cloneNode(true); copy.querySelectorAll("details:not([open]) > :not(summary)").forEach((el) => el.remove()); return copy.textContent; };
const fold = (name) => screen.getByText(name, { selector: "summary", exact: false }).closest("details");
const scored = (analysis) => ["wording_drift", "rule_drift"].map((name) => analysis.fingerprint?.[name]).filter((item) => item?.value != null);

// The backend as recorded in the fixtures: questions (with any chosen section) and stored analyses; anything else is a 404.
function stubApi() {
  vi.stubGlobal("fetch", vi.fn(async (url, init) => {
    const id = String(url).match(/\/api\/analyses\/(an_[0-9a-f]{24})/)?.[1];
    const sent = String(url).includes("/api/rag/query") ? JSON.parse(init.body) : null;
    const body = sent ? Object.values(responses).find((r) => r.query === sent.query && r.mode === sent.mode && !r.scenario && (r.selection?.section || null) === (sent.section || null))
      : id ? Object.values(responses).find((r) => r.analysis_id === id)
      : String(url).includes("/api/corpus") ? { entries: [] } : String(url).includes("/api/sources/health") ? { sources: [] }
      : String(url).includes("/api/sources/notifications") ? recorded.notifications : String(url).includes("/api/methods/tlds") ? recorded.method : { ready: true };
    return { ok: Boolean(body), status: body ? 200 : 404, json: async () => body || { error: "not found" } };
  }));
}

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
      expect(page().textContent).not.toMatch(/pretrained semantic embedding/i);
      expect(page().textContent).toContain("it is not legal accuracy, not the materiality of the amendment, not compliance risk and not a probability");
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
    expect(card.textContent).toMatch(/Incomplete: no combined score\. Missing: Legal effect \(L\)\. A missing component is never counted as 0/);
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
  beforeEach(stubApi);

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
    const suggestions = screen.getByRole("group", { name: "Try asking" }).querySelectorAll("button");
    expect([...suggestions].map((b) => b.textContent)).toEqual(FAQ.starters);
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

describe("Act-only questions, section choice and evidence limits", () => {
  beforeEach(stubApi);
  it("lists the sections that can be compared, why each is listed, and where its evidence is", () => {
    const found = responses["mv-act"].version_evidence.section_candidates;
    render(<AssistantResult analysis={responses["mv-act"]} />);
    const chooser = screen.getByRole("article", { name: /Sections of the Motor Vehicles Act 1988 you can open/ });
    const items = within(chooser).getAllByRole("listitem");
    expect(items).toHaveLength(found.candidates.length);
    expect(items[0].textContent).toContain(`Section ${found.candidates[0].section}`);
    expect(items[0].textContent).toContain("Before/after available");
    expect(items[0].textContent).toContain(found.candidates[0].why);
    expect(within(items[0]).getByRole("link", { name: /Source PDF/ }).getAttribute("href")).toBe(found.candidates[0].source.pdf_url);
    expect(chooser.textContent).toContain("not the Act's complete amendment history");
    expect(screen.queryByRole("article", { name: "The change, measured" })).toBeNull();  // no score for a whole Act
    expect(within(screen.getByRole("article", { name: "Answer" })).queryByRole("region", { name: "Sections you can choose" })).toBeNull();  // not listed twice
  });

  it("labels sections that cannot be compared differently from supported ones", () => {
    render(<AssistantResult analysis={responses.ocr} />);  // IT Act + "data privacy": topic matches first
    const items = within(screen.getByRole("article", { name: /you can open/ })).getAllByRole("listitem");
    expect(items[0].textContent).toContain("Mentions your topic; no recorded change");
    expect(within(items[0]).getByRole("button").textContent).toBe("See why");
  });

  it("compares a chosen section with one click, keeps the question and records the choice", async () => {
    const user = userEvent.setup();
    const act = responses["mv-act"], chosen = responses["mv-act-194"];
    window.history.replaceState(null, "", `#assistant/${act.analysis_id}`);
    render(<App />);
    await waitFor(() => screen.getByRole("article", { name: /you can open/ }));
    await user.click(screen.getByRole("button", { name: "Compare section 194" }));
    await waitFor(() => expect(window.location.hash).toBe(`#assistant/${chosen.analysis_id}`));
    expect(fetch).toHaveBeenCalledWith("/api/rag/query", expect.objectContaining({ body: JSON.stringify({ query: act.query, mode: "specific", section: "194" }) }));
    expect(screen.getByText(/Section chosen from the list:/).textContent).toContain("section 194 of the Motor Vehicles Act 1988");
    expect(screen.getByLabelText("Legal research question").value).toBe(act.query);
    expect(screen.getByRole("article", { name: "The change, measured" })).toBeTruthy();
    expect(readHistory().filter((row) => row.query === act.query).length).toBeLessThanOrEqual(1);  // a chosen section is not a second entry
  });

  it("explains when no section passes the evidence checks, and when the Act is not in the corpus", () => {
    render(<AssistantResult analysis={responses["ibc-act-2025"]} />);
    expect(screen.getByRole("article", { name: "No section to compare" })).toBeTruthy();
    expect(screen.getByRole("article", { name: "Answer" }).textContent).toMatch(/come from other amendments\. Check the official text on India Code/);
    cleanup();
    render(<AssistantResult analysis={responses["unknown-act"]} />);
    expect(screen.getByRole("article", { name: "Answer" }).textContent).toContain("No Act in this corpus matches the name used");
    expect(screen.getByRole("link", { name: /India Code/ }).getAttribute("href")).toMatch(/indiacode/);
  });

  it("never scores a footnote from a different amendment year", () => {
    render(<AssistantResult analysis={responses["ibc99-2025"]} />);
    expect(screen.getByRole("article", { name: "Answer" }).textContent).toMatch(/made by Act 6 of 2026, not by a 2025 amendment/);
    expect(document.querySelector(".change-glance-list")).toBeNull();
  });
});

describe("FAQ, recent questions and follow-ups", () => {
  const post = () => fetch.mock.calls.filter(([url]) => String(url).includes("/api/rag/query"));
  beforeEach(stubApi);

  it("an FAQ click with an old result present asks exactly that question, once", async () => {
    const user = userEvent.setup();
    const old = responses.ibc99, faq = FAQ.questions[0];
    window.history.replaceState(null, "", `#assistant/${old.analysis_id}`);
    render(<App />);
    await waitFor(() => screen.getByRole("article", { name: "Answer" }));
    await user.click(within(screen.getByRole("navigation")).getByRole("button", { name: /Recent changes FAQ/ }));
    expect(screen.getByRole("heading", { name: "Questions about amended Acts in this corpus" })).toBeTruthy();
    const card = screen.getByText(faq.question, { selector: "h3" }).closest("article");
    await user.click(within(card).getByRole("button", { name: /Ask this question/ }));
    expect(screen.getByLabelText("Legal research question").value).toBe(faq.question);
    await waitFor(() => expect(window.location.hash).toBe(`#assistant/${responses["mv-act"].analysis_id}`));
    expect(screen.getByLabelText("Legal research question").value).toBe(faq.question);  // the old result never replaces it
    expect(post().map(([, init]) => JSON.parse(init.body).query)).toEqual([faq.question]);
  });

  it("a direct question link asks once, even with an old analysis in the session, and Back does not re-ask", async () => {
    const question = responses["mv-act"].query;
    window.sessionStorage.setItem("tldrift:last-analysis", responses.ibc99.analysis_id);
    window.history.replaceState(null, "", `#assistant?q=${encodeURIComponent(question)}`);
    render(<App />);
    await waitFor(() => expect(window.location.hash).toBe(`#assistant/${responses["mv-act"].analysis_id}`));
    expect(post()).toHaveLength(1);
    expect(fetch.mock.calls.some(([url]) => String(url).includes(responses.ibc99.analysis_id))).toBe(false);
    window.history.back();
    await waitFor(() => expect(window.location.hash).toBe("#assistant"));
    expect(post()).toHaveLength(1);
  });

  it("every FAQ card says what it does and none claims to be recent", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(within(screen.getByRole("navigation")).getByRole("button", { name: /Recent changes FAQ/ }));
    const cards = document.querySelectorAll(".faq-card");
    expect(cards).toHaveLength(FAQ.questions.length);
    for (const card of cards) expect(within(card).getByRole("button").textContent).toMatch(/^Ask this question/);
    expect(document.querySelector(".page-section").textContent).not.toMatch(/recent/i);
  });

  it("keeps a short, deduplicated history of successful questions in this browser, with a way to clear it", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "#assistant");
    render(<App />);
    expect(screen.queryByRole("group", { name: "Recently asked" })).toBeNull();  // empty history: starters only
    expect(within(screen.getByRole("group", { name: "Try asking" })).getAllByRole("button")).toHaveLength(3);
    const input = screen.getByLabelText("Legal research question");
    for (const text of [responses["mv-act"].query, responses.ibc99.query, responses["mv-act"].query]) {
      await user.clear(input); await user.type(input, text);
      await user.click(screen.getByRole("button", { name: /Analyse/ }));
      await waitFor(() => expect(screen.getByRole("article", { name: "Answer" }).textContent).toContain(Object.values(responses).find((r) => r.query === text && !r.scenario && !r.selection).answer.direct_answer));
    }
    const recent = screen.getByRole("group", { name: "Recently asked" });
    expect(within(recent).getAllByRole("button").map((b) => b.textContent)).toEqual([responses["mv-act"].query, responses.ibc99.query, "Clear history"]);
    expect(readHistory().map((row) => Object.keys(row).sort())).toEqual([["act", "mode", "query"], ["act", "mode", "query"]]);  // no facts stored
    await user.click(within(recent).getByRole("button", { name: "Clear history" }));
    expect(screen.queryByRole("group", { name: "Recently asked" })).toBeNull();
    expect(window.localStorage.getItem("tldrift:recent-questions")).toBeNull();
  });

  it("caps history at five and survives unreadable storage", () => {
    let rows = [];
    for (let i = 0; i < 7; i++) rows = remember(rows, { query: `Question ${i}`, mode: "specific", act: null });
    expect(rows.map((row) => row.query)).toEqual(["Question 6", "Question 5", "Question 4", "Question 3", "Question 2"]);
    expect(remember(rows, { query: "  QUESTION   4 ", mode: "specific", act: null }).map((row) => row.query)).toEqual(["  QUESTION   4 ", "Question 6", "Question 5", "Question 3", "Question 2"]);
    window.localStorage.setItem("tldrift:recent-questions", "{not json");
    expect(readHistory()).toEqual([]);
  });

  it("suggests follow-ups from the Act and sections of the last answer, labelled as suggestions", async () => {
    const supported = responses["mv-act"].version_evidence.section_candidates.candidates.filter((row) => row.status === "SUPPORTED").slice(0, 2);
    expect(followUps(responses["mv-act"])).toEqual(supported.map((row) => `Compare section ${row.section} of the Motor Vehicles Act 1988 before and after the ${row.amendment_year} amendment.`));
    expect(followUps(responses.ibc99)).toEqual(["What changed in the Insolvency Bankruptcy Code 2016?"]);
    expect(followUps(responses.general)).toEqual([]);
    window.history.replaceState(null, "", `#assistant/${responses.ibc99.analysis_id}`);
    render(<App />);
    const group = await screen.findByRole("group", { name: "Suggested follow-ups" });
    await userEvent.setup().click(within(group).getByRole("button"));
    expect(screen.getByLabelText("Legal research question").value).toBe("What changed in the Insolvency Bankruptcy Code 2016?");
    expect(screen.getByText(/a comparison appears only if the evidence supports it/)).toBeTruthy();
  });
});

describe("latest discoveries from the monitored sources", () => {
  beforeEach(stubApi);
  const open = async (user) => user.click(await screen.findByRole("button", { name: /Latest discoveries/ }));

  it("lists discovered documents with source, dates, status and official link, and states each source's condition", async () => {
    const user = userEvent.setup();
    const data = recorded.notifications;
    render(<App />);
    const toggle = await screen.findByRole("button", { name: /Latest discoveries/ });
    await waitFor(() => expect(toggle.textContent).toContain(String(data.total)));  // unread count
    await open(user);
    const panel = screen.getByRole("complementary", { name: "Latest discovered in monitored sources" });
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(panel.textContent).toContain("Not a complete list of Indian amendments");
    const states = within(panel).getByRole("list", { name: "Source status" }).textContent;
    expect(states).toContain("Last check failed");
    expect(states).toContain("Not checked recently");
    const items = panel.querySelectorAll(".discovery-list > li");
    expect(items).toHaveLength(data.items.length);
    data.items.forEach((row, index) => {
      expect(items[index].textContent).toContain(row.title);
      expect(items[index].textContent).toContain(row.status_label);
      expect(items[index].textContent).toContain(row.source);
      expect(within(items[index]).getByRole("link", { name: /Official record/ }).getAttribute("href")).toBe(row.official_url);
    });
    expect(panel.textContent).toMatch(/Machine extraction names .*; this relationship is not verified\./);
    for (const item of items) expect(item.querySelector(".status-tag").textContent).not.toMatch(/confirmed|in force|commenced|amended/i);
    expect(panel.textContent).toContain("is not a confirmed change to law");
    expect(panel.textContent).toContain(`${data.listed_total} other listings seen but not downloaded`);
  });

  it("keeps read marks in this browser and closes with Escape, returning focus", async () => {
    const user = userEvent.setup();
    render(<App />);
    await open(user);
    const panel = screen.getByRole("complementary", { name: "Latest discovered in monitored sources" });
    await waitFor(() => expect(within(panel).getAllByText("New").length).toBe(recorded.notifications.total));
    await user.click(within(panel).getAllByRole("button", { name: "Mark as read" })[0]);
    expect(within(panel).getAllByText("New")).toHaveLength(recorded.notifications.total - 1);
    await user.click(within(panel).getByRole("button", { name: "Mark all as read" }));
    expect(within(panel).queryAllByText("New")).toHaveLength(0);
    expect(JSON.parse(window.localStorage.getItem("tldrift:seen-discoveries"))).toHaveLength(recorded.notifications.total);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("complementary", { name: "Latest discovered in monitored sources" })).toBeNull();
    expect(document.activeElement.textContent).toMatch(/^Latest discoveries/);
  });

  it("shows empty and unavailable states honestly", async () => {
    const user = userEvent.setup();
    const empty = { ...recorded.notifications, items: [], total: 0, listed: [], listed_total: 0 };
    const base = fetch.getMockImplementation();
    fetch.mockImplementation(async (url, init) => (String(url).includes("/api/sources/notifications") ? { ok: true, status: 200, json: async () => empty } : base(url, init)));
    render(<App />);
    await open(user);
    expect(await screen.findByText("No new documents are recorded from the monitored sources.")).toBeTruthy();
    cleanup();
    fetch.mockImplementation(async (url, init) => (String(url).includes("/api/sources/notifications") ? { ok: false, status: 500, json: async () => ({ error: "x" }) } : base(url, init)));
    render(<App />);
    await open(user);
    expect(await screen.findByText(/The discovery list could not be loaded/)).toBeTruthy();
  });
});

describe("worked score weights", () => {
  const request = vi.fn(async (path) => (path === "/api/methods/tlds" ? recorded.method : null));
  const calcPage = (analysis) => render(<ScoreCalculationPage analysis={analysis} onEvidence={vi.fn()} onField={vi.fn()} onAssistant={vi.fn()} request={request} />);

  it("shows value × weight = points for each component, adding up to the stored score, with its inputs", async () => {
    const tlds = responses.ibc99.fingerprint.tlds;
    calcPage(responses.ibc99);
    await waitFor(() => expect(screen.getByText(/not learned from data, not optimised and not legally validated/)).toBeTruthy());  // method loaded
    const table = screen.getByRole("table", { name: /value × weight × 100 = points/ });
    const rows = within(table).getAllByRole("row").slice(1, 5);
    const points = rows.map((row) => Number(row.cells[4].textContent));
    expect(points).toEqual(["textual", "semantic", "legal_effect", "rule_structure"].map((key) => Number(tlds.contributions[key].toFixed(1))));
    expect(Math.abs(points.reduce((a, b) => a + b, 0) - tlds.value)).toBeLessThan(0.2);  // rounding of the shown points only
    expect(rows[2].textContent).toContain(recorded.method.components.legal_effect.measures);
    expect(within(rows[2]).getByRole("button", { name: "Show the words behind legal effect: Deadline or period" })).toBeTruthy();
    expect(within(table).getByRole("row", { name: /Total/ }).textContent).toContain(tlds.calculation);
    await waitFor(() => expect(screen.getByText(/not learned from data, not optimised and not legally validated/)).toBeTruthy());
    for (const key of Object.keys(recorded.method.components)) expect(document.body.textContent).toContain(recorded.method.components[key].why_this_weight);
  });

  it("surfaces the sensitivity finding: the band depends on the weights", async () => {
    calcPage(responses.ibc99);
    const table = await screen.findByRole("table", { name: /held-out changes with a complete score, under four weightings/ });
    expect(within(table).getAllByRole("row")).toHaveLength(5);
    expect(within(table).getByRole("row", { name: /Current weights/ }).textContent).toContain("42");
    expect(document.body.textContent).toContain("There are no expert labels to say which weighting is right");
    expect(document.body.textContent).toContain("The weights were not changed to improve these numbers");
  });

  it("flags one component at 1 and the others at 0 prominently instead of hiding it in the total", () => {
    const base = responses.ibc99;
    const tlds = { ...base.fingerprint.tlds, value: 40, band: "Moderate", label: "40.0/100 · Moderate", calculation: "100 × (0.2 × 0.0000 + 0.3 × 0.0000 + 0.4 × 1.0000 + 0.1 × 0.0000) = 40.0",
      contributions: { textual: 0, semantic: 0, legal_effect: 40, rule_structure: 0 },
      disagreement: { spread: 1, highest: "legal_effect", lowest: "textual", strong: true, rule: "x" },
      components: Object.fromEntries(Object.entries(base.fingerprint.tlds.components).map(([key, part]) => [key, { ...part, value: key === "legal_effect" ? 1 : 0 }])) };
    calcPage({ ...base, fingerprint: { ...base.fingerprint, tlds } });
    const note = screen.getAllByRole("note").find((el) => el.textContent.startsWith("The components disagree."));
    expect(note.textContent).toContain("Legal effect (L) is 1.00 but Textual (T) is 0.00");
  });

  it("never counts a missing component as 0 and withholds the total", () => {
    calcPage(responses.mv170);
    const row = within(screen.getByRole("table", { name: /value × weight × 100 = points/ })).getByRole("row", { name: /Legal effect/ });
    expect(row.textContent).toContain("missing");
    expect(row.textContent).toContain("not counted");
    expect(document.body.textContent).toContain("A missing component is never counted as 0, so the total is withheld");
  });
});

describe("dedicated clause comparison page", () => {
  beforeEach(stubApi);
  const handlers = () => ({ onEvidence: vi.fn(), onField: vi.fn(), onAssistant: vi.fn(), onPage: vi.fn() });

  it("opens from a supported answer at #comparison/<id> and survives a refresh", async () => {
    const user = userEvent.setup();
    const analysis = responses.ibc99;
    window.history.replaceState(null, "", `#assistant/${analysis.analysis_id}`);
    render(<App />);
    await user.click(await screen.findByRole("button", { name: /View detailed clause comparison/ }));
    expect(window.location.hash).toBe(`#comparison/${analysis.analysis_id}`);
    expect(screen.getByRole("heading", { name: "Before and after, side by side" })).toBeTruthy();
    cleanup();
    window.history.replaceState(null, "", `#comparison/${analysis.analysis_id}`);
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Before and after, side by side" })).toBeTruthy();
    window.history.back();
  });

  it("shows provision, amendment, status, both sides with page links, highlighted changes and the rule fields", async () => {
    const user = userEvent.setup();
    const analysis = responses.ibc99, h = handlers();
    render(<ComparisonPage analysis={analysis} {...h} />);
    const page = document.querySelector(".comparison-page");
    expect(page.textContent).toContain("Insolvency Bankruptcy Code 2016");
    expect(page.textContent).toMatch(/Section 99/);
    expect(page.textContent).toContain("Act 6 of 2026 (from the footnote)");
    expect(page.textContent).toContain("Evidence status: Earlier wording reconstructed from India Code's own footnote (derived, not verbatim)");
    expect(page.querySelectorAll(".comparison-panel.full .compare-pane")).toHaveLength(2);
    expect(page.querySelector(".compare-pane.derived").textContent).toContain("Derived text — not a verbatim quote");
    expect([...page.querySelectorAll(".compare-pane a")].filter((a) => /Open source PDF at page 98/.test(a.textContent))).toHaveLength(2);
    expect(page.querySelector(".comparison-panel del")).toBeTruthy();
    expect(page.querySelector(".comparison-panel ins")).toBeTruthy();
    expect(page.textContent).toContain("“within ten days” → “within twenty-one days”");
    await user.click(screen.getAllByRole("button", { name: "Drift explanation →" })[0]);
    await user.click(screen.getAllByRole("button", { name: "Score calculation →" })[0]);
    expect(h.onPage.mock.calls).toEqual([["drift"], ["calculation"]]);
  });

  it("explains precisely why there is no pair, and never shows unrelated excerpts as versions", () => {
    render(<ComparisonPage analysis={responses["wrong-act"]} {...handlers()} />);
    expect(screen.getByRole("heading", { name: "No before and after to compare" })).toBeTruthy();
    expect(document.querySelector(".compare-pane")).toBeNull();
    expect(document.body.textContent).toContain(responses["wrong-act"].version_evidence.reason);
    cleanup();
    render(<AssistantResult analysis={responses["mv-act"]} />);
    expect(screen.queryByRole("button", { name: /View detailed clause comparison/ })).toBeNull();
  });
});

describe("question area and layout", () => {
  beforeEach(stubApi);

  it("jumps to the recently asked and suggested questions and focuses them, respecting reduced motion", async () => {
    const user = userEvent.setup();
    const scroll = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = scroll;
    window.matchMedia = vi.fn(() => ({ matches: true }));
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Recently asked and suggested questions/ }));
    expect(document.activeElement).toBe(screen.getByRole("region", { name: "Recently asked and suggested questions" }));
    expect(scroll).toHaveBeenCalledWith({ behavior: "auto", block: "center" });
    delete window.HTMLElement.prototype.scrollIntoView;
    delete window.matchMedia;
  });

  it("stacks the panel, chips and comparison on narrow screens and honours reduced motion", () => {
    const css = readFileSync("src/styles.css", "utf8");
    expect(css).toMatch(/@media \(max-width:900px\)\{\.discoveries\{position:static/);
    expect(css).toMatch(/@media \(max-width:620px\)\{\.question-chips \.suggestions button\{flex:1 1 100%\}/);
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)\{html\{scroll-behavior:auto\}/);
    expect(css).toMatch(/\.comparison-panel\.full \.compare-text\{max-height:none/);
    expect(css).toMatch(/\.compare-text,\.clause-text\{font:15px\/1\.7 var\(--reading\);overflow-wrap:anywhere\}/);
  });
});

