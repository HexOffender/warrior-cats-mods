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
};

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
export const clear = node => { node.textContent = ""; return node; };

export function toast(message, kind = "info") {
  const box = document.getElementById("toasts");
  if (!box) return;
  const t = el("div", { class: `toast ${kind === "bad" ? "bad" : ""}`, role: "status", text: message });
  box.append(t);
  setTimeout(() => t.remove(), kind === "bad" ? 6000 : 3000);
}

// Two-step button: first click arms it, second click within 4s runs it (the frame has no confirm()).
export function confirmButton(label, armedLabel, onConfirm, cls = "btn") {
  const b = el("button", { class: cls, text: label });
  let armed = null;
  b.addEventListener("click", async () => {
    if (!armed) {
      b.textContent = armedLabel;
      armed = setTimeout(() => { armed = null; b.textContent = label; }, 4000);
      return;
    }
    clearTimeout(armed); armed = null; b.textContent = label;
    await onConfirm();
  });
  return b;
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
// call target.save(obj) to write the file. Picks `defaultId` (creating it on first save) when nothing is chosen.
export function modTarget({ file, defaultId, defaultName, onLoad, getValue }) {
  const key = `wc-target:${file}`;
  let mods = [], current = null, dirty = false;
  const select = el("select", { "aria-label": `Mod that stores ${file}` });
  const status = el("span", { class: "dirty" });
  const saveBtn = el("button", { class: "btn primary", text: "Save to mod" });
  const newBtn = el("button", { class: "btn ghost", text: "New mod…" });
  const newBox = el("span", { class: "row", hidden: true });
  const newId = el("input", { type: "text", placeholder: "my-mod-name", "aria-label": "New mod folder name", spellcheck: "false" });
  newBox.append(newId, el("button", { class: "btn small", text: "Create", onclick: () => create(newId.value.trim()) }));
  const box = el("div", { class: "target" },
    el("span", { class: "lbl", text: "Editing mod" }), select, newBtn, newBox, el("span", { style: { flex: "1" } }), status, saveBtn);

  async function refresh(selectId) {
    mods = await api.get("/mods");
    clear(select);
    const withFile = [];
    for (const m of mods) {
      const has = m.kinds.includes(file.replace(".json", "")) || (file === "palette.json" && m.kinds.includes("palette"));
      withFile.push({ m, has });
    }
    withFile.sort((a, b) => (b.has - a.has) || a.m.id.localeCompare(b.m.id));
    if (!mods.some(m => m.id === defaultId)) select.append(el("option", { value: defaultId, text: `${defaultName || defaultId} (new)` }));
    for (const { m, has } of withFile) {
      select.append(el("option", { value: m.id, text: `${m.name}${has ? "" : " (no " + file + " yet)"}${m.enabled ? "" : " · off"}` }));
    }
    let pick = selectId;
    if (!pick) { try { pick = localStorage.getItem(key); } catch (e) { /* storage blocked */ } }
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
    onLoad(obj, id);
  }
  // Saving to a mod means you want it applied: create it, or turn it on if it's off.
  async function ensureMod(id) {
    const existing = mods.find(m => m.id === id);
    if (!existing) {
      await api.post("/mods", { id, name: id === defaultId ? defaultName : undefined, enabled: true });
      bus.emit("mods-changed");
    } else if (!existing.enabled) {
      await api.patch(`/mods/${encodeURIComponent(id)}`, { enabled: true });
      toast(`Turned on ${existing.name} so this applies when you install`);
      bus.emit("mods-changed");
    }
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
  select.addEventListener("change", async () => {
    if (dirty) toast("Switched mods; unsaved changes were dropped");
    await load(select.value);
  });
  newBtn.addEventListener("click", () => { newBox.hidden = !newBox.hidden; if (!newBox.hidden) newId.focus(); });
  saveBtn.addEventListener("click", async () => {
    try {
      const value = getValue();
      await ensureMod(current);
      await api.put(`/mods/${encodeURIComponent(current)}/file/${file}`, { text: JSON.stringify(value, null, 2) });
      setDirty(false);
      bus.emit("mods-changed");
      toast(`Saved ${file} in ${current}. Install mods to apply it.`);
      await refresh(current);
    } catch (e) { toast(e.message, "bad"); }
  });
  return { element: box, refresh, markDirty: () => setDirty(true), get current() { return current; } };
}

export function codePanel(title) {
  const pre = el("pre");
  const node = el("div", { class: "card" },
    el("div", { class: "row spread" }, el("h3", { text: title }),
      el("button", { class: "btn small", text: "Copy", onclick: () => copy(pre.textContent) })),
    el("div", { class: "code" }, pre));
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
