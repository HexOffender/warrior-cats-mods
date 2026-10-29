// The Palettes page's palette.json, without the page: reading a file into what the page edits and writing it
// back, which eye row a key means, the number a new colour takes, the whole-tab changes (Start from, Game
// colours, Reset tab, the moods) and the eye strips the preview draws. The game's eye names, its colour tables
// and how many colours each table has come in as arguments, so tests/studio/palette.test.mjs runs these in node.
//
// The page's state: { eyes: {row: {mode: "single"|"grad", colors: ["#RRGGBB", ...]}}, fur|pattern|marking:
// {slot: "#RRGGBB"}, kept: the file's other parts, as they were, notes: {part: {"_key": value}}, unread: [{section,
// key, value, why, slot?}] }. unread holds what the page can't show (a misspelt eye, a coat past the game's, a part a
// palette hasn't got): each is written back as it was until its Remove button takes it out, or until the page sets the
// colour it names (slot: that eye row or colour number), whose own then takes its place (replaced()), so nothing goes
// unsaid.
import { color } from "./colour.js";

export const PARTS = ["fur", "pattern", "marking"];       // the game's colour tables, by slot number
// The ones that take new colours: pattern and marking as new slots (palettes.GROWABLE), and coats as coat presets
// the cat maker offers the same way (palettes.fur_presets: the game's coat table can't grow).
export const GROWABLE = ["fur", "pattern", "marking"];
// The file's parts the page doesn't edit, kept as they were: the cat maker's eye buttons, coat presets, and the
// palette's own name and description (palettes.SECTIONS, and what palettes.load skips).
export const KEPT = new Set(["iris_ui", "coats", "name", "description"]);
export const HELP = "Written by Clan Mod Studio. Eye keys are the game's eye colour names; coat, pattern and marking keys " +
  "are colour numbers, counted from 0. See docs/formats.md, palette.json.";
const WORD = { eyes: "Eyes", fur: "Coat", pattern: "Pattern", marking: "Markings" };
const NOUN = { fur: "coat", pattern: "pattern", marking: "marking" };
// A _help this page wrote is written afresh; one written by hand is kept, as every "_" key is.
const ownHelp = v => typeof v === "string" && v.startsWith("Written by Clan Mod Studio");

export function blank(kept = {}) {
  return { eyes: {}, fur: {}, pattern: {}, marking: {}, kept, notes: {}, unread: [] };
}
const isObject = v => v !== null && typeof v === "object" && !Array.isArray(v);
// A list whose first value isn't a number is a gradient; [r, g, b] is one colour (as palettes.load tells them apart).
const isGradient = v => Array.isArray(v) && v.length > 0 && typeof v[0] !== "number" && typeof v[0] !== "boolean";
// A key the browser puts first in an object, in number order, wherever the file had it ("3" or "9", not "03" or
// "iris9"): beside another key for the same colour, which of the two is later in the file can't be told.
const numberFirst = k => /^(0|[1-9][0-9]{0,8})$/.test(k);

// An eye row in the page's words: row 0 is the eye white and the "Dlc" rows are extra eyes from a game add-on;
// the rest go by the game's names. lower: as it reads inside a sentence ("the eye white").
export function eyeWord(labels, row, lower = false) {
  const m = /^dlc([0-9]*)$/i.exec((labels && labels[row]) || "");   // as eyeGroups tells them
  const word = row === 0 ? "Eye white" : m ? `Extra eye ${m[1]}`.trim() : (labels && labels[row]) || `Eye ${row}`;
  return !lower ? word : row === 0 ? "the eye white" : m ? `extra eye ${m[1]}`.trim() : word;
}

// The row an eye key means, as wcmods/eyeatlas.resolve finds it: one of the game's names in any case, then
// "irisN", "rowN" or a number that's one of the rows. null for anything else.
export function eyeRow(labels, key) {
  const k = String(key).trim().toLowerCase();
  const i = labels.findIndex(l => l.toLowerCase() === k);
  if (i >= 0) return i;
  const m = /^(?:row|iris)?([0-9]+)$/.exec(k);
  return m && Number(m[1]) < labels.length ? Number(m[1]) : null;
}

// A palette.json (an object, or null for none) as the page's state. labels: the game's eye names, or null while
// they can't be read (the file's eyes are then kept as they are). gameSlots: how many colours each of the game's
// tables has (palettes.GAME_SLOTS).
//
// Two keys for one colour ("Amber" and "iris2", "03" and "003"): the build takes the later in the file, and so does
// the page; the earlier is listed, and Save puts the page's in its place. Where one of the two is a plain number
// ("9" and "iris09", "3" and "03") the page can't tell which is later (a plain number comes first in what the
// browser reads, wherever it is in the file), so neither is the page's: both are listed and written back as they
// are, until one is removed or the colour is set here. The Editing mod bar's notes say which one Apply uses.
export function fromPalette(p, { labels = null, gameSlots = 25 } = {}) {
  const s = blank();
  const src = isObject(p) ? p : {};
  // slot: the eye row or colour number an entry names, where the page can set it too (see replaced()).
  const skip = (section, key, value, why, slot = null) => s.unread.push({ section, key, value, why, ...(slot !== null ? { slot } : {}) });
  // found: the entries the page could read for one colour, in the order it reads them.
  const settle = (sec, slot, found, what) => {
    const last = found[found.length - 1];
    if (found.length > 1 && found.some(f => numberFirst(f.key))) {
      const keys = found.map(f => `"${f.key}"`).join(" and ");
      for (const f of found) skip(sec, f.key, f.value, `${keys} both name ${what}, and which one the game uses depends on their order in the file, which this page can't see: remove one`, slot);
      return;
    }
    for (const f of found.slice(0, -1)) skip(sec, f.key, f.value, `"${last.key}", later in the file, also names ${what}: the game uses that one`, slot);
    s[sec][slot] = last.read;
  };
  for (const [k, v] of Object.entries(src)) {
    if (k === "eyes" || PARTS.includes(k)) continue;
    if (k === "_help" && ownHelp(v)) continue;   // the page's own help line, written afresh
    if (KEPT.has(k) || k.startsWith("_")) s.kept[k] = v;
    else skip(k, null, v, "not something a palette has");
  }
  if ("eyes" in src) {
    if (!labels) s.kept.eyes = src.eyes;
    else if (!isObject(src.eyes)) skip("eyes", null, src.eyes, "not a list of eye colours by name");
    else {
      const byRow = new Map();
      for (const [key, val] of Object.entries(src.eyes)) {
        if (key.startsWith("_")) { (s.notes.eyes ||= {})[key] = val; continue; }
        const row = eyeRow(labels, key);
        const colors = isGradient(val) ? val.map(color.parse) : [color.parse(val)];
        if (row === null) skip("eyes", key, val, "not one of the game's eye colours");
        else if (!colors.length || colors.some(c => !c)) skip("eyes", key, val, "not a colour this page reads", row);
        else {
          // A list of one colour is that colour flat, pupil to rim: as a gradient of two the same, it draws, builds
          // and edits the same (One colour would keep the game's shading, a different look).
          const read = isGradient(val) ? { mode: "grad", colors: colors.length > 1 ? colors : [colors[0], colors[0]] }
            : { mode: "single", colors };
          if (!byRow.has(row)) byRow.set(row, []);
          byRow.get(row).push({ key, value: val, read });
        }
      }
      const eye = row => (eyeWord(labels, row) === labels[row] ? `the ${labels[row]} eye` : eyeWord(labels, row, true));
      for (const [row, found] of byRow) settle("eyes", row, found, eye(row));
    }
  }
  for (const sec of PARTS) {
    if (!(sec in src)) continue;
    if (!isObject(src[sec])) { skip(sec, null, src[sec], "not a list of colours by number"); continue; }
    const byNumber = new Map();
    for (const [key, val] of Object.entries(src[sec])) {
      if (key.startsWith("_")) { (s.notes[sec] ||= {})[key] = val; continue; }
      if (!/^[0-9]+$/.test(key)) { skip(sec, key, val, "not a colour number"); continue; }
      const i = Number(key);
      const c = isGradient(val) ? null : color.parse(val);
      if (isGradient(val)) skip(sec, key, val, "only eyes take more than one colour", i);
      else if (!c) skip(sec, key, val, "not a colour this page reads", i);
      else {
        if (!byNumber.has(i)) byNumber.set(i, []);
        byNumber.get(i).push({ key, value: val, read: c });
      }
    }
    for (const [i, found] of byNumber) settle(sec, i, found, `${NOUN[sec]} colour ${i}`);
  }
  return s;
}

// Whether Save leaves out an entry the page can't show because the page's own takes its place: the page sets the
// eye or colour it names, or (for a whole part that isn't a list of colours) has colours of its own in that part.
export function replaced(state, u) {
  if (u.section !== "eyes" && !PARTS.includes(u.section)) return false;
  if (u.key === null) return Object.keys(state[u.section]).length > 0;
  return u.slot !== undefined && state[u.section][u.slot] !== undefined;
}

// The state as a palette.json: what the page can't show first, then the page's colours in order, then the file's
// other parts as they were. An entry the page's own replaces (replaced()) is left out, so the build takes the
// page's: one entry for each colour.
export function toPalette(state, labels) {
  const out = { _help: HELP };
  const unread = state.unread.filter(u => !replaced(state, u));
  for (const sec of ["eyes", ...PARTS]) {
    const entries = {};
    for (const u of unread) if (u.section === sec && u.key !== null) entries[u.key] = u.value;
    Object.assign(entries, state.notes[sec] || {});
    if (sec === "eyes") {
      for (const r of Object.keys(state.eyes).map(Number).sort((a, b) => a - b)) {
        const ov = state.eyes[r];
        entries[labels[r]] = ov.mode === "grad" ? ov.colors.slice() : ov.colors[0];
      }
    } else {
      for (const i of Object.keys(state[sec]).map(Number).sort((a, b) => a - b)) entries[String(i)] = state[sec][i];
    }
    if (Object.keys(entries).length) out[sec] = entries;
  }
  for (const u of unread) if (u.key === null) out[u.section] = u.value;
  return Object.assign(out, state.kept);
}

// How an entry the page can't show reads in its list: where it is, what it says, and why; with the state, also
// when Save puts the page's own in its place.
export function describeUnread(u, state = null) {
  const where = WORD[u.section] || `"${u.section}"`;
  const instead = isObject(state) && replaced(state, u)   // (not when it's map()'s index)
    ? (u.key === null ? "; Save puts your colours on this tab in its place" : "; Save puts the colour set here in its place") : "";
  return `${where}${u.key !== null ? ` "${u.key}"` : ""}: ${JSON.stringify(u.value)} (${u.why}${instead})`;
}

// The number a new pattern or marking colour takes: past the game's, past this palette's own new colours and past
// every other palette's, so no two palettes add the same one.
export function nextSlot(own, others, gameSlots) {
  const past = list => list.filter(i => i >= gameSlots).map(i => i + 1);
  return Math.max(gameSlots, ...past(own), ...past(others));
}

// Palettes switched on together ([{name, palette}], in the Mods list's order) that change the same colours, as the
// build merges them (palettes.merge): the later one wins each coat, pattern and marking colour by its number, and
// each eye by its row whatever each palette calls it. One entry for each pair where the later one's colours show
// over the earlier's (and no palette later still takes them): {earlier, later, what: the colours in words ("coat 3",
// "25 coats and 20 eyes"), onTop}. onTop: the earlier is a full theme (it changes the coats and the eyes) and the later
// isn't, which is how a palette for just the eyes or just the coats is meant to be used. labels: the game's eye
// names, or null while they can't be read (eyes then match by the name written).
export function overlaps(list, labels) {
  const keysOf = p => Object.fromEntries(["eyes", ...PARTS].map(part => {
    const set = new Set();
    for (const k of Object.keys(isObject(p[part]) ? p[part] : {})) {
      if (k.startsWith("_")) continue;
      if (part !== "eyes") { if (/^[0-9]+$/.test(k)) set.add(Number(k)); continue; }
      if (!labels) set.add(k.trim().toLowerCase());
      else if (eyeRow(labels, k) !== null) set.add(eyeRow(labels, k));   // one the build skips changes nothing
    }
    return [part, set];
  }));
  const keys = list.map(d => keysOf(isObject(d.palette) ? d.palette : {}));
  const full = k => k.eyes.size > 0 && k.fur.size > 0;
  const and = words => (words.length > 1 ? `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}` : words[0]);
  const eye = row => {
    if (typeof row !== "number") return "an eye";
    const w = eyeWord(labels, row, true);
    return row === 0 || /^extra eye/.test(w) ? w : `the ${w} eye`;
  };
  const out = [];
  list.forEach((a, i) => list.forEach((b, j) => {
    if (j <= i) return;
    const words = [];
    for (const part of ["fur", "pattern", "marking", "eyes"]) {
      const shared = [...keys[i][part]].filter(k => keys[j][part].has(k) && !keys.slice(j + 1).some(later => later[part].has(k)));
      if (!shared.length) continue;
      const n = shared.length, one = shared[0];
      words.push(part === "eyes" ? (n === 1 ? eye(one) : `${n} eyes`)
        : part === "fur" ? (n === 1 ? `coat ${one}` : `${n} coats`)
        : n === 1 ? `${NOUN[part]} colour ${one}` : `${n} ${NOUN[part]} colours`);
    }
    if (words.length) out.push({ earlier: a.name, later: b.name, what: and(words), onTop: full(keys[i]) && !full(keys[j]) });
  }));
  return out;
}

// The eye rows in the page's three groups: the eye white (row 0), the extra eyes from a game add-on (the "Dlc" rows)
// and the standard ones, from the game's names rather than counted.
export function eyeGroups(labels) {
  const out = { white: [], standard: [], extra: [] };
  labels.forEach((l, r) => (r === 0 ? out.white : /^dlc\d*$/i.test(l) ? out.extra : out.standard).push(r));
  return out;
}

const copy = state => JSON.parse(JSON.stringify(state));
const newOnly = (entries, gameSlots) => Object.fromEntries(Object.entries(entries).filter(([i]) => Number(i) >= gameSlots));

// While the game's eye names can't be read, the file's eyes are kept as written (kept.eyes), out of sight: Start from
// and Game colours change them as a whole all the same, so each does what it says. `eyes` (another palette's, as
// written, or null for none) takes their place; the file's own notes ("_" keys) in them stay.
function keptEyes(s, eyes) {
  const notes = isObject(s.kept.eyes) ? Object.entries(s.kept.eyes).filter(([k]) => k.startsWith("_")) : [];
  const theirs = isObject(eyes) ? Object.entries(eyes).filter(([k]) => !k.startsWith("_")) : [];
  if (notes.length || theirs.length) s.kept.eyes = Object.fromEntries([...theirs, ...notes]);
  else delete s.kept.eyes;
}

// Start from another palette: its eyes and its changes to the game's colours. This palette's new colours, coat
// presets, other parts and what the page can't show stay: new colours keep their numbers, which cats may wear.
export function startFrom(state, other, { labels, gameSlots = 25 }) {
  const theirs = fromPalette(other, { labels, gameSlots });
  const s = copy(state);
  if (labels) s.eyes = theirs.eyes;
  else keptEyes(s, theirs.kept.eyes);
  for (const sec of PARTS) {
    s[sec] = { ...Object.fromEntries(Object.entries(theirs[sec]).filter(([i]) => Number(i) < gameSlots)), ...newOnly(s[sec], gameSlots) };
  }
  return s;
}
// The game's colours: every change to the game's own colours and eyes goes (the file's eyes too while the page
// can't show them); new colours and the rest stay.
export function gameColours(state, gameSlots = 25) {
  const s = copy(state);
  s.eyes = {};
  if ("eyes" in s.kept) keptEyes(s, null);
  for (const sec of PARTS) s[sec] = newOnly(s[sec], gameSlots);
  return s;
}
// Reset one tab: its changes to the game's colours (or every eye) go; its new colours stay.
export function resetTab(state, tab, gameSlots = 25) {
  const s = copy(state);
  s[tab] = tab === "eyes" ? {} : newOnly(s[tab], gameSlots);
  return s;
}
// A mood over one tab: every eye but the eye white (from the game's rims), or every one of the game's colours in
// the table (from the game's own). eyeRims: the game's rim colour per row, as hex; table: the tab's game colours.
export function restyle(state, tab, mood, { eyeRims = [], table = [] } = {}) {
  const s = copy(state);
  if (tab === "eyes") eyeRims.forEach((hex, r) => { if (r > 0 && hex) s.eyes[r] = { mode: "single", colors: [color.mood(hex, mood)] }; });
  else table.forEach((hex, i) => { s[tab][i] = color.mood(hex, mood); });
  return s;
}

// An eye row's strip, pupil to rim, as linear colours: the game's row (orig, linear [r, g, b] per pixel) with a
// palette's colours on it, as wcmods/palettes.apply_eyes paints it. One colour keeps the row's shading (a row that
// ramps up from black), a gradient spreads its colours evenly.
export function eyeRamp(orig, ov) {
  if (!ov) return orig;
  const w = orig.length;
  if (ov.mode === "grad" && ov.colors.length > 1) {
    const stops = ov.colors.map(color.hexToLinear), n = stops.length;
    return orig.map((_, x) => {
      const t = x / (w - 1) * (n - 1), i = Math.min(Math.floor(t), n - 2), f = t - i;
      return [0, 1, 2].map(k => stops[i][k] + (stops[i + 1][k] - stops[i][k]) * f);
    });
  }
  const target = color.hexToLinear(ov.colors[0]);
  const lums = orig.map(color.luminance), peak = Math.max(...lums);
  const ramp = lums[0] < 0.02 * Math.max(peak, 1e-6);
  return orig.map((_, x) => { const s = ramp && peak > 0 ? lums[x] / peak : 1; return target.map(c => c * s); });
}
// A stand-in eye row while the game's can't be read: black at the pupil up to a mid grey at the rim, so a colour
// on it still shows its shading.
export function plainRow(width = 64, white = false) {
  return [...Array(width).keys()].map(x => (white ? [0.8, 0.8, 0.78] : [0.2, 0.2, 0.2].map(c => c * x / (width - 1))));
}
