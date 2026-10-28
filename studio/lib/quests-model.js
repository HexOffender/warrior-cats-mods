// The Questlines page's quests as data, without the page: quests.json read in and written out, the words
// the game's objective panel shows for a step left without its own, and what keeps a quest from working
// (a step with nothing chosen, a cat that's gone, quests that wait for each other in a circle).
// wcmods/story.py checks the same file at save and at Apply, and fills in the objectives at Apply.

export const STEP_LABEL = { talk: "Talk", collect: "Pick up", visit: "Go somewhere" };
export const PLACES = { "medicine-cat": "the nearest medicine cat" };   // story.py's PLACE_WORDS
export const HELP = "Written by Clan Mod Studio (Questlines). This mod's questlines, which the Sandbox mode mod runs. See docs/formats.md, quests.json.";
const OWN_MARKS = ["_new", "_auto"];   // the page's own, never saved

// What the game's objective panel says for a step left without an objective, with today's names: the build
// writes the same words at Apply (story.objective), so a renamed cat or item reads right after the next Apply.
// names: {cat(id) -> name, item(tag) -> name}.
export function autoObjective(s, q, names) {
  if (s.do === "talk") return `Talk to ${names.cat(s.npc || q.giver) || "them"}`;
  if (s.do === "collect") {
    if (!s.item) return "Find something";
    const n = s.count || 1;
    return n > 1 ? `Find ${n} ${names.item(s.item)}` : `Find ${names.item(s.item)}`;
  }
  if (s.do === "visit") return s.place ? `Visit ${PLACES[s.place] || s.place}` : "Go to the marked place";
  return "";
}
// The words this page wrote into the file before the build filled them in: a step saved with them counts as
// one with no objective of its own, so it follows renames from its next save on.
function oldAutoObjective(s, q, names) {
  if (s.do === "talk") return `Talk to ${names.cat(s.npc || q.giver) || "someone"}`;
  if (s.do === "collect") return s.item ? `Find ${names.item(s.item)}${(s.count || 1) > 1 ? ` ×${s.count}` : ""}` : "Find something";
  if (s.do === "visit") return s.place ? `Visit ${s.place === "medicine-cat" ? "your Clan's medicine cat" : s.place}` : "Go to the marked place";
  return "";
}

// quests.json as the page holds it: {quests, extra}. A step whose objective is the automatic one (today's
// words, or the ones this page used to write) is marked _auto.
export function load(obj, names) {
  const extra = {}, quests = [];
  for (const [k, v] of Object.entries(obj && typeof obj === "object" ? obj : {})) if (k !== "quests" && k !== "_help") extra[k] = v;
  for (const q of (obj && Array.isArray(obj.quests) ? obj.quests : [])) {
    if (!q || typeof q !== "object") continue;
    const quest = { after: [], reward: {}, ...q, after: Array.isArray(q.after) ? [...q.after] : [],
      reward: q.reward && typeof q.reward === "object" && !Array.isArray(q.reward) ? { ...q.reward } : {} };
    quest.steps = (Array.isArray(q.steps) ? q.steps : []).filter(s => s && typeof s === "object").map(s => {
      const step = { ...s };
      if (s.do === "talk") step.lines = Array.isArray(s.lines) ? s.lines.filter(l => typeof l === "string") : [];
      step._auto = !s.objective || s.objective === autoObjective(s, quest, names) || s.objective === oldAutoObjective(s, quest, names);
      return step;
    });
    quests.push(quest);
  }
  return { quests, extra };
}

// The quests as quests.json: no automatic objective (the build fills it in), "Starts after" only naming
// quests that are there, no empty reward, and the notes ("_" keys) kept.
export function toJson(quests, extra = {}) {
  const ids = new Set(quests.map(q => q.id));
  const list = quests.map(q => {
    const o = { id: q.id, title: (q.title || "").trim() || q.id };
    if (q.description && q.description.trim()) o.description = q.description.trim();
    if (q.giver) o.giver = q.giver;
    o.after = (q.after || []).filter(a => ids.has(a) && a !== q.id);
    o.steps = (q.steps || []).map(s => {
      const step = { do: s.do };
      if (s.do === "talk") { if (s.npc || q.giver) step.npc = s.npc || q.giver; step.lines = s.lines || []; }
      if (s.do === "collect") { step.item = s.item; step.count = s.count || 1; }
      if (s.do === "visit") {
        if (s.place) step.place = s.place;
        else { step.at = s.at; if (s.level) step.level = s.level; }
        step.radius = s.radius || 400;
      }
      if (!s._auto && s.objective && s.objective.trim()) step.objective = s.objective.trim();
      for (const [k, v] of Object.entries(s)) if (!(k in step) && k.startsWith("_") && !OWN_MARKS.includes(k)) step[k] = v;
      return step;
    });
    if (Object.keys(q.reward || {}).length) o.reward = { ...q.reward };
    for (const [k, v] of Object.entries(q)) if (!(k in o) && k.startsWith("_") && !OWN_MARKS.includes(k)) o[k] = v;
    return o;
  });
  return { _help: HELP, ...extra, quests: list };
}

// The quests `id` waits for, directly or through others (ids).
export function waitsFor(quests, id) {
  const byId = new Map(quests.map(q => [q.id, q]));
  const seen = new Set(), todo = [...((byId.get(id) || {}).after || [])];
  while (todo.length) {
    const a = todo.shift();
    if (seen.has(a)) continue;
    seen.add(a);
    todo.push(...((byId.get(a) || {}).after || []));
  }
  return seen;
}

// A circle of "Starts after" through quest q: [q, ..., q] (ids), or null.
export function circle(quests, q) {
  const byId = new Map(quests.map(x => [x.id, x]));
  const walk = (id, path) => {
    for (const a of (byId.get(id) || {}).after || []) {
      if (a === q.id) return [...path, a];
      if (!path.includes(a) && byId.has(a)) {
        const found = walk(a, [...path, a]);
        if (found) return found;
      }
    }
    return null;
  };
  return walk(q.id, [q.id]);
}

// What keeps a quest from working, as {text, step} (step: its index, or null for the quest), for the "Not
// ready yet" note at the top of the open quest and the mark on the step. cats: the mod's cats ({id, name}).
export function problems(q, quests, cats) {
  const p = [];
  const has = id => cats.some(c => c.id === id);
  const title = id => (quests.find(x => x.id === id) || {}).title || id;
  if (!(q.title || "").trim()) p.push({ text: "It has no title yet: type one in Title.", step: null });
  if (!(q.steps || []).length) p.push({ text: "It has no steps yet: add a Talk, Pick up or Go somewhere step.", step: null });
  if (q.giver && !has(q.giver)) p.push({ text: `Given by ${q.giver}, who isn't one of this mod's cats any more: choose another in Given by.`, step: null });
  const loop = circle(quests, q);
  if (loop) p.push({ text: `Starts after goes round in a circle: ${loop.map(title).join(" → ")}. None of them would ever start: untick one.`, step: null });
  (q.steps || []).forEach((s, n) => {
    const at = `Step ${n + 1}`;
    if (s.do === "talk" && !(s.npc || q.giver)) p.push({ text: `${at}: who to talk to? Choose a cat.`, step: n });
    else if (s.do === "talk" && !has(s.npc || q.giver)) p.push({ text: `${at}: ${s.npc || q.giver} isn't one of this mod's cats any more: choose another.`, step: n });
    if (s.do === "talk" && !(s.lines || []).length) p.push({ text: `${at}: what do they say? Type at least one line.`, step: n });
    if (s.do === "collect" && !s.item) p.push({ text: `${at}: which item? Choose one.`, step: n });
    if (s.do === "visit" && !s.place && !s.at) p.push({ text: `${at}: where? Use where your cat is standing, or type all three numbers.`, step: n });
  });
  return p;
}
