// The Palettes page's palette.json, without the page: reading a file into what the page edits and writing it
// back, which eye row a key means, the number a new colour takes, the whole-tab changes (Start from, Game
// colours, Reset tab, the moods) and the eye strips the preview draws. The game's eye names, its colour tables
// and how many colours each table has come in as arguments, so tests/studio/palette.test.mjs runs these in node.
//
// The page's state: { eyes: {row: {mode: "single"|"grad", colors: ["#RRGGBB", ...]}}, fur|pattern|marking:
// {slot: "#RRGGBB"}, kept: the file's other parts, as they were, notes: {part: {"_key": value}}, unread: [{section,
// key, value, why}] }. unread holds what the page can't show (a misspelt eye, a coat past the game's, a part a palette
// hasn't got): each is written back as it was until its Remove button takes it out, so nothing goes unsaid.
import { color } from "./colour.js";

export const PARTS = ["fur", "pattern", "marking"];       // the game's colour tables, by slot number
export const GROWABLE = ["pattern", "marking"];           // the ones that take new colours (palettes.GROWABLE)
// The file's parts the page doesn't edit, kept as they were: the cat maker's eye buttons, coat presets, and the
// palette's own name and description (palettes.SECTIONS, and what palettes.load skips).
export const KEPT = new Set(["iris_ui", "coats", "name", "description"]);
export const HELP = "Written by Clan Mod Studio. Eye keys are the game's eye colour names; coat, pattern and marking keys " +
  "are colour numbers, counted from 0. See docs/formats.md, palette.json.";
const WORD = { eyes: "Eyes", fur: "Coat", pattern: "Pattern", marking: "Markings" };

export function blank(kept = {}) {
  return { eyes: {}, fur: {}, pattern: {}, marking: {}, kept, notes: {}, unread: [] };
}
const isObject = v => v !== null && typeof v === "object" && !Array.isArray(v);
// A list whose first value isn't a number is a gradient; [r, g, b] is one colour (as palettes.load tells them apart).
const isGradient = v => Array.isArray(v) && v.length > 0 && typeof v[0] !== "number" && typeof v[0] !== "boolean";

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
export function fromPalette(p, { labels = null, gameSlots = 25 } = {}) {
  const s = blank();
  const src = isObject(p) ? p : {};
  const skip = (section, key, value, why) => s.unread.push({ section, key, value, why });
  for (const [k, v] of Object.entries(src)) {
    if (k === "_help" || k === "eyes" || PARTS.includes(k)) continue;
    if (KEPT.has(k) || k.startsWith("_")) s.kept[k] = v;
    else skip(k, null, v, "not something a palette has");
  }
  if ("eyes" in src) {
    if (!labels) s.kept.eyes = src.eyes;
    else if (!isObject(src.eyes)) skip("eyes", null, src.eyes, "not a list of eye colours by name");
    else {
      for (const [key, val] of Object.entries(src.eyes)) {
        if (key.startsWith("_")) { (s.notes.eyes ||= {})[key] = val; continue; }
        const row = eyeRow(labels, key);
        const colors = isGradient(val) ? val.map(color.parse) : [color.parse(val)];
        if (row === null) skip("eyes", key, val, "not one of the game's eye colours");
        else if (!colors.length || colors.some(c => !c)) skip("eyes", key, val, "not a colour this page reads");
        else {
          // Two keys for one eye: the later wins, in the build too; the earlier is kept as written.
          if (s.eyes[row]) skip("eyes", s.eyes[row].key, s.eyes[row].value, "another entry names the same eye");
          // A list of one colour is that colour flat, pupil to rim: as a gradient of two the same, it draws, builds
          // and edits the same (One colour would keep the game's shading, a different look).
          const ov = isGradient(val) ? { mode: "grad", colors: colors.length > 1 ? colors : [colors[0], colors[0]] }
            : { mode: "single", colors };
          s.eyes[row] = { ...ov, key, value: val };
        }
      }
      for (const ov of Object.values(s.eyes)) { delete ov.key; delete ov.value; }
    }
  }
  for (const sec of PARTS) {
    if (!(sec in src)) continue;
    if (!isObject(src[sec])) { skip(sec, null, src[sec], "not a list of colours by number"); continue; }
    const seen = {};
    for (const [key, val] of Object.entries(src[sec])) {
      if (key.startsWith("_")) { (s.notes[sec] ||= {})[key] = val; continue; }
      if (!/^[0-9]+$/.test(key)) { skip(sec, key, val, "not a colour number"); continue; }
      const i = Number(key);
      const c = isGradient(val) ? null : color.parse(val);
      if (sec === "fur" && i >= gameSlots) skip(sec, key, val, `the game has coats 0-${gameSlots - 1} only`);
      else if (isGradient(val)) skip(sec, key, val, "only eyes take more than one colour");
      else if (!c) skip(sec, key, val, "not a colour this page reads");
      else {
        if (i in seen) skip(sec, seen[i], src[sec][seen[i]], "another entry names the same colour");
        seen[i] = key;
        s[sec][i] = c;
      }
    }
  }
  return s;
}

// The state as a palette.json: what the page can't show first (so the page's own choice is the one the build
// takes where both name one colour), then the page's colours in order, then the file's other parts as they were.
export function toPalette(state, labels) {
  const out = { _help: HELP };
  for (const sec of ["eyes", ...PARTS]) {
    const entries = {};
    for (const u of state.unread) if (u.section === sec && u.key !== null) entries[u.key] = u.value;
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
  for (const u of state.unread) if (u.key === null) out[u.section] = u.value;
  return Object.assign(out, state.kept);
}

// How an entry the page can't show reads in its list: where it is, what it says, and why.
export function describeUnread(u) {
  const where = WORD[u.section] || `"${u.section}"`;
  return `${where}${u.key !== null ? ` "${u.key}"` : ""}: ${JSON.stringify(u.value)} (${u.why})`;
}

// The number a new pattern or marking colour takes: past the game's, past this palette's own new colours and past
// every other palette's, so no two palettes add the same one.
export function nextSlot(own, others, gameSlots) {
  const past = list => list.filter(i => i >= gameSlots).map(i => i + 1);
  return Math.max(gameSlots, ...past(own), ...past(others));
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

// Start from another palette: its eyes and its changes to the game's colours. This palette's new colours, coat
// presets, other parts and what the page can't show stay: new colours keep their numbers, which cats may wear.
export function startFrom(state, other, { labels, gameSlots = 25 }) {
  const theirs = fromPalette(other, { labels, gameSlots });
  const s = copy(state);
  s.eyes = labels ? theirs.eyes : s.eyes;
  for (const sec of PARTS) {
    s[sec] = { ...Object.fromEntries(Object.entries(theirs[sec]).filter(([i]) => Number(i) < gameSlots)), ...newOnly(s[sec], gameSlots) };
  }
  return s;
}
// The game's colours: every change to the game's own colours and eyes goes; new colours and the rest stay.
export function gameColours(state, gameSlots = 25) {
  const s = copy(state);
  s.eyes = {};
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
