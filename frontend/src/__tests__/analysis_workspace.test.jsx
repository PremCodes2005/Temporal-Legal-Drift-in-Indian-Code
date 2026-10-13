// @vitest-environment jsdom
// rag-answer-v5 analysis workspace against real backend responses (fixtures/rag_answer_v5.json, generated offline;
// "timeout" used a real local socket that never answered). One v4 record checks that v0.14 links still open.
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import AnalysisWorkspace, { TABS } from "../AnalysisWorkspace";

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

describe("Drift Explanation and Score Calculation", () => {
  it("keep one analysis's evidence and numbers across all six views", async () => {
    const user = userEvent.setup();
    const analysis = responses["ibc99-day15"];
    render(<AnalysisWorkspace analysis={analysis} />);
    const seen = {};
    for (const { label } of [...TABS, ...TABS]) {
      await open(user, label);
      const text = panel().textContent;
      expect(text.length, label).toBeGreaterThan(80);
      if (seen[label]) expect(text).toBe(seen[label]);   // revisiting a view shows exactly the same content
      seen[label] = text;
    }
    await open(user, "Compare Evidence");
    expect(screen.getByRole("region", { name: "Clause after" }).querySelector(".compare-text").textContent).toBe(analysis.fingerprint.wording_drift.details.after_clause);
  });

  it("is never blank when the Answer tab displays a score", async () => {
    const user = userEvent.setup();
    for (const [key, analysis] of Object.entries(responses)) {
      render(<AnalysisWorkspace analysis={analysis} />);
      const labels = scored(analysis).map((item) => item.label);
      for (const view of ["Drift Explanation", "Score Calculation"]) {
        await open(user, view);
        for (const label of labels) expect(panel().textContent, `${key} ${view}`).toContain(label);
        if (!labels.length) expect(within(panel()).getByRole("status").textContent, key).toMatch(/No change to explain|could not be measured/);
      }
      cleanup();
    }
  });

  it("explains a small wording edit that changes a deadline, without averaging", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses.ibc99} />);
    await open(user, "Drift Explanation");
    expect(screen.getAllByRole("note")[0].textContent).toMatch(/Only 0\.8% of the wording changed, yet the deadline or period changed/);
    expect(panel().textContent).toContain("“within ten days” → “within twenty-one days”");
    expect(panel().textContent).toContain("Why it matters: it changes when compliance is due.");
    expect(panel().textContent).not.toMatch(/overall|average[ds]? (?!into)/i);
  });

  it("shows every rule-field contribution, and the total is reproducible from the shown weights", async () => {
    const user = userEvent.setup();
    for (const key of ["ibc99", "sra", "mv173", "ibc240", "dm31"]) {
      const rule = responses[key].fingerprint.rule_drift;
      render(<AnalysisWorkspace analysis={responses[key]} />);
      await open(user, "Score Calculation");
      const rows = within(screen.getByRole("table", { name: /Each rule field/ })).getAllByRole("row").slice(1, -1);
      const added = rows.map((row) => Number(row.cells[5].textContent));
      expect(rows).toHaveLength(8);
      expect(added.reduce((a, b) => a + b, 0), key).toBe(rule.value);
      for (const row of rule.details.fields) expect(row.contribution).toBe(["ADDED", "REMOVED", "CHANGED"].includes(row.operation) ? weights[row.field] : 0);
      expect(panel().textContent).toContain(rule.details.calculation);
      cleanup();
    }
  });

  it("links each number to the cited words in Compare Evidence", async () => {
    const user = userEvent.setup();
    const analysis = responses.ibc99;
    render(<AnalysisWorkspace analysis={analysis} />);
    await open(user, "Score Calculation");
    await user.click(screen.getByRole("button", { name: "Show the words for Deadline or period" }));
    expect(screen.getByRole("tab", { name: "Compare Evidence" }).getAttribute("aria-selected")).toBe("true");
    const marks = [...document.querySelectorAll(".clause-pair mark")].map((m) => m.textContent);
    expect(marks).toEqual(["within ten days", "within twenty-one days"]);
    await open(user, "Score Calculation");
    const first = analysis.fingerprint.rule_drift.evidence_ids[0];
    await user.click(within(screen.getByRole("region", { name: /Rule drift =/ })).getByRole("button", { name: `Show evidence ${first}` }));
    await waitFor(() => expect(document.activeElement.id).toBe(`evidence-${first}`));
  });

  it("gives the specific reason instead of a number when a change cannot be scored", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses.mv170} />);
    await open(user, "Score Calculation");
    const card = screen.getByRole("region", { name: /Rule drift =/ });
    expect(within(card).getByText(/No score is shown\./).parentElement.textContent).toMatch(/Only a cross-reference changed \(“149” → “150”\)/);
    expect(card.querySelector("tfoot")).toBeNull();
  });

  it("uses the same sources and scores in Generic and Specific mode", async () => {
    const user = userEvent.setup();
    const views = [];
    for (const key of ["it-s19", "it-s19-generic"]) {
      render(<AnalysisWorkspace analysis={responses[key]} />);
      await open(user, "Score Calculation");
      views.push(panel().textContent.replace(/stored analysis an_[0-9a-f]+/, ""));
      cleanup();
    }
    expect(views[0]).toBe(views[1]);
  });

  it("labels hypothetical boundary values as not the user's facts", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses["ibc99-day25"]} />);
    await open(user, "Score Calculation");
    expect(panel().textContent).toContain("Hypothetical boundary values (not your facts)");
    expect(panel().textContent).toContain("elapsed_days = 25");
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
  it("explains unsupported pairing and unreadable text where the detail belongs", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses["wrong-act"]} />);
    await open(user, "Drift Explanation");
    expect(within(panel()).getByRole("status").textContent).toMatch(/could not be measured.*Nothing is scored, so no number is shown/);
    cleanup();
    render(<AnalysisWorkspace analysis={responses.ocr} />);
    await open(user, "Sources & Review");
    expect(screen.getByText(/Source text unreliable: it-amendment-act-2008/)).toBeTruthy();
    expect(screen.getByText(/Legal validation: UNVERIFIED/)).toBeTruthy();
  });

  it("marks materiality as provisional machine triage, not gold", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses.ibc99} />);
    await open(user, "Sources & Review");
    const card = screen.getByRole("heading", { name: /Materiality of the amendment/ }).closest("article");
    await user.click(within(card).getByText("Method and evidence"));
    expect(within(card).getAllByText(/computed for this answer/).length).toBeGreaterThan(0);
  });

  it("shows the combined TLDS beside its four parts, and flags a legal effect the composite would hide", async () => {
    const user = userEvent.setup();
    const tlds = responses.ibc99.fingerprint.tlds;
    render(<AnalysisWorkspace analysis={responses.ibc99} />);
    await open(user, "Drift Explanation");
    const card = screen.getByRole("region", { name: /Hybrid drift score \(TLDS\)/ });
    const parts = Object.values(tlds.components).map((part) => part.value);
    for (const value of parts) expect(card.textContent).toContain(value.toFixed(3));
    const recomputed = 100 * Object.entries(tlds.components).reduce((sum, [name, part]) => sum + tlds.weights[name] * part.value, 0);
    expect(card.textContent).toContain(`= ${recomputed.toFixed(1)}`);
    expect(within(card).getByRole("note").textContent).toMatch(/combined score is low, but legal-effect drift is 0\.50\. Material change/i);
  });

  it("marks the combined score incomplete when legal effect is missing, never 0", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses.mv170} />);
    await open(user, "Drift Explanation");
    const card = screen.getByRole("region", { name: /Hybrid drift score \(TLDS\)/ });
    expect(card.textContent).toMatch(/No complete score\. Missing: legal effect/);
    expect(card.textContent).toContain("not comparable with complete scores");
  });

  it("still opens a stored v4 analysis from a v0.14 link", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={v4["dm31-month18"]} />);
    for (const { label } of TABS) { await open(user, label); expect(panel().textContent.length, label).toBeGreaterThan(40); }
    await open(user, "Drift Explanation");
    expect(screen.queryByRole("region", { name: /Hybrid drift score/ })).toBeNull();  // records without TLDS omit the section
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

  it("opens a shared link on its view, including old 'scores' links", async () => {
    const analysis = responses["ibc99-day15"];
    window.history.replaceState(null, "", `#analysis/${analysis.analysis_id}/scores`);
    render(<App />);
    await waitFor(() => expect(screen.getByRole("tab", { name: "Score Calculation" }).getAttribute("aria-selected")).toBe("true"));
    expect(fetch).toHaveBeenCalledWith(`/api/analyses/${analysis.analysis_id}`, expect.anything());
    await waitFor(() => expect(screen.getByLabelText("Legal research question").value).toBe(analysis.query));  // the question is shown again
  });

  it("restores the separate Drift explanation and Score calculation navigation", async () => {
    const user = userEvent.setup();
    const analysis = responses.ibc99;
    window.history.replaceState(null, "", `#analysis/${analysis.analysis_id}/answer`);
    render(<App />);
    await waitFor(() => screen.getByRole("tab", { name: "Answer" }));
    const nav = screen.getByRole("navigation");
    await user.click(within(nav).getByRole("button", { name: /Drift explanation/ }));
    expect(screen.getByRole("tab", { name: "Drift Explanation" }).getAttribute("aria-selected")).toBe("true");
    expect(within(nav).getByRole("button", { name: /Drift explanation/ }).getAttribute("aria-current")).toBe("page");
    expect(window.location.hash).toBe(`#analysis/${analysis.analysis_id}/drift`);
    await user.click(within(nav).getByRole("button", { name: /Score calculation/ }));
    expect(window.location.hash).toBe(`#analysis/${analysis.analysis_id}/calculation`);
  });

  it("moves back and forward between views of the same analysis", async () => {
    const user = userEvent.setup();
    const analysis = responses.dm31;
    window.history.replaceState(null, "", `#analysis/${analysis.analysis_id}/answer`);
    render(<App />);
    await waitFor(() => screen.getByRole("tab", { name: "Compare Evidence" }));
    await open(user, "Compare Evidence");
    await open(user, "Score Calculation");
    window.history.back();
    await waitFor(() => expect(screen.getByRole("tab", { name: "Compare Evidence" }).getAttribute("aria-selected")).toBe("true"));
    window.history.forward();
    await waitFor(() => expect(screen.getByRole("tab", { name: "Score Calculation" }).getAttribute("aria-selected")).toBe("true"));
  });

  it("shows a helpful page for the score views before any analysis exists", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(within(screen.getByRole("navigation")).getByRole("button", { name: /Score calculation/ }));
    expect(screen.getByText("Ask a comparison question first.")).toBeTruthy();
  });

  it("moves between six views with the arrow keys and labels every panel", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses.sra} />);
    screen.getByRole("tab", { name: "Answer" }).focus();
    await user.keyboard("{ArrowRight}{ArrowRight}");
    expect(document.activeElement.textContent).toBe("Drift Explanation");
    expect(screen.getByRole("tabpanel").getAttribute("aria-labelledby")).toBe("tab-drift");
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
