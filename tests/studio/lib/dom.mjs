// A small DOM for running studio/lib/wc.js under node --test, with no browser: elements with attributes,
// children, events and a few selectors; a select's options and value; document, window, localStorage and a
// fetch the test supplies. Enough for the Editing mod bar (wc.modTarget); not a browser.

function parseSelector(sel) {
  // "tag", "#id", ".class", "[attr=\"value\"]", "[attr]", any of them joined, and a descendant chain with spaces.
  return sel.trim().split(/\s+/).map(part => {
    const out = { tag: null, id: null, classes: [], attrs: [] };
    const re = /([a-z0-9-]+)|#([\w-]+)|\.([\w-]+)|\[([\w-]+)(?:="([^"]*)")?\]/gi;
    let m;
    while ((m = re.exec(part))) {
      if (m[1]) out.tag = m[1].toUpperCase();
      else if (m[2]) out.id = m[2];
      else if (m[3]) out.classes.push(m[3]);
      else out.attrs.push([m[4], m[5]]);
    }
    return out;
  });
}

export class Element {
  constructor(tag, doc) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = doc;
    this.children = [];
    this.parentNode = null;
    this.attrs = {};
    this.listeners = {};
    this.style = {};
    this._text = null;   // a text node of its own, when set through textContent
    this._value = "";
    this.dataset = new Proxy({}, {
      get: (_, k) => this.attrs["data-" + k.replace(/[A-Z]/g, c => "-" + c.toLowerCase())],
      set: (_, k, v) => { this.attrs["data-" + k.replace(/[A-Z]/g, c => "-" + c.toLowerCase())] = String(v); return true; },
      deleteProperty: (_, k) => { delete this.attrs["data-" + k]; return true; },
    });
    this.classList = {
      add: (...c) => { const s = new Set(this.className.split(/\s+/).filter(Boolean)); c.forEach(x => s.add(x)); this.className = [...s].join(" "); },
      remove: (...c) => { this.className = this.className.split(/\s+/).filter(x => x && !c.includes(x)).join(" "); },
      contains: c => this.className.split(/\s+/).includes(c),
    };
  }
  get id() { return this.attrs.id || ""; }
  set id(v) { this.attrs.id = v; }
  // Attribute-backed, as in a browser: el() sets them as attributes, the page reads and sets them as properties.
  get hidden() { return "hidden" in this.attrs; }
  set hidden(v) { if (v) this.attrs.hidden = ""; else delete this.attrs.hidden; }
  get disabled() { return "disabled" in this.attrs; }
  set disabled(v) { if (v) this.attrs.disabled = ""; else delete this.attrs.disabled; }
  get selected() { return !!this._selected; }
  set selected(v) { this._selected = !!v; }
  get className() { return this.attrs.class || ""; }
  set className(v) { this.attrs.class = v; }
  get tabIndex() { return Number(this.attrs.tabindex ?? -1); }
  set tabIndex(v) { this.attrs.tabindex = String(v); }
  get childNodes() { return [...this.children]; }
  get firstChild() { return this.children[0] || null; }
  get attributes() { return Object.entries(this.attrs).map(([name, value]) => ({ name, value })); }
  get isConnected() { let n = this; while (n.parentNode) n = n.parentNode; return n === this.ownerDocument.body || n === this.ownerDocument; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  hasAttribute(k) { return k in this.attrs; }
  append(...kids) {
    for (const kid of kids) {
      if (kid == null) continue;
      const node = typeof kid === "string" ? this.ownerDocument.createTextNode(kid) : kid;
      if (node.parentNode) node.parentNode.children = node.parentNode.children.filter(c => c !== node);
      node.parentNode = this;
      this.children.push(node);
    }
  }
  prepend(...kids) { const was = this.children; this.children = []; this.append(...kids); this.children.push(...was); }
  after(...kids) { const i = this.parentNode.children.indexOf(this); for (const k of kids) { k.parentNode = this.parentNode; } this.parentNode.children.splice(i + 1, 0, ...kids); }
  remove() { if (this.parentNode) { this.parentNode.children = this.parentNode.children.filter(c => c !== this); this.parentNode = null; } }
  replaceWith(...nodes) { const p = this.parentNode, i = p.children.indexOf(this); nodes.forEach(n => { n.parentNode = p; }); p.children.splice(i, 1, ...nodes); this.parentNode = null; }
  contains(n) { while (n) { if (n === this) return true; n = n.parentNode; } return false; }
  get textContent() {
    if (this._text !== null) return this._text;
    return this.children.map(c => c.textContent).join("");
  }
  set textContent(v) { this.children = []; this._text = v === "" ? null : String(v); }
  get value() {
    if (this.tagName === "OPTION") return this.attrs.value ?? this.textContent;
    if (this.tagName === "SELECT") {
      const opts = this.options;
      const chosen = opts.find(o => o.selected) || opts[0];
      return chosen ? chosen.value : "";
    }
    return this._value;
  }
  set value(v) {
    if (this.tagName === "SELECT") {
      const opts = this.options;
      if (!opts.some(o => o.value === String(v))) { opts.forEach(o => { o.selected = false; }); return; }
      opts.forEach(o => { o.selected = o.value === String(v); });
      return;
    }
    this._value = String(v);
  }
  get options() { return this.children.filter(c => c.tagName === "OPTION"); }
  get selectedOptions() { return this.options.filter(o => o.selected); }
  get checked() { return !!this._checked; }
  set checked(v) { this._checked = !!v; }
  get files() { return this._files || []; }
  matches(sel) { return parseSelector(sel).some(() => false) || matchOne(this, parseSelector(sel)); }
  closest(sel) { let n = this; while (n && n instanceof Element) { if (n.matches(sel)) return n; n = n.parentNode; } return null; }
  querySelectorAll(sel) { const chain = parseSelector(sel), out = []; walk(this, n => { if (n !== this && matchOne(n, chain)) out.push(n); }); return out; }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  getElementsByTagName(tag) { return this.querySelectorAll(tag); }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener(type, fn) { this.listeners[type] = (this.listeners[type] || []).filter(f => f !== fn); }
  dispatchEvent(evt) {
    evt.target ||= this;
    for (let n = this; n; n = n.parentNode) {
      evt.currentTarget = n;
      for (const fn of n.listeners?.[evt.type] || []) fn(evt);
      if (!evt.bubbles) break;
    }
    return !evt.defaultPrevented;
  }
  click() { this.dispatchEvent(new Event("click", { bubbles: true })); }
  focus() { this.ownerDocument.activeElement = this; this.dispatchEvent(new Event("focusin", { bubbles: true })); }
  blur() { if (this.ownerDocument.activeElement === this) this.ownerDocument.activeElement = this.ownerDocument.body; }
  getClientRects() { return this.isConnected ? [{}] : []; }
  scrollIntoView() {}
}

class Text {
  constructor(text, doc) { this.text = String(text); this.ownerDocument = doc; this.parentNode = null; this.nodeType = 3; }
  get textContent() { return this.text; }
  remove() { if (this.parentNode) { this.parentNode.children = this.parentNode.children.filter(c => c !== this); } }
}

function walk(node, fn) {
  for (const c of node.children || []) { if (c instanceof Element) { fn(c); walk(c, fn); } }
}
function matchSimple(n, s) {
  if (s.tag && n.tagName !== s.tag) return false;
  if (s.id && n.id !== s.id) return false;
  if (s.classes.some(c => !n.classList.contains(c))) return false;
  for (const [k, v] of s.attrs) {
    if (!(k in n.attrs)) return false;
    if (v !== undefined && n.attrs[k] !== v) return false;
  }
  return true;
}
function matchOne(n, chain) {
  // The last part matches n; each earlier part matches some ancestor, in order.
  if (!matchSimple(n, chain[chain.length - 1])) return false;
  let a = n.parentNode, i = chain.length - 2;
  while (i >= 0 && a && a instanceof Element) {
    if (matchSimple(a, chain[i])) i--;
    a = a.parentNode;
  }
  return i < 0;
}

export class Event {
  constructor(type, init = {}) { this.type = type; this.bubbles = !!init.bubbles; this.defaultPrevented = false; this.target = null; }
  preventDefault() { this.defaultPrevented = true; }
  stopPropagation() { this.bubbles = false; }
}

class Document {
  constructor() {
    this.body = new Element("body", this);
    this.head = new Element("head", this);
    this.activeElement = this.body;
    this.listeners = {};
    this.nodeType = 9;
  }
  createElement(tag) { return new Element(tag, this); }
  createTextNode(t) { return new Text(t, this); }
  getElementById(id) { return this.body.querySelector(`#${id}`) || this.head.querySelector(`#${id}`); }
  querySelector(sel) { return this.body.querySelector(sel) || this.head.querySelector(sel); }
  querySelectorAll(sel) { return [...this.body.querySelectorAll(sel), ...this.head.querySelectorAll(sel)]; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener() {}
}

// Set the DOM up as globals and give the page the live regions and toasts index.html has. `fetch(path,
// options)` answers API calls: it gets the path after /api and the options, and returns an object (a JSON
// answer), or throws an Error with .status to answer with that status.
export function install({ fetch: answer, token = "test-token" } = {}) {
  const document = new Document();
  const storage = new Map();
  const localStorage = {
    getItem: k => (storage.has(k) ? storage.get(k) : null), setItem: (k, v) => storage.set(k, String(v)),
    removeItem: k => storage.delete(k), clear: () => storage.clear(),
  };
  const window = {
    listeners: {},
    addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); },
    dispatchEvent(evt) { for (const fn of this.listeners[evt.type] || []) fn(evt); return !evt.defaultPrevented; },
    localStorage, sessionStorage: localStorage, document,
  };
  const meta = document.createElement("meta");
  meta.setAttribute("name", "wc-token");
  meta.content = token;
  document.head.append(meta);
  for (const [id, cls] of [["toasts", "toasts"], ["say", "sr-only"], ["shout", "sr-only"], ["main", "main"]]) {
    const n = document.createElement("div");
    n.id = id; n.className = cls;
    document.body.append(n);
  }
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    const path = url.replace(/^\/api/, "");
    const body = options.body ? JSON.parse(options.body) : undefined;
    calls.push({ method: options.method || "GET", path, body });
    try {
      const data = await answer(path, { ...options, method: options.method || "GET", body });
      return { ok: true, status: 200, statusText: "OK", json: async () => data, headers: { get: () => null } };
    } catch (e) {
      const status = e.status || 500;
      return { ok: false, status, statusText: "Error", json: async () => ({ error: e.message }), headers: { get: () => null } };
    }
  };
  Object.assign(globalThis, { document, window, localStorage, sessionStorage: localStorage, Event, Node: { TEXT_NODE: 3, ELEMENT_NODE: 1 },
    CSS: { escape: s => String(s).replace(/([^\w-])/g, "\\$1") }, location: { hash: "", search: "" } });
  globalThis.HTMLElement = Element;
  return { document, window, localStorage, calls };
}

// Let the page's timers run: wc.js announces and toasts a moment later.
export const tick = (ms = 0) => new Promise(r => setTimeout(r, ms));
