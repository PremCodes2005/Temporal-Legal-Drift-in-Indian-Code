// Real-browser checks over the Chrome DevTools protocol: keyboard flow, accessibility tree, narrow viewports.
// Usage: start `tldrift serve-dashboard --port 8799` and Chrome with `--headless=new --remote-debugging-port=9333`,
// then `node frontend/scripts/browser-a11y-check.mjs <output-dir>`. Exits 1 when a check fails.
// The accessibility tree is what screen readers consume; this is not a substitute for listening with one.
import { writeFileSync } from "node:fs";
const OUT = process.argv[2];
const BASE = process.env.TLD_URL || "http://127.0.0.1:8799";
const URL_ = BASE + "/#assistant?q=" + encodeURIComponent("Compare Section 19 before and after the IT Amendment Act, 2008.");
const target = await (await fetch((process.env.CDP_URL || "http://127.0.0.1:9333") + "/json/new?about:blank", { method: "PUT" })).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0; const pending = new Map();
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise((resolve, reject) => { const n = ++id; pending.set(n, (m) => m.error ? reject(new Error(method + ": " + m.error.message)) : resolve(m.result)); ws.send(JSON.stringify({ id: n, method, params })); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const evaluate = async (expression) => (await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result.value;
const key = async (k, code, keyCode) => { const text = k === "Enter" ? "\r" : k === " " ? " " : undefined; await send("Input.dispatchKeyEvent", { type: text ? "keyDown" : "rawKeyDown", key: k, code, text, windowsVirtualKeyCode: keyCode, nativeVirtualKeyCode: keyCode }); await send("Input.dispatchKeyEvent", { type: "keyUp", key: k, code, windowsVirtualKeyCode: keyCode, nativeVirtualKeyCode: keyCode }); };
const shot = async (name) => writeFileSync(`${OUT}/${name}.png`, Buffer.from((await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true })).data, "base64"));

await send("Page.enable"); await send("Runtime.enable"); await send("Accessibility.enable");
const report = {};
async function load(width, height = 900, mobile = false) {
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
  await send("Page.navigate", { url: URL_ });
  for (let i = 0; i < 120; i++) { await sleep(500); if (await evaluate("!!document.querySelector('[role=tablist]')")) break; }
  await sleep(500);
}

// 1. Keyboard flow at desktop width.
await load(1280);
const focusInfo = `(() => { const el = document.activeElement; if (!el || el === document.body) return null; const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
  return { tag: el.tagName, text: (el.getAttribute('aria-label') || el.innerText || el.value || el.getAttribute('href') || '').trim().slice(0, 60),
    visibleFocus: cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0 || cs.boxShadow !== 'none', size: [Math.round(r.width), Math.round(r.height)], inViewport: r.bottom > 0 && r.top < innerHeight }; })()`;
const stops = [];
// Tab to the analysis views, arrow to Scores & Method (ARIA tabs), then Tab into its panel to the wording explanation.
// Native date inputs style their inner focus a tick after the key event, so each stop settles briefly.
for (let i = 0; i < 120; i++) { await key("Tab", "Tab", 9); await sleep(150); const f = await evaluate(focusInfo); if (!f) continue; stops.push(f); if (await evaluate("document.activeElement.getAttribute('role') === 'tab'")) break; }
await key("ArrowRight", "ArrowRight", 39); await key("ArrowRight", "ArrowRight", 39); await sleep(300);
report.arrowsReachScores = await evaluate("document.activeElement.id === 'tab-scores' && document.activeElement.getAttribute('aria-selected') === 'true'");
for (let i = 0; i < 60; i++) { await key("Tab", "Tab", 9); await sleep(150); const f = await evaluate(focusInfo); if (!f) continue; stops.push(f); if (f.text.startsWith("How wording drift was calculated")) break; }
report.tabStops = stops.length; report.noVisibleFocus = stops.filter((s) => !s.visibleFocus); report.zeroSize = stops.filter((s) => !s.size[0] || !s.size[1]);
report.reachedSummary = stops.at(-1)?.text?.startsWith("How wording drift was calculated") || false;
report.pdfLinkReachable = stops.some((s) => s.text.startsWith("Open source PDF at page"));
report.focusScrolledIntoView = stops.every((s) => s.inViewport);
if (report.reachedSummary) { const was = await evaluate("document.querySelector('.fp-details').open"); await key("Enter", "Enter", 13); await sleep(200); report.enterTogglesDetails = (await evaluate("document.querySelector('.fp-details').open")) !== was; await key(" ", "Space", 32); await sleep(200); report.spaceTogglesBack = (await evaluate("document.querySelector('.fp-details').open")) === was; }
report.offscreen = stops.filter((s) => !s.inViewport).map((s) => `${s.tag}:${s.text}`);
report.stopsSample = stops.slice(0, 40).map((s) => `${s.tag}:${s.text}`);

// 2. Accessibility tree as exposed to assistive technology (Compare & Evidence view, where the before/after text lives).
await evaluate("document.getElementById('tab-evidence').click(), true"); await sleep(400);
const { nodes } = await send("Accessibility.getFullAXTree");
const named = (n) => (n.name?.value || "").trim();
const interactive = new Set(["button", "link", "textbox", "combobox", "checkbox", "radio", "tab", "menuitem", "DisclosureTriangle", "switch"]);
report.unnamedInteractive = nodes.filter((n) => !n.ignored && interactive.has(n.role?.value) && !named(n)).map((n) => n.role.value);
report.headings = nodes.filter((n) => !n.ignored && n.role?.value === "heading").map((n) => `${n.properties?.find((p) => p.name === "level")?.value?.value}:${named(n).slice(0, 50)}`);
report.roles = [...new Set(nodes.filter((n) => !n.ignored).map((n) => n.role?.value))].sort();
report.insDelNodes = nodes.filter((n) => !n.ignored && ["deletion", "insertion"].includes(n.role?.value)).map((n) => `${n.role.value}:${named(n)}`).slice(0, 6);
report.statusRegions = nodes.filter((n) => !n.ignored && ["status", "alert", "note"].includes(n.role?.value)).map((n) => n.role.value);
report.lang = await evaluate("document.documentElement.lang");
report.title = await evaluate("document.title");
report.imagesWithoutAlt = await evaluate("[...document.images].filter(i => !i.hasAttribute('alt')).length");
await shot("desk-1280");

// 3. Narrow viewports.
report.narrow = {};
for (const w of [320, 360, 414, 480]) {
  await load(w, 800, true);
  for (const view of ["answer", "scores"]) {
  await evaluate(`document.getElementById('tab-${view}').click(), true`); await sleep(300);
  report.narrow[`${w}-${view}`] = await evaluate(`(() => { const W = document.documentElement.clientWidth; const over = [...document.querySelectorAll('body *')].filter(el => { const r = el.getBoundingClientRect(); return r.width && r.right > W + 1 && getComputedStyle(el).position !== 'fixed'; });
    const leaf = over.filter(el => !over.some(o => o !== el && el.contains(o)));
    return { scrollWidth: document.documentElement.scrollWidth, clientWidth: W, overflowing: leaf.slice(0, 8).map(el => el.tagName + '.' + (el.className || '').toString().split(' ')[0] + ':' + Math.round(el.getBoundingClientRect().right)),
      tinyText: [...document.querySelectorAll('body *')].filter(el => el.childNodes.length && [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(el).fontSize) < 10).length,
      smallTargets: [...document.querySelectorAll('a,button,summary')].filter(el => { const r = el.getBoundingClientRect(); return r.width && r.height < 24; }).length }; })()`);
  await shot(`w${w}-${view}`);
  }
}
writeFileSync(`${OUT}/report.json`, JSON.stringify(report, null, 1));
await fetch(`${process.env.CDP_URL || "http://127.0.0.1:9333"}/json/close/${target.id}`); ws.close();
console.log(JSON.stringify(report, null, 1));
const text = nodes.filter((n) => n.role?.value === "StaticText").map((n) => n.name?.value || "").join("");
const failures = [
  report.noVisibleFocus.length && "focus without a visible indicator", report.unnamedInteractive.length && "unnamed controls",
  !report.reachedSummary && "score explanation not reachable by Tab", !report.arrowsReachScores && "arrow keys do not move between analysis views", !report.enterTogglesDetails && "Enter does not toggle the score explanation",
  !text.includes("[removed:") && "no screen-reader cue for removed words",
  ...Object.entries(report.narrow).map(([w, v]) => v.scrollWidth > v.clientWidth && `horizontal scroll at ${w}px`),
].filter(Boolean);
if (failures.length) { console.error("FAILED:", failures.join("; ")); process.exit(1); }
