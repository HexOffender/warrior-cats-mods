// The Your cat page's cats.json, without the page: each cat's look read from the file into what the page edits, and
// written back. What the build knows (the colour parts, colour slots, scars and shape parts) comes in as `known`,
// from GET /cat, so wcmods/catcolours.py stays the one place that says it; tests/studio/catlook.test.mjs runs these
// in node.
//
// One cat's look: { colours: {part: "#RRGGBB"}, slots: {part: n}, scars: {place: n}, look: {part: n, size: x},
// raw: {colours|slots|scars|look: {key: value}}, extra: {key: value}, notes: {"_key": value}, inner: {colours|slots|
// scars|look: {"_key": value}} }. raw and extra hold
// what the page can't change (a part the build doesn't know, a number past the game's, a colour it can't read, a
// key cats.json hasn't got): written back as they were, and listed on the page, each with a Remove button, so
// nothing goes unsaid. notes and inner are "_" keys (the cat's own, and its parts'), written back as they were and
// not listed.
import { color } from "./colour.js";

export const KEYS = ["colours", "slots", "scars", "look"];
const isObject = v => v !== null && typeof v === "object" && !Array.isArray(v);

export function blank() {
  const parts = () => ({ colours: {}, slots: {}, scars: {}, look: {} });
  return { ...parts(), raw: parts(), extra: {}, notes: {}, inner: parts() };
}

// known: { colours: [part], slots: [part], eyeSlots: [part], lookMax: {part: highest}, size: [lo, hi],
// scars: {place: [[name, label], ...]}, gameSlots }: what GET /cat says the build takes (see knownFrom).
export function knownFrom(info) {
  return {
    colours: Object.keys(info.parts || {}),
    slots: info.slot_parts || ["fur", "pattern", "marking", "eye_left", "eye_right"],
    lookMax: (info.look || {}).parts || {},
    size: (info.look || {}).size || [0.05, 1.5],
    scars: (info.scars || {}).types || {},
    gameSlots: info.game_slots || 25,
  };
}

// A scar by its name ("notch-left") or number, as a number (0 for "none"); undefined when it isn't one the page shows.
function scarNumber(known, place, v) {
  const types = known.scars[place] || [];
  if (v === "none") return 0;
  if (typeof v === "string") { const i = types.findIndex(t => t[0] === v); return i < 0 ? undefined : i + 1; }
  return Number.isInteger(v) && v >= 0 && v <= types.length ? v : undefined;
}

// One cat's entry (an object, or anything else for none) as the page's look.
export function parseOne(p, known) {
  const l = blank();
  if (!isObject(p)) return l;
  for (const [k, v] of Object.entries(p)) {
    if (k.startsWith("_")) l.notes[k] = v;
    else if (!KEYS.includes(k)) l.extra[k] = v;
    else if (k === "scars" && v === "none") for (const place of Object.keys(known.scars)) l.scars[place] = 0;
    else if (!isObject(v)) l.extra[k] = v;     // a part that isn't a list of its own: kept, as written
  }
  const each = (key, fn) => {
    if (!isObject(p[key])) return;
    for (const [k, v] of Object.entries(p[key])) {
      if (k.startsWith("_")) { l.inner[key][k] = v; continue; }
      if (!fn(k, v)) l.raw[key][k] = v;
    }
  };
  // Colours in any form the build reads ("red", [255, 0, 0], "#ff000080"); the page writes them back as #RRGGBB.
  each("colours", (k, v) => {
    const c = color.parse(v);
    if (!known.colours.includes(k) || !c) return false;
    l.colours[k] = c;
    return true;
  });
  // Slots: the coat and the eyes are the game's 25; patterns and markings any number, new ones a palette adds too.
  each("slots", (k, v) => {
    const capped = k === "fur" || k === "eyes" || k === "eye_left" || k === "eye_right";
    if (!Number.isInteger(v) || v < 0 || (capped && v >= known.gameSlots)) return false;
    if (k === "eyes") { l.slots.eye_left = v; l.slots.eye_right = v; return true; }
    if (!known.slots.includes(k)) return false;
    l.slots[k] = v;
    return true;
  });
  // Scars by name or number; "body" is the save's word for the back.
  each("scars", (k, v) => {
    const place = k === "body" ? "back" : k;
    const n = place in known.scars ? scarNumber(known, place, v) : undefined;
    if (n === undefined) return false;
    l.scars[place] = n;
    return true;
  });
  // The shape: each part one of the game's (0 to its highest), and the size a scale.
  each("look", (k, v) => {
    if (k === "size") {
      const [lo, hi] = known.size;
      if (typeof v !== "number" || !(v >= lo && v <= hi)) return false;
    } else if (!(k in known.lookMax) || !Number.isInteger(v) || v < 0 || v > known.lookMax[k]) return false;
    l.look[k] = v;
    return true;
  });
  return l;
}

// One cat's look as its cats.json entry: what the page can't change first, then the page's own choices over it.
export function oneJson(l, known) {
  const o = { ...l.extra, ...l.notes };
  const part = (key, mine) => {
    const out = { ...l.raw[key], ...l.inner[key], ...mine };
    if (Object.keys(out).length) o[key] = out;
  };
  part("colours", l.colours);
  const slots = { ...l.slots };
  if (slots.eye_left !== undefined && slots.eye_left === slots.eye_right) {
    slots.eyes = slots.eye_left; delete slots.eye_left; delete slots.eye_right;
  }
  part("slots", slots);
  const places = Object.keys(known.scars), scars = Object.entries(l.scars);
  if (!Object.keys(l.raw.scars).length && !Object.keys(l.inner.scars).length && places.length
      && scars.length === places.length && scars.every(([, n]) => n === 0)) o.scars = "none";
  else {
    const named = {};
    for (const place of places) {
      if (!(place in l.scars)) continue;
      const n = l.scars[place];
      named[place] = n === 0 ? "none" : ((known.scars[place] || [])[n - 1] || [])[0] || n;
    }
    part("scars", named);
  }
  part("look", l.look);
  return o;
}

// The whole file: every cat's look (by its key; "player" for yours) and the file's own other keys. A cat's entry that
// isn't an object ("player": "none", "cats": {"X": null}) is one of those, kept as written (fileExtra "player" or
// "cats.X") and listed, until the page sets a look for that cat (lookFor()), which then takes its place.
export function load(obj, known) {
  const src = isObject(obj) ? obj : {};
  const looks = { player: parseOne(src.player, known) }, fileExtra = {};
  for (const [k, v] of Object.entries(src)) {   // in the file's order, so the lists follow it
    if (k === "cats" && isObject(v)) {
      for (const [t, c] of Object.entries(v)) {
        if (t.startsWith("_") || !isObject(c)) fileExtra[`cats.${t}`] = c;
        else looks[t] = parseOne(c, known);
      }
    } else if (!(k === "player" && isObject(v)) && !(k === "_help" && ownHelp(v))) fileExtra[k] = v;   // a hand-written _help too
  }
  return { looks, fileExtra };
}
export const HELP = "Written by Clan Mod Studio. See docs/formats.md, cats.json.";
// A _help this page wrote is written afresh; one written by hand is kept.
const ownHelp = v => typeof v === "string" && v.startsWith("Written by Clan Mod Studio");
// Whether the page sets a look of its own for the cat a fileExtra key is about ("player", "cats.X", or "cats" written
// as something other than a list of cats: any other cat): Save writes the page's in its place.
export function lookFor(looks, where, known) {
  const has = t => !!looks[t] && Object.keys(oneJson(looks[t], known)).length > 0;
  if (where === "cats") return Object.keys(looks).some(t => t !== "player" && has(t));
  const t = where === "player" ? "player" : where.startsWith("cats.") && !where.startsWith("cats._") ? where.slice(5) : null;
  return t !== null && has(t);
}
export function toJson(looks, fileExtra, known) {
  const player = oneJson(looks.player || blank(), known), cats = {};
  for (const [k, v] of Object.entries(fileExtra)) if (k.startsWith("cats.")) cats[k.slice(5)] = v;
  for (const [t, l] of Object.entries(looks)) {
    if (t === "player") continue;
    const o = oneJson(l, known);
    if (Object.keys(o).length) cats[t] = o;   // over a "cats.X" written as something else
  }
  const rest = Object.fromEntries(Object.entries(fileExtra).filter(([k]) => !k.startsWith("cats.")
    && !((k === "player" || k === "cats") && lookFor(looks, k, known))));
  return { _help: HELP, ...(Object.keys(player).length ? { player } : {}), ...(Object.keys(cats).length ? { cats } : {}), ...rest };
}

// What the page can't change about one cat (and, with fileExtra, about the file), for its lists: [{where, value,
// remove()}], each remove() taking the entry out.
export function cantChange(l, fileExtra = null) {
  const out = [];
  for (const k of Object.keys(l.extra)) out.push({ where: k, value: l.extra[k], remove: () => { delete l.extra[k]; } });
  for (const key of KEYS) {
    for (const k of Object.keys(l.raw[key])) out.push({ where: `${key}.${k}`, value: l.raw[key][k], remove: () => { delete l.raw[key][k]; } });
  }
  if (fileExtra) {
    for (const k of Object.keys(fileExtra)) {
      if (!k.startsWith("_") && !k.startsWith("cats._")) out.push({ where: k, value: fileExtra[k], remove: () => { delete fileExtra[k]; } });
    }
  }
  return out;
}
