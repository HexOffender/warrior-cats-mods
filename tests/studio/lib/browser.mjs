// A headless Chromium driven over the DevTools protocol with nothing but Node: for the studio's end-to-end
// tests (e2e/). The browser is found (WC_BROWSER, Edge, Chrome, or chromium on the PATH), started headless
// on a port of its own with a fresh profile, and spoken to over Node's own WebSocket.
//
//   const browser = await launch();          // throws when no browser is found: findBrowser() first to skip
//   const page = await browser.page();
//   await page.goto(url);
//   await page.waitFor("#nav button");
//   await page.click({ text: "New mod…" });
//   await page.type('input[aria-label="New mod folder name"]', "my-mod");
//   await browser.close();
import { spawn, execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const sleep = ms => new Promise(r => setTimeout(r, ms));

// The browser to use: WC_BROWSER names one (an exe's path); else Edge, then Chrome, where they're installed;
// on Linux and macOS, what the PATH or the Applications folder has. null when there's none.
export function findBrowser() {
  const env = process.env.WC_BROWSER;
  if (env) return fs.existsSync(env) ? env : null;
  const programs = ["C:/Program Files (x86)", "C:/Program Files", process.env.LOCALAPPDATA].filter(Boolean);
  const candidates = process.platform === "win32"
    ? programs.flatMap(p => [`${p}/Microsoft/Edge/Application/msedge.exe`, `${p}/Google/Chrome/Application/chrome.exe`,
      `${p}/Chromium/Application/chrome.exe`])
    : process.platform === "darwin"
      ? ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium"]
      : [];
  for (const c of candidates) if (fs.existsSync(c)) return c;
  if (process.platform !== "win32") {
    for (const name of ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "microsoft-edge"]) {
      try {
        const found = execFileSync("which", [name], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
        if (found) return found;
      } catch (e) { /* not that one */ }
    }
  }
  return null;
}

// One connection to the browser: commands with ids, and events to whoever listens.
class Connection {
  constructor(ws) {
    this.ws = ws;
    this.next = 1;
    this.waiting = new Map();
    this.listeners = [];
    ws.onmessage = e => this.receive(JSON.parse(e.data));
    ws.onclose = () => { for (const w of this.waiting.values()) w.bad(new Error("the browser went away")); this.waiting.clear(); };
  }
  send(method, params = {}, sessionId = undefined) {
    return new Promise((ok, bad) => {
      const id = this.next++;
      this.waiting.set(id, { ok, bad, method });
      this.ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  }
  receive(msg) {
    if (msg.id) {
      const w = this.waiting.get(msg.id);
      this.waiting.delete(msg.id);
      if (!w) return;
      if (msg.error) w.bad(new Error(`${w.method}: ${msg.error.message}`));
      else w.ok(msg.result);
    } else {
      for (const fn of this.listeners) fn(msg);
    }
  }
  on(fn) { this.listeners.push(fn); return () => { this.listeners = this.listeners.filter(f => f !== fn); }; }
}

export class Browser {
  constructor(proc, connection, dir) {
    this.proc = proc;
    this.c = connection;
    this.dir = dir;
    this.pages = [];
  }
  // A new tab, attached (flat sessions), with its own console record.
  async page() {
    const { targetId } = await this.c.send("Target.createTarget", { url: "about:blank" });
    const { sessionId } = await this.c.send("Target.attachToTarget", { targetId, flatten: true });
    const page = new Page(this, sessionId, targetId);
    await page.init();
    this.pages.push(page);
    return page;
  }
  // Close the browser (over the protocol: the process started here may be only Edge's launcher) and
  // remove its profile once it lets go of the files.
  async close() {
    try { await Promise.race([this.c.send("Browser.close"), sleep(3000)]); } catch (e) { /* it may be gone already */ }
    try { this.c.ws.close(); } catch (e) { /* closed by the browser */ }
    const gone = new Promise(r => { if (this.proc.exitCode !== null) r(); else this.proc.once("exit", r); });
    await Promise.race([gone, sleep(5000).then(() => { try { this.proc.kill(); } catch (e) { /* gone */ } })]);
    for (let i = 0; i < 20; i++) {
      await sleep(250);
      try { fs.rmSync(this.dir, { recursive: true, force: true }); break; } catch (e) { /* still being let go */ }
    }
  }
}

// What a test asks for on the page: a CSS selector, or {text, tag?} for the element whose text (trimmed) is
// that, among `tag`s (buttons unless said). Evaluated in the page.
function locator(target) {
  const t = typeof target === "string" ? { selector: target } : target;
  return `(() => {
    const t = ${JSON.stringify(t)};
    if (t.selector) return document.querySelector(t.selector);
    return [...document.querySelectorAll(t.tag || "button")].find(n => n.textContent.trim() === t.text) || null;
  })()`;
}

export class Page {
  constructor(browser, sessionId, targetId) {
    this.browser = browser;
    this.c = browser.c;
    this.sessionId = sessionId;
    this.targetId = targetId;
    this.errors = [];
    this.loads = [];
  }
  send(method, params) { return this.c.send(method, params, this.sessionId); }
  async init() {
    this.off = this.c.on(msg => {
      if (msg.sessionId !== this.sessionId) return;
      if (msg.method === "Runtime.consoleAPICalled" && ["error", "assert"].includes(msg.params.type)) {
        this.errors.push(msg.params.args.map(a => a.description || String(a.value)).join(" "));
      } else if (msg.method === "Runtime.exceptionThrown") {
        const d = msg.params.exceptionDetails;
        this.errors.push(d.exception && d.exception.description || d.text);
      } else if (msg.method === "Page.loadEventFired" || msg.method === "Page.navigatedWithinDocument") {
        // A URL that differs only by its #fragment doesn't load again: the page gets a hashchange instead.
        for (const r of this.loads.splice(0)) r();
      }
    });
    await this.send("Page.enable");
    await this.send("Runtime.enable");
    await this.send("DOM.enable");
  }
  // Load a URL and wait for its load event (10 s); a change of #fragment alone waits for the hashchange.
  async goto(url) {
    const loaded = this.nextLoad(`${url} didn't load in 10 s`);
    const r = await this.send("Page.navigate", { url });
    if (r.errorText) throw new Error(`${url}: ${r.errorText}`);
    await loaded;
  }
  // Load the page again, as F5 would.
  async reload() {
    const loaded = this.nextLoad("the page didn't load again in 10 s");
    await this.send("Page.reload");
    await loaded;
  }
  nextLoad(why) {
    return new Promise((ok, bad) => { this.loads.push(ok); setTimeout(() => bad(new Error(why)), 10000); });
  }
  // The value of an expression (or a function, called) in the page; a promise is awaited.
  async evaluate(expr) {
    const expression = typeof expr === "function" ? `(${expr.toString()})()` : expr;
    const r = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) {
      const d = r.exceptionDetails;
      throw new Error(d.exception && d.exception.description || d.text);
    }
    return r.result.value;
  }
  // Wait until a selector (a string) matches, or a predicate (a function, run in the page) gives something true.
  async waitFor(what, timeout = 10000) {
    const expr = typeof what === "string" ? `!!document.querySelector(${JSON.stringify(what)})` : `(${what.toString()})()`;
    const end = Date.now() + timeout;
    for (;;) {
      let value = null;
      try { value = await this.evaluate(expr); } catch (e) { /* the page may be mid-load */ }
      if (value) return value;
      if (Date.now() > end) throw new Error(`waited ${timeout} ms for ${typeof what === "function" ? what.toString() : what}`);
      await sleep(50);
    }
  }
  async text(target) {
    return this.evaluate(`(n => n ? n.textContent : null)(${locator(target)})`);
  }
  async count(selector) {
    return this.evaluate(`document.querySelectorAll(${JSON.stringify(selector)}).length`);
  }
  // Where an element is, scrolled into view: {x, y} of its middle in the viewport.
  async middle(target) {
    const box = await this.evaluate(`(n => { if (!n) return null; n.scrollIntoView({ block: "center" }); const r = n.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height }; })(${locator(target)})`);
    if (!box) throw new Error(`nothing on the page matches ${JSON.stringify(target)}`);
    if (!box.w || !box.h) throw new Error(`${JSON.stringify(target)} has no size (hidden?)`);
    return box;
  }
  // A real click: the mouse moves there, presses and releases.
  async click(target) {
    const { x, y } = await this.middle(target);
    await this.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
    await this.send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
    await this.send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  }
  // Type into a field: it's focused, then the text is inserted as typing would (input events and all).
  async type(target, text) {
    const ok = await this.evaluate(`(n => { if (!n) return false; n.focus(); return document.activeElement === n; })(${locator(target)})`);
    if (!ok) throw new Error(`couldn't focus ${JSON.stringify(target)}`);
    await this.send("Input.insertText", { text });
  }
  // A key pressed and let go: a letter, or Enter, Escape or Tab (which moves focus as a person's Tab would).
  async press(key) {
    const text = key.length === 1 ? key : undefined;
    const code = { Enter: 13, Escape: 27, Tab: 9 }[key] || 0;
    const named = key === "Tab" ? { code: "Tab" } : {};
    await this.send("Input.dispatchKeyEvent", { type: "keyDown", key, text, windowsVirtualKeyCode: code, ...named });
    await this.send("Input.dispatchKeyEvent", { type: "keyUp", key, windowsVirtualKeyCode: code, ...named });
  }
  // Give a file input files from disk, as choosing them would.
  async setFiles(selector, paths) {
    const { root } = await this.send("DOM.getDocument", { depth: 0 });
    const { nodeId } = await this.send("DOM.querySelector", { nodeId: root.nodeId, selector });
    if (!nodeId) throw new Error(`no ${selector} on the page`);
    await this.send("DOM.setFileInputFiles", { nodeId, files: paths.map(p => path.resolve(p)) });
  }
  // console.error calls and uncaught exceptions so far.
  consoleErrors() { return [...this.errors]; }
  async screenshot(file) {
    const { data } = await this.send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(file, Buffer.from(data, "base64"));
    return file;
  }
  async close() {
    this.off && this.off();
    try { await this.c.send("Target.closeTarget", { targetId: this.targetId }); } catch (e) { /* gone with the browser */ }
    this.browser.pages = this.browser.pages.filter(p => p !== this);
  }
}

// Start the browser headless with a profile of its own and connect to it.
export async function launch({ browser = findBrowser(), headless = true } = {}) {
  if (!browser) throw new Error("no browser: set WC_BROWSER to a Chromium's exe (Edge, Chrome or Chromium)");
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wc-browser-"));
  const args = [headless ? "--headless=new" : null, "--remote-debugging-port=0", `--user-data-dir=${dir}`, "--no-first-run",
    "--no-default-browser-check", "--disable-gpu", "--disable-extensions", "--disable-background-networking",
    "--disable-sync", "--disable-features=Translate,OptimizationHints", "--window-size=1280,900", "about:blank"].filter(Boolean);
  const proc = spawn(browser, args, { stdio: ["ignore", "ignore", "pipe"] });
  let stderr = "";
  proc.stderr.on("data", d => { stderr += d; });
  const portFile = path.join(dir, "DevToolsActivePort");
  const end = Date.now() + 30000;
  let port = null;
  while (!port) {
    // Edge on Windows starts the browser as a process of its own and ends the one started here with 0: the
    // port file says whether a browser is coming. Anything else is the browser failing to start.
    if (proc.exitCode !== null && proc.exitCode !== 0) throw new Error(`the browser ended (${proc.exitCode}): ${stderr.trim()}`);
    if (Date.now() > end) { try { proc.kill(); } catch (e) { /* gone */ } throw new Error(`the browser didn't start in 30 s: ${stderr.trim()}`); }
    try {
      const lines = fs.readFileSync(portFile, "utf8").trim().split(/\r?\n/);
      if (lines.length >= 2 && Number(lines[0]) > 0) port = Number(lines[0]);
    } catch (e) { /* not written yet */ }
    if (!port) await sleep(50);
  }
  const version = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
  const ws = new WebSocket(version.webSocketDebuggerUrl);
  await new Promise((ok, bad) => { ws.onopen = ok; ws.onerror = () => bad(new Error("couldn't connect to the browser")); });
  return new Browser(proc, new Connection(ws), dir);
}
