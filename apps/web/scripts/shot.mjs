// Minimal CDP driver: launch Chrome headless, measure overflow, screenshot full page.
// Usage: node shot.mjs <url> <out.png> <width> <height> [fullPage]
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const [, , url, out, widthArg = "1440", heightArg = "900", mode = "viewport", locale = ""] =
  process.argv;
const width = Number(widthArg);
const height = Number(heightArg);

const chrome = spawn(CHROME, [
  "--headless=new",
  "--disable-gpu",
  "--no-first-run",
  "--hide-scrollbars",
  "--force-device-scale-factor=1",
  "--remote-debugging-port=9333",
  `--user-data-dir=C:/temp/cdp-${Date.now()}`,
  `--window-size=${width},${height}`,
  "about:blank",
]);

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForDevtools() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch("http://127.0.0.1:9333/json/version");
      if (response.ok) return (await response.json()).webSocketDebuggerUrl;
    } catch {
      // Chrome not listening yet.
    }
    await sleep(250);
  }
  throw new Error("devtools never came up");
}

const browserWs = await waitForDevtools();
const browser = new WebSocket(browserWs);
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

await send("Emulation.setDeviceMetricsOverride", {
  width,
  height,
  deviceScaleFactor: 1,
  mobile: width < 600,
}, sessionId);
await send("Page.enable", {}, sessionId);
await send("Runtime.enable", {}, sessionId);
await send("Network.enable", {}, sessionId);
if (locale) {
  await send(
    "Network.setCookie",
    { name: "lum_locale", value: locale, domain: "localhost", path: "/" },
    sessionId,
  );
}
await send("Page.navigate", { url }, sessionId);
await sleep(2500);

const metrics = await send("Runtime.evaluate", {
  expression: `(() => {
    const doc = document.documentElement;
    const offenders = [...document.querySelectorAll('*')]
      .filter((el) => el.getBoundingClientRect().right > doc.clientWidth + 1 && el.getBoundingClientRect().width > 0)
      .slice(0, 12)
      .map((el) => el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ').slice(0, 3).join('.') : '') + ' w=' + Math.round(el.getBoundingClientRect().width) + ' right=' + Math.round(el.getBoundingClientRect().right));
    return JSON.stringify({
      scrollWidth: doc.scrollWidth,
      clientWidth: doc.clientWidth,
      scrollHeight: doc.scrollHeight,
      offenders,
    }, null, 2);
  })()`,
  returnByValue: true,
}, sessionId);

console.log(metrics.result.value);

const docHeight = JSON.parse(metrics.result.value).scrollHeight;
const shot = await send(
  "Page.captureScreenshot",
  mode === "full"
    ? {
        format: "png",
        captureBeyondViewport: true,
        clip: { x: 0, y: 0, width, height: Math.min(docHeight, 20000), scale: 1 },
      }
    : { format: "png", captureBeyondViewport: false },
  sessionId,
);

writeFileSync(out, Buffer.from(shot.data, "base64"));
console.log("saved", out);
browser.close();
chrome.kill();
