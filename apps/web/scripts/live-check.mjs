// Live-mode walkthrough: demo copy, pipeline edit, run, captures.
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const [, , base = "http://localhost:3000", prefix = "live"] = process.argv;

const chrome = spawn(CHROME, [
  "--headless=new",
  "--disable-gpu",
  "--no-first-run",
  "--hide-scrollbars",
  "--remote-debugging-port=9335",
  `--user-data-dir=C:/temp/cdp-live-${Date.now()}`,
  "--window-size=1440,900",
  "about:blank",
]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function socket() {
  for (let i = 0; i < 80; i += 1) {
    try {
      const res = await fetch("http://127.0.0.1:9335/json/version");
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
await sleep(4000);

const evaluate = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, sessionId);
  return r.exceptionDetails ? `ERR ${r.exceptionDetails.text}` : r.result.value;
};
const shot = async (name) => {
  const s = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }, sessionId);
  writeFileSync(`screenshots/${name}.png`, Buffer.from(s.data, "base64"));
  console.log("saved", name);
};
const clickText = (text) =>
  evaluate(`(() => {
    const el = [...document.querySelectorAll('button')].find((b) => (b.textContent || '').includes(${JSON.stringify(text)}));
    if (!el) return 'missing: ' + ${JSON.stringify(text)};
    el.click(); return 'clicked';
  })()`);

console.log("rail:", await evaluate(`JSON.stringify({
  lang: document.documentElement.lang,
  demoItems: [...document.querySelectorAll('aside button')].map((b) => b.textContent.replace(/\\s+/g,' ').trim()).slice(0, 8),
  countText: document.querySelector('aside')?.textContent.replace(/\\s+/g,' ').slice(0, 220),
})`));

// Load the course sample.
console.log("load demo:", await clickText("Endoscopie laryngée"));
await sleep(3500);
console.log("after demo:", await evaluate(`JSON.stringify({
  images: [...document.querySelectorAll('aside button')].map((b) => b.textContent.replace(/\\s+/g,' ').trim()).filter((t) => t.includes('endoscopie')),
  target: document.body.textContent.includes('Aucune image') ? 'empty' : 'ok',
  alert: document.querySelector('[role=alert]')?.textContent ?? null,
})`));

// Build the k-means chain: add k-means and largest component, drop Otsu.
console.log("select kmeans:", await evaluate(`(() => {
  const select = document.querySelector('#step-kind');
  if (!select) return 'no select';
  const option = [...select.options].find((o) => o.textContent.includes('k-means'));
  if (!option) return 'no option';
  select.value = option.value;
  select.dispatchEvent(new Event('change', { bubbles: true }));
  return option.value;
})()`));
await sleep(300);
console.log("add kmeans:", await evaluate(`(() => {
  const b = document.querySelector('button[title="Ajouter une étape"]');
  if (!b) return 'no add';
  b.click(); return 'added';
})()`));
await sleep(300);
console.log("add largest:", await evaluate(`(() => {
  const select = document.querySelector('#step-kind');
  const option = [...select.options].find((o) => o.textContent.includes('Plus grande'));
  select.value = option.value;
  select.dispatchEvent(new Event('change', { bubbles: true }));
  const b = document.querySelector('button[title="Ajouter une étape"]');
  b.click(); return 'added';
})()`));
await sleep(300);
console.log("remove median/otsu:", await evaluate(`(() => {
  const remove = (label) => {
    const row = [...document.querySelectorAll('ol > li')].find((li) => li.textContent.includes(label));
    if (!row) return 'no row ' + label;
    const b = [...row.querySelectorAll('button')].find((x) => (x.getAttribute('aria-label') || '').startsWith('Retirer'));
    if (!b) return 'no button ' + label;
    b.click();
    return 'removed ' + label;
  };
  const first = remove('Filtre médian');
  return first;
})()`));
await sleep(400);
console.log("remove otsu:", await evaluate(`(() => {
  const row = [...document.querySelectorAll('ol > li')].find((li) => li.textContent.includes("Otsu"));
  if (!row) return 'no row';
  const b = [...row.querySelectorAll('button')].find((x) => (x.getAttribute('aria-label') || '').startsWith('Retirer'));
  if (!b) return 'no button';
  b.click(); return 'removed';
})()`));
await sleep(400);
console.log("move kmeans up:", await evaluate(`(() => {
  const row = [...document.querySelectorAll('ol > li')].find((li) => li.querySelector('h3')?.textContent === 'k-means');
  if (!row) return 'no kmeans row';
  const b = [...row.querySelectorAll('button')].find((x) => (x.getAttribute('aria-label') || '') === 'Monter');
  if (!b) return 'no up';
  b.click(); return 'moved';
})()`));
await sleep(400);
await sleep(500);
console.log("pipeline now:", await evaluate(`JSON.stringify([...document.querySelectorAll('ol > li h3')].map((h) => h.textContent))`));

console.log("run:", await clickText("Lancer l'analyse"));
await sleep(12000);
console.log("result:", await evaluate(`JSON.stringify({
  alert: document.querySelector('[role=alert]')?.textContent ?? null,
  cards: document.querySelector('aside[aria-label="Inspecteur"]')?.textContent.replace(/\\s+/g,' ').slice(0, 400),
})`));
await shot(`${prefix}-loaded`);

console.log("measures:", await clickText("Mesures"));
await sleep(800);
console.log("table:", await evaluate(`JSON.stringify([...document.querySelectorAll('table.measure-table tr')].map((r) => r.textContent.replace(/\\s+/g,' ').trim()).slice(0, 8))`));
await shot(`${prefix}-measures`);

// Second analysis for the comparison shot: Otsu in one click via rail then measures stay.
console.log("run 2:", await clickText("Lancer l'analyse"));
await sleep(12000);
console.log("analyses:", await evaluate(`JSON.stringify([...document.querySelectorAll('aside button[aria-current], aside button')].map((b) => b.textContent.replace(/\\s+/g,' ').trim()).filter((t) => t.includes('Seuillage') || t.includes('k-means')))`));
await shot(`${prefix}-compare`);

browser.close();
chrome.kill();
