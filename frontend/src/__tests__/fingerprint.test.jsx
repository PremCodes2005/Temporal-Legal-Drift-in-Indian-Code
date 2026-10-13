// @vitest-environment jsdom
// Legal Change Fingerprint UI against real backend responses: displayed values must equal the API's.
import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RagResult } from "../App";

afterEach(cleanup);
const { responses } = JSON.parse(readFileSync("src/__tests__/fixtures/rag_answer_v3.json", "utf8"));
const card = (title) => screen.getByRole("heading", { name: title, level: 3 }).closest("article");

describe("three separate measures", () => {
  it("shows wording, rule and outcome drift exactly as the backend computed them, with no combined score", () => {
    const result = responses.sra;
    render(<RagResult result={result} onExplain={() => {}} />);
    const fingerprint = screen.getByRole("region", { name: "Three separate measures of this change" });
    expect(within(card("Wording drift")).getByText(result.fingerprint.wording_drift.label)).toBeTruthy();
    expect(within(card("Rule drift")).getByText(result.fingerprint.rule_drift.label)).toBeTruthy();
    expect(within(card("Outcome drift")).getByText("Cannot determine")).toBeTruthy();
    expect(within(fingerprint).getByText(/never averaged/)).toBeTruthy();
    expect(fingerprint.querySelectorAll(".fp-value").length).toBe(3);  // three values, no combined fingerprint score
    expect(result.fingerprint).not.toHaveProperty("overall");
  });

  it("explains wording drift with its formula, exact spans and a labelled legacy diagnostic", () => {
    const result = responses.sra;
    render(<RagResult result={result} onExplain={() => {}} />);
    const panel = within(card("Wording drift")).getByText("How wording drift was calculated").closest("details");
    expect(within(panel).getByText(/0.5 × lexical drift \+ 0.5 × feature-vector drift/)).toBeTruthy();
    const span = result.fingerprint.wording_drift.details.spans[0];
    expect(within(panel).getByText(span.before_text).tagName).toBe("DEL");
    expect(within(panel).getByText(span.after_text).tagName).toBe("INS");
    expect(within(panel).getByText(/not a pretrained semantic model/)).toBeTruthy();
    expect(within(panel).getByText(/Legacy diagnostic \(drift-metrics-v3\)/)).toBeTruthy();
    expect(within(panel).getByText("legacy overall (diagnostic)")).toBeTruthy();
  });

  it("lists the rule delta with weights that add up to the displayed score", () => {
    const result = responses["mv181-breach"];
    render(<RagResult result={result} onExplain={() => {}} />);
    const table = within(card("Rule drift")).getByRole("table", { name: /Rule fields/ });
    const contributions = within(table).getAllByRole("row").slice(1).map((row) => Number(row.lastChild.textContent));
    expect(contributions.reduce((a, b) => a + b, 0)).toBe(result.fingerprint.rule_drift.value);
  });

  it("shows the decisive facts, both answers and the controlled-scenario denominator", () => {
    const result = responses["dm31-facts"];
    render(<RagResult result={result} onExplain={() => {}} />);
    const outcome = card("Outcome drift");
    expect(within(outcome).getByText("Changed")).toBeTruthy();
    expect(within(outcome).getByText("elapsed_months = 18")).toBeTruthy();
    const controlled = result.fingerprint.outcome_drift.details.controlled_scenarios;
    expect(within(outcome).getByText(new RegExp(`${controlled.flips} of ${controlled.evaluated} generated`))).toBeTruthy();
    expect(within(outcome).getByText(/Outcome drift is not risk/)).toBeTruthy();
  });

  it("explains a missing component and asks for the exact facts in the form", () => {
    render(<RagResult result={responses.sra} onExplain={() => {}} />);
    expect(within(card("Outcome drift")).getByText(/Add the facts asked for below/)).toBeTruthy();
    const form = screen.getByRole("form", { name: "Add your situation" });
    expect(within(form).getByLabelText("Does your situation fall within this provision?")).toBeTruthy();
  });

  it("puts each explanation panel in the keyboard order", async () => {
    const user = userEvent.setup();
    render(<RagResult result={responses["dm31-facts"]} onExplain={() => {}} />);
    const seen = [];
    for (let i = 0; i < 80; i++) {
      await user.tab();
      if (document.activeElement.tagName === "SUMMARY") seen.push(document.activeElement.textContent);
    }
    const panels = ["How wording drift was calculated", "Rule delta and score", "Facts applied to both versions"];
    expect([...new Set(seen.filter((text) => panels.includes(text)))]).toEqual(panels);  // first visit of each, in page order
  });
});
