// @vitest-environment jsdom
// rag-answer-v5 analysis workspace and the standalone #drift / #calculation pages against real backend responses (fixtures/rag_answer_v5.json, generated offline;
// "timeout" used a real local socket that never answered). One v4 record checks that v0.14 links still open.
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import AnalysisWorkspace, { TABS } from "../AnalysisWorkspace";
import { DriftExplanationPage, ScoreCalculationPage } from "../ExplanationPages";

const { responses } = JSON.parse(readFileSync("src/__tests__/fixtures/rag_answer_v5.json", "utf8"));
const v4 = JSON.parse(readFileSync("src/__tests__/fixtures/rag_answer_v4.json", "utf8")).responses;
const weights = Object.fromEntries(Object.entries(JSON.parse(readFileSync("../configs/metrics/rule_drift.v1.2.json", "utf8")).fields).map(([k, v]) => [k, v.weight]));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); window.sessionStorage.clear(); });
const open = async (user, name) => user.click(screen.getByRole("tab", { name }));
const panel = () => screen.getByRole("tabpanel");
const scored = (analysis) => ["wording_drift", "rule_drift"].map((name) => analysis.fingerprint?.[name]).filter((item) => item?.value != null);

describe("a clean Answer tab", () => {
  it("shows the answer and supported results only, never a wall of empty assessments", () => {
    for (const key of ["it-s19", "ibc240", "mv170", "dm31", "wrong-act", "ocr", "general", "timeout"]) {
      render(<AnalysisWorkspace analysis={responses[key]} />);
      const text = panel().textContent;
      for (const empty of ["Cannot determine", "Needs your facts", "Not enough evidence", "Not scored", "Not applicable"]) expect(text, `${key}: ${empty}`).not.toContain(empty);
      expect(document.querySelectorAll(".determination, .fingerprint-card").length).toBe(0);
      expect(screen.queryAllByRole("button", { name: "Check your situation" }).length).toBeLessThanOrEqual(1);
      cleanup();
    }
  });

  it("offers one unobtrusive way to check a personal conclusion that needs facts", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses["it-s19"]} />);
    expect(screen.getByText("3 facts decide whether this changes for you.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Check your situation" }));
    expect(screen.getByRole("tab", { name: "Scenario & Impact" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("form", { name: "Your situation" })).toBeTruthy();
  });

  it("shows a determination only when it was decided for stated facts", () => {
    render(<AnalysisWorkspace analysis={responses["dm31-month18"]} />);
    const glance = screen.getByRole("region", { name: "The change at a glance" });
    expect(within(glance).getByText("For your facts").nextSibling.textContent).toBe("Changed");
    expect(within(glance).getByText("Rule change").nextSibling.textContent).toBe("15/100");
  });

  it("labels a model timeout and still answers from the evidence", () => {
    render(<AnalysisWorkspace analysis={responses.timeout} />);
    expect(screen.getByRole("status").textContent).toMatch(/Extractive evidence summary.*TimeoutError; this answer was produced without it/);
  });
});

describe("standalone Drift explanation and Score calculation pages", () => {
  const handlers = () => ({ onEvidence: vi.fn(), onField: vi.fn(), onAssistant: vi.fn(), onCalculation: vi.fn() });
  const drift = (analysis, props = {}) => render(<DriftExplanationPage analysis={analysis} {...handlers()} {...props} />);
  const calc = (analysis, props = {}) => render(<ScoreCalculationPage analysis={analysis} {...handlers()} {...props} />);
  const page = () => document.querySelector(".page-section");

  it("are not tabs of the workspace any more", () => {
    render(<AnalysisWorkspace analysis={responses.ibc99} />);
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Answer", "Compare Evidence", "Scenario & Impact", "Sources & Review"]);
  });

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

describe("Scenario & Impact", () => {
  it("re-runs with the facts that decide the outcome, and keeps irrelevant risk out", async () => {
    const user = userEvent.setup();
    const onScenario = vi.fn();
    render(<AnalysisWorkspace analysis={responses.ibc99} onScenario={onScenario} />);
    await open(user, "Scenario & Impact");
    await user.type(screen.getByLabelText(/How many days have passed/), "15");
    await user.click(screen.getByRole("button", { name: "Re-run with these facts" }));
    expect(onScenario).toHaveBeenCalledWith({ facts: { elapsed_days: 15 } });
    expect(screen.getByText(/No modelled compliance obligation covers this provision/)).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Conditional compliance risk" })).toBeNull();
  });

  it("shows a deadline flip for one scenario and not for another", async () => {
    const user = userEvent.setup();
    for (const [key, label] of [["ibc99-day15", "Changed"], ["ibc99-day25", "Unchanged"]]) {
      render(<AnalysisWorkspace analysis={responses[key]} />);
      await open(user, "Scenario & Impact");
      expect(within(screen.getByRole("region", { name: "Impact on your situation" })).getByText(label)).toBeTruthy();
      cleanup();
    }
  });
});

describe("abstention and sources", () => {
  it("explains unreadable text where the detail belongs", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses.ocr} />);
    await open(user, "Sources & Review");
    expect(screen.getByText(/Source text unreliable: it-amendment-act-2008/)).toBeTruthy();
    expect(screen.getByText(/Legal validation: UNVERIFIED/)).toBeTruthy();
  });

  it("still opens a stored v4 analysis from a v0.14 link", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={v4["dm31-month18"]} />);
    for (const { label } of TABS) { await open(user, label); expect(panel().textContent.length, label).toBeGreaterThan(40); }
  });


  it("marks materiality as provisional machine triage, not gold", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses.ibc99} />);
    await open(user, "Sources & Review");
    const card = screen.getByRole("heading", { name: /Materiality of the amendment/ }).closest("article");
    await user.click(within(card).getByText("Method and evidence"));
    expect(within(card).getAllByText(/computed for this answer/).length).toBeGreaterThan(0);
  });



});

describe("links, history and keyboard", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      const id = String(url).match(/\/api\/analyses\/(an_[0-9a-f]{24})/)?.[1];
      const body = id ? Object.values(responses).find((r) => r.analysis_id === id) : String(url).includes("/api/corpus") ? { entries: [] } : String(url).includes("/api/sources/health") ? { sources: [] } : { ready: true };
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
    window.history.replaceState(null, "", `#analysis/${analysis.analysis_id}/answer`);
    render(<App />);
    await waitFor(() => screen.getByRole("tab", { name: "Answer" }));
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
    await waitFor(() => expect(screen.getByRole("tab", { name: "Answer" }).getAttribute("aria-selected")).toBe("true"));
    window.history.forward();
    await waitFor(() => expect(screen.getByRole("heading", { name: "What the drift score means" })).toBeTruthy());
    await user.click(within(nav).getByRole("button", { name: /Legal drift assistant/ }));
    expect(window.location.hash).toBe(`#analysis/${analysis.analysis_id}/answer`);
    expect(screen.getByLabelText("Legal research question").value).toBe(analysis.query);
  });

  it("links from the answer to the pages, and from a page's evidence and rule fields back to the cited words", async () => {
    const user = userEvent.setup();
    const analysis = responses.ibc99;
    window.history.replaceState(null, "", `#analysis/${analysis.analysis_id}/answer`);
    render(<App />);
    await waitFor(() => screen.getByRole("tab", { name: "Answer" }));
    await user.click(screen.getByRole("button", { name: "Score calculation →" }));
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

  it("moves between the four views with the arrow keys and labels every panel", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses.sra} />);
    screen.getByRole("tab", { name: "Answer" }).focus();
    await user.keyboard("{ArrowRight}{ArrowRight}");
    expect(document.activeElement.textContent).toBe("Scenario & Impact");
    expect(screen.getByRole("tabpanel").getAttribute("aria-labelledby")).toBe("tab-scenario");
    await user.keyboard("{End}");
    expect(document.activeElement.textContent).toBe("Sources & Review");
  });

  it("stacks dense calculation rows on narrow screens", () => {
    const css = readFileSync("src/styles.css", "utf8");
    expect(css).toMatch(/\.table-scroll\{position:relative;overflow-x:auto\}/);  // relative: the sr-only header must not escape the scroller
    expect(css).toMatch(/@media \(max-width:620px\)\{\.calc-list\{grid-template-columns:1fr\}\.table-scroll \.fp-table\{min-width:600px\}/);
    expect(css).toMatch(/\.analysis-tabs\{[^}]*overflow-x:auto/);
  });
});
