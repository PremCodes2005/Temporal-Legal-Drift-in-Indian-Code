import { useCallback, useEffect, useRef, useState } from "react";

// Voice input for the question box. Speech is transcribed by the browser's own speech recognition (Web Speech API);
// this app never records, uploads or stores audio. When the browser cannot transcribe on the device, the user is told
// that its speech service may send audio to the browser maker, and must agree before listening starts.
export const LANGUAGE = "en-IN";
const CONSENT_KEY = "tld.dictation.consent";

const MESSAGES = {
  requesting: "Allow microphone access in your browser to dictate.",
  listening: "Listening… speak your question, then press Stop.",
  processing: "Processing your speech…",
  stopped: "Dictation stopped. Review or edit the question, then press Analyse.",
  empty: "Dictation stopped. No words were transcribed.",
  denied: "Microphone access is blocked. Allow it in your browser's site settings, or type your question.",
  "no-speech": "No speech was detected. Try again closer to the microphone, or type your question.",
  "no-microphone": "No microphone was found. Type your question instead.",
  network: "The browser's speech service could not be reached. Type your question instead.",
  error: "Voice input stopped because of an error. Type your question instead.",
  insecure: "Voice input needs a secure (https) connection. Type your question instead.",
  unsupported: "Voice input is not available in this browser. Type your question, or use a current Chrome, Edge or Safari.",
};

export function recognitionConstructor(scope = globalThis) {
  return scope.SpeechRecognition || scope.webkitSpeechRecognition || null;
}

// Dictated words go after whatever is already in the box; typed text is never replaced.
export function appendText(current, addition, limit = 4000) {
  const words = addition.trim();
  if (!words) return current;
  const joined = !current ? words : /\s$/.test(current) ? current + words : `${current} ${words}`;
  return joined.slice(0, limit);
}

const recognitionErrors = { "not-allowed": "denied", "service-not-allowed": "denied", "no-speech": "no-speech", "audio-capture": "no-microphone", network: "network" };
const permissionErrors = { NotAllowedError: "denied", SecurityError: "denied", NotFoundError: "no-microphone", NotReadableError: "no-microphone" };

function readConsent() { try { return window.sessionStorage.getItem(CONSENT_KEY) === "yes"; } catch { return false; } }
function saveConsent() { try { window.sessionStorage.setItem(CONSENT_KEY, "yes"); } catch { /* consent is then asked again next time */ } }

async function onDeviceAvailable(Recognition) {
  if (typeof Recognition.available !== "function" || !("processLocally" in Recognition.prototype)) return false;
  try { return (await Recognition.available({ langs: [LANGUAGE], processLocally: true })) === "available"; } catch { return false; }
}

// States: idle, consent, requesting, listening, processing, stopped, empty, denied, no-speech, no-microphone,
// network, error, insecure, unsupported. Only one recognition session exists at a time.
export function useDictation(onText) {
  const [state, setState] = useState("idle");
  const [interim, setInterim] = useState("");
  const session = useRef(null);  // { recognition, heard, cancelled } for the live session
  const deliver = useRef(onText);
  deliver.current = onText;

  const end = useCallback((current, next) => {
    if (session.current !== current) return;
    session.current = null;
    setInterim("");
    setState(next);
  }, []);

  const listen = useCallback(async () => {
    if (session.current) return;  // one session at a time
    const Recognition = recognitionConstructor();
    const current = { recognition: null, heard: false, cancelled: false, failure: null };
    session.current = current;
    setState("requesting");
    try {
      // Ask for the microphone explicitly, then release it at once: the stream is never recorded or kept.
      const stream = await navigator.mediaDevices?.getUserMedia?.({ audio: true });
      stream?.getTracks().forEach((track) => track.stop());
    } catch (error) {
      return end(current, permissionErrors[error?.name] || "error");
    }
    const local = await onDeviceAvailable(Recognition);
    if (current.cancelled || session.current !== current) return;
    const recognition = new Recognition();
    current.recognition = recognition;
    recognition.lang = LANGUAGE;
    recognition.continuous = true;
    recognition.interimResults = true;
    if (local) recognition.processLocally = true;
    recognition.onstart = () => { if (session.current === current) setState("listening"); };
    recognition.onresult = (event) => {
      if (session.current !== current) return;
      let pending = "";
      for (let index = event.resultIndex; index < event.results.length; index++) {
        const result = event.results[index];
        const words = result[0]?.transcript || "";
        if (result.isFinal) { if (words.trim()) { current.heard = true; deliver.current(words); } }
        else pending += words;
      }
      setInterim(pending.trim());
    };
    recognition.onerror = (event) => {
      if (event.error === "aborted") return;
      current.failure = recognitionErrors[event.error] || "error";
    };
    recognition.onend = () => end(current, current.failure || (current.heard ? "stopped" : "empty"));
    try { recognition.start(); } catch { end(current, "error"); }
  }, [end]);

  const start = useCallback(() => {
    if (session.current) return;  // one session at a time
    if (!recognitionConstructor()) return setState("unsupported");
    if (window.isSecureContext === false) return setState("insecure");
    if (readConsent()) return listen();
    // Cloud transcription must be agreed to first; on-device recognition needs no notice.
    const Recognition = recognitionConstructor();
    const marker = { cancelled: false };
    session.current = marker;
    setState("requesting");
    onDeviceAvailable(Recognition).then((local) => {
      if (session.current !== marker) return;
      session.current = null;
      if (local) listen(); else setState("consent");
    });
  }, [listen]);

  const accept = useCallback(() => { if (session.current) return; saveConsent(); listen(); }, [listen]);
  const decline = useCallback(() => setState("idle"), []);

  // Stop: keep what was heard; the browser delivers the last words, then ends.
  const stop = useCallback(() => {
    const current = session.current;
    if (!current) return;
    if (!current.recognition) { current.cancelled = true; return end(current, "idle"); }
    setState("processing");
    current.recognition.stop();
  }, [end]);

  // Cancel (question submitted, page left): discard anything not yet delivered.
  const cancel = useCallback(() => {
    const current = session.current;
    if (!current) return;
    current.cancelled = true;
    session.current = null;
    const recognition = current.recognition;
    if (recognition) { recognition.onresult = recognition.onerror = recognition.onend = recognition.onstart = null; recognition.abort(); }
    setInterim("");
    setState("idle");
  }, []);

  useEffect(() => () => {
    const current = session.current;
    session.current = null;
    const recognition = current?.recognition;
    if (recognition) { recognition.onresult = recognition.onerror = recognition.onend = recognition.onstart = null; recognition.abort(); }
  }, []);

  return { state, interim, start, stop, cancel, accept, decline, active: ["requesting", "listening", "processing"].includes(state) };
}

function MicrophoneIcon() {
  return <svg aria-hidden="true" focusable="false" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0" /><path d="M12 18v3" /></svg>;
}

export function DictationButton({ dictation, disabled = false }) {
  const { state, start, stop } = dictation;
  const listening = state === "listening" || state === "processing";
  const unavailable = state === "unsupported" || state === "insecure";
  return (
    <button type="button" className={`voice-button${listening ? " listening" : ""}`} aria-pressed={listening}
      aria-label={listening ? "Stop voice input" : "Start voice input"} aria-describedby="voice-status"
      aria-disabled={disabled || unavailable || state === "requesting" || state === "processing" ? "true" : undefined}
      onClick={() => { if (disabled || state === "processing" || state === "requesting") return; if (listening) stop(); else start(); }}>
      <MicrophoneIcon /><span>{listening ? "Stop" : "Dictate"}</span>
    </button>);
}

export function DictationStatus({ dictation, onTypeInstead = () => {} }) {
  const { state, interim, accept, decline, active } = dictation;
  const proceed = useRef(null);
  useEffect(() => { if (state === "consent") proceed.current?.focus(); }, [state]);  // the notice sits before the button in tab order
  return <>
    <div className="voice-status" id="voice-status" role="status" aria-live="polite">
      {state === "consent"
        ? <div className="voice-consent">
            <p>Your browser cannot transcribe speech on this device. Its speech service may send your audio to the browser maker (for example Google in Chrome) to be transcribed. This app does not record or store audio.</p>
            <div><button type="button" ref={proceed} className="secondary-button" onClick={accept}>Continue with voice input</button>
              <button type="button" className="link-button" onClick={() => { decline(); onTypeInstead(); }}>Type instead</button></div>
          </div>
        : MESSAGES[state] && <span className={`voice-message ${state}`}>{MESSAGES[state]}</span>}
    </div>
    {active && interim && <p className="voice-interim" aria-hidden="true">Hearing: {interim}</p>}
  </>;
}
