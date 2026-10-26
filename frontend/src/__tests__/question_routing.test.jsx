// @vitest-environment jsdom
// rag-answer-v6 routing in the assistant, against real backend responses (fixtures/rag_answer_v6_routing.json, generated offline by
// frontend/scripts/generate_routing_fixture.py): "Interpreted as", choosing an Act, an Act not in the corpus, and latest records.
import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import AssistantResult from "../AssistantResult";

const { responses } = JSON.parse(readFileSync("src/__tests__/fixtures/rag_answer_v6_routing.json", "utf8"));
const recorded = JSON.parse(readFileSync("src/__tests__/fixtures/methods_and_discoveries.json", "utf8"));
const ACTS = [{ entry_id: "companies-act-2013", name: "Companies Act 2013" }, { entry_id: "representation-of-the-people-act-1950", name: "Representation Of The People Act 1950" }];
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); window.sessionStorage.clear(); window.localStorage.clear(); });

const heading = () => document.getElementById("result-title").textContent;
const ragCalls = () => fetch.mock.calls.filter(([url]) => String(url).includes("/api/rag/query")).map(([, init]) => JSON.parse(init.body));

describe("routing in the answer", () => {
  it("names the Act the question was read as, and offers to answer from another Act", async () => {
    const onAct = vi.fn();
    const user = userEvent.setup();
    render(<AssistantResult analysis={responses.overview} acts={ACTS} onAct={onAct} />);
    const note = screen.getByText("Interpreted as").closest(".interpreted-as");
    expect(note.textContent).toContain("Motor Vehicles Act 1988");
    expect(screen.getByRole("article", { name: "Answer" }).textContent).toContain("An Act to consolidate and amend the law relating to motor vehicles.");
    expect(screen.queryByRole("article", { name: "The change, measured" })).toBeNull();  // an overview has no score

    await user.click(within(note).getByRole("button", { name: "Not this Act?" }));
    const submit = screen.getByRole("button", { name: "Use this Act" });
    expect(submit.disabled).toBe(true);
    await user.selectOptions(screen.getByLabelText("Answer the same question from"), "companies-act-2013");
    await user.click(submit);
    expect(onAct).toHaveBeenCalledWith("companies-act-2013");
  });

  it("asks which Act is meant when one name fits two Acts, and answers from none of them", async () => {
    const onAct = vi.fn();
    const user = userEvent.setup();
    render(<AssistantResult analysis={responses.ambiguous} onAct={onAct} />);
    expect(heading()).toBe("Choose an Act");
    expect(screen.queryByText("Interpreted as")).toBeNull();
    expect(screen.getByText(/No answer was generated from any Act/)).toBeTruthy();
    const choices = screen.getByRole("article", { name: "Which Act do you mean?" });
    expect(within(choices).getAllByRole("button").map((b) => b.textContent)).toEqual(["Representation Of The People Act 1950", "Representation Of The People Act 1951"]);
    await user.click(within(choices).getByRole("button", { name: "Representation Of The People Act 1951" }));
    expect(onAct).toHaveBeenCalledWith("representation-of-the-people-act-1951");
  });

  it("shows the Act the user chose as their choice", () => {
    render(<AssistantResult analysis={responses.chosen} />);
    expect(screen.getByText("Act you chose").closest(".interpreted-as").textContent).toContain("Representation Of The People Act 1951");
    expect(document.querySelector(".selection-note")).toBeNull();  // no section was chosen
  });

  it("reports an Act not in the corpus with what was checked, close matches and official searches", () => {
    render(<AssistantResult analysis={responses["not-found"]} />);
    expect(heading()).toBe("Act not found in the corpus");
    const answer = screen.getByRole("article", { name: "Answer" }).textContent;
    expect(answer).toContain("I could not find “Compnies Act”");
    expect(answer).toContain("This does not mean no such Act exists");
    expect(within(screen.getByRole("article", { name: "Did you mean one of these?" })).getByRole("button").textContent).toBe("Companies Act 2013");
    const links = within(screen.getByRole("article", { name: "Where to search" })).getAllByRole("link");
    expect(links.map((a) => a.textContent)).toEqual(["Search India Code ↗", "Search the e-Gazette ↗"]);
    expect(links.every((a) => a.getAttribute("rel") === "noreferrer" && a.getAttribute("target") === "_blank")).toBe(true);
  });

  it("compares two named Acts side by side without a change score", () => {
    render(<AssistantResult analysis={responses.comparison} />);
    expect(heading()).toBe("Comparison of Acts");
    expect(screen.getByText("Interpreted as").closest(".interpreted-as").textContent).toContain("Aadhaar Act 2016 and IT Act 2000");
    expect(screen.queryByRole("article", { name: "The change, measured" })).toBeNull();
  });

  it("offers the Acts an amending Act is recorded as amending when it was paired with another", () => {
    render(<AssistantResult analysis={responses.mismatch} />);
    expect(screen.getByRole("article", { name: "Answer" }).textContent).toContain("not recorded as amending");
    expect(within(screen.getByRole("article", { name: "Acts it is recorded as amending" })).getAllByRole("button").length).toBeGreaterThan(0);
  });

  it("lists the latest monitored records with their kind, dates, status and source checks", () => {
    for (const key of ["latest-india-code", "latest-egazette"]) {
      render(<AssistantResult analysis={responses[key]} />);
      const feed = responses[key].latest_records;
      expect(heading(), key).toBe("Latest records");
      const list = screen.getByRole("article", { name: /record|No records observed/ });
      expect(list.textContent).toContain("nothing fetched for this question");
      for (const source of feed.sources) expect(list.textContent).toContain(source.source);
      for (const item of feed.items) {
        expect(list.textContent, key).toContain(item.title);
        expect(list.textContent, key).toContain(item.record_kind_label);
      }
      expect(feed.items.every((item) => item.source_key === feed.sources_asked[0]), key).toBe(true);
      cleanup();
    }
  });

  it("explains the scope for a question outside the legal domain", () => {
    render(<AssistantResult analysis={responses.outside} />);
    expect(heading()).toBe("Outside this assistant's scope");
    expect(document.querySelector(".act-choices")).toBeNull();
  });
});

describe("choosing an Act from the assistant page", () => {
  it("re-asks the same question with the chosen Act, without adding it to recent questions again", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url, init) => {
      const sent = String(url).includes("/api/rag/query") ? JSON.parse(init.body) : null;
      const body = sent ? Object.values(responses).find((r) => r.query === sent.query && (r.selection?.act_entry_id || null) === (sent.act || null)
          && (r.routing.reason_code === "USER_SELECTED_ACT") === Boolean(sent.act))
        : String(url).includes("/api/corpus") ? { entries: [] } : String(url).includes("/api/sources/health") ? { sources: [] }
        : String(url).includes("/api/sources/notifications") ? recorded.notifications : { ready: true };
      return { ok: Boolean(body), status: body ? 200 : 404, json: async () => body || { error: "not found" } };
    }));
    window.history.replaceState(null, "", "#assistant");
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Legal research question"), responses.ambiguous.query);
    await user.click(screen.getByRole("button", { name: /Analyse/ }));
    await waitFor(() => expect(heading()).toBe("Choose an Act"));
    await user.click(screen.getByRole("button", { name: "Representation Of The People Act 1951" }));
    await waitFor(() => expect(screen.getByText("Act you chose")).toBeTruthy());
    expect(ragCalls()).toEqual([{ query: responses.ambiguous.query, mode: "specific" },
      { query: responses.ambiguous.query, mode: "specific", act: "representation-of-the-people-act-1951" }]);
    expect(JSON.parse(window.localStorage.getItem("tldrift:recent-questions"))).toHaveLength(1);  // a re-ask is not a new question
  });
});
