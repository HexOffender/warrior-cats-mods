// Clan Mod Studio shared library. Built-in sections and mod-provided sections import this.
//
// A section is an ES module whose default export is:
//   { title: "My page", mount(root, wc) { ...; return { unmount() {} } } }
// `wc` is this module. See docs/SDK.md for a worked example.

const TOKEN = document.querySelector('meta[name="wc-token"]')?.content || "";

// ---------- API ----------
async function call(method, path, body) {
  const res = await fetch("/api" + path, {
    method,
    headers: { "X-WC-Token": TOKEN, ...(body !== undefined ? { "Content-Type": "application/json" } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch (e) { /* empty body */ }
  if (!res.ok) throw new Error((data && data.error) || `${res.status} ${res.statusText}`);
  return data;
}
export const api = {
  get: p => call("GET", p),
  post: (p, b = {}) => call("POST", p, b),
  put: (p, b) => call("PUT", p, b),
  patch: (p, b) => call("PATCH", p, b),
  del: p => call("DELETE", p),
  // Send a file as the request's body (a downloaded mod's .zip, a picture); the answer is JSON.
  async upload(p, file, type = "application/zip") {
    const res = await fetch("/api" + p, { method: "POST", headers: { "X-WC-Token": TOKEN, "Content-Type": type }, body: file });
    let data = null;
    try { data = await res.json(); } catch (e) { /* empty body */ }
    if (!res.ok) throw new Error((data && data.error) || `${res.status} ${res.statusText}`);
    return data;
  },
  // Fetch a file the API makes (a mod as a .zip) and hand it to the browser to save.
  async download(p) {
    const res = await fetch("/api" + p, { headers: { "X-WC-Token": TOKEN } });
    if (!res.ok) {
      let data = null;
      try { data = await res.json(); } catch (e) { /* not JSON */ }
      throw new Error((data && data.error) || `${res.status} ${res.statusText}`);
    }
    const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "")?.[1] || "download";
    const url = URL.createObjectURL(await res.blob());
    const a = el("a", { href: url, download: name });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    return name;
  },
  // A picture the API makes (an item's icon) as a URL for an <img>; kept, so asking again is free.
  async image(p) {
    if (!images.has(p)) {
      images.set(p, (async () => {
        const res = await fetch("/api" + p, { headers: { "X-WC-Token": TOKEN } });
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return URL.createObjectURL(await res.blob());
      })());
      images.get(p).catch(() => images.delete(p));
    }
    return images.get(p);
  },
  forget(p) { images.delete(p); },
};
const images = new Map();   // API path -> Promise of an object URL

// Hand the browser a file to save that the page made itself (a .json exported from a page).
export function saveFile(name, text, type = "application/json") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = el("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

// ---------- DOM ----------
export function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k === "style" && typeof v === "object") Object.assign(n.style, v);
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) n.append(kid);
  return n;
}
export const $ = (sel, root = document) => root.querySelector(sel);

// A link to one of the docs, opened in a new tab: docLink("docs/scripting.md", "docs/scripting.md"), or with
// a heading: docLink("README.md#remapping-keys", "Remapping keys").
export const DOCS = "https://github.com/HexOffender/warrior-cats-mods/blob/main/";
export const docLink = (path, text) => el("a", { href: DOCS + path, target: "_blank", rel: "noopener", text: text || path });
export const clear = node => { node.textContent = ""; return node; };

// Say something to screen readers, without showing it: politely, or at once for a problem. The live
// regions are in index.html; the text goes in a moment after they're emptied, so saying the same thing
// twice is heard twice, and what's said in that moment (a toast and the status line) goes in together.
const saying = {};
export function announce(message, kind = "info") {
  const id = kind === "bad" ? "shout" : "say";
  const box = document.getElementById(id);
  if (!box) return;
  if (saying[id]) { saying[id].push(message); return; }
  saying[id] = [message];
  box.textContent = "";
  setTimeout(() => { box.textContent = saying[id].join(" "); saying[id] = null; }, 60);
}

// A message that shows for a while (longer for a long one, and for a problem) and is read out. It stays
// while the mouse is on it; a problem has a button to close it.
export function toast(message, kind = "info") {
  announce(message, kind);
  const box = document.getElementById("toasts");
  if (!box) return;
  const bad = kind === "bad";
  const t = el("div", { class: `toast ${bad ? "bad" : ""}` }, el("span", { text: message }));
  let timer = null;
  const close = () => { clearTimeout(timer); t.remove(); };
  const wait = () => { clearTimeout(timer); timer = setTimeout(close, Math.max(bad ? 8000 : 4000, message.length * 70)); };
  // Never focused (not by Tab, not by a click): the toasts are hidden from screen readers, which hear them instead.
  if (bad) t.append(el("button", { class: "toast-close", type: "button", tabindex: "-1", onmousedown: e => e.preventDefault(), text: "×", "aria-label": "Close this message", onclick: close }));
  t.addEventListener("mouseenter", () => clearTimeout(timer));
  t.addEventListener("mouseleave", wait);
  box.append(t);
  wait();
}

// Two-step button: the first press arms it, a second press within 6s runs it (the frame has no confirm()).
export function confirmButton(label, armedLabel, onConfirm, cls = "btn") {
  const b = el("button", { class: cls, text: label });
  let armed = null;
  const disarm = () => { clearTimeout(armed); armed = null; b.textContent = label; b.classList.remove("armed"); };
  b.addEventListener("click", async () => {
    if (!armed) {
      b.textContent = armedLabel;
      b.classList.add("armed");
      announce(armedLabel);
      armed = setTimeout(disarm, 6000);
      return;
    }
    disarm();
    await onConfirm();
  });
  b.addEventListener("blur", () => { if (armed) disarm(); });
  return b;
}

// ---------- keeping the keyboard's place ----------
// Pages redraw parts of themselves after a change, which takes away the element that had focus and
// would leave a keyboard or screen reader user at the top of the page. keepFocus() (app.js calls it
// once) watches for that and focuses the redrawn element instead: the one with the same id, the same
// data-focus key, or the same label (or text) inside the same data-key part of the page.
export function focusKey(n) {
  if (!n || !n.matches || n === document.body) return null;
  if (n.id) return { sel: `#${CSS.escape(n.id)}` };
  // Its own data-focus, or the one of what it's in (a table cell's edit box goes back to the cell).
  const keyed = n.closest("[data-focus]");
  if (keyed) return { sel: `[data-focus="${CSS.escape(keyed.dataset.focus)}"]` };
  const scope = n.closest("[data-key]")?.dataset.key;
  const label = n.getAttribute("aria-label");
  const tag = n.tagName.toLowerCase();
  if (label) return { sel: `${scope ? `[data-key="${CSS.escape(scope)}"] ` : ""}${tag}[aria-label="${CSS.escape(label)}"]` };
  if (scope && n.textContent.trim()) return { scope, tag, text: n.textContent.trim() };
  return null;
}
function findKey(key) {
  if (!key) return null;
  if (key.sel) return document.querySelector(key.sel);
  const scope = document.querySelector(`[data-key="${CSS.escape(key.scope)}"]`);
  return scope ? [...scope.querySelectorAll(key.tag)].find(x => x.textContent.trim() === key.text) || null : null;
}
const focusable = n => n && n.isConnected && !n.disabled && n.getClientRects().length > 0 && !n.closest('[aria-hidden="true"]');
// The element that had focus, and when it was found gone: a redraw puts its replacement in within a
// moment (after its data comes back); after that, the key is forgotten, so it can't pull focus later.
let lastKey = null, lostAt = 0;
const WAIT = 3000;
export function keepFocus() {
  document.addEventListener("focusin", e => { lastKey = focusKey(e.target); lostAt = 0; });
  document.addEventListener("focusout", e => {
    // Focus moved off on purpose (a click on the page): forget it. A redraw takes the element out first.
    const t = e.target, key = lastKey;
    setTimeout(() => { if (t.isConnected && lastKey === key && document.activeElement === document.body) lastKey = null; }, 0);
  });
  new MutationObserver(() => {
    if (!lastKey || (document.activeElement && document.activeElement !== document.body)) return;
    lostAt ||= Date.now();
    if (Date.now() - lostAt > WAIT) { lastKey = null; return; }
    const n = findKey(lastKey);
    if (focusable(n)) n.focus({ preventScroll: true });
  }).observe(document.body, { childList: true, subtree: true });
}
// The page itself, as a place for focus (the skip link, a panel closing with nothing to go back to). It
// takes focus only then: a page that always could would catch every click on its text, and Tab would
// start again from its top.
export function focusMain() {
  const main = document.getElementById("main");
  if (!main) return;
  main.tabIndex = -1;
  main.addEventListener("blur", () => main.removeAttribute("tabindex"), { once: true });
  main.focus({ preventScroll: true });
}
// For a dialog or panel that takes focus: back() puts it back where it was, on the element or the one
// that replaced it (or on the page, when neither is there any more).
export function keepPlace(node = document.activeElement) {
  const key = focusKey(node);
  return () => {
    const n = node && node.isConnected ? node : findKey(key);
    if (focusable(n)) n.focus({ preventScroll: true });
    else focusMain();
  };
}

// ---------- events between sections ----------
const listeners = {};
export const bus = {
  on(evt, fn) { (listeners[evt] ||= []).push(fn); return () => { listeners[evt] = listeners[evt].filter(f => f !== fn); }; },
  emit(evt, data) { for (const fn of listeners[evt] || []) { try { fn(data); } catch (e) { console.error(e); } } },
};

// ---------- colours (sRGB hex in files, linear floats in the engine) ----------
const hexRe = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i;
function normHex(h) {
  const m = hexRe.exec(String(h).trim());
  if (!m) return null;
  let s = m[1];
  if (s.length === 3) s = s.split("").map(c => c + c).join("");
  return "#" + s.toUpperCase();
}
const hexToRgb = h => { const s = normHex(h).slice(1); return [0, 2, 4].map(i => parseInt(s.slice(i, i + 2), 16) / 255); };
const rgbToHex = c => "#" + c.map(v => Math.round(Math.max(0, Math.min(1, v)) * 255).toString(16).padStart(2, "0")).join("").toUpperCase();
const s2l = c => c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
const l2s = c => { c = Math.max(0, Math.min(1, c)); return c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055; };
const luminance = p => 0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2];
function rgbToHsl([r, g, b]) {
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
  if (mx === mn) return [0, 0, l];
  const d = mx - mn, s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
  const h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [h * 60, s, l];
}
function hslToRgb([h, s, l]) {
  h = ((h % 360) + 360) % 360 / 360;
  if (s === 0) return [l, l, l];
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
  const f = t => { t = (t + 1) % 1; return t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p; };
  return [f(h + 1 / 3), f(h), f(h - 1 / 3)];
}
const clamp01 = v => Math.max(0, Math.min(1, v));
const toward = (h, t, a) => h + (((t - h + 540) % 360) - 180) * a;
const MOODS = {
  vivid: { name: "Vivid", fn: ([h, s, l]) => [h, clamp01(s * 1.35 + 0.06), l] },
  pastel: { name: "Pastel", fn: ([h, s, l]) => [h, s * 0.55, l + (1 - l) * 0.45] },
  moonlit: { name: "Moonlit", fn: ([h, s, l]) => [toward(h, 212, 0.4), s * 0.7, clamp01(l * 0.9 + 0.08)] },
  ember: { name: "Ember", fn: ([h, s, l]) => [toward(h, 20, 0.45), clamp01(s * 1.2 + 0.05), l * 0.92] },
};
export const color = {
  normHex, hexToRgb, rgbToHex, srgbToLinear: s2l, linearToSrgb: l2s, luminance, rgbToHsl, hslToRgb, MOODS,
  hexToLinear: h => hexToRgb(h).map(s2l),
  linearToHex: p => rgbToHex(p.map(l2s)),
  shade: (hex, amt) => { const [h, s, l] = rgbToHsl(hexToRgb(hex)); return rgbToHex(hslToRgb([h, s, clamp01(l * amt)])); },
  mood: (hex, name) => rgbToHex(hslToRgb(MOODS[name].fn(rgbToHsl(hexToRgb(hex))))),
};

// ---------- which mod a section edits ----------
// Renders "Editing mod: [select] [New mod] [Save]". onLoad(obj|null, modId) fires when the target changes;
// call target.save(obj) to write the file. Every page starts on the mod last chosen on any page, else on one
// mod for a player's own edits, "My mods" (made on the first save). The built-in mod menu is never offered.
// The mod a page saves its file into, with a Share part: the mod's details (its name, author, version and
// description, which a shared .zip carries), Save as .zip for others to add on their Mods page, and the
// page's file on its own, out (Export) and in (Import). share: false leaves the Share part out.
export function modTarget({ file, onLoad, getValue, share = true }) {
  const defaultId = "my-mods", defaultName = "My mods";
  const key = "wc-target";   // the mod last chosen, on whichever page
  const kind = file.replace(".json", "");
  let mods = [], current = null, dirty = false;
  const select = el("select", { "aria-label": `Mod that stores ${file}` });
  const status = el("span", { class: "dirty" });
  const saveBtn = el("button", { class: "btn primary", text: "Save to mod" });
  const newBtn = el("button", { class: "btn ghost", text: "New mod…" });
  const newBox = el("span", { class: "row", hidden: true });
  const newId = el("input", { type: "text", placeholder: "my-mod-name", "aria-label": "New mod folder name", spellcheck: "false" });
  newBox.append(newId, el("button", { class: "btn small", text: "Create", onclick: () => create(newId.value.trim()) }));
  const bar = el("div", { class: "target" },
    el("span", { class: "lbl", text: "Editing mod" }), select, newBtn, newBox, el("span", { style: { flex: "1" } }), status, saveBtn);
  const shareBox = share ? shareCard() : null;
  const box = shareBox ? el("div", { class: "stack" }, bar, shareBox.element) : bar;

  async function refresh(selectId) {
    mods = await api.get("/mods");
    clear(select);
    const withFile = [];
    for (const m of mods) {
      const has = m.kinds.includes(kind) || (file === "palette.json" && m.kinds.includes("palette"))
        || (file === "npcs.json" && m.kinds.includes("characters")) || (file === "quests.json" && m.kinds.includes("questlines"));
      withFile.push({ m, has });
    }
    withFile.sort((a, b) => (b.has - a.has) || a.m.id.localeCompare(b.m.id));
    if (!mods.some(m => m.id === defaultId)) select.append(el("option", { value: defaultId, text: `${defaultName || defaultId} (new)` }));
    for (const { m, has } of withFile) {
      select.append(el("option", { value: m.id, text: `${m.name}${has ? "" : " (no " + file + " yet)"}${m.enabled ? "" : " · off"}` }));
    }
    let pick = selectId;
    if (!pick) {
      try {
        // The choice made before the picker was shared across pages (one key per file) counts once, then goes.
        const old = `wc-target:${file}`;
        pick = localStorage.getItem(key) || localStorage.getItem(old);
        localStorage.removeItem(old);
      } catch (e) { /* storage blocked */ }
    }
    if (!pick || ![...select.options].some(o => o.value === pick)) pick = select.options[0]?.value;
    select.value = pick;
    await load(pick);
  }
  async function load(id) {
    current = id;
    try { localStorage.setItem(key, id); } catch (e) { /* storage blocked */ }
    let obj = null;
    if (mods.some(m => m.id === id)) {
      const r = await api.get(`/mods/${encodeURIComponent(id)}/file/${file}`);
      if (r.exists) { try { obj = JSON.parse(r.text); } catch (e) { toast(`${file} in ${id} isn't valid JSON`, "bad"); } }
    }
    setDirty(false);
    shareBox?.show(mods.find(m => m.id === id));
    onLoad(obj, id);
  }
  // Saving to a mod means you want it applied: create it if it's new. A mod that exists but is off
  // is turned on only after its file has been written, so a failed save can't enable old content.
  async function ensureMod(id) {
    const existing = mods.find(m => m.id === id);
    if (!existing) {
      await api.post("/mods", { id, name: id === defaultId ? defaultName : undefined, enabled: true });
      bus.emit("mods-changed");
    }
    return existing;
  }
  async function create(id) {
    if (!id) return;
    try {
      await api.post("/mods", { id, enabled: true });
      bus.emit("mods-changed");
      newBox.hidden = true; newId.value = "";
      await refresh(id);
      toast(`Created mod ${id}`);
    } catch (e) { toast(e.message, "bad"); }
  }
  function setDirty(v) { dirty = v; status.textContent = v ? "Unsaved changes" : ""; }
  // Writes the page's file into the mod; true when it's saved. quiet: no toast (Save as .zip says what it did).
  async function save(quiet = false) {
    try {
      const value = getValue();
      if (value === undefined) return false;   // the page said what's wrong
      const existing = await ensureMod(current);
      const r = await api.put(`/mods/${encodeURIComponent(current)}/file/${file}`, { text: JSON.stringify(value, null, 2) });
      setDirty(false);
      if (r && r.problem) {
        toast(`Saved, but it can't go in the game until this is sorted: ${r.problem}`, "bad");
      } else if (existing && !existing.enabled) {
        await api.patch(`/mods/${encodeURIComponent(current)}`, { enabled: true });
        if (!quiet) toast(`Saved and turned on ${existing.name}. Apply to game to use it.`);
      } else if (!quiet) {
        toast(`Saved ${file} in ${current}. Apply to game to use it.`);
      }
      bus.emit("mods-changed");
      await refresh(current);
      return true;
    } catch (e) { toast(e.message, "bad"); return false; }
  }
  select.addEventListener("change", async () => {
    if (dirty) toast("Switched mods; unsaved changes were dropped");
    await load(select.value);
  });
  newBtn.addEventListener("click", () => { newBox.hidden = !newBox.hidden; if (!newBox.hidden) newId.focus(); });
  saveBtn.addEventListener("click", () => save());

  // ---------- sharing ----------
  function shareCard() {
    const fields = {
      name: el("input", { type: "text", "aria-label": "Mod name", placeholder: "My mod" }),
      author: el("input", { type: "text", "aria-label": "Author", placeholder: "your name" }),
      version: el("input", { type: "text", "aria-label": "Version", placeholder: "1.0", size: "6" }),
      description: el("textarea", { "aria-label": "Description", rows: "2", style: { minHeight: "54px", fontFamily: "var(--body)", fontSize: "0.95rem" },
        placeholder: "What it does, in a sentence or two. People see this before they add it." }),
    };
    const field = (label, input) => el("label", { class: "field" }, el("span", { class: "lbl", text: label }), input);
    const needs = el("p", { class: "note" });
    const picker = el("input", { type: "file", accept: ".json,application/json", hidden: true });
    picker.addEventListener("change", async () => {
      const f = picker.files[0];
      picker.value = "";
      if (!f) return;
      let obj;
      try { obj = JSON.parse(await f.text()); } catch (e) { toast(`${f.name} isn't a ${file} (it isn't valid JSON)`, "bad"); return; }
      if (!obj || typeof obj !== "object" || Array.isArray(obj)) { toast(`${f.name} isn't a ${file}`, "bad"); return; }
      onLoad(obj, current);
      setDirty(true);
      toast(`Loaded ${f.name}. Save to mod to keep it in ${select.selectedOptions[0]?.textContent || current}.`);
    });
    const saveDetails = el("button", { class: "btn small", text: "Save details", onclick: async () => {
      try {
        await ensureMod(current);
        const body = Object.fromEntries(Object.entries(fields).map(([k, i]) => [k, i.value.trim()]));
        if (!body.name) delete body.name;
        await api.patch(`/mods/${encodeURIComponent(current)}`, body);
        toast("Saved the mod's details");
        bus.emit("mods-changed");
        // Not refresh(): that loads the file again, and the page may have changes not saved yet.
        mods = await api.get("/mods");
        const m = mods.find(x => x.id === current), opt = [...select.options].find(o => o.value === current);
        if (m && opt) opt.textContent = opt.textContent.replace(/^.*?(?= \(no |\s·\soff|$)/, m.name);
        show(m);
      } catch (e) { toast(e.message, "bad"); }
    } });
    const zipBtn = el("button", { class: "btn primary small", text: "Save as .zip", onclick: async () => {
      // What's on the page goes in: unsaved changes are saved first.
      if ((dirty || !mods.some(m => m.id === current)) && !await save(true)) return;
      try { toast(`Saved ${await api.download(`/mods/${encodeURIComponent(current)}/zip`)}. Send it to anyone: they drop it on their Mods page.`); }
      catch (e) { toast(e.message, "bad"); }
    } });
    const exportBtn = el("button", { class: "btn small", text: `Export ${file}`, onclick: () => {
      const value = getValue();
      if (value === undefined) return;
      saveFile(`${current}-${file}`, JSON.stringify(value, null, 2) + "\n");
    } });
    const importBtn = el("button", { class: "btn small", text: `Import ${file}…`, onclick: () => picker.click() });
    const element = el("details", { class: "card fold", "data-key": `share:${file}` },
      el("summary", {}, el("h3", { text: "Share" }), el("span", { class: "muted", text: "Save as a .zip for others, or export this page's file" })),
      el("p", { class: "note", text: "A .zip is the whole mod, ready to share: whoever you send it to drops it on Clan Mod Studio's Mods page (or on the file that opens the studio). Its name, author, version and description below go with it." }),
      el("div", { style: { display: "grid", gap: "10px", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" } },
        field("Name", fields.name), field("Author", fields.author), field("Version", fields.version)),
      field("Description", fields.description),
      needs,
      el("div", { class: "row" }, saveDetails, el("span", { style: { flex: "1" } }), zipBtn, exportBtn, importBtn, picker),
      el("p", { class: "note", text: `Export gives just this page's ${file}, to keep or to send to someone making mods; Import loads one into this page (Save to mod keeps it).` }));
    function show(m) {
      fields.name.value = m ? m.name : (current === defaultId ? defaultName : current || "");
      fields.author.value = m ? m.author || "" : "";
      fields.version.value = m ? m.version || "" : "";
      fields.description.value = m ? m.description || "" : "";
      const req = m ? m.requires || [] : [];
      needs.textContent = req.length ? `It needs ${req.map(i => (mods.find(x => x.id === i) || {}).name || i).join(", ")}: whoever adds it is asked to add that too (their Mods page says so).` : "";
      needs.hidden = !req.length;
    }
    return { element, show };
  }
  return { element: box, refresh, markDirty: () => setDirty(true), save: () => save(), get current() { return current; },
           get mods() { return mods; } };
}

export function codePanel(title) {
  const pre = el("pre");
  const node = el("div", { class: "card" },
    el("div", { class: "row spread" }, el("h3", { text: title }),
      el("button", { class: "btn small", text: "Copy", "aria-label": `Copy ${title}`, onclick: () => copy(pre.textContent) })),
    // Focusable, so it scrolls from the keyboard too.
    el("div", { class: "code", tabindex: "0", role: "region", "aria-label": title }, pre));
  return { element: node, set: obj => { pre.textContent = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2); } };
}

export async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast("Copied"); }
  catch (e) { toast("Couldn't copy; select the text and press Ctrl+C", "bad"); }
}

// ---------- input names (Unreal FKey) ----------
const CODE_TO_KEY = {
  Space: "SpaceBar", Enter: "Enter", NumpadEnter: "Enter", Escape: "Escape", Tab: "Tab", Backspace: "BackSpace",
  CapsLock: "CapsLock", ShiftLeft: "LeftShift", ShiftRight: "RightShift", ControlLeft: "LeftControl",
  ControlRight: "RightControl", AltLeft: "LeftAlt", AltRight: "RightAlt", ArrowUp: "Up", ArrowDown: "Down",
  ArrowLeft: "Left", ArrowRight: "Right", Insert: "Insert", Delete: "Delete", Home: "Home", End: "End",
  PageUp: "PageUp", PageDown: "PageDown", Backquote: "Tilde", Minus: "Hyphen", Equal: "Equals",
  BracketLeft: "LeftBracket", BracketRight: "RightBracket", Backslash: "Backslash", Semicolon: "Semicolon",
  Quote: "Apostrophe", Comma: "Comma", Period: "Period", Slash: "Slash", NumpadMultiply: "Multiply",
  NumpadAdd: "Add", NumpadSubtract: "Subtract", NumpadDecimal: "Decimal", NumpadDivide: "Divide",
};
const DIGITS = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"];
function keyFromEvent(e) {
  const c = e.code;
  if (/^Key[A-Z]$/.test(c)) return c.slice(3);
  if (/^Digit\d$/.test(c)) return DIGITS[+c.slice(5)];
  if (/^Numpad\d$/.test(c)) return "NumPad" + DIGITS[+c.slice(6)];
  if (/^F\d{1,2}$/.test(c)) return c;
  return CODE_TO_KEY[c] || null;
}
const MOUSE = ["LeftMouseButton", "MiddleMouseButton", "RightMouseButton", "ThumbMouseButton", "ThumbMouseButton2"];
// Standard Gamepad API layout -> Unreal names.
const PAD_BUTTONS = ["Gamepad_FaceButton_Bottom", "Gamepad_FaceButton_Right", "Gamepad_FaceButton_Left",
  "Gamepad_FaceButton_Top", "Gamepad_LeftShoulder", "Gamepad_RightShoulder", "Gamepad_LeftTrigger",
  "Gamepad_RightTrigger", "Gamepad_Special_Left", "Gamepad_Special_Right", "Gamepad_LeftThumbstick",
  "Gamepad_RightThumbstick", "Gamepad_DPad_Up", "Gamepad_DPad_Down", "Gamepad_DPad_Left", "Gamepad_DPad_Right"];
const PAD_AXES = ["Gamepad_LeftX", "Gamepad_LeftY", "Gamepad_RightX", "Gamepad_RightY"];
const GLYPHS = {
  xbox: { Bottom: "A", Right: "B", Left: "X", Top: "Y", LeftShoulder: "LB", RightShoulder: "RB", LeftTrigger: "LT",
    RightTrigger: "RT", Special_Left: "View", Special_Right: "Menu", LeftThumbstick: "LS click", RightThumbstick: "RS click" },
  playstation: { Bottom: "✕", Right: "○", Left: "□", Top: "△", LeftShoulder: "L1", RightShoulder: "R1", LeftTrigger: "L2",
    RightTrigger: "R2", Special_Left: "Create", Special_Right: "Options", LeftThumbstick: "L3", RightThumbstick: "R3" },
  switch: { Bottom: "B", Right: "A", Left: "Y", Top: "X", LeftShoulder: "L", RightShoulder: "R", LeftTrigger: "ZL",
    RightTrigger: "ZR", Special_Left: "−", Special_Right: "+", LeftThumbstick: "L-stick click", RightThumbstick: "R-stick click" },
};
const KEY_LABELS = {
  SpaceBar: "Space", LeftShift: "Left Shift", RightShift: "Right Shift", LeftControl: "Left Ctrl", RightControl: "Right Ctrl",
  LeftAlt: "Left Alt", RightAlt: "Right Alt", Up: "↑", Down: "↓", Left: "←", Right: "→", BackSpace: "Backspace",
  LeftMouseButton: "Left mouse", RightMouseButton: "Right mouse", MiddleMouseButton: "Middle mouse",
  ThumbMouseButton: "Mouse 4", ThumbMouseButton2: "Mouse 5", MouseScrollUp: "Wheel up", MouseScrollDown: "Wheel down",
  Tilde: "`", Hyphen: "-", Equals: "=", LeftBracket: "[", RightBracket: "]", Semicolon: ";", Apostrophe: "'",
  Comma: ",", Period: ".", Slash: "/", Backslash: "\\",
  Gamepad_LeftX: "Left stick ↔", Gamepad_LeftY: "Left stick ↕", Gamepad_RightX: "Right stick ↔", Gamepad_RightY: "Right stick ↕",
  Gamepad_DPad_Up: "D-pad ↑", Gamepad_DPad_Down: "D-pad ↓", Gamepad_DPad_Left: "D-pad ←", Gamepad_DPad_Right: "D-pad →",
};
function keyLabel(key, style = "xbox") {
  if (!key) return "—";
  const m = /^Gamepad_(?:FaceButton_)?(.+)$/.exec(key);
  if (m && GLYPHS[style][m[1]]) return GLYPHS[style][m[1]];
  if (KEY_LABELS[key]) return KEY_LABELS[key];
  if (key.startsWith("NumPad")) return "Num " + DIGITS.indexOf(key.slice(6));
  const d = DIGITS.indexOf(key);
  return d >= 0 ? String(d) : key;
}
export const input = { keyFromEvent, MOUSE, PAD_BUTTONS, PAD_AXES, GLYPHS, keyLabel };

// ---------- small save-path helpers ----------
export function getPath(obj, path) {
  let node = obj;
  for (const part of path.split("/").filter(Boolean)) {
    if (node == null) return undefined;
    node = Array.isArray(node) ? node[Number(part)] : node[part];
  }
  return node;
}
