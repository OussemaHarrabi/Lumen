// Registration walkthrough: load FIRE pair, run homography, capture checkerboard.
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const [, , base = "http://localhost:3000", prefix = "recalage"] = process.argv;

const chrome = spawn(CHROME, [
  "--headless=new",
  "--disable-gpu",
  "--no-first-run",
  "--hide-scrollbars",
  "--remote-debugging-port=9337",
  `--user-data-dir=C:/temp/cdp-reg-${Date.now()}`,
  "--window-size=1440,900",
  "about:blank",
]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function socket() {
  for (let i = 0; i < 80; i += 1) {
    try {
      const res = await fetch("http://127.0.0.1:9337/json/version");
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
await send("Page.navigate", { url: `${base}/recalage` }, sessionId);
await sleep(3000);

const evaluate = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, sessionId);
  return r.exceptionDetails ? `ERR ${r.exceptionDetails.text}` : r.result.value;
};
const clickText = (text) =>
  evaluate(`(() => {
    const el = [...document.querySelectorAll('button, a')].find((b) => (b.textContent || '').includes(${JSON.stringify(text)}));
    if (!el) return 'missing: ' + ${JSON.stringify(text)};
    el.click(); return 'clicked';
  })()`);
const shot = async (name) => {
  const s = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }, sessionId);
  writeFileSync(`screenshots/${name}.png`, Buffer.from(s.data, "base64"));
  console.log("saved", name);
};

console.log("load pair:", await clickText("Charger la paire FIRE"));
await sleep(5000);
console.log("pair:", await evaluate(`JSON.stringify([...document.querySelectorAll('select')].map((s) => s.value))`));
await shot(`${prefix}-pair`);
console.log("run:", await clickText("Recaler"));
await sleep(30000);
console.log("metrics:", await evaluate(`JSON.stringify([...document.querySelectorAll('table.measure-table tr')].map((r) => r.textContent.replace(/\\s+/g,' ').trim()))`));
console.log("alert:", await evaluate(`document.querySelector('[role=alert]')?.textContent ?? null`));
await shot(`${prefix}-overlay`);
console.log("checkerboard:", await clickText("Damier"));
await sleep(800);
await shot(`${prefix}-checkerboard`);

browser.close();
chrome.kill();
