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
import { spawn, spawnSync, execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const sleep = ms => new Promise(r => setTimeout(r, ms));
// Windows' key codes for the keys a test presses by name, which the browser needs to act on them.
const KEY_CODES = { Enter: 13, Escape: 27, Tab: 9, Backspace: 8, Delete: 46, ArrowLeft: 37, ArrowUp: 38, ArrowRight: 39,
  ArrowDown: 40, Home: 36, End: 35, " ": 32 };
const KEY_NAMES = { " ": "Space" };
// p, or a rejection with `why` after ms; the timer never outlives it (an open timer keeps node running).
function within(p, ms, why) {
  let timer;
  const late = new Promise((_, bad) => { timer = setTimeout(() => bad(new Error(why)), ms); });
  return Promise.race([p, late]).finally(() => clearTimeout(timer));
}

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
  // Close the browser and remove its profile (shutDown: over the protocol, then by its profile when that
  // isn't enough, as the process started here may be only Edge's launcher).
  async close() {
    await shutDown({ proc: this.proc, dir: this.dir, c: this.c });
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

// A failed request the browser logs that isn't the page's error: /favicon.ico, which the browser asks for by
// itself; a request to another host (the web fonts, which a computer offline can't reach); and the studio's
// API saying no (a 4xx with a sentence the page shows: a game route with no game's files to read, say), the
// page working as made. A page file that's missing, an answer of 5xx, or a request to the studio that got no
// answer counts.
function notThePages(entry) {
  if (entry.source !== "network" || !entry.url) return false;
  let url;
  try { url = new URL(entry.url); } catch (e) { return false; }
  if (!["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)) return true;
  if (url.pathname === "/favicon.ico") return true;
  return url.pathname.startsWith("/api/") && /status of 4\d\d\b/.test(entry.text);
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
      } else if (msg.method === "Log.entryAdded" && msg.params.entry.level === "error" && !notThePages(msg.params.entry)) {
        // The browser's own errors: a page file or a request that failed, a blocked resource.
        const e = msg.params.entry;
        this.errors.push(e.url && !e.text.includes(e.url) ? `${e.text} (${e.url})` : e.text);
      } else if (msg.method === "Page.loadEventFired" || msg.method === "Page.navigatedWithinDocument") {
        // A URL that differs only by its #fragment doesn't load again: the page gets a hashchange instead.
        for (const r of this.loads.splice(0)) r();
      }
    });
    await this.send("Page.enable");
    await this.send("Runtime.enable");
    await this.send("Log.enable");
    await this.send("DOM.enable");
  }
  // Load a URL and wait for its load event (10 s, or `timeout` ms); a change of #fragment alone waits for the
  // hashchange.
  async goto(url, { timeout = 10000 } = {}) {
    const loaded = this.nextLoad(`${url} didn't load in ${timeout / 1000} s`, timeout);
    let r;
    try {
      r = await this.send("Page.navigate", { url });
    } catch (e) {
      loaded.cancel();
      throw e;
    }
    if (r.errorText) {
      loaded.cancel();
      throw new Error(`${url}: ${r.errorText}`);
    }
    await loaded;
  }
  // Load the page again, as F5 would.
  async reload({ timeout = 10000 } = {}) {
    const loaded = this.nextLoad(`the page didn't load again in ${timeout / 1000} s`, timeout);
    try {
      await this.send("Page.reload");
    } catch (e) {
      loaded.cancel();
      throw e;
    }
    await loaded;
  }
  // The page's next load (or change of #fragment): a promise rejected with `why` after `timeout` ms, whose
  // timer is cleared as soon as it loads. cancel() drops it, timer and all, when the navigation never started.
  nextLoad(why, timeout = 10000) {
    let timer, done;
    const loaded = new Promise((ok, bad) => {
      done = () => { clearTimeout(timer); ok(); };
      this.loads.push(done);
      timer = setTimeout(() => { this.loads = this.loads.filter(f => f !== done); bad(new Error(why)); }, timeout);
    });
    loaded.cancel = () => {
      clearTimeout(timer);
      this.loads = this.loads.filter(f => f !== done);
      loaded.catch(() => { /* never awaited, and never settled now */ });
    };
    return loaded;
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
  // Where an element is, scrolled into view: {x, y} of its middle in the viewport, once it's ready for a click
  // there: it has a size, it's in the same place 50 ms apart (a layout still settling moves it: a neighbour's
  // label growing pushes it aside), and it, not something over it, is what that point hits. Waits up to
  // `timeout` ms for that, then says what's wrong.
  async middle(target, timeout = 10000) {
    const probe = `(async n => {
      if (!n) return { why: "nothing on the page matches it" };
      n.scrollIntoView({ block: "center" });
      const box = () => { const r = n.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; };
      const before = box();
      await new Promise(r => setTimeout(r, 50));
      const [x, y, w, h] = box();
      if (!w || !h) return { why: "it has no size (hidden?)" };
      if ([x, y, w, h].join() !== before.join()) return { why: "it keeps moving" };
      const at = document.elementFromPoint(x + w / 2, y + h / 2);
      if (!at || !(at === n || n.contains(at))) return { why: "something else is over its middle: " + (at ? at.outerHTML.slice(0, 80) : "nothing") };
      return { x: x + w / 2, y: y + h / 2, w, h };
    })(${locator(target)})`;
    const end = Date.now() + timeout;
    for (;;) {
      const box = await this.evaluate(probe);
      if (!box.why) return box;
      if (Date.now() > end) throw new Error(`can't click ${JSON.stringify(target)}: ${box.why}`);
    }
  }
  // A real click: the mouse moves to the element's middle (once middle() says it's ready), presses and releases.
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
  // A key pressed and let go: a character, or a key's name (Enter, Escape, Tab, Space, the arrows...), which the
  // browser then acts on as it would on a real press (Tab moves focus, Enter's text presses a focused button).
  // `code` is the key's place on the keyboard ("KeyF", "Insert"), which a page reading KeyboardEvent.code needs
  // (a named key's own and a letter's are filled in); `shift` holds Shift.
  async press(key, { code, shift = false } = {}) {
    const text = key.length === 1 ? key : key === "Enter" ? "\r" : undefined;
    const letter = /^[a-z]$/i.test(key);
    const vk = KEY_CODES[key] || (letter ? key.toUpperCase().charCodeAt(0) : 0);
    code ||= KEY_NAMES[key] || (letter ? `Key${key.toUpperCase()}` : key);
    const fields = { key, code, modifiers: shift ? 8 : 0, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk };
    await this.send("Input.dispatchKeyEvent", { type: text ? "keyDown" : "rawKeyDown", text, ...fields });
    await this.send("Input.dispatchKeyEvent", { type: "keyUp", ...fields });
  }
  // Give a file input files from disk, as choosing them would.
  async setFiles(selector, paths) {
    const { root } = await this.send("DOM.getDocument", { depth: 0 });
    const { nodeId } = await this.send("DOM.querySelector", { nodeId: root.nodeId, selector });
    if (!nodeId) throw new Error(`no ${selector} on the page`);
    await this.send("DOM.setFileInputFiles", { nodeId, files: paths.map(p => path.resolve(p)) });
  }
  // console.error calls, uncaught exceptions and the browser's own errors so far: a page file that failed to
  // load, a request to the studio answered 5xx or not at all (and not what notThePages() leaves out).
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

// End every process whose command line names `dir`, the profile launch() made (nothing else names it). Edge's
// launcher hands the browser to a process of its own and exits, so the process started here is often not the
// browser, and the browser's helpers (GPU, renderers, the crash handler) aren't under it either. A helper is
// given the profile as --user-data-dir="<dir>", quoted when the path has a space, so it's the folder that's
// looked for rather than the whole switch. The folder reaches PowerShell through the environment, not its
// command line, so PowerShell never matches itself.
function killByProfile(dir) {
  if (process.platform === "win32") {
    const script = "$d = $env:WC_PROFILE_DIR.ToLowerInvariant(); Get-CimInstance Win32_Process | Where-Object { " +
      "$_.ProcessId -ne $PID -and $_.CommandLine -and $_.CommandLine.ToLowerInvariant().Contains($d) } | " +
      "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }";
    spawnSync("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", script],
      { env: { ...process.env, WC_PROFILE_DIR: dir }, stdio: "ignore", timeout: 60000, windowsHide: true });
  } else {
    spawnSync("pkill", ["-KILL", "-f", "--", dir.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")], { stdio: "ignore", timeout: 10000 });
  }
}

// Remove the profile, trying again while the browser's processes let go of its files; whether it's gone.
async function removeProfile(dir, tries) {
  for (let i = 0; i < tries; i++) {
    try { fs.rmSync(dir, { recursive: true, force: true }); return true; } catch (e) { await sleep(250); }
  }
  return !fs.existsSync(dir);
}

// Ask a browser to close, over a connection of its own to the endpoint its port file names.
async function closeOverProtocol(endpoint) {
  let ws = null;
  try {
    ws = new WebSocket(endpoint);
    await within(new Promise((ok, bad) => { ws.onopen = ok; ws.onerror = () => bad(new Error("no connection")); }), 3000, "no connection");
    const closed = new Promise(ok => { ws.onclose = ok; });
    ws.send(JSON.stringify({ id: 1, method: "Browser.close" }));
    await within(closed, 3000, "still open");
  } catch (e) {
    /* not listening, or not closing: the processes on its profile are ended instead */
  } finally {
    try { if (ws) ws.close(); } catch (e) { /* closed */ }
  }
}

// End a browser launch() started, for good, and remove its profile. Browser.close over the protocol (`c`, the
// browser's connection, or a new one to `endpoint`), then the process started here goes (or is killed). Then
// whatever still runs on the profile is ended by its command line: always when `sure` (a launch that failed
// partway, where the protocol may never have answered) or off Windows (where a folder in use can be removed
// all the same), else only when the folder can't be removed yet. Then the folder goes.
async function shutDown({ proc, dir, c = null, endpoint = null, sure = false }) {
  if (c) {
    try { await within(c.send("Browser.close"), 3000, "Browser.close"); } catch (e) { /* gone already, or stuck */ }
    try { c.ws.close(); } catch (e) { /* closed by the browser */ }
  } else if (endpoint) {
    await closeOverProtocol(endpoint);
  }
  if (proc) {
    const gone = proc.exitCode !== null || proc.signalCode !== null ? Promise.resolve() : new Promise(r => proc.once("exit", r));
    try { await within(gone, 5000, "still running"); } catch (e) { try { proc.kill(); } catch (e2) { /* gone */ } }
  }
  if (sure || process.platform !== "win32") killByProfile(dir);
  if (await removeProfile(dir, 8)) return;
  killByProfile(dir);
  if (!(await removeProfile(dir, 20))) console.warn(`couldn't remove the browser's profile ${dir}`);
}

// Start the browser headless with a profile of its own and connect to it, waiting `timeout` ms for it to start.
// `exeArgs` go before the browser's own arguments (a script, when `browser` is an interpreter: the tests' fake
// browser). Anything that fails once the profile is made ends the browser and removes the profile first.
export async function launch({ browser = findBrowser(), headless = true, timeout = 30000, exeArgs = [] } = {}) {
  if (!browser) throw new Error("no browser: set WC_BROWSER to a Chromium's exe (Edge, Chrome or Chromium)");
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wc-browser-"));
  let proc = null, endpoint = null;
  try {
    const args = [...exeArgs, headless ? "--headless=new" : null, "--remote-debugging-port=0", `--user-data-dir=${dir}`,
      "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--disable-extensions",
      "--disable-background-networking", "--disable-sync", "--disable-features=Translate,OptimizationHints",
      "--window-size=1280,900", "about:blank"].filter(Boolean);
    proc = spawn(browser, args, { stdio: ["ignore", "ignore", "pipe"], windowsHide: true });
    let stderr = "", failed = null;
    proc.on("error", e => { failed = e; });   // it couldn't be started at all
    proc.stderr.on("data", d => { stderr += d; });
    const portFile = path.join(dir, "DevToolsActivePort");
    const end = Date.now() + timeout;
    while (!endpoint) {
      // The port file says a browser is listening: its port, then its endpoint's path.
      try {
        const lines = fs.readFileSync(portFile, "utf8").trim().split(/\r?\n/);
        if (lines.length >= 2 && Number(lines[0]) > 0) {
          endpoint = `ws://127.0.0.1:${Number(lines[0])}${lines[1]}`;
          break;
        }
      } catch (e) { /* not written yet */ }
      // Edge on Windows starts the browser as a process of its own and ends the one started here with 0, so
      // only another ending is the browser failing to start.
      if (failed) throw new Error(`the browser couldn't be started: ${failed.message}`);
      if (proc.signalCode !== null || (proc.exitCode !== null && proc.exitCode !== 0)) {
        throw new Error(`the browser ended (${proc.exitCode ?? proc.signalCode}): ${stderr.trim()}`);
      }
      if (Date.now() > end) throw new Error(`the browser didn't start in ${timeout / 1000} s: ${stderr.trim()}`);
      await sleep(50);
    }
    const ws = new WebSocket(endpoint);
    try {
      await within(new Promise((ok, bad) => { ws.onopen = ok; ws.onerror = () => bad(new Error(`couldn't connect to the browser at ${endpoint}`)); }),
        10000, `couldn't connect to the browser at ${endpoint} in 10 s`);
    } catch (e) {
      try { ws.close(); } catch (e2) { /* never opened */ }
      throw e;
    }
    return new Browser(proc, new Connection(ws), dir);
  } catch (e) {
    await shutDown({ proc, dir, endpoint, sure: true });
    throw e;
  }
}
