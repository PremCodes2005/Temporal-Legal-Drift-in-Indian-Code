// @vitest-environment jsdom
// rag-answer-v2 rendering against real backend responses (fixtures/rag_answer_v2.json, generated offline).
import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RagResult } from "../App";

afterEach(cleanup);
const { responses } = JSON.parse(readFileSync("src/__tests__/fixtures/rag_answer_v2.json", "utf8"));
const card = (title) => screen.getByRole("heading", { name: title, level: 3 }).closest("article");

describe("answer first, then four separate determinations", () => {
  it("opens with the direct answer and links every claim to its evidence", () => {
    render(<RagResult result={responses["mv-s173"]} onExplain={() => {}} />);
    expect(screen.getByText(/“ten thousand” was replaced by “one lakh”/)).toBeTruthy();
    const effect = screen.getByRole("region", { name: "Effect on your question" });
    expect(within(effect).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual(["#evidence-E2", "#evidence-E3"]);
    expect(document.getElementById("evidence-E1").textContent).toMatch(/Amendment instruction \(verbatim\)/);
    expect(screen.getAllByRole("link", { name: /Open source PDF at page 32/ }).length).toBeGreaterThan(0);
  });

  it("shows each determination with its own state and reason, and no invented labels", () => {
    render(<RagResult result={responses["mv-s173"]} onExplain={() => {}} />);
    expect(within(card("Textual drift")).getByText("Determined")).toBeTruthy();
    expect(within(card("Materiality")).getByText("Provisional")).toBeTruthy();
    expect(within(card("Materiality")).getByText(/not an expert judgment/)).toBeTruthy();
    expect(within(card("Answer change")).getByText("Changes")).toBeTruthy();
    expect(within(card("Risk")).getByText("Not applicable")).toBeTruthy();
    expect(within(card("Risk")).getByText("—")).toBeTruthy();
    expect(within(card("Risk")).getByText(/no rule for this provision/)).toBeTruthy();
  });

  it("labels reconstructed and current-consolidated wording for the Section 19 example", () => {
    render(<RagResult result={responses["it-s19"]} onExplain={() => {}} />);
    expect(screen.getByText(/“Digital Signature” was replaced by “electronic signature”/)).toBeTruthy();
    expect(screen.getByText(/reconstructed from the India Code footnote \(derived/)).toBeTruthy();
    expect(screen.getByText(/current consolidated text \(today's wording/)).toBeTruthy();
    expect(within(card("Materiality")).getByText("Not enough evidence")).toBeTruthy();
    expect(within(card("Risk")).getByText("Needs your facts")).toBeTruthy();
  });
});

describe("scenario facts", () => {
  it("asks only for what the backend needs and re-runs the same question with those facts", async () => {
    const user = userEvent.setup();
    const onScenario = vi.fn();
    render(<RagResult result={responses["it-s19"]} onExplain={() => {}} onScenario={onScenario} />);
    const form = screen.getByRole("form", { name: "Add your situation" });
    await user.selectOptions(within(form).getByLabelText("Organization type"), "foreign_certifying_authority");
    await user.selectOptions(within(form).getByLabelText("Is digital signature"), "yes");
    await user.type(within(form).getByLabelText(/Reference date/), "2009-10-27");
    await user.click(within(form).getByRole("button", { name: "Re-run with these facts" }));
    expect(onScenario).toHaveBeenCalledWith({ organization_type: "foreign_certifying_authority", reference_date: "2009-10-27", facts: { is_digital_signature: true } });
  });

  it("shows a conditional risk and a conditional answer change once facts match a modelled rule", () => {
    render(<RagResult result={responses["it-s19-scenario"]} onExplain={() => {}} />);
    expect(within(card("Risk")).getByText("Conditional")).toBeTruthy();
    expect(within(card("Risk")).getByText("Medium")).toBeTruthy();
    expect(within(card("Risk")).getByText(/stipulated for demonstration/)).toBeTruthy();
    expect(within(card("Answer change")).getByText("Changes")).toBeTruthy();
    expect(screen.getByText(/Using your facts:/)).toBeTruthy();
  });
});

describe("partial and abstaining answers", () => {
  it("rejects a wrong amending Act without showing clause cards or a score", () => {
    render(<RagResult result={responses["wrong-act"]} onExplain={() => {}} />);
    expect(screen.getByText(/not recorded as amending/)).toBeTruthy();
    expect(screen.queryByText("Clause comparison")).toBeNull();
    expect(screen.queryByText("How this score was calculated")).toBeNull();
    expect(within(card("Textual drift")).getByText("Not enough evidence")).toBeTruthy();
  });

  it("answers a general question from the cited section without a before/after", () => {
    render(<RagResult result={responses.general} onExplain={() => {}} />);
    expect(screen.getByText(/Section 37 \(Reference to mediation\)/)).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Before" })).toBeNull();
    for (const title of ["Textual drift", "Materiality", "Answer change", "Risk"]) expect(within(card(title)).getByText("Not applicable")).toBeTruthy();
  });

  it("says an unknown Act is not in the corpus instead of answering from another document", () => {
    render(<RagResult result={responses["out-of-scope"]} onExplain={() => {}} />);
    expect(document.querySelector(".direct-answer").textContent).toMatch(/^The Shops and Commercial Establishments Act is not in the local corpus/);
    expect(screen.queryByRole("heading", { name: "Evidence" })).toBeNull();
  });
});

describe("keyboard and screen-reader basics", () => {
  it("reaches the determination details and the facts form by keyboard, with labelled controls", async () => {
    const user = userEvent.setup();
    render(<RagResult result={responses["it-s19"]} onExplain={() => {}} />);
    let guard = 0;
    while (document.activeElement?.textContent !== "Method and evidence" && guard++ < 80) await user.tab();
    expect(document.activeElement.tagName).toBe("SUMMARY");
    for (const control of screen.getByRole("form", { name: "Add your situation" }).querySelectorAll("select, input")) {
      expect(control.labels?.length).toBeGreaterThan(0);
    }
  });
});
