// A script mod's settings.json as the rows of its Settings block on the Mods page, by the same rules as the page
// the script bootstrap makes for it in the mod menu (wcmods/lua/script_bootstrap.lua): true or false is a switch,
// a number a number box, "#rrggbb" a colour, other text a text box, a "_" key with text a note, and anything
// nested is shown as it is, to change in the file. "_help_<key>" shows under that key's row, and "_min_<key>" and
// "_max_<key>" bound its number. docs/formats.md, "scripts/ and settings.json", has the rules for people.

// "heal_key" as "Heal key", "healKey" too (the bootstrap's label()).
export function label(key) {
  const s = String(key).replace(/_/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// The file's top-level keys in the order it has them, which of its numbers are written with a point or an
// exponent (12.0, 1.5, 1e3: those stay numbers with a fraction, for the game too, when they're written back), and
// each value's text as the file has it (a value left as it was is written back the same). JSON.parse keeps none
// of these (it puts keys that look like whole numbers first, and reads 12.0 as 12). A key written twice is in
// `keys` twice; its float and its text are the last one's, the value JSON.parse keeps.
export function scan(text) {
  const keys = [], floats = new Set(), raw = {};
  let depth = 0, i = 0, open = null;   // open: the key whose value is being read, and where it starts
  const space = k => { while (k < text.length && /\s/.test(text[k])) k++; return k; };
  const close = end => { if (open) raw[open.key] = text.slice(open.start, end).trim(); open = null; };
  while (i < text.length) {
    const c = text[i];
    if (c === '"') {
      let j = i + 1;
      while (j < text.length && text[j] !== '"') j += text[j] === "\\" ? 2 : 1;
      const quoted = text.slice(i, j + 1);
      i = j + 1;
      if (depth === 1 && !open) {
        let k = space(i);
        if (text[k] === ":") {
          const key = JSON.parse(quoted);
          keys.push(key);
          k = space(k + 1);
          const m = /^-?\d+(\.\d+)?([eE][+-]?\d+)?/.exec(text.slice(k, k + 40));
          if (m && (m[1] || m[2])) floats.add(key);
          else floats.delete(key);
          open = { key, start: k };
          i = k;
        }
      }
      continue;
    }
    if (depth === 1 && (c === "," || c === "}")) close(i);
    if (c === "{" || c === "[") depth++;
    else if (c === "}" || c === "]") depth--;
    i++;
  }
  return { keys, floats, raw };
}

// settings.json's text as { values, order, floats, raw, original, twice }; an Error saying what's wrong when it
// isn't JSON holding an object. Change `values` (a copy), never `original`. A key the file has twice counts as
// its last one, as JSON.parse and the game read it: `twice` names it, and `order` has it once, where the last one
// is, so a Save writes it once.
export function read(text) {
  let values;
  try { values = JSON.parse(text.replace(/^﻿/, "")); } catch (e) { throw new Error(`settings.json isn't valid JSON (${e.message})`); }
  if (!values || typeof values !== "object" || Array.isArray(values)) throw new Error('settings.json should hold an object: {"name": value, ...}');
  const { keys, floats, raw } = scan(text);
  const order = [], twice = [];
  for (const k of keys) {
    if (!Object.hasOwn(values, k)) continue;
    const at = order.indexOf(k);
    if (at >= 0) {
      order.splice(at, 1);
      if (!twice.includes(k)) twice.push(k);
    }
    order.push(k);
  }
  for (const k of Object.keys(values)) if (!order.includes(k)) order.push(k);
  return { values: { ...values }, order, floats, raw, original: values, twice };
}

const isColour = v => typeof v === "string" && /^#[0-9a-f]{6}$/i.test(v);
// The key a "_help_x", "_min_x" or "_max_x" goes with, when the file has it.
function partOf(key, values) {
  const m = /^_(help|min|max)_(.+)$/.exec(key);
  return m && m[2] in values ? m[2] : null;
}

// The rows to draw, in the file's order: { key, kind: "switch" | "number" | "colour" | "text" | "note" | "nested",
// label, value, help, and for a number whole, step, min, max, and `text`, the file's own, for a whole number
// past 2^53 (JavaScript's numbers lose its last digits: the box shows the file's, and it can't be changed here).
export function rows({ values, order, floats, raw = {} }) {
  const out = [];
  for (const key of order) {
    if (partOf(key, values)) continue;
    const value = values[key];
    if (key.startsWith("_")) {
      if (typeof value === "string") out.push({ key, kind: "note", value });
      continue;
    }
    const row = { key, label: label(key), value, help: typeof values[`_help_${key}`] === "string" ? values[`_help_${key}`] : null };
    if (typeof value === "boolean") row.kind = "switch";
    else if (typeof value === "number") {
      const whole = !floats.has(key) && Number.isInteger(value);
      Object.assign(row, { kind: "number", whole, step: whole ? 1 : 0.1 });
      if (typeof values[`_min_${key}`] === "number") row.min = values[`_min_${key}`];
      if (typeof values[`_max_${key}`] === "number") row.max = values[`_max_${key}`];
      if (Number.isInteger(value) && !Number.isSafeInteger(value) && typeof raw[key] === "string") row.text = raw[key];
    } else if (isColour(value)) row.kind = "colour";
    else if (typeof value === "string") row.kind = "text";
    else row.kind = "nested";
    out.push(row);
  }
  return out;
}

// A number as JSON: one with a fraction stays one (12 written as 12.0) when `float`.
function number(v, float) {
  const s = JSON.stringify(v);
  return float && Number.isInteger(v) && !/[eE]/.test(s) ? `${s}.0` : s;
}

// The file's text again: its keys in its order, two spaces in, a value left as it was just as the file had it,
// and the numbers written with a point still with one.
export function write({ values, order, floats, raw = {}, original = {} }) {
  const same = k => k in raw && k in original && JSON.stringify(original[k]) === JSON.stringify(values[k]);
  const parts = order.filter(k => k in values).map(k => {
    const v = values[k];
    const text = same(k) ? raw[k]
      : typeof v === "number" ? number(v, floats.has(k)) : JSON.stringify(v, null, 2).replace(/\n/g, "\n  ");
    return `  ${JSON.stringify(k)}: ${text}`;
  });
  return parts.length ? `{\n${parts.join(",\n")}\n}\n` : "{}\n";
}

// What's wrong with a value typed into a row, in words, or null: a number that isn't one, or out of its bounds,
// or past 2^53 (one the file has that big is fine left as it is).
export function problem(row, typed) {
  if (row.kind !== "number") return null;
  if (row.text !== undefined && String(typed).trim() === row.text) return null;
  const n = Number(typed);
  if (typed === "" || !Number.isFinite(n)) return `${row.label} should be a number`;
  if (Math.abs(n) > Number.MAX_SAFE_INTEGER) {
    return `${row.label} can't be changed here to a number that big (past ${Number.MAX_SAFE_INTEGER} it loses its last digits): change it in the file itself`;
  }
  if (row.whole && !Number.isInteger(n)) return `${row.label} should be a whole number`;
  if (row.min !== undefined && n < row.min) return `${row.label} should be at least ${row.min}`;
  if (row.max !== undefined && n > row.max) return `${row.label} should be at most ${row.max}`;
  return null;
}
