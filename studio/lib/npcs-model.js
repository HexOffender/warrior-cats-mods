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
const OWN_MARKS = ["_new", "_placing"];   // the page's own, never saved

const filled = o => !!o && typeof o === "object" && Object.keys(o).length > 0;
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
