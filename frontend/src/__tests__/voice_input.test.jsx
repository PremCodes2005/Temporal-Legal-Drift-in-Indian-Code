// @vitest-environment jsdom
// Voice input in the question box: a fake browser speech recognizer and microphone stand in for the Web Speech API.
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { appendText } from "../VoiceInput";
const recorded = JSON.parse(readFileSync("src/__tests__/fixtures/methods_and_discoveries.json", "utf8"));

class FakeRecognition {
  static instances = [];
  static availability = "available";
  static available = vi.fn(async () => FakeRecognition.availability);
  constructor() {
    FakeRecognition.instances.push(this);
    this.start = vi.fn(() => this.onstart?.());
    this.stop = vi.fn();
    this.abort = vi.fn();
  }
}
FakeRecognition.prototype.processLocally = false;

const track = { stop: vi.fn() };
let getUserMedia;
const recognizer = () => FakeRecognition.instances.at(-1);
const field = () => screen.getByLabelText("Legal research question");
const status = () => document.getElementById("voice-status").textContent;
const ragCalls = () => fetch.mock.calls.filter(([url]) => String(url).includes("/api/rag/query"));
const hear = (words, isFinal = true) => act(() => recognizer().onresult({ resultIndex: 0, results: [Object.assign([{ transcript: words }], { isFinal })] }));

beforeEach(() => {
  FakeRecognition.instances = [];
  FakeRecognition.availability = "available";
  track.stop.mockClear();
  getUserMedia = vi.fn(async () => ({ getTracks: () => [track] }));
  Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true });
  vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
  vi.stubGlobal("fetch", vi.fn(async (url) => {
    const body = String(url).includes("/api/corpus") ? { entries: [] } : String(url).includes("/api/sources/health") ? { sources: [] }
      : String(url).includes("/api/sources/notifications") ? recorded.notifications : String(url).includes("/api/rag/query") ? null : { ready: true };
    return { ok: Boolean(body), status: body ? 200 : 404, json: async () => body || { error: "not found" } };
  }));
  window.history.replaceState(null, "", "#assistant");
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); window.sessionStorage.clear(); window.localStorage.clear(); });

async function startListening(user) {
  await user.click(screen.getByRole("button", { name: "Start voice input" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Stop voice input" })).toBeTruthy());
}

describe("voice input in the question box", () => {
  it("dictates into the field after typed text, never submits, and lets the user stop and edit", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.type(field(), "What changed in");
    await startListening(user);
    expect(getUserMedia).toHaveBeenCalledWith({ audio: true });
    expect(track.stop).toHaveBeenCalled();  // the permission stream is released at once, nothing is recorded
    expect(recognizer().lang).toBe("en-IN");
    expect(recognizer().processLocally).toBe(true);  // on-device recognition when the browser offers it
    expect(screen.getByRole("button", { name: "Stop voice input" }).getAttribute("aria-pressed")).toBe("true");
    expect(status()).toContain("Listening");

    hear("the IT Act", false);
    expect(screen.getByText("Hearing: the IT Act")).toBeTruthy();
    expect(field().value).toBe("What changed in");  // interim words are only previewed
    hear("the IT Act section 19");
    expect(field().value).toBe("What changed in the IT Act section 19");
    expect(ragCalls()).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Stop voice input" }));
    expect(recognizer().stop).toHaveBeenCalled();
    expect(status()).toContain("Processing");
    act(() => recognizer().onend());
    expect(status()).toContain("Review or edit the question, then press Analyse");
    expect(screen.getByRole("button", { name: "Start voice input" }).getAttribute("aria-pressed")).toBe("false");

    await user.type(field(), "?");
    expect(field().value).toBe("What changed in the IT Act section 19?");
    expect(ragCalls()).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: /Analyse/ }));
    await waitFor(() => expect(ragCalls()).toHaveLength(1));
    expect(JSON.parse(ragCalls()[0][1].body).query).toBe("What changed in the IT Act section 19?");
  });

  it("keeps typing available and explains when the browser has no speech recognition", async () => {
    vi.stubGlobal("webkitSpeechRecognition", undefined);
    const user = userEvent.setup();
    render(<App />);
    await user.type(field(), "Typed question");
    await user.click(screen.getByRole("button", { name: "Start voice input" }));
    expect(status()).toContain("not available in this browser");
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Start voice input" }).getAttribute("aria-disabled")).toBe("true");
    await user.type(field(), " still works");
    expect(field().value).toBe("Typed question still works");
  });

  it("reports a blocked microphone and starts no recognition", async () => {
    getUserMedia.mockRejectedValueOnce(Object.assign(new Error("denied"), { name: "NotAllowedError" }));
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Start voice input" }));
    await waitFor(() => expect(status()).toContain("Microphone access is blocked"));
    expect(FakeRecognition.instances).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Start voice input" })).toBeTruthy();
  });

  it("reports a missing microphone", async () => {
    getUserMedia.mockRejectedValueOnce(Object.assign(new Error("none"), { name: "NotFoundError" }));
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Start voice input" }));
    await waitFor(() => expect(status()).toContain("No microphone was found"));
  });

  it("maps recognition errors: blocked by the browser, no speech, service unreachable", async () => {
    const user = userEvent.setup();
    render(<App />);
    for (const [error, message] of [["not-allowed", "Microphone access is blocked"], ["no-speech", "No speech was detected"], ["network", "could not be reached"]]) {
      await startListening(user);
      act(() => { recognizer().onerror({ error }); recognizer().onend(); });
      expect(status(), error).toContain(message);
    }
    await startListening(user);
    act(() => recognizer().onend());
    expect(status()).toContain("No words were transcribed");
    expect(field().value).toBe("");
  });

  it("runs one session at a time", async () => {
    let release;
    getUserMedia.mockImplementationOnce(() => new Promise((resolve) => { release = resolve; }));
    const user = userEvent.setup();
    render(<App />);
    const button = screen.getByRole("button", { name: "Start voice input" });
    await user.click(button);
    expect(status()).toContain("Allow microphone access");
    await user.click(button);
    await user.click(button);
    await act(async () => release({ getTracks: () => [track] }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Stop voice input" })).toBeTruthy());
    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(FakeRecognition.instances).toHaveLength(1);
  });

  it("stops listening when the question is submitted and ignores words that arrive afterwards", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.type(field(), "What changed in the Aadhaar Act");
    await startListening(user);
    const live = recognizer();
    await user.click(screen.getByRole("button", { name: /Analyse/ }));
    expect(live.abort).toHaveBeenCalled();
    expect(live.onresult).toBeNull();
    await waitFor(() => expect(ragCalls()).toHaveLength(1));
    expect(field().value).toBe("What changed in the Aadhaar Act");
    expect(screen.getByRole("button", { name: "Start voice input" })).toBeTruthy();
  });

  it("aborts recognition when the question box is removed", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<App />);
    await startListening(user);
    const live = recognizer();
    unmount();
    expect(live.abort).toHaveBeenCalled();
    expect(live.onresult).toBeNull();
    expect(live.onend).toBeNull();
  });

  it("asks before using a speech service that may send audio off the device, and remembers the answer for the session", async () => {
    FakeRecognition.availability = "unavailable";
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Start voice input" }));
    await waitFor(() => expect(status()).toContain("may send your audio to the browser maker"));
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Continue with voice input" }));  // keyboard users land on the choice
    await user.click(screen.getByRole("button", { name: "Type instead" }));
    expect(FakeRecognition.instances).toHaveLength(0);
    expect(status()).toBe("");
    expect(document.activeElement).toBe(field());

    await user.click(screen.getByRole("button", { name: "Start voice input" }));
    await user.click(await screen.findByRole("button", { name: "Continue with voice input" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Stop voice input" })).toBeTruthy());
    expect(recognizer().processLocally).toBe(false);
    await user.click(screen.getByRole("button", { name: "Stop voice input" }));
    act(() => recognizer().onend());

    await user.click(screen.getByRole("button", { name: "Start voice input" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Stop voice input" })).toBeTruthy());
    expect(screen.queryByText(/may send your audio/)).toBeNull();
  });
});

describe("appendText", () => {
  it("adds dictated words after existing text with one space and respects the field limit", () => {
    expect(appendText("", " hello ")).toBe("hello");
    expect(appendText("What", "changed")).toBe("What changed");
    expect(appendText("What ", "changed")).toBe("What changed");
    expect(appendText("Keep", "   ")).toBe("Keep");
    expect(appendText("abc", "def", 5)).toBe("abc d");
  });
});
