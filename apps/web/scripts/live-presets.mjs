// Preset check: load course sample, apply watershed preset, run, capture.
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const base = process.argv[2] ?? "http://localhost:3100";
const prefix = process.argv[3] ?? "live";
const chrome = spawn(CHROME, [
  "--headless=new",
  "--disable-gpu",
  "--no-first-run",
  "--hide-scrollbars",
  "--remote-debugging-port=9336",
  `--user-data-dir=C:/temp/cdp-preset-${Date.now()}`,
  "--window-size=1440,900",
  "about:blank",
]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function socket() {
  for (let i = 0; i < 80; i += 1) {
    try {
      const res = await fetch("http://127.0.0.1:9336/json/version");
      if (res.ok) return (await res.json()).webSocketDebuggerUrl;
    } catch {}
    await sleep(250);
  }
  throw new Error("devtools down");
}

const browser = new WebSocket(await socket());
await new Promise((r) => (browser.onopen = r));
let id = 0;
const pending = new Map();
browser.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) {
    pending.get(m.id)(m);
    pending.delete(m.id);
  }
};
const send = (method, params = {}, sessionId) => {
  id += 1;
  const msg = { id, method, params };
  if (sessionId) msg.sessionId = sessionId;
  browser.send(JSON.stringify(msg));
  return new Promise((res, rej) =>
    pending.set(id, (r) => (r.error ? rej(new Error(JSON.stringify(r.error))) : res(r.result))),
  );
};

const { targetId } = await send("Target.createTarget", { url: "about:blank" });
const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false }, sessionId);
await send("Page.enable", {}, sessionId);
await send("Runtime.enable", {}, sessionId);
await send("Page.navigate", { url: `${base}/app` }, sessionId);
await sleep(3500);

const evaluate = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, sessionId);
  return r.exceptionDetails ? `ERR ${r.exceptionDetails.text}` : r.result.value;
};
const clickText = (text) =>
  evaluate(`(() => {
    const el = [...document.querySelectorAll('button')].find((b) => (b.textContent || '').includes(${JSON.stringify(text)}));
    if (!el) return 'missing: ' + ${JSON.stringify(text)};
    el.click(); return 'clicked';
  })()`);
const shot = async (name) => {
  const s = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }, sessionId);
  writeFileSync(`screenshots/${name}.png`, Buffer.from(s.data, "base64"));
  console.log("saved", name);
};

console.log("load:", await clickText("Endoscopie laryngée"));
await sleep(3000);
console.log("preset:", await clickText("Watershed sur le gradient"));
await sleep(500);
console.log("steps:", await evaluate(`JSON.stringify([...document.querySelectorAll('ol > li h3')].map((h) => h.textContent))`));
console.log("run:", await clickText("Lancer l'analyse"));
await sleep(14000);
console.log("measures tab:", await clickText("Mesures"));
await sleep(500);
console.log("dice:", await evaluate(`[...document.querySelectorAll('table.measure-table tr')].map((r) => r.textContent.replace(/\\s+/g,' ').trim()).slice(0, 6).join(' | ')`));
await shot(`${prefix}-watershed`);

// Second analysis on the same image with the k-means preset, for the comparison shot.
console.log("back to method:", await clickText("Méthode"));
await sleep(300);
console.log("preset2:", await clickText("k-means 3 classes"));
await sleep(300);
console.log("run2:", await clickText("Lancer l'analyse"));
await sleep(12000);
await clickText("Mesures");
await sleep(500);
console.log("analyses:", await evaluate(`JSON.stringify([...document.querySelectorAll('aside button')].map((b) => b.textContent.replace(/\\s+/g,' ').trim()).filter((t) => t.includes('k-means') || t.includes('Watershed')))`));
await shot(`${prefix}-compare`);

browser.close();
chrome.kill();
