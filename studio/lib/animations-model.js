// The Animations page's pure parts (studio/sections/animations.js), apart from the page so node:test can check
// them: an animation's id, the animations.json the page saves, where an animation comes from and what it does,
// the switches that put settings aside, the game's sequences in groups with their plain names, and the keys an
// emote shouldn't share. The game's sequences are /game/anim-sequences' list (wcmods/studio.py,
// anim_sequences): name, paths, additive, label ("Yawn"), group ("everyday", "poses" or null).

// The keys the page has controls for; any other (a typo, a key a newer wcmods knows) the game won't take.
export const EDITED = new Set(["id", "name", "file", "game", "for", "clip", "loop", "speed", "blend", "emote", "key", "claws", "replaces"]);
// What each "What it does" choice uses; switching puts the ones the next choice doesn't use aside.
export const ROLE_KEYS = { emote: ["emote", "key", "claws", "loop", "speed", "blend"], scripts: ["loop", "speed", "blend"], replaces: ["replaces"] };
// What each "Where it comes from" choice uses.
export const SOURCE_KEYS = { game: ["game"], file: ["file", "clip", "_info"] };
// What a change of For puts aside: a file made for one animal has none of another's bones, and the game's
// sequences are each animal's own.
export const KIND_KEYS = ["file", "clip", "_info", "game", "replaces", "emote", "key", "claws"];
export const NEW_NAME = "New animation";

// "Tail wave" -> "TailWave": an animation's id is part of its name in the game, letters and digits; unique among
// `taken` without case, as the game's package names are.
export function animId(name, taken = []) {
  let base = (name || "").normalize("NFKD").replace(/[^A-Za-z0-9 ]+/g, "").split(/\s+/).filter(Boolean)
    .map(w => w[0].toUpperCase() + w.slice(1)).join("").slice(0, 40);
  if (!/^[A-Za-z]/.test(base)) base = "Anim" + base;
  const used = new Set(taken.map(x => String(x).toLowerCase()));
  let id = base, n = 2;
  while (used.has(id.toLowerCase())) id = `${base}${n++}`;
  return id;
}

// animations.json from the page's animations and the file's other keys: empty values, false, "for": "cat" (the
// default) and the page's own _new and _info are left out; an animation's other _ keys are kept.
export function toJson(anims, extra = {}) {
  const list = anims.map(a => {
    const o = {};
    for (const [k, v] of Object.entries(a)) {
      if (k === "_new" || k === "_info" || v === undefined || v === null || v === "" || v === false) continue;
      if (k === "for" && v === "cat") continue;
      o[k] = v;
    }
    return o;
  });
  return { _help: "Written by Clan Mod Studio (Animations). Animations of this mod's own. See docs/SDK.md, Animations.", ...extra, animations: list };
}

// Where it comes from: "game" (one of the game's sequences) or "file" (a glTF made in Blender). One with
// neither yet is what the page last chose for it (`chosen`), else the game's.
export function sourceOf(a, chosen) {
  if (a.game !== undefined) return "game";
  if (a.file !== undefined) return "file";
  return (chosen && chosen.get(a)) || "game";
}
// What it does: "replaces" (plays where the game plays one of its own), "emote" (your cat's), or "scripts". One
// chosen to replace a game animation, before that one is picked, is what the page last chose for it (`chosen`).
export function roleOf(a, chosen) {
  if (a.replaces) return "replaces";
  if (a.emote) return "emote";
  return chosen && chosen.get(a) === "replaces" ? "replaces" : "scripts";
}

// Switch one of the choices (group: "role", "source" or "kind") from `from` to `to`: the keys `from` uses and
// `to` doesn't go aside in `stash` (a WeakMap the page holds), and what was put aside for `to` comes back.
// keys: {choice: [keys]} for each choice, or one list for every choice.
export function switchChoice(a, stash, group, from, to, keys) {
  const aside = stash.get(a) || {};
  const mine = (aside[group] ||= {});
  const drop = Array.isArray(keys) ? keys : (keys[from] || []).filter(k => !(keys[to] || []).includes(k));
  const put = {};
  for (const k of drop) if (a[k] !== undefined) { put[k] = a[k]; delete a[k]; }
  if (Object.keys(put).length) mine[from] = put;
  if (mine[to]) { Object.assign(a, mine[to]); delete mine[to]; }
  stash.set(a, aside);
  return a;
}

// The game's sequences in the groups the page lists them in: the everyday ones by their plain names, the
// photo poses by the game's names for them, then all of them by their own names. Additive ones (keys added
// to another pose) can't play on their own and aren't listed.
export function sequenceGroups(list) {
  const usable = list.filter(s => !s.additive);
  const byLabel = (a, b) => a.label.localeCompare(b.label);
  const pose = s => Number((/(\d+)$/.exec(s.name) || [])[1] || 0);
  return [
    ["Everyday", usable.filter(s => s.group === "everyday" && s.label).sort(byLabel)],
    ["Photo poses", usable.filter(s => s.group === "poses" && s.label).sort((a, b) => pose(a) - pose(b))],
    ["All of them", usable],
  ].filter(([, l]) => l.length);
}
// A sequence's options in a list: its value (its name, or each path when the name is in more than one folder)
// and its text, the plain name first when there is one: "Yawn (A_CatMaster_Yawn_1)".
export function sequenceOptions(s) {
  const text = s.label ? `${s.label} (${s.name})` : s.name;
  return s.paths.length > 1 ? s.paths.map(p => ({ value: p, text: `${text}, in ${p.split("/").slice(-2, -1)[0]}` }))
    : [{ value: s.name, text }];
}
// The sequence a value names (a name, or one of its paths, maybe with ".<object>" after it).
export function findSequence(list, value) {
  if (!value) return null;
  const path = value.split(".")[0];
  return list.find(s => s.name === value || s.paths.includes(path)) || null;
}
// What the page calls a game sequence: its plain name, else its own short name.
export function plainName(list, value) {
  const s = findSequence(list || [], value);
  return s && s.label ? s.label : (value || "").split(".")[0].split("/").pop();
}

// ---------- whether it reached the game ----------
const manifestOf = r => r && (r.sections ? r : r.manifest && r.manifest.sections ? r.manifest : null);

// Why the build left one out, without the ", so it's left out of the game" the page says itself.
const plainWhy = w => String(w).replace(/, so it's left out( of the game)?$/, "");

// What the last Apply did with one of this mod's animations: null when it can't be told (no build yet), else
// {state: "in", "out" or "new", why (for "out"), key (an emote's, for "in"), replaced (the path of the game's
// sequence it plays in place of)}. "new": the last Apply didn't know it (added since, or saved but not applied:
// no note or warning names it), so the page says it isn't applied yet and doesn't count it. From the animations
// section's notes (animations, emotes, replaced) and its warnings, "animations: <mod>: <id>: ..."
// (sections/animations.py).
export function animationStatus(result, modId, a) {
  const m = manifestOf(result);
  if (!m || !a || !a.id) return null;
  const section = (m.sections || {}).animations;
  const notes = (m.notes || {}).animations;
  if (!notes && !section) return null;
  if (a._new) return { state: "new" };
  if (!(m.mods || []).includes(modId)) return { state: "out", why: "its mod wasn't in the last Apply (it was off, or couldn't be made ready)" };
  const full = `${modId}/${a.id}`;
  const prefix = `animations: ${modId}: ${a.id}: `;
  const said = (m.warnings || []).filter(w => w.startsWith(prefix)).map(w => w.slice(prefix.length));
  const replaced = Object.entries((notes || {}).replaced || {}).find(([, who]) => who === full);
  if (replaced) return { state: "in", replaced: replaced[0], also: said };
  if (((notes || {}).animations || []).includes(full)) {
    return { state: "in", key: ((notes || {}).emotes || []).includes(full) ? a.key || null : null, also: said };
  }
  const failed = ((section && section.failed) || []).find(([mod]) => mod === modId);
  if (!said.length && !failed) return { state: "new" };
  return { state: "out", why: plainWhy(said[0] || failed[1]) };
}

// The line at the top of the page: "In the game: Yawn (F7), Flap; left out: Long (the animation is 70.0 s long...)".
export function animationsSummary(result, modId, anims, label = k => k) {
  const states = anims.map(a => [a, animationStatus(result, modId, a)]).filter(([, s]) => s && s.state !== "new");
  if (!states.length) return null;
  const name = a => a.name || a.id;
  const inGame = states.filter(([, s]) => s.state === "in").map(([a, s]) => `${name(a)}${s.key ? ` (${label(s.key)})` : ""}`);
  const out = states.filter(([, s]) => s.state === "out").map(([a, s]) => `${name(a)} (${s.why})`);
  return [inGame.length ? `In the game: ${inGame.join(", ")}` : "Nothing here went in the game",
    out.length ? `left out: ${out.join(", ")}` : null].filter(Boolean).join("; ") + ".";
}

// The keys an emote shouldn't share, with why: the other emotes' keys in this mod (only one of them would
// play), and the game's full screen key. {key: why}
export function emoteReserved(anims, a, label = k => k) {
  const out = { F11: "F11 is the game's full screen key" };
  for (const o of anims) {
    if (o !== a && o.emote && o.key) out[o.key] = `${label(o.key)} is ${o.name || o.id}'s key too, and only one of them would play`;
  }
  return out;
}
