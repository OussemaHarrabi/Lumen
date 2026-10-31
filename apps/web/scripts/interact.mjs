// Interaction check through CDP: locale switch, tabs, layers, compare, run.
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const url = process.argv[2] ?? "http://localhost:3100/app";
const out = process.argv[3] ?? "screenshots/workspace-measures.png";

const chrome = spawn(CHROME, [
  "--headless=new",
  "--disable-gpu",
  "--no-first-run",
  "--hide-scrollbars",
  "--remote-debugging-port=9334",
  `--user-data-dir=C:/temp/cdp-i-${Date.now()}`,
  "--window-size=1440,900",
  "about:blank",
]);

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function devtoolsSocket() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch("http://127.0.0.1:9334/json/version");
      if (response.ok) return (await response.json()).webSocketDebuggerUrl;
    } catch {
      // not listening yet
    }
    await sleep(250);
  }
  throw new Error("devtools never came up");
}

const browser = new WebSocket(await devtoolsSocket());
await new Promise((resolve) => (browser.onopen = resolve));

let id = 0;
const pending = new Map();
browser.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
  }
};

function send(method, params = {}, sessionId) {
  id += 1;
  const message = { id, method, params };
  if (sessionId) message.sessionId = sessionId;
  browser.send(JSON.stringify(message));
  return new Promise((resolve, reject) => {
    pending.set(id, (reply) => (reply.error ? reject(new Error(JSON.stringify(reply.error))) : resolve(reply.result)));
  });
}

const { targetId } = await send("Target.createTarget", { url: "about:blank" });
const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false }, sessionId);
await send("Page.enable", {}, sessionId);
await send("Runtime.enable", {}, sessionId);
await send("Page.navigate", { url }, sessionId);
await sleep(2500);

async function evaluate(expression) {
  const reply = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, sessionId);
  if (reply.exceptionDetails) return { error: reply.exceptionDetails.text };
  return reply.result.value;
}

const click = (label) =>
  evaluate(`(() => {
    const buttons = [...document.querySelectorAll('button')];
    const target = buttons.find((b) => (b.getAttribute('aria-label') || b.textContent || '').trim().includes(${JSON.stringify(label)}));
    if (!target) return 'not found: ' + ${JSON.stringify(label)};
    target.click();
    return 'clicked';
  })()`);

console.log("before:", await evaluate(`JSON.stringify({ lang: document.documentElement.lang, title: document.title })`));
console.log("EN switch:", await click("EN"));
await sleep(1200);
console.log("after EN:", await evaluate(`JSON.stringify({ lang: document.documentElement.lang, h1: document.querySelector('h1')?.textContent, tab: document.querySelector('[role=tab][aria-selected=true]')?.textContent })`));

// Back to French.
console.log("FR switch:", await click("FR"));
await sleep(1200);

console.log("run:", await click("Lancer l'analyse"));
await sleep(3600);
console.log("measures tab:", await click("Mesures"));
await sleep(400);

const report = await evaluate(`(() => {
  const rows = [...document.querySelectorAll('table.measure-table tr')].map((row) => row.textContent.replace(/\\s+/g, ' ').trim());
  const status = document.querySelector('[role=progressbar]')?.getAttribute('aria-valuenow');
  const alert = document.querySelector('[role=alert]')?.textContent?.trim() ?? null;
  return JSON.stringify({ rows: rows.slice(0, 9), progress: status, alert, lang: document.documentElement.lang });
})()`);
console.log("report:", report);

const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }, sessionId);
writeFileSync(out, Buffer.from(shot.data, "base64"));
console.log("saved", out);
browser.close();
chrome.kill();
