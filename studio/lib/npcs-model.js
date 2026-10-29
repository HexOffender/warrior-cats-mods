// The Characters page's cats as data, without the page: npcs.json read in and written out, what a cat
// still needs before it does what its maker meant, and the words for its size. wcmods/story.py checks the
// same file at save and at Apply; this says what it accepts but the creator didn't mean.

// A fixed look's parts (npcs.json "look"), each one of the game's options counted from 0, and the colour
// slots it wears ("slots"), with the colour table each slot is in and the drawing's part it colours.
export const LOOK_PARTS = [["body", "Body"], ["fur", "Fur"], ["tail", "Tail"], ["ears", "Ears"], ["eyes", "Eye shape"],
  ["whiskers", "Whiskers"], ["face", "Face"], ["pattern", "Pattern"], ["marking", "Markings"]];
export const SLOT_PARTS = [["fur", "Coat colour", "FurColors", "fur"], ["pattern", "Pattern colour", "PatternMaskColors", "pattern"],
  ["marking", "Markings colour", "MarkingMaskColors", "markings"]];
export const MAX_LINES = 30, MAX_LINE = 400, MAX_NAME = 40;   // story.py's limits
export const HELP = "Written by Clan Mod Studio (Characters). Cats of this mod's own, which the Sandbox mode mod brings into the game. See docs/formats.md, npcs.json.";
const OWN_MARKS = ["_new", "_placing", "_patrol"];   // the page's own, never saved

const filled = o => !!o && typeof o === "object" && Object.keys(o).length > 0;
const isObj = o => !!o && typeof o === "object" && !Array.isArray(o);
// A fixed look: some part of the shape or a colour slot chosen. One with nothing chosen is the game's look.
export const isFixed = c => filled(c.look) || filled(c.slots);

// A look chosen once and kept: every part and colour slot at random, as the game would. options is the
// studio's /cat/options (how many of each part, the game's colour slots). Its coat is one of the first 20
// (20 to 24 are the Feral Edition's, swapped for another without it); its pattern and marking colours are
// the game's slots, not new ones a palette adds (they'd go if the palette went).
export const EYES = 25, RANDOM_COATS = 20;
export const partMax = (options, p) => (options.parts || {})[p] ?? (p === "pattern" || p === "marking" ? 20 : 9);
export function roll(c, options = {}, rnd = Math.random) {
  const any = n => Math.floor(rnd() * n);
  const slots = options.game_slots || 25;
  c.look = Object.fromEntries(LOOK_PARTS.map(([p]) => [p, any(partMax(options, p) + 1)]));
  c.slots = { fur: any(RANDOM_COATS), pattern: any(slots), marking: any(slots) };
  return c;
}
// Eyes of a colour kept too, for a look that's kept, unless they have one.
export function keepEyes(c, rnd = Math.random) {
  if (c.eyes === undefined || c.eyes === null) c.eyes = Math.floor(rnd() * EYES);
  return c;
}
// A new cat: "New cat" (with an id no other cat has), with a look of its own kept, so it's one you'll know again.
export function newCat(taken, options, slug, rnd = Math.random) {
  return keepEyes(roll({ id: slug("New cat", taken, "cat"), name: "New cat", colours: {}, lines: [], _new: true }, options, rnd), rnd);
}

// npcs.json as the page holds it: {cats, extra}. extra keeps the file's other keys and notes (but _help,
// which the page writes); a cat gets colours and lines it can draw, and "at": null (At one spot, with no spot
// filled in yet) is the open picker again.
export function load(obj) {
  const extra = {}, cats = [];
  for (const [k, v] of Object.entries(obj && typeof obj === "object" ? obj : {})) if (k !== "npcs" && k !== "_help") extra[k] = v;
  for (const c of (obj && Array.isArray(obj.npcs) ? obj.npcs : [])) {
    if (!c || typeof c !== "object") continue;
    const cat = { ...c, colours: c.colours && typeof c.colours === "object" && !Array.isArray(c.colours) ? { ...c.colours } : {},
      lines: Array.isArray(c.lines) ? c.lines.filter(s => typeof s === "string") : [] };
    if (c.at === null) cat._placing = true;
    // A patrol's points as the page edits them: an [x, y, z] becomes {x, y, z}; the rest is kept as it is.
    if (patrolEditable(c.patrol) && Array.isArray(c.patrol.points)) cat.patrol = { ...c.patrol, points: c.patrol.points.map(point) };
    cats.push(cat);
  }
  return { cats, extra };
}

// The cats as npcs.json: only what's chosen. An all-random fixed look is no look at all (the game makes it up
// each time either way); a cat "At one spot" with no spot yet keeps "at": null, so the page reopens on it.
export function toJson(cats, extra = {}) {
  const npcs = cats.map(c => {
    const o = { id: c.id, name: (c.name || "").trim() || c.id };
    if (c.title && c.title.trim()) o.title = c.title.trim();
    if (filled(c.colours)) o.colours = { ...c.colours };
    for (const k of ["eyes", "size"]) if (c[k] !== undefined && c[k] !== null) o[k] = c[k];
    if (filled(c.look)) o.look = { ...c.look };
    if (filled(c.slots)) o.slots = { ...c.slots };
    if (Object.hasOwn(c, "patrol")) o.patrol = c.patrol;
    if (c.at) {
      o.at = c.at;
      if (c.yaw !== undefined && c.yaw !== null) o.yaw = c.yaw;
      if (c.level) o.level = c.level;
    } else if (c._placing) {
      o.at = null;
    }
    o.lines = c.lines || [];
    for (const [k, v] of Object.entries(c)) if (!(k in o) && k.startsWith("_") && !OWN_MARKS.includes(k)) o[k] = v;   // notes kept
    return o;
  });
  return { _help: HELP, ...extra, npcs };
}

// What would make a cat other than its maker meant, in sentences for the "Not ready yet" note at its top.
// addedSlots: {pattern: [slot...], marking: [...]}, the new colour slots the palettes that are on add.
export function problems(c, { gameSlots = 25, addedSlots = null } = {}) {
  const p = [];
  if (!(c.name || "").trim()) p.push("It has no name yet: type one in Name.");
  if (c._placing && !c.at) p.push("Where they stand is At one spot, but no spot is filled in yet: use where your cat is standing, or type all three numbers. Until then they stand beside your cat.");
  const lines = c.lines || [];
  if (lines.length > MAX_LINES) p.push(`What they say has ${lines.length} lines; ${MAX_LINES} is the most. Take some out.`);
  if (lines.some(s => s.length > MAX_LINE)) p.push(`A line of what they say is longer than ${MAX_LINE} letters. Split it into two lines.`);
  if (addedSlots) {
    for (const [part, words] of [["pattern", "pattern"], ["marking", "markings"]]) {
      const n = c.slots && c.slots[part];
      if (n !== undefined && n >= gameSlots && !(addedSlots[part] || []).includes(n)) {
        p.push(`They wear ${words} colour ${n}, which no palette that's on adds, so it shows no colour there. Choose another, or turn that palette on.`);
      }
    }
  }
  return p.concat(patrolProblems(c.patrol));
}

// ---------- patrols
// A cat's "patrol": a route Sandbox mode (0.6 or newer) walks them along, with waits at its points. story.py's
// _patrol checks it as Sandbox mode's runner (sandbox/scripts/patrol.lua) reads it; keys the page doesn't know
// are kept as they are.
export const PATROL_MODES = [["pingpong", "Back and forth", "to the last point, then back the way they came"],
  ["loop", "Round and round", "from the last point straight back to the first"], ["once", "Once", "to the last point, then they stay there"]];
export const WALK_SPEED = 175, RETRIES = 2;   // the runner's, when the patrol says nothing: a cat's walk, in cm a second
export const AXES = ["x", "y", "z"];
const AXIS_WORDS = { x: "X", y: "Y", z: "Z" };
const num = v => typeof v === "number" && Number.isFinite(v) ? v : null;

// A patrol the page can show: an object whose points, if it has any yet, are a list.
export const patrolEditable = p => isObj(p) && (p.points === undefined || Array.isArray(p.points));
// A point as the page edits it: {x, y, z} with null for a number not filled in, and its other keys.
export function point(p) {
  if (Array.isArray(p)) return { x: num(p[0]), y: num(p[1]), z: num(p[2]) };
  return isObj(p) ? p : { x: null, y: null, z: null };
}
// A new patrol starts where the cat stands, when it stands at one spot.
export function newPatrol(c) {
  const first = c.at ? { x: c.at[0], y: c.at[1], z: c.at[2], ...(c.level ? { level: c.level } : {}) } : null;
  return { points: first ? [first] : [] };
}
// Point i moved by one (-1 up, 1 down), or left where it is at the end of the list.
export function movePoint(patrol, i, by) {
  const j = i + by, pts = patrol.points;
  if (j < 0 || j >= pts.length) return false;
  [pts[i], pts[j]] = [pts[j], pts[i]];
  return true;
}

// A wait: how long a cat stays at a point. kind is "default" (none given: a point's is the patrol's, the patrol's
// is none), "none", "seconds", "range", "until" or "other" (a wait the page has no words for, kept as it is).
export function waitKind(w) {
  if (w === undefined) return "default";
  if (w === "none") return "none";
  if (typeof w === "number") return "seconds";
  if (Array.isArray(w)) return "range";
  if (w === "release") return "until";   // the same as {"until": {"release": true}}
  if (isObj(w)) return "until" in w ? "until" : "min" in w || "max" in w ? "range" : "other";
  return "other";
}
// A range's two numbers, [min, max] (null when one isn't filled in).
export function rangeOf(w) {
  if (Array.isArray(w)) return [num(w[0]), num(w[1])];
  if (isObj(w)) return [num(w.min), num(w.max)];
  return [null, null];
}
// The range with new numbers: a [min, max] stays one; an object keeps its other keys.
export const withRange = (w, lo, hi) => Array.isArray(w) ? [lo, hi] : { ...(isObj(w) ? w : {}), min: lo, max: hi };
// The wait as another kind, keeping what it can: its seconds, its range's, an object's keys of its own.
export function waitAs(w, kind) {
  if (kind === waitKind(w)) return w;
  const own = isObj(w) ? Object.fromEntries(Object.entries(w).filter(([k]) => !["min", "max", "until", "timeout"].includes(k))) : {};
  const secs = typeof w === "number" ? w : rangeOf(w)[0];
  if (kind === "none") return "none";
  if (kind === "seconds") return secs ?? 5;
  if (kind === "range") return { ...own, min: secs ?? 3, max: (secs ?? 3) + 5 };
  if (kind === "until") return { ...own, until: {} };
  return undefined;   // default
}
// An "until" wait as an object to edit ("release" becomes {"until": {"release": true}}), its until an object.
export function untilWait(w) {
  if (w === "release") return { until: { release: true } };
  return isObj(w) && isObj(w.until) ? w : { ...(isObj(w) ? w : {}), until: {} };
}

// What Sandbox mode would do other than meant with the patrol, in sentences: what its runner drops, and what
// story.py won't take (Apply leaves the mod's cats and questlines out).
function patrolProblems(patrol) {
  if (patrol === undefined) return [];
  if (!patrolEditable(patrol)) return ["Their patrol isn't laid out as this page writes it, so they stand still: start a new route under Where they walk."];
  const p = [], points = patrol.points || [];
  if (!points.length) p.push("Their patrol has no points yet: add one under Where they walk. Until then they stand still.");
  points.forEach((pt, i) => {
    const missing = AXES.filter(a => num(point(pt)[a]) === null);
    if (missing.length) {
      const what = missing.length === 3 ? "no numbers" : `no ${missing.map(a => AXIS_WORDS[a]).join(" or ")}`;
      p.push(`Patrol point ${i + 1} has ${what} yet: use where your cat is standing, or type all three numbers. Until it has, Apply leaves this mod's cats and questlines out.`);
    }
  });
  if (patrol.speed !== undefined && !(num(patrol.speed) > 0)) p.push("Their walking speed should be more than 0: type another, or leave it empty for a cat's walk.");
  if (patrol.retries !== undefined && !(Number.isInteger(patrol.retries) && patrol.retries >= 0)) {
    p.push("Tries before skipping a point should be a whole number, 0 or more: type another, or leave it empty for 2.");
  }
  p.push(...waitProblems(patrol.wait, "The patrol's wait"));
  points.forEach((pt, i) => p.push(...waitProblems(isObj(pt) ? pt.wait : undefined, `Patrol point ${i + 1}'s wait`)));
  return p;
}
function waitProblems(w, who) {
  const p = [], kind = waitKind(w);
  if (kind === "seconds" && !(w >= 0)) p.push(`${who} should be 0 seconds or more.`);
  if (kind === "range") {
    const [lo, hi] = rangeOf(w);
    if (lo === null || hi === null) p.push(`${who} is a random time, but it needs both numbers: from and to.`);
    else if (lo < 0 || hi < 0) p.push(`${who} should be 0 seconds or more.`);
    else if (lo > hi) p.push(`${who} goes from ${lo} to ${hi} seconds: the first should be the smaller.`);
  }
  if (kind === "until" && w !== "release") {
    const u = isObj(w.until) ? w.until : {};
    if (!["quest", "event", "release"].some(k => k in u)) p.push(`${who} is Until…, but nothing is chosen to wait for: choose a quest, type an event, or tick Released by a script.`);
    if ("step" in u && !("quest" in u)) p.push(`${who} waits for a step, but of no quest: choose the quest.`);
    else if ("step" in u && !(Number.isInteger(u.step) && u.step >= 1)) p.push(`${who} waits for a step of the quest: its number should be a whole number, 1 or more.`);
    if (w.timeout !== undefined && !(num(w.timeout) > 0)) p.push(`${who} gives up after a time: it should be more than 0 seconds, or empty to wait as long as it takes.`);
  }
  return p;
}

// The game's sizes for its own cats (docs/mechanics/npcs.md, CatSize.csv: apprentices 0.40 to 0.50, elders
// 0.65 to 0.75, warriors 0.70 to 0.80, leaders 0.90 to 1.00): the size slider's words.
export const DEFAULT_SIZE = 0.85;
function role(size) {
  if (size > 1) return "bigger than a leader";
  if (size >= 0.9) return "leader size";
  if (size > 0.8) return "between warrior and leader size";
  if (size > 0.75) return "warrior size";
  if (size >= 0.7) return "elder or warrior size";
  if (size >= 0.65) return "elder size";
  if (size > 0.5) return "between apprentice and elder size";
  if (size >= 0.4) return "apprentice size";
  return "smaller than an apprentice";
}
export function sizeText(v) {
  const size = Math.round((v ?? DEFAULT_SIZE) * 100) / 100;
  return `${Math.round(size * 100)}%, ${role(size)}`;
}

// The quests in a mod's quests.json that name a cat (its giver, or a talk step's cat), by title.
export function questsNaming(questsJson, catId) {
  const out = [];
  for (const q of (questsJson && Array.isArray(questsJson.quests) ? questsJson.quests : [])) {
    if (!q || typeof q !== "object") continue;
    const steps = Array.isArray(q.steps) ? q.steps : [];
    if (q.giver === catId || steps.some(s => s && s.do === "talk" && s.npc === catId)) out.push(q.title || q.id);
  }
  return out;
}
