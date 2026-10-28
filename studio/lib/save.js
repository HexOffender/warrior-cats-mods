// The Save page's logic, without the page (studio/sections/save.js draws it): the list of changes to make, in
// save.json's shape ({ set, add, remove }), checked against the save and against the ranges the game takes;
// a save path in words; which values are only shown, not changed; and the presets. The words and the ranges
// come from the server (GET /api/save: wcmods/sections/savedit.py WORDS and RANGES), one home for both.

export const ITEM_ROOT = "Gameplay.Inventory.";
export const HERBS = ["Consumable.SmallHealingHerb", "Consumable.MediumHealingHerb", "Consumable.BigHealingHerb", "Consumable.SmallCatnip"]
  .map(t => ITEM_ROOT + t);

export function getPath(obj, path) {
  let node = obj;
  for (const part of String(path).split("/").filter(Boolean)) {
    if (node == null || typeof node !== "object") return undefined;
    node = Array.isArray(node) ? node[Number(part)] : node[part];
  }
  return node;
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// A key in words: "MasterVolume" -> "Master volume", "SmallHealingHerb" -> "Small Healing Herb".
export function words(name) {
  const spaced = String(name).replace(/[._]/g, " ").replace(/(?<=[a-z0-9])(?=[A-Z])/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
// An item's name from its tag alone, when the game's names can't be read.
export function itemWords(tag) {
  const rest = tag.startsWith(ITEM_ROOT) ? tag.slice(ITEM_ROOT.length) : tag;
  const parts = rest.split(".");
  return words((parts.length > 1 ? parts.slice(1) : parts).join(" "));
}
// A save path in words, as savedit.label says it: "Fawnstar's level". say: { words, cats: {slot: name},
// current: the slot being played, items: {tag: name} }.
export function describe(path, say = {}) {
  const last = words(String(path).replace(/\/$/, "").split("/").pop());
  for (const w of say.words || []) {
    const m = new RegExp(w.match).exec(path);
    if (!m) continue;
    const said = { name: last.toLowerCase() };
    if (w.say.includes("{cat}")) said.cat = say.cats?.[m[1]] || (m[1] === String(say.current) ? "your cat" : `cat slot ${m[1]}`);
    if (w.say.includes("{item}")) said.item = say.items?.[m[2]] || itemWords(m[2]);
    return w.say.replace(/\{(\w+)\}/g, (_, k) => said[k] ?? "");
  }
  return last;
}
// A value in words: none, on, off, a number, or the text.
export function said(v) {
  if (v === undefined || v === null) return "none";
  if (typeof v === "boolean") return v ? "on" : "off";
  return typeof v === "string" ? v : JSON.stringify(v);
}

// Why a value can't go at a path, in words (savedit.range_problem); null when it's fine.
export function rangeProblem(path, value, ranges = []) {
  for (const r of ranges) {
    if (!new RegExp(r.match).test(path)) continue;
    if (typeof value !== "number" || !Number.isFinite(value)) return `${r.what} has to be a number`;
    if (r.whole && !Number.isInteger(value)) return `${r.what} has to be a whole number`;
    if (value < r.min || (r.max !== null && r.max !== undefined && value > r.max)) {
      return `${r.what} goes from ${r.min}${r.max !== null && r.max !== undefined ? ` to ${r.max}` : " or more"}, not ${value}`;
    }
    return null;
  }
  return null;
}
// The range for a path, for a number box's min and max ({} for none).
export function rangeFor(path, ranges = []) {
  return ranges.find(r => new RegExp(r.match).test(path)) || {};
}

// Values the page shows but doesn't change, and why (null: it can be changed here).
export function readOnly(path, value) {
  if (/^Shared\/Input(Keyboard|Gamepad)(\/|$)/.test(path)) return "Key bindings: the game keeps its own copy and ignores changes here. The Controls page changes them.";
  if (/(^|\/)Customization$/.test(path)) return "A cat's record, written as one piece: one wrong character spoils it. The Your cat and Names pages change cats.";
  if (/\/State\/(Health|Stamina)$/.test(path)) return "Refills in play: stamina comes back at 20 a second and a fight starts at full health, so a change here doesn't last.";
  if (/\/GameplayProgression\/Stats$/.test(path)) return "Changed in the Combat stats card, number by number.";
  if (typeof value === "string" && /^\(.*=.*\)$/s.test(value.trim())) return "Written by the game as one piece of text: one wrong character spoils it.";
  return null;
}

// ---------- the list of changes to make ----------
export const emptyList = () => ({ set: {}, add: {}, remove: [] });
export const isEmpty = list => !Object.keys(list.set).length && !Object.keys(list.add).length && !list.remove.length;
// A save.json (or what sessionStorage kept) as a list; anything that isn't one is an empty list.
export function fromSaveJson(obj) {
  const list = emptyList();
  if (!obj || typeof obj !== "object") return list;
  for (const [k, v] of Object.entries(obj.set || {})) if (!k.startsWith("_")) list.set[k] = v;
  for (const [o, entries] of Object.entries(obj.add || {})) {
    if (o.startsWith("_") || !entries || typeof entries !== "object") continue;
    list.add[o] = { ...entries };
  }
  if (Array.isArray(obj.remove)) list.remove = obj.remove.filter(p => typeof p === "string");
  return list;
}
export function toSaveJson(list) {
  const out = { _help: "Written by Clan Mod Studio's Save page. Each change is made once in the save of whoever installs this mod, after a backup.", set: { ...list.set }, add: JSON.parse(JSON.stringify(list.add)) };
  if (list.remove.length) out.remove = [...list.remove];
  return out;
}
// What the route takes: [{path, value}], [{add, key, value}], [{remove}].
export function toChanges(list) {
  return [
    ...Object.entries(list.set).map(([path, value]) => ({ path, value })),
    ...Object.entries(list.add).flatMap(([obj, entries]) => Object.entries(entries).map(([key, value]) => ({ add: obj, key, value }))),
    ...list.remove.map(path => ({ remove: path })),
  ];
}
// The value a path will have once the list is made (undefined: not there).
export function after(list, data, path) {
  if (list.remove.includes(path)) return undefined;
  if (path in list.set) return list.set[path];
  const at = path.lastIndexOf("/");
  const added = list.add[path.slice(0, at)];
  if (added && path.slice(at + 1) in added) return added[path.slice(at + 1)];
  return getPath(data, path);
}
// Set a value the save has. The save's own value takes the change away. Returns the list.
export function setValue(list, data, path, value) {
  list.remove = list.remove.filter(p => p !== path);
  if (same(getPath(data, path), value)) delete list.set[path];
  else list.set[path] = value;
  return list;
}
// Add a key to an object (an item to the inventory); a key the save has already becomes a set of its value.
export function addKey(list, data, objPath, key, value) {
  const path = `${objPath}/${key}`;
  if (getPath(data, path) !== undefined) return setValue(list, data, path, value);
  (list.add[objPath] ||= {})[key] = value;
  return list;
}
// Take a key out: an added one leaves the list; one the save has is removed from the save.
export function removeKey(list, data, path) {
  const at = path.lastIndexOf("/"), obj = path.slice(0, at), key = path.slice(at + 1);
  if (list.add[obj] && key in list.add[obj]) {
    delete list.add[obj][key];
    if (!Object.keys(list.add[obj]).length) delete list.add[obj];
    return list;
  }
  delete list.set[path];
  if (getPath(data, path) !== undefined && !list.remove.includes(path)) list.remove.push(path);
  return list;
}
// Forget one change in the list (the page's remove on a line of Changes to make).
export function forget(list, change) {
  if (change.kind === "set") delete list.set[change.path];
  else if (change.kind === "add") removeKey(list, {}, change.path);
  else list.remove = list.remove.filter(p => p !== change.path);
  return list;
}
// The list in words, for Changes to make: [{kind, path, label, was, now}].
export function entries(list, data, say = {}) {
  const out = [];
  for (const [path, value] of Object.entries(list.set)) out.push({ kind: "set", path, label: describe(path, say), was: getPath(data, path), now: value });
  for (const [obj, adds] of Object.entries(list.add)) {
    for (const [key, value] of Object.entries(adds)) {
      const path = `${obj}/${key}`;
      out.push({ kind: "add", path, label: describe(path, say), was: getPath(data, path), now: value });
    }
  }
  for (const path of list.remove) out.push({ kind: "remove", path, label: describe(path, say), was: getPath(data, path), now: undefined });
  return out;
}
// Every change's problem against the ranges, in words.
export function problems(list, ranges, say = {}) {
  const out = [];
  for (const c of entries(list, {}, say)) {
    if (c.kind === "remove") continue;
    const why = rangeProblem(c.path, c.now, ranges);
    if (why) out.push(`${c.label}: ${why}`);
  }
  return out;
}

// ---------- presets ----------
// What a preset puts in the list for the cat in `slot` (only the values its save has).
export function preset(name, list, data, slot) {
  const P = `${slot}/GameplayProgression`;
  const has = p => getPath(data, p) !== undefined;
  if (name === "max-level") {
    if (has(`${P}/Level`)) setValue(list, data, `${P}/Level`, 20);
    if (has(`${P}/Experience`)) setValue(list, data, `${P}/Experience`, 0);
  } else if (name === "fill-pile") {
    if (has(`${P}/FreshKill/Value`)) setValue(list, data, `${P}/FreshKill/Value`, 100);
  } else if (name === "give-herbs") {
    const inv = `${P}/State/Inventory`;
    if (getPath(data, inv) && typeof getPath(data, inv) === "object") {
      for (const tag of HERBS) addKey(list, data, inv, tag, (Number(getPath(data, `${inv}/${tag}`)) || 0) + 5);
    }
  }
  return list;
}

// ---------- combat stats: one string, "(Prowess=90.000000,Strength=85.000000)" ----------
export function readStats(text) {
  return Object.fromEntries([...String(text || "").matchAll(/(\w+)=(-?\d+(?:\.\d+)?)/g)].map(m => [m[1], Number(m[2])]));
}
// The string with one stat changed, everything else in it as it was.
export function writeStat(text, name, value) {
  const re = new RegExp(`(^|[,(])(${name})=(-?\\d+(?:\\.\\d+)?)`);
  return String(text).replace(re, (_, lead, key) => `${lead}${key}=${Number(value).toFixed(6)}`);
}
