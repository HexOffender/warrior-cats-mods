// The smallest DOM the studio's library needs under node:test: enough of document, Element, localStorage and
// fetch for studio/lib/wc.js to import (the token's <meta>), make elements (el), say things (announce, toast)
// and pick a mod (modTarget). Nothing here draws; a test that needs a real page uses lib/browser.mjs.
//
//   import { install } from "./lib/dom.mjs";
//   const dom = install();            // sets the globals, once
//   dom.routes = { "GET /mods": () => [...] };   // what fetch("/api/...") answers
//   const wc = await import(dom.studio("lib/wc.js"));
import { pathToFileURL } from "node:url";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
export const STUDIO = path.join(REPO, "studio");

export class Element {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.attrs = {};
    this.style = {};
    this.listeners = {};
    this.parent = null;
    this.isConnected = true;
    this.disabled = false;
    this._hidden = false;
  }
  get id() { return this.attrs.id || ""; }
  set id(v) { this.attrs.id = String(v); }
  get className() { return this.attrs.class || ""; }
  set className(v) { this.attrs.class = String(v); }
  get classList() {
    const n = this;
    const list = () => (n.attrs.class || "").split(" ").filter(Boolean);
    return {
      add: (...cs) => { n.attrs.class = [...new Set([...list(), ...cs])].join(" "); },
      remove: (...cs) => { n.attrs.class = list().filter(x => !cs.includes(x)).join(" "); },
      contains: c => list().includes(c),
      toggle: (c, on) => { const has = list().includes(c); if (on ?? !has) n.classList.add(c); else n.classList.remove(c); },
    };
  }
  get dataset() { return Object.fromEntries(Object.entries(this.attrs).filter(([k]) => k.startsWith("data-")).map(([k, v]) => [k.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase()), v])); }
  get hidden() { return this._hidden || "hidden" in this.attrs; }
  set hidden(v) { this._hidden = !!v; if (v) this.attrs.hidden = ""; else delete this.attrs.hidden; }
  get textContent() { return this.children.map(c => typeof c === "string" ? c : c.textContent).join(""); }
  set textContent(v) { for (const c of this.children) if (typeof c !== "string") c.parent = null; this.children = v === "" || v == null ? [] : [String(v)]; }
  get innerHTML() { return this._html || ""; }
  set innerHTML(v) { this._html = String(v); this.children = []; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  hasAttribute(k) { return k in this.attrs; }
  append(...kids) { for (const k of kids) { if (typeof k !== "string") { k.parent = this; k.isConnected = true; } this.children.push(k); } }
  appendChild(k) { this.append(k); return k; }
  after(...nodes) { if (!this.parent) return; const i = this.parent.children.indexOf(this); this.parent.children.splice(i + 1, 0, ...nodes); for (const n of nodes) if (typeof n !== "string") n.parent = this.parent; }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(c => c !== this); this.parent = null; this.isConnected = false; }
  contains(n) { for (let x = n; x; x = x.parent) if (x === this) return true; return false; }
  // <select>: its <option>s and the chosen value; an <option>: its value attribute or its text.
  get options() { return this.all().filter(c => c.tagName === "OPTION"); }
  get selectedOptions() { return this.options.filter(o => o.value === this.value); }
  get value() {
    if (this.tagName === "OPTION") return this.attrs.value ?? this.textContent;
    if (this.tagName === "SELECT") return this._value ?? this.options[0]?.value ?? "";
    return this._value ?? this.attrs.value ?? "";
  }
  set value(v) { this._value = String(v); }
  get checked() { return this._checked ?? "checked" in this.attrs; }
  set checked(v) { this._checked = !!v; }
  get files() { return this._files || []; }
  addEventListener(t, fn) { (this.listeners[t] ||= []).push(fn); }
  removeEventListener(t, fn) { this.listeners[t] = (this.listeners[t] || []).filter(f => f !== fn); }
  // A test's way of pressing, typing or blurring: the listeners for `type` run with a small event.
  dispatch(type, extra = {}) {
    const e = { type, target: this, currentTarget: this, preventDefault() {}, stopPropagation() {}, ...extra };
    for (const fn of this.listeners[type] || []) fn(e);
    return e;
  }
  click() { this.dispatch("click"); }
  focus() { document.activeElement = this; this.dispatch("focus"); }
  blur() { if (document.activeElement === this) document.activeElement = document.body; this.dispatch("blur"); }
  all() { const out = []; const walk = n => { for (const c of n.children) if (typeof c !== "string") { out.push(c); walk(c); } }; walk(this); return out; }
  // Selectors a test needs: a tag, .class, #id, [attr="value"], and one of those with a trailing :not() left out.
  matches(sel) {
    const m = /^(\w+)?(?:#([\w-]+))?(?:\.([\w-]+))?(?:\[([\w-]+)(?:="([^"]*)")?\])?$/.exec(sel.trim());
    if (!m) return false;
    const [, tag, id, cls, attr, val] = m;
    if (tag && this.tagName !== tag.toUpperCase()) return false;
    if (id && this.id !== id) return false;
    if (cls && !this.classList.contains(cls)) return false;
    if (attr && !(attr in this.attrs && (val === undefined || this.attrs[attr] === val))) return false;
    return true;
  }
  querySelectorAll(sel) { return this.all().filter(n => n.matches(sel)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  closest(sel) { for (let n = this; n; n = n.parent) if (n.matches(sel)) return n; return null; }
  getClientRects() { return this.isConnected ? [1] : []; }
  getBoundingClientRect() { return { x: 0, y: 0, width: 1, height: 1, top: 0, left: 0 }; }
  scrollIntoView() {}
  setSelectionRange() {}
}

let installed = null;

export function install() {
  if (installed) return installed;
  const body = new Element("body");
  const byId = {};
  const document = {
    body, activeElement: body,
    createElement: tag => new Element(tag),
    createElementNS: (ns, tag) => new Element(tag),
    getElementById: id => byId[id] || body.querySelector(`#${id}`),
    querySelector: sel => (sel === 'meta[name="wc-token"]' ? { content: "test-token" } : body.querySelector(sel)),
    querySelectorAll: sel => body.querySelectorAll(sel),
    addEventListener() {},
    title: "",
  };
  // The live regions and the toasts' box, as index.html has them.
  for (const id of ["toasts", "say", "shout", "main"]) { byId[id] = new Element("div"); byId[id].id = id; body.append(byId[id]); }
  globalThis.document = document;
  globalThis.CSS = { escape: s => String(s).replace(/([^\w-])/g, "\\$1") };
  globalThis.MutationObserver = class { observe() {} disconnect() {} };
  globalThis.localStorage = {
    _m: {}, getItem(k) { return k in this._m ? this._m[k] : null; }, setItem(k, v) { this._m[k] = String(v); },
    removeItem(k) { delete this._m[k]; }, clear() { this._m = {}; },
  };
  // Node has a navigator of its own (read-only); the clipboard is the one thing wc.js asks of it.
  Object.defineProperty(globalThis, "navigator", { value: { clipboard: { writeText: async () => {} } }, configurable: true });
  globalThis.URL.createObjectURL ||= () => "blob:test";
  globalThis.URL.revokeObjectURL ||= () => {};
  globalThis.window = globalThis;
  // The window's own events (beforeunload, focus): Node's globalThis has no listeners of its own. A test
  // dispatches one with window.dispatchEvent({ type, preventDefault() {...} }).
  const windowListeners = {};   // dom.windowListeners: a test clears it between pages, as a reload would
  globalThis.addEventListener = (type, fn) => { (windowListeners[type] ||= []).push(fn); };
  globalThis.removeEventListener = (type, fn) => { windowListeners[type] = (windowListeners[type] || []).filter(f => f !== fn); };
  globalThis.dispatchEvent = evt => { for (const fn of windowListeners[evt.type] || []) fn(evt); return !evt.defaultPrevented; };
  // fetch: a scripted API. routes maps "GET /mods" to a handler(body, headers) whose return is the answer;
  // a handler may throw {status, error} for an error answer. Every call is noted in `calls`.
  const dom = {
    document, body, byId, routes: {}, calls: [], windowListeners,
    studio: rel => pathToFileURL(path.join(STUDIO, rel)).href,
  };
  globalThis.fetch = async (url, init = {}) => {
    const method = init.method || "GET";
    const key = `${method} ${String(url).replace(/^\/api/, "")}`;
    const body = init.body ? JSON.parse(init.body) : undefined;
    dom.calls.push({ method, url: String(url), body, headers: init.headers || {} });
    const handler = dom.routes[key];
    if (!handler) return { ok: false, status: 404, statusText: "no route", headers: new Map(), json: async () => ({ error: `unknown API route ${key}` }) };
    try {
      const out = await handler(body, init.headers || {});
      return { ok: true, status: 200, statusText: "OK", headers: new Map(), json: async () => out };
    } catch (e) {
      if (e && e.status) return { ok: false, status: e.status, statusText: "error", headers: new Map(), json: async () => ({ error: e.error }) };
      throw e;
    }
  };
  installed = dom;
  return dom;
}

export const tick = (ms = 0) => new Promise(r => setTimeout(r, ms));
