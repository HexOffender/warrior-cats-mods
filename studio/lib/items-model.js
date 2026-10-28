// The Items page's pure parts (studio/sections/items.js), apart from the page so node:test can check them: an
// item's id, the items.json the page saves, an item's tag and kind, what a new accessory look needs, the Kind
// switch that puts fields aside, and the words for what a herb does, who it's for and its badge.
// The game's items are /game/items' list (wcmods/studio.py, game_items): tag, short, kind, name, effect, words,
// target, combat, exploring, fight_only, group...

export const KIND = { consumable: "Herb", material: "Material", accessory: "Accessory" };
// Accessories that can take new looks, by their slot, and what the page calls the slot; head ones can't.
export const SLOTS = { Neck: "Neck", Body: "Body", Legs: "Paw" };
// What makes a new accessory look its own (wcmods/sections/items.py, OWN_LOOK), and the colour a new one starts in.
export const OWN_LOOK = ["texture", "model", "place", "opacity"];
export const NEW_LOOK = "#a8c4ff";
// The herb a new herb starts from: Medium Healing Herb, which heals 50.
export const START_HERB = "MediumHealingHerb";

// "Moon Herb" -> "MoonHerb": an item's id is part of its tag, letters and digits. Unique among `taken` (the
// mod's other items) and `avoid` (the game's own short ids of that kind), ignoring case as Windows does.
export function itemId(name, taken = [], avoid = []) {
  let base = (name || "").normalize("NFKD").replace(/[^A-Za-z0-9 ]+/g, "").split(/\s+/).filter(Boolean)
    .map(w => w[0].toUpperCase() + w.slice(1)).join("").slice(0, 40);
  if (!/^[A-Za-z]/.test(base)) base = "Item" + base;
  const used = new Set([...taken, ...avoid].map(x => String(x).toLowerCase()));
  let id = base, n = 2;
  while (used.has(id.toLowerCase())) id = `${base}${n++}`;
  return id;
}

// A picture of the mod's own (a path in its folder), not one of the game's items or textures.
export const isPicture = v => typeof v === "string" && (v.startsWith("pictures/") || v.toLowerCase().endsWith(".png"));

// items.json from the page's items and the file's other keys: empty values and an empty recipe are left out,
// and so is the page's own _new; an item's other _ keys (a note written by hand) are kept.
export function toJson(items, extra = {}) {
  const list = items.map(it => {
    const o = {};
    for (const [k, v] of Object.entries(it)) {
      if (k === "_new" || v === undefined || v === null || v === "") continue;
      if (k === "recipe" && (!v || !Object.keys(v).length)) continue;
      o[k] = v;
    }
    return o;
  });
  return { _help: "Written by Clan Mod Studio (Items). Herbs, materials and accessories of this mod's own. See docs/SDK.md, New items.", ...extra, items: list };
}

// A game item's whole tag from what items.json may say: "Neck.DogCollar.1", "Cosmetic.Neck.DogCollar.1",
// "Dandelion" (a herb's or a material's short id, looked up in byTag), or the whole tag.
export function fullTag(short, byTag) {
  if (!short) return null;
  if (short.startsWith("Gameplay.Inventory.")) return short;
  if (/^(Head|Neck|Body|Legs)\./.test(short)) return `Gameplay.Inventory.Cosmetic.${short}`;
  if (short.startsWith("Cosmetic.")) return `Gameplay.Inventory.${short}`;
  for (const k of ["Consumable", "Materials"]) if (byTag.has(`Gameplay.Inventory.${k}.${short}`)) return `Gameplay.Inventory.${k}.${short}`;
  return null;
}

// An item's kind: its own, or the kind of the game item it's "like".
export function kindOf(it, byTag) {
  if (it.kind) return it.kind;
  const like = byTag.get(fullTag(it.like, byTag));
  return like ? like.kind : null;
}

// Whether an accessory has nothing of its own: no look, model, place or opacity, so it would be the look it
// starts from again (the build leaves it out). Only accessories: a herb's or a material's model is optional.
export function needsOwn(it, kind) {
  return kind === "accessory" && OWN_LOOK.every(k => it[k] === undefined);
}
// Give such an accessory a colour of its own again; true when it did (the page says why).
export function giveOwn(it, kind) {
  if (!needsOwn(it, kind)) return false;
  it.texture = { tint: NEW_LOOK };
  return true;
}

// The Kind switch. Each kind keeps its own fields (what it starts from, its effect, recipe, look, model,
// place, icon...) in `stash`, a WeakMap the page holds, never on the item: switching away puts them aside,
// switching back before the page is left brings them back. The name, description, how many to start with,
// and hand-written _ notes stay with the item. start(kind) is what a kind with nothing put aside starts from.
const KEEP = new Set(["id", "name", "description", "give", "kind"]);
export function switchKind(it, kind, stash, start, from = it.kind) {
  const aside = stash.get(it) || {};
  const mine = {};
  for (const k of Object.keys(it)) {
    if (KEEP.has(k) || k.startsWith("_")) continue;
    mine[k] = it[k];
    delete it[k];
  }
  if (from) aside[from] = mine;
  it.kind = kind;
  if (aside[kind]) {
    Object.assign(it, aside[kind]);
    delete aside[kind];
  } else {
    it.like = start(kind);
    if (kind === "accessory") it.texture = { tint: NEW_LOOK };
  }
  stash.set(it, aside);
  return it;
}

// The game's herb an effect is named by: one that's for you alone when there's one (Marigold Petal, not the
// pouch for your team), with words when there are.
export function effectHerb(effect, herbs) {
  const who = herbs.filter(h => h.effect === effect);
  return who.find(h => h.words && h.target !== "OwnerTeam") || who.find(h => h.words) || who[0] || null;
}
// What an effect does, in words, and the herb that does it: "Heals 50 health (Marigold Petal)". For an
// effect the words don't cover (a game update's), the herbs that have it, as before.
export function effectName(effect, herbs) {
  const h = effectHerb(effect, herbs);
  if (h && h.words) return `${h.words} (${h.name})`;
  const who = herbs.filter(x => x.effect === effect).map(x => x.name);
  return who.length ? `${who.slice(0, 2).join(", ")}'s` : effect.replace("Gameplay.Effect.Consumable.", "").replace(/\./g, " ");
}
// The keys an effect's herb brings with it: choosing "Whole team +50% Strength for the fight" makes the herb
// work as that one does (who for, and when), so what the list said is what it does.
export const EFFECT_KEYS = ["effect", "type", "target", "combat", "exploring", "fight_only"];
export function chooseEffect(it, effect, herbs) {
  for (const k of EFFECT_KEYS) delete it[k];
  const h = effect ? effectHerb(effect, herbs) : null;
  if (!h) return it;
  it.effect = effect;
  if (h.type) it.type = h.type;
  for (const k of ["target", "combat", "exploring", "fight_only"]) if (h[k] !== undefined) it[k] = h[k];
  return it;
}

// Who a herb is for and when it can be used, from its own keys or the herb it starts from: "Used anywhere,
// for you", "Used in fights only, for your whole team; it wears off when the fight ends".
export function whoAndWhen(it, like = {}) {
  const get = k => (it[k] !== undefined ? it[k] : like[k]);
  const combat = get("combat") !== false, exploring = get("exploring") !== false;
  const where = combat && exploring ? "anywhere" : combat ? "in fights only" : exploring ? "while exploring only" : "never";
  const who = get("target") === "OwnerTeam" ? "for your whole team" : "for you";
  return `Used ${where}, ${who}${combat && get("fight_only") ? "; it wears off when the fight ends" : ""}`;
}

// A badge in words: which of the game's herbs carry it.
export function badgeWords(group, herbs) {
  if (!group || group === "None") return "No badge";
  const who = herbs.filter(h => h.group === group).map(h => h.name);
  return who.length ? `${group}: like ${who.slice(0, 2).join(" and ")}${who.length > 2 ? " and others" : ""}` : group;
}

// ---------- whether it reached the game ----------
// The build's manifest from an "installed" event's result, or from /build/last's (both may hold it as `manifest`).
export const manifestOf = r => r && (r.sections ? r : r.manifest && r.manifest.sections ? r.manifest : null);
// What the build says about an item that still went in: said in the page's words.
const STILL_IN = [[/lies there as the game's pickup instead$/, "on the ground it's the game's pickup"],
  [/^no save yet to give it in/, "no save to give it in yet"]];

// What the last Apply did with one of this mod's items: null when it can't be told (no build yet, or one an
// older wcmods made, whose note lists tags only), else {state: "in" or "out", why (for "out"), also (for
// "in": what it said about it, in words), look (an accessory's: its look number)}. From the items section's
// note {"<mod>/<id>": tag} and its warnings, "items: <mod>: <id>: ..." (sections/items.py).
export function itemStatus(result, modId, item) {
  const m = manifestOf(result);
  if (!m || !item || !item.id) return null;
  const section = (m.sections || {}).items;
  const note = ((m.notes || {}).items || {}).items;
  if (Array.isArray(note) || (!note && !section)) return null;
  if (!(m.mods || []).includes(modId)) return { state: "out", why: "its mod wasn't in the last Apply (it was off, or couldn't be made ready)" };
  const prefix = `items: ${modId}: ${item.id}: `;
  const said = (m.warnings || []).filter(w => w.startsWith(prefix)).map(w => w.slice(prefix.length));
  const tag = (note || {})[`${modId}/${item.id}`];
  if (!tag) {
    const failed = ((section && section.failed) || []).find(([mod]) => mod === modId);
    return { state: "out", why: said[0] || (failed ? failed[1] : "it didn't go in") };
  }
  // One tag, or (a herb and a material with one id) a list of them.
  const look = [].concat(tag).map(t => /^Gameplay\.Inventory\.Cosmetic\..*\.(\d+)$/.exec(t)).find(Boolean);
  return { state: "in", also: said.map(w => (STILL_IN.find(([re]) => re.test(w)) || [null, w])[1]), look: look ? Number(look[1]) : null };
}

// The line at the top of the page: how many of the items went in, and the first that didn't, by name.
export function itemsSummary(result, modId, items) {
  const states = items.map(it => [it, itemStatus(result, modId, it)]).filter(([, s]) => s);
  if (!states.length) return null;
  const went = states.filter(([, s]) => s.state === "in").length;
  const out = states.find(([, s]) => s.state === "out");
  return `${went} of ${states.length} item${states.length === 1 ? "" : "s"} went in.` +
    (out ? ` ${out[0].name || out[0].id} was left out: ${out[1].why}.` : "");
}
