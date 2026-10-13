// @vitest-environment jsdom
// rag-answer-v4 analysis workspace against real backend responses (fixtures/rag_answer_v4.json, generated offline).
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import AnalysisWorkspace from "../AnalysisWorkspace";

const { responses } = JSON.parse(readFileSync("src/__tests__/fixtures/rag_answer_v4.json", "utf8"));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; window.sessionStorage.clear(); });
const open = async (user, name) => user.click(screen.getByRole("tab", { name }));

describe("one analysis, five views", () => {
  it("keeps the same evidence and scores when moving between views", async () => {
    const user = userEvent.setup();
    const analysis = responses["dm31-month18"];
    render(<AnalysisWorkspace analysis={analysis} />);
    const wording = analysis.fingerprint.wording_drift;
    expect(screen.getByText(/“annually” was replaced/)).toBeTruthy();
    await open(user, "Scores & Method");
    expect(screen.getAllByText(wording.label).length).toBeGreaterThan(0);
    const clause = () => screen.getByRole("region", { name: "Clause after" }).querySelector(".compare-text").textContent;
    expect(clause()).toBe(wording.details.after_clause);     // the exact scored clause
    await open(user, "Compare & Evidence");
    expect(clause()).toBe(wording.details.after_clause);
    await open(user, "Answer");
    await open(user, "Scores & Method");
    expect(screen.getAllByText(wording.label).length).toBeGreaterThan(0); // nothing disappears or is recomputed
  });

  it("links every score to the cited evidence that produced it", async () => {
    const user = userEvent.setup();
    const analysis = responses["dm31-month18"];
    render(<AnalysisWorkspace analysis={analysis} />);
    await open(user, "Scores & Method");
    const card = screen.getByRole("heading", { name: "Wording drift", level: 3 }).closest("article");
    const first = analysis.fingerprint.wording_drift.evidence_ids[0];
    await user.click(within(card).getByRole("button", { name: `Show evidence ${first}` }));
    await waitFor(() => expect(document.activeElement.id).toBe(`evidence-${first}`));
    expect(screen.getByRole("tab", { name: "Compare & Evidence" }).getAttribute("aria-selected")).toBe("true");
    const span = analysis.fingerprint.wording_drift.details.spans[0];
    expect(screen.getByRole("region", { name: "Clause before" }).querySelector("del").textContent).toBe(span.before_text);
  });

  it("never shows a rule score for an unsupported field (the IT s.19 'actor' case)", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses["it-s19"]} />);
    await open(user, "Scores & Method");
    const card = screen.getByRole("heading", { name: "Rule drift", level: 3 }).closest("article");
    expect(within(card).getByText("Not scored")).toBeTruthy();
    expect(within(card).queryByText(/\/100/)).toBeNull();
    expect(within(card).getByText(/not one of the rule fields/)).toBeTruthy();
    expect(within(card).queryByRole("rowheader", { name: /actor/i })).toBeNull();   // no bogus actor field
  });
});

describe("only the facts that are needed", () => {
  it("asks beside the answer for the decisive facts only and re-runs with them", async () => {
    const user = userEvent.setup();
    const onScenario = vi.fn();
    render(<AnalysisWorkspace analysis={responses["it-s19"]} onScenario={onScenario} />);
    const form = screen.getByRole("form", { name: "Your situation" });
    expect(within(form).getAllByRole("combobox").length + within(form).getAllByRole("textbox").length).toBe(3);
    expect(within(form).queryByLabelText(/Organization type/)).toBeNull();          // risk-only facts are not in the short form
    await user.selectOptions(within(form).getByLabelText(/Is digital signature/), "yes");
    await user.selectOptions(within(form).getByLabelText(/Is notified electronic signature/), "no");
    await user.click(within(form).getByRole("button", { name: "Re-run with these facts" }));
    expect(onScenario).toHaveBeenCalledWith({ facts: { is_digital_signature: true, is_notified_electronic_signature: false } });
  });

  it("keeps risk facts optional and grouped in Scenario & Impact", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses["it-s19"]} />);
    await open(user, "Scenario & Impact");
    expect(screen.getByText(/Also assess conditional risk \(optional, 8 facts\)/)).toBeTruthy();
  });

  it("uses a fact written in the question and says so", () => {
    render(<AnalysisWorkspace analysis={responses["dm31-question-fact"]} />);
    expect(screen.getByText("Changed")).toBeTruthy();
    expect(screen.queryByLabelText(/How many months/)).toBeNull();   // already supplied by the question
  });

  it("shows a deadline flip for one scenario but not for another", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<AnalysisWorkspace analysis={responses["dm31-month18"]} />);
    await open(user, "Scenario & Impact");
    expect(within(screen.getByRole("region", { name: "Impact on your situation" })).getByText("Changed")).toBeTruthy();
    unmount();
    render(<AnalysisWorkspace analysis={responses["dm31-month6"]} />);
    await open(user, "Scenario & Impact");
    expect(within(screen.getByRole("region", { name: "Impact on your situation" })).getByText("Unchanged")).toBeTruthy();
  });
});

describe("missing evidence is not missing facts", () => {
  it("offers no facts form when the law itself is unsupported, and says why", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses["wrong-act"]} />);
    expect(screen.queryByRole("form", { name: "Your situation" })).toBeNull();
    await open(user, "Scenario & Impact");
    expect(screen.getByText(/Facts cannot fill missing legal evidence/)).toBeTruthy();
    expect(screen.getAllByText(/Missing legal evidence \(your facts cannot fill this\)/).length).toBeGreaterThan(0);
  });

  it("gives one next step instead of repeating 'not assessed' on the first screen", () => {
    render(<AnalysisWorkspace analysis={responses["it-s19"]} />);
    expect(screen.getAllByRole("note").filter((n) => n.className.includes("next-action")).length).toBe(1);
    expect(screen.queryByText(/Not enough evidence/)).toBeNull();
    expect(document.querySelectorAll(".determination").length).toBe(0);  // detailed cards live in their own views
  });

  it("explains an unreadable source and an unsupported question honestly", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses.ocr} />);
    expect(screen.getByText(/name the section/i)).toBeTruthy();
    await open(user, "Sources & Review");
    expect(screen.getByText(/Source text unreliable: it-amendment-act-2008/)).toBeTruthy();
    cleanup();
    render(<AnalysisWorkspace analysis={responses["out-of-scope"]} />);
    await open(user, "Compare & Evidence");
    expect(screen.getByText("No before/after comparison for this question")).toBeTruthy();
  });

  it("marks materiality as machine triage, distinguishing on-the-fly from the frozen set", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses["mv-s173"]} />);
    await open(user, "Sources & Review");
    const card = screen.getByRole("heading", { name: "Materiality of the amendment", level: 3 }).closest("article");
    await user.click(within(card).getByText("Method and evidence"));
    expect(within(card).getByText(/Frozen silver set|computed for this answer/)).toBeTruthy();
    expect(within(card).getByText(/not gold/)).toBeTruthy();
  });
});

describe("links, refresh and keyboard", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      const id = String(url).match(/\/api\/analyses\/(an_[0-9a-f]{24})/)?.[1];
      const body = id ? Object.values(responses).find((r) => r.analysis_id === id) : String(url).includes("/api/corpus") ? { documents: [] } : { ready: true };
      return { ok: Boolean(body), status: body ? 200 : 404, json: async () => body || { error: "Analysis not found" } };
    }));
  });

  it("opens a shared analysis link on the requested view after a refresh", async () => {
    const analysis = responses["dm31-month18"];
    window.location.hash = `#analysis/${analysis.analysis_id}/scores`;
    render(<App />);
    await waitFor(() => expect(screen.getByRole("tab", { name: "Scores & Method" }).getAttribute("aria-selected")).toBe("true"));
    expect(screen.getAllByText(analysis.fingerprint.rule_drift.label).length).toBeGreaterThan(0);
    expect(fetch).toHaveBeenCalledWith(`/api/analyses/${analysis.analysis_id}`, expect.anything());
  });

  it("writes the active view into the shareable address", async () => {
    const user = userEvent.setup();
    const analysis = responses["sra"];
    window.location.hash = `#analysis/${analysis.analysis_id}/answer`;
    render(<App />);
    await waitFor(() => screen.getByRole("tab", { name: "Compare & Evidence" }));
    await open(user, "Compare & Evidence");
    expect(window.location.hash).toBe(`#analysis/${analysis.analysis_id}/evidence`);
  });

  it("moves between views with the arrow keys and labels every panel", async () => {
    const user = userEvent.setup();
    render(<AnalysisWorkspace analysis={responses.sra} />);
    screen.getByRole("tab", { name: "Answer" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(document.activeElement.textContent).toBe("Compare & Evidence");
    expect(screen.getByRole("tabpanel").getAttribute("aria-labelledby")).toBe("tab-evidence");
    await user.keyboard("{End}");
    expect(document.activeElement.textContent).toBe("Sources & Review");
  });

  it("stacks the answer and the facts form on narrow screens", () => {
    const css = readFileSync("src/styles.css", "utf8");
    expect(css).toMatch(/@media \(max-width:900px\)\{\.answer-layout\{grid-template-columns:1fr\}/);
    expect(css).toMatch(/\.analysis-tabs\{[^}]*overflow-x:auto/);
  });
});
