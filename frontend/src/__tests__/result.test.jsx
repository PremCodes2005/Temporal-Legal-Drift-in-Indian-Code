// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RagResult } from "../App";
import ComparisonPanel from "../ComparisonPanel";
import SourceHealth from "../SourceHealth";

afterEach(cleanup);

const comparison = {
  support_class: "GRAPH_TRANSITION_FRAGMENTS", operation: "SUBSTITUTE", provision_path: "section:43A",
  changed_spans: [{ before: "five", after: "ten" }], abstention_reasons: [],
  before: { role: "before_fragment", act_name: "Information Technology Act, 2000", page: 3, compared_text: "a penalty of five lakh rupees", local_pdf_url: "/corpus/pdf/a.pdf#page=3", document_version: "sha256:aa" },
  after: { role: "after_fragment", act_name: "Information Technology (Amendment) Act, 2008", page: 7, compared_text: "a penalty of ten lakh rupees", local_pdf_url: "/corpus/pdf/b.pdf#page=7", span_basis: "derived_text_not_a_verbatim_source_span" },
};
const metrics = {
  metrics_contract_version: "drift-metrics-v3", semantic_drift_percent: 20, lexical_drift_percent: 30, conceptual_drift_percent: 40, overall_drift_percent: 31.6,
  conceptual_method: "deterministic_legal_cue_proxy", component_disagreement: false,
  score_basis: { pre_excerpt: "a penalty of five lakh rupees", post_excerpt: "a penalty of ten lakh rupees" },
  reliability: { pairing: "graph_aligned", evidence_coverage: "complete", temporal_certainty: { status: "UNRESOLVED" }, retrieval_relevance: 0.8 },
  question_relevance: { status: "ANSWERS_REQUESTED_PROVISION", explanation: "Section 43A was requested." },
  calculation_trace: {
    semantic: { formula: "100*(1-cos)", cosine_similarity_percent: 80 },
    lexical: { formula: "mean", jaccard_similarity_percent: 70, sequence_similarity_percent: 70 },
    conceptual: { pre_legal_cues: ["five"], post_legal_cues: ["ten"] },
    overall: { formula: "sqrt(0.4V²+0.3L²+0.3C²)", sum_of_weighted_squares: 1000, weighted_square_contributions: { semantic: 160, lexical: 270, conceptual: 480 } },
  },
};
const result = (over = {}) => ({
  intent: "comparison", mode: "local", comparison, metrics,
  answer: { answer_type: "comparison", generation_method: "llm_grounded", pre_amendment_baseline: "five", post_amendment_revision: "ten", key_differences: ["amount"] },
  retrieval: { pair_status: "graph_aligned_amendment_fragments" }, citations: [], verification: { passed: false, checks: [] }, source_guidance: { message: "Check India Code.", url: "https://www.indiacode.nic.in/", label: "India Code" },
  ...over,
});

describe("query-specific result", () => {
  it("shows clause citations, PDF page links and highlights for the compared clause", () => {
    render(<ComparisonPanel comparison={comparison} />);
    expect(screen.getAllByText(/section 43A/).length).toBe(2);
    expect(screen.getAllByText(/Operation: substitute/).length).toBe(2);
    expect(screen.getByRole("link", { name: /Open source PDF at page 3/ }).getAttribute("href")).toBe("/corpus/pdf/a.pdf#page=3");
    expect(screen.getByText("five").tagName).toBe("DEL");
    expect(screen.getByText("ten").tagName).toBe("INS");
    expect(screen.getByText(/Derived text — not a verbatim quote/)).toBeTruthy();
    expect(screen.getByText(/= inserted/)).toBeTruthy();
  });

  it("explains the score with its inputs, and keeps the four indicators separate", async () => {
    render(<RagResult result={result()} onExplain={() => {}} />);
    for (const label of ["Textual drift", "Materiality", "Answer change", "Risk"]) expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getAllByText("31.6%").length).toBeGreaterThan(0);
    expect(screen.getByText(/Legal-version status:/)).toBeTruthy();
    expect(screen.getByText(/Only amendment fragments are available/)).toBeTruthy();
    expect(screen.getByText(/sqrt\(0.4V²\+0.3L²\+0.3C²\) = √1000 = 31.6%/)).toBeTruthy();
  });

  it("reaches the score explanation by Tab and opens it", async () => {
    const user = userEvent.setup();
    render(<RagResult result={result()} onExplain={() => {}} />);
    const details = screen.getByText("How this score was calculated").closest("details");
    expect(details.open).toBe(false);
    let guard = 0;
    while (document.activeElement?.textContent !== "How this score was calculated" && guard++ < 50) await user.tab();
    expect(document.activeElement.tagName).toBe("SUMMARY");
    // shortcut: jsdom does not implement Enter-to-toggle on <summary> (browsers do natively); activate the focused element instead.
    await user.click(document.activeElement);
    expect(details.open).toBe(true);
  });

  it("gives no score and says so when no aligned pair exists", () => {
    const unpaired = { ...comparison, support_class: "UNALIGNED_EXCERPTS", operation: null, changed_spans: [], abstention_reasons: ["PAIR_UNALIGNED", "SCORING_UNAVAILABLE"] };
    render(<RagResult result={result({ comparison: unpaired, metrics: null, retrieval: { pair_status: "unaligned" } })} onExplain={() => {}} />);
    expect(screen.getByText("Excerpts only — no aligned versions")).toBeTruthy();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.queryByText("How this score was calculated")).toBeNull();
    expect(screen.getByText(/no change is asserted and no score is given/)).toBeTruthy();
    expect(screen.queryByText(/%$/)).toBeNull();
  });

  it("discloses the evidence-only fallback after a model timeout", () => {
    render(<RagResult result={result({ answer: { ...result().answer, generation_method: "extractive_fallback", generation_warning: "Model request timed out" } })} onExplain={() => {}} />);
    expect(screen.getByText(/not a language-model conclusion/)).toBeTruthy();
    expect(screen.getByText(/Model request timed out. The displayed response uses the evidence-only fallback./)).toBeTruthy();
  });
});

describe("source health", () => {
  it("reports a failed health request instead of a stale status", async () => {
    render(<SourceHealth request={() => Promise.reject(new Error("down"))} />);
    await waitFor(() => expect(screen.getByText("Scheduled source-monitoring status is unavailable.")).toBeTruthy());
  });

  it("lists both scheduled sources and the review backlog", async () => {
    const health = { review_queue_pending: 2, sources: [
      { source_key: "india_code", last_success_at: "2026-10-12T10:00:00Z", scheduled_ingestion_healthy: true },
      { source_key: "egazette", last_success_at: null, last_status: "SOURCE_UNAVAILABLE" } ] };
    render(<SourceHealth request={() => Promise.resolve(health)} />);
    await waitFor(() => expect(screen.getByText(/e-Gazette: not yet checked by the daily job \(last attempt: source unavailable\)/)).toBeTruthy());
    expect(screen.getByText(/2 new document\(s\) awaiting review/)).toBeTruthy();
  });
});

describe("mobile layout", () => {
  // jsdom has no layout engine; this checks the single-column rules that the 500px screenshot exercises.
  it("collapses side-by-side clauses and indicators to one column on narrow screens", () => {
    const css = readFileSync("src/styles.css", "utf8");
    expect(css).toMatch(/@media \(max-width:900px\)\{[^@]*\.compare-grid\{grid-template-columns:1fr\}/);
    expect(css).toMatch(/@media \(max-width:520px\)\{\.indicator-strip\{grid-template-columns:1fr\}/);
  });
});
