// The Names page's plain logic, with no page in it: reading a names.json into what the page edits and back, how
// a cat is named in "cats", what the line under a cat's box says, and the words for ranks, story roles and games.
// studio/sections/names.js draws the page with these; tests/studio/unit/names.test.mjs checks them. The answers
// they read are the studio's GET /names and POST /names/preview (wcmods/studio.py, names_preview).

// What the page edits; the rest of a names.json (weights, banned.clear) is kept as written.
export const EMPTY = () => ({
  prefixes: { rename: {}, add: {}, remove: [] }, suffixes: { rename: {}, add: {}, remove: [] },
  rogues: { rename: {}, add: [], remove: [] }, banned: { add: [], remove: [] }, names: {}, cats: {}, text: {},
});
// Kits, apprentices and leaders have one suffix each; the build keeps them even if asked to remove them.
export const KEEP = ["kit", "paw", "star"];
export const CLAN_LABEL = { ThunderClan: "Thunder", RiverClan: "River", ShadowClan: "Shadow", WindClan: "Wind", OutOfClans: "outside clans" };
const OUTSIDERS = ["RogueCat", "RogueCatLeader"];
const CLANS = ["ThunderClan", "RiverClan", "ShadowClan", "WindClan"];

const low = s => String(s ?? "").toLowerCase();
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

// ---------- reading and writing names.json ----------
// A names.json as the page edits it: { spec, extra, unplaced }. Renames, removals and ban-list entries written in
// another case or by the game's ID (by hand, or by an older page) are filed under the game's own text, so their
// boxes show them, and two keys for one name become one (the later wins, as it does in the build). Names the
// game's lists don't have are kept as written, and listed in `unplaced` for the page to say once.
export function readNames(obj, game) {
  const spec = EMPTY(), extra = {}, unplaced = [];
  obj = obj && typeof obj === "object" && !Array.isArray(obj) ? obj : {};
  const parts = {
    prefixes: game?.prefixes || [], suffixes: game?.suffixes || [],
    rogues: (game?.rogues || []).map(r => ({ text: r.text, id: r.id, label: r.label })),
  };
  const find = (kind, name) => {
    const n = low(name);
    const hit = parts[kind].find(x => low(x.text) === n || low(x.id) === n || (x.label && low(x.label) === n));
    if (!hit) { if (!unplaced.includes(String(name))) unplaced.push(String(name)); return String(name); }
    return hit.text;
  };
  const banName = name => {
    const n = low(name);
    const hit = (game?.banned || []).find(b => low(b.name) === n || low(textOf(game, b.prefix, b.suffix)) === n);
    if (!hit) { if (!unplaced.includes(String(name))) unplaced.push(String(name)); return String(name); }
    return hit.name;
  };
  for (const [k, v] of Object.entries(obj)) {
    if (k.startsWith("_")) continue;
    if (!(k in spec) || !v || typeof v !== "object" || Array.isArray(v)) { extra[k] = v; continue; }
    for (const [op, val] of Object.entries(v)) {
      if (k === "names" || k === "cats" || k === "text") { spec[k][op] = val; continue; }
      const want = spec[k][op];
      if (want === undefined || Array.isArray(want) !== Array.isArray(val) || !val || typeof val !== "object") {
        (extra[k] ||= {})[op] = val;   // weights, banned.clear, or a shape this page doesn't edit: kept as written
        continue;
      }
      if (k === "banned") {   // a name to allow again is one on the game's ban list; a name to ban is any the game can make
        for (const n of val) { const name = op === "remove" ? banName(n) : n; if (!want.includes(name)) want.push(name); }
        continue;
      }
      if (op === "rename") { for (const [from, to] of Object.entries(val)) { const key = find(k, from); delete want[key]; want[key] = to; } continue; }
      if (op === "remove") { for (const n of val) { const key = find(k, n); if (!want.includes(key)) want.push(key); } continue; }
      // add: new names, as written; a part's "like" names a game part, filed under its text.
      if (Array.isArray(val)) { for (const n of val) if (!want.includes(n)) want.push(n); continue; }
      for (const [name, opts] of Object.entries(val)) {
        want[name] = opts && typeof opts === "object" && typeof opts.like === "string" ? { ...opts, like: find(k, opts.like) } : opts;
      }
    }
  }
  return { spec, extra, unplaced };
}

// The page's names.json: its edits, with what it keeps as written put back where it was.
export function writeNames(spec, extra = {}) {
  const o = { _help: "Written by Clan Mod Studio. See docs/formats.md, names.json." };
  for (const [k, v] of Object.entries(spec)) {
    const part = {};
    if (k === "names" || k === "cats" || k === "text") Object.assign(part, v);
    else for (const [op, val] of Object.entries(v)) if (Array.isArray(val) ? val.length : Object.keys(val).length) part[op] = val;
    if (extra[k] && typeof extra[k] === "object" && !Array.isArray(extra[k])) Object.assign(part, extra[k]);
    if (Object.keys(part).length) o[k] = part;
  }
  for (const [k, v] of Object.entries(extra)) if (!(k in spec) || typeof v !== "object" || Array.isArray(v) || v === null) o[k] = v;
  return o;
}

// ---------- the game's parts ----------
// The text a prefix ID and suffix ID make, after the page's renames when `final` (the preview's) is given.
export function textOf(game, prefixId, suffixId, final = null) {
  const pi = (game?.prefixes || []).findIndex(p => p.id === prefixId);
  const si = (game?.suffixes || []).findIndex(s => s.id === suffixId);
  if (pi < 0 || si < 0) return "";
  return (final?.prefixes?.[pi] ?? game.prefixes[pi].text) + (final?.suffixes?.[si] ?? game.suffixes[si].text);
}

// [prefix, suffix] whose texts (after the page's renames) make `name`, or null: "Mothheart" is Moth + heart.
export function splitName(name, game, final = null) {
  const n = low(name);
  if (!n) return null;
  const ps = (final?.prefixes || (game?.prefixes || []).map(p => p.text));
  const ss = (final?.suffixes || (game?.suffixes || []).map(s => s.text));
  for (const p of ps) {
    if (!n.startsWith(low(p))) continue;
    const s = ss.find(x => low(p) + low(x) === n);
    if (s !== undefined) return [p, s];
  }
  return null;
}

// Every name the game gives a cat, for the Any name box's suggestions: the cameo cats, the rogues and loners,
// and each prefix with each suffix.
export function catNames(game, final = null) {
  const out = new Set(Object.values(game?.iconic || {}));
  for (const r of final?.rogues || (game?.rogues || []).map(x => x.text)) out.add(r);
  const ps = final?.prefixes || (game?.prefixes || []).map(p => p.text);
  const ss = final?.suffixes || (game?.suffixes || []).map(s => s.text);
  for (const p of ps) for (const s of ss) out.add(p + s);
  return [...out].sort((a, b) => a.localeCompare(b));
}

// ---------- cats ----------
export const isOutsider = role => OUTSIDERS.includes(role);

// How names.json's "cats" names a cat: "player"; its name, when it's in the game being played, the name is known
// (not made up from a mod's IDs while that mod is off) and no other cat in the save has it; else its place, with
// "was" (catEntry). A cat in another game always goes by its place with the slot first: a bare name would mean
// the game being played as soon as a cat there gets that name.
export function catKey(c, nameCount) {
  if (c.target === "player") return "player";
  return c.current && c.name_known !== false && (nameCount.get(low(c.name)) || 0) === 1 ? c.name : c.target;
}
export function countNames(cats) {
  const m = new Map();
  for (const c of cats) m.set(low(c.name), (m.get(low(c.name)) || 0) + 1);
  return m;
}

// The key a cats entry for this cat is under in `entries`, or null: the key the page would write (catKey), else
// the cat's name in another case, its place, or "player" for your cat by name, as an older page or a hand-written
// file may have put it.
export function entryKeyFor(c, entries, nameCount) {
  const mine = catKey(c, nameCount);
  if (mine in entries) return mine;
  const keys = Object.keys(entries);
  return keys.find(k => k === c.target)
    || (c.current && c.name_known !== false && (nameCount.get(low(c.name)) || 0) === 1 ? keys.find(k => low(k) === low(c.name)) : null)
    || null;
}

// A cats entry as the box shows it: its text, and whether "grows with rank" is ticked. An entry written as
// {"fixed": ...} or {"name": ...} (the old three-way choice, or by hand) shows its text unticked.
export function entryText(value) {
  if (typeof value === "string") return { text: value, grows: false };
  if (value && typeof value === "object") {
    if (value.prefix) return { text: String(value.prefix), grows: true };
    return { text: String(value.fixed || value.name || ""), grows: false };
  }
  return { text: "", grows: false };
}

// What the box writes: nothing when it's empty; {"prefix": text} when "grows with rank" is ticked; else the plain
// name. A cat named by its place says what it's called now ("was"), so the entry stops counting if another cat
// takes that place.
export function catEntry(text, grows, key, c) {
  text = String(text || "").trim();
  if (!text) return undefined;
  const byPlace = key.includes("/") && !/(^|\/)player$/.test(key);
  if (byPlace) return grows ? { prefix: text, was: c.was ?? c.name } : { name: text, was: c.was ?? c.name };
  return grows ? { prefix: text } : text;
}

// Whether a cat can have "grows with rank": a clan cat (rogues and loners have no suffix to grow) whose new name
// isn't a prefix + suffix already (which grows on its own).
export function canGrow(c, text, game, final = null) {
  return !isOutsider(c.role) && !!String(text || "").trim() && !splitName(text, game, final);
}

// The line under a cat's box: how its new name works, from the preview's "how" for it.
export function outcomeLine(c, text, game, final = null, note = "") {
  text = String(text || "").trim();
  if (!text) return "";
  switch (c.how) {
    case "parts": { const s = splitName(text, game, final); return s ? `${s[0]} + ${s[1]}: grows with rank` : "grows with rank"; }
    case "fixed": return `${text} at every rank`;
    case "rogue": return "a rogue name";
    case "prefix": case "own-prefix": return `${c.with_mods || text} now; the end changes with each rank`;
    case "none": return note || "The game would have no text for this name, so the cat keeps its name";
    default: return "";
  }
}

// A name the game has for a cat a mod named, for "Give it a game name": the name it had before, when a mod's file
// says (c.before, from the preview: Wrenheart in {"Wrenheart": {"fixed": "Sparkle"}}) or this page's does, and the
// game can make it; else one of the game's prefixes with the suffix its rank gets; a rogue name for a rogue or loner.
export function gameNameFor(c, entries, game, final = null) {
  const rogues = final?.rogues || (game?.rogues || []).map(r => r.text);
  if (isOutsider(c.role)) return rogues.find(r => low(r) === low(c.before)) ?? rogues[0] ?? "";
  if (c.before && splitName(c.before, game, final)) return splitName(c.before, game, final).join("");
  for (const [k, v] of Object.entries(entries || {})) {
    const { text, grows } = entryText(v);
    if (!text || !c.name) continue;
    const named = grows ? low(c.name).startsWith(low(text)) : low(c.name) === low(text);
    if (!named) continue;
    if (!k.includes("/") && k !== "player" && splitName(k, game, final)) return splitName(k, game, final).join("");
    if (v && typeof v === "object" && v.was && splitName(v.was, game, final)) return splitName(v.was, game, final).join("");
  }
  const prefixes = game?.prefixes || [], suffixes = game?.suffixes || [];
  if (!prefixes.length || !suffixes.length) return "";
  const clan = CLANS.find(x => String(c.where || "").split("/")[0] === x);
  const pi = Math.max(0, prefixes.findIndex(p => (p.weights?.[clan] || 0) > 0));
  const rank = { Kit: "Kit", Apprentice: "Apprentice", Leader: "Leader" }[c.role] || "Warrior";
  const si = Math.max(0, suffixes.findIndex(s => (s.weights?.[rank] || 0) > 0));
  return (final?.prefixes?.[pi] ?? prefixes[pi].text) + (final?.suffixes?.[si] ?? suffixes[si].text);
}

// ---------- words ----------
// "MedicineCat" is "Medicine cat"; "RogueCatLeader" is "Rogue cat leader".
export function rankWords(role) {
  const s = String(role || "").replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}
// A story role in words: "TheAgingLeader" is "the aging leader", "ThunderClanDeputy" "ThunderClan deputy".
export function roleWords(role) {
  const words = String(role || "").match(/(?:Thunder|River|Shadow|Wind|Star)Clan|[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+/g) || [];
  return words.map(w => /Clan$/.test(w) ? w : w.toLowerCase()).join(" ");
}
export function ordinal(n) {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}
// A game's heading in the cats list: "Your 2nd game (Duskfang's)", the one being played said so.
export function slotHeading(slot, cats) {
  const you = cats.find(c => c.player);
  const n = /^\d+$/.test(String(slot)) ? ordinal(Number(slot) + 1) : String(slot);
  return `Your ${n} game${you ? ` (${you.name}'s)` : ""}`;
}
// Where a cat is, in words: "RiverClan · Warrior · 3", "you", with its story roles.
export function whereWords(c) {
  const where = c.where === "you" ? "your cat" : String(c.where || "").split("/").join(" · ");
  return [where, c.roles?.length ? `story role: ${c.roles.map(roleWords).join(", ")}` : ""].filter(Boolean).join(" · ");
}
export const clansWords = w => Object.entries(w || {}).filter(([, v]) => v > 0).map(([k]) => CLAN_LABEL[k] || k).join(", ") || "not given out";
export const ranksWords = w => Object.entries(w || {}).filter(([, v]) => v > 0).map(([k]) => rankWords(k).toLowerCase()).join(", ") || "not given out";

// "What this does", in a sentence, from a preview.
export function summary(view) {
  const n = view?.changed_names || 0, t = view?.changed_texts || 0, r = view?.renames || [];
  const said = [];
  if (n || t) said.push(`${plural(n, "name")} and ${plural(t, "text")} in the game change or are added`);
  if (r.length) said.push(`${plural(r.length, "cat")} renamed in your save: ${r.map(x => `${x.from} → ${x.to}`).join(", ")}`);
  return said.length ? said.join("; ") + "." : "Nothing changes yet: rename something below.";
}

// ---------- places, quests and items ----------
// A quest's name from its tag's last part: "RankUp" is "Rank Up", "Rest1" "Rest 1".
export function questWords(quest) {
  return String(quest || "").replace(/([a-z])([A-Z0-9])/g, "$1 $2");
}
// The quest titles of GET /names/texts grouped by quest, in the order they come: [{ quest, tag, titles: [...] }].
export function questGroups(quests) {
  const groups = new Map();
  for (const q of quests || []) {
    if (!groups.has(q.tag)) groups.set(q.tag, { quest: questWords(q.quest), tag: q.tag, titles: [] });
    groups.get(q.tag).titles.push(q);
  }
  return [...groups.values()];
}
export const KIND_WORDS = { consumable: "Herbs", material: "Materials", accessory: "Accessories", decoration: "Decorations" };
// The "text" entries none of the lists has: kept, and shown with their key so they can be changed or taken out.
export function otherTexts(entries, texts) {
  const known = new Set([...(texts?.areas || []), ...(texts?.quests || []), ...(texts?.items || [])].map(x => x.key).filter(Boolean));
  return Object.keys(entries || {}).filter(k => !known.has(k));
}

// The planner's notes about one part of names.json ("prefixes.rename.Otter", "cats.player").
export const notesAt = (view, where) => (view?.notes || []).filter(n => n.where === where).map(n => n.text);
