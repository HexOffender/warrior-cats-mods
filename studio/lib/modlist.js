// The Mods page's words and choices, without the page: what Find a mod matches, what a mod's requirements
// come to in an add preview, which state chip and button a mod that goes with Clan Mod Studio gets, what the
// toast says after adding, and what the "Not in the game yet" banner lists. Plain functions of the API's
// answers, so tests/studio/modlist.test.mjs runs them under node without a page.

// The four mods that go with Clan Mod Studio, as the scripts step names them (GET /addons has the rest).
export const ADDON_NAMES = "Menu pages, Sandbox mode, Creator palettes and the Emote wheel";

// A sentence as the page shows it: its first letter a capital, a full stop at the end.
export function sentence(text) {
  const s = String(text || "").trim();
  if (!s) return "";
  const capital = s.charAt(0).toUpperCase() + s.slice(1);
  return /[.!?:]$/.test(capital) ? capital : capital + ".";
}

// Whether a mod is one Find a mod shows for what's typed: the box keeps what's typed as it is; the match
// ignores capitals and the spaces at either end, and looks in the name, folder name, description and author.
export function matches(mod, typed) {
  const want = String(typed || "").trim().toLowerCase();
  if (!want) return true;
  return [mod.name, mod.id, mod.description, mod.author].map(v => String(v || "").toLowerCase()).join(" ").includes(want);
}

// What a mod in an add preview needs, against the mods in the same .zip (`inZip`, the preview's mods), the
// mods you have (`have`, GET /mods) and the mods that go with Clan Mod Studio (`addons`, GET /addons):
// [{id, name, where: "zip" | "have" | "missing", addon (true for one the add-ons card can add)}].
export function needs(mod, inZip = [], have = [], addons = []) {
  return (mod.requires || []).map(id => {
    const z = inZip.find(m => m.id === id && m !== mod);
    if (z) return { id, name: z.name, where: "zip", addon: false };
    const h = have.find(m => m.id === id);
    if (h) return { id, name: h.name, where: "have", addon: false };
    const a = addons.find(x => x.id === id);
    return { id, name: a ? a.name : id, where: "missing", addon: !!a };
  });
}

// The mods it works with that go with Clan Mod Studio and that you don't have ("uses" in mod.json).
export function worksWith(mod, inZip = [], have = [], addons = []) {
  return (mod.uses || []).filter(id => !inZip.some(m => m.id === id) && !have.some(m => m.id === id))
    .map(id => addons.find(a => a.id === id)).filter(Boolean);
}

// The line an add preview shows for a mod's requirements: [text, kind ("" or "warn")], or null with none.
export function needsLine(list) {
  if (!list.length) return null;
  const said = list.map(n => n.where === "zip" ? `${n.name} (in this .zip)` : n.name).join(", ");
  const missing = list.filter(n => n.where === "missing");
  if (!missing.length) return [`Needs ${said}, turned on with it.`, ""];
  const them = missing.map(n => n.name).join(", ");
  return [`Needs ${said}. You don't have ${them}, so it goes in switched off until you add ${missing.length > 1 ? "them" : "it"}.`, "warn"];
}

// A mod that goes with Clan Mod Studio, as its row on the add-ons card shows it: the chip (text and kind) and
// the one button it offers ("add", "on", "latest" or null), from GET /addons.
export function addonState(a) {
  let chip;
  if (!a.installed) chip = a.no_release ? ["No release yet", "warn"] : ["Not added", ""];
  else if (a.too_new) chip = ["Needs a newer Clan Mod Studio", "bad"];
  else if (!a.enabled) chip = ["Off", "warn"];
  else if (a.needs_code) chip = ["Needs scripts allowed", "warn"];
  else if (a.newer) chip = [`Newer one out: ${a.latest}`, "warn"];
  else chip = [a.version ? `In, ${a.version}` : "In", "good"];
  const action = !a.installed ? (a.no_release ? null : "add") : !a.enabled ? "on" : a.newer ? "latest" : null;
  return { chip: chip[0], kind: chip[1], action };
}

// Whether every one of them is in, on and current: the card then folds to one line.
export const allSet = addons => addons.length > 0 && addons.every(a => addonState(a).kind === "good");

// What the toast says after adding mods (modzip.add_zip's entries): what went in, what went on with them, and
// for a mod left off because a mod it needs is missing, what to do.
export function addedToast(added, addons = []) {
  const name = id => (addons.find(a => a.id === id) || {}).name || id;
  const parts = [];
  const fine = added.filter(a => !a.off_because);
  if (fine.length) parts.push(`Added ${fine.map(a => a.name).join(", ")}.`);
  const also = [...new Set(fine.flatMap(a => a.also_on || []))];
  if (also.length) parts.push(`Also on, because ${fine.length > 1 ? "they need" : "it needs"} them: ${also.join(", ")}.`);
  for (const a of added.filter(x => x.off_because)) {
    const missing = a.missing || [];
    const known = missing.length && missing.every(id => addons.some(x => x.id === id));
    const them = missing.length > 1 ? "them" : "it";
    parts.push(`Added ${a.name}, switched off: it needs ${missing.map(name).join(", ")}. ` +
      (known ? `Add ${them} from the add-ons card, then switch it on.` : `Add ${them}, then switch it on.`));
  }
  if (fine.some(a => a.on)) parts.push("Press Play to play with it.");
  return parts.join(" ");
}

// What a mod that goes with Clan Mod Studio being added or updated (POST /addons/<id>) says.
export function addonToast(r, codeAllowed) {
  if (r.unchanged) return `${r.name} ${r.version} is the latest already.`;
  const runsCode = (r.added || []).some(a => a.code);
  const extra = (r.added || []).filter(a => a.id !== r.id);
  const kept = r.kept || [];
  let said = `${r.name}${r.version ? " " + r.version : ""} is in your mods` +
    (r.replaced ? ", with your settings kept." : ".") +
    (extra.length ? ` It came with ${extra.length} more: ${extra.filter(a => a.on).length} on, the rest off.` : "") +
    (kept.length ? ` Your own ${kept.map(k => k.name).join(", ")} ${kept.length > 1 ? "have the same folder names as mods in it, so they were" : "has the same folder name as a mod in it, so it was"} left as ${kept.length > 1 ? "they are" : "it is"}.` : "");
  if (!r.on) said += " It's still off: switch it on, then Apply.";
  else if (runsCode && !codeAllowed) said += " It runs its own scripts, so allow that (Get set up, or Options on Settings and repair) for the game to get it.";
  else said += " Press Play to put it in the game.";
  return said;
}

// After a game update: the mods made for an older version, sorted by what the re-check (POST /mods/recheck)
// made of them, from GET /mods. fine: built on the new version, not applied since; failed: didn't build, with
// why (m.rechecked); couldnt: not checked, as the game's files couldn't be read; maker: code or the game's own
// kind of files, which only its maker can vouch for; unchecked: not checked yet.
export function recheckSorted(mods) {
  const left = mods.filter(m => m.enabled && m.outdated && !m.outdated.allowed);
  const couldnt = r => String(r || "").startsWith("couldn't check");
  return {
    fine: mods.filter(m => m.rechecked === "ok" && m.rechecked_since_apply),
    failed: left.filter(m => m.checkable && m.rechecked && m.rechecked !== "ok" && !couldnt(m.rechecked)),
    couldnt: left.filter(m => m.checkable && couldnt(m.rechecked)),
    maker: left.filter(m => !m.checkable),
    unchecked: left.filter(m => m.checkable && !m.rechecked),
  };
}

// The update banner's first sentence: "3 of your mods were checked on the new version and are fine. 1
// couldn't go in:" (the ones that couldn't follow, each with its reason), or "" when nothing was checked.
// `updated`: the game is on a build wcmods wasn't checked on ("the new version"); on the one it was checked on,
// a mod made for an older build is checked on "this version of the game".
export function recheckSentence(sorted, updated = true) {
  const { fine, failed } = sorted;
  const n = (k, one, many) => `${k} ${k === 1 ? one : many}`;
  const parts = [];
  if (fine.length) parts.push(`${n(fine.length, "of your mods was", "of your mods were")} checked on ${updated ? "the new version" : "this version of the game"} and ${fine.length === 1 ? "is" : "are"} fine.`);
  if (failed.length) parts.push(`${fine.length ? failed.length : n(failed.length, "of your mods", "of your mods")} couldn't go in:`);
  return parts.join(" ");
}

// The update banner's heading on the build wcmods was checked on: what's left out, or only what was checked.
export function recheckHeading(sorted) {
  const left = ["failed", "couldnt", "maker", "unchecked"].some(k => sorted[k].length);
  return left ? "Some mods are left out on this version of the game" : "Your mods were checked on this version of the game";
}

// The sentence for "No internet connection": what GitHub's trouble comes to when it couldn't be reached at all.
export const OFFLINE = "No internet connection; press Add all four again when you're online.";

// What Add all four says once it's done, from what happened to each: `went` (["Menu pages 1.0", …]),
// `unreleased` (names of those with no release yet) and `failed` ([{message, offline}], the other errors).
// {text, kind, done}: done says whether Get set up's step counts as done ("added"), which it doesn't when
// nothing went in for a reason other than no release yet. With no connection, one sentence says so.
export function addAllToast(went, unreleased, failed, codeAllowed) {
  const and = list => list.length > 1 ? `${list.slice(0, -1).join(", ")} and ${list[list.length - 1]}` : list[0];
  const done = went.length > 0 || failed.length === 0;
  if (!went.length && failed.length && failed.every(f => f.offline)) return { text: OFFLINE, kind: "bad", done };
  const offline = failed.filter(f => f.offline), other = failed.filter(f => !f.offline);
  const text = (went.length ? `Added ${and(went)}.` : "Nothing was added.")
    + (unreleased.length ? ` ${and(unreleased)} ${unreleased.length > 1 ? "have" : "has"} no release yet: the owner of that mod has to publish one, and its row below says so until then.` : "")
    + (offline.length ? ` The connection dropped before ${offline.length > 1 ? `${offline.length} of them` : "one of them"} went in; press its Add below to try again.` : "")
    + other.map(f => ` ${sentence(f.message)}`).join("")
    + (went.length && !codeAllowed ? " They run their own scripts, so Let mods run their own scripts is the next step." : went.length ? " Press Play to put them in the game." : "");
  return { text, kind: failed.length && !went.length ? "bad" : "info", done };
}

// What the add-ons card says when GitHub had no answer for "Check for newer versions" (GET /addons?latest=1):
// one sentence when it couldn't be reached at all, else each one's trouble ({id: sentence}); null when it
// answered for every one (no release yet is an answer, which each row says itself).
export function checkTrouble(addons) {
  const trouble = addons.filter(a => a.error && !a.no_release);
  if (!trouble.length) return null;
  if (trouble.every(a => a.offline)) return { all: "No internet connection, so GitHub couldn't be asked; press Check for newer versions again when you're online.", each: {} };
  return { all: null, each: Object.fromEntries(trouble.map(a => [a.id, sentence(a.error)])) };
}

// The "Not in the game yet" banner's list, from GET /changes.
export function changeParts(c) {
  const name = i => (c.names || {})[i] || i;
  return [
    ...c.on.map(i => `${name(i)} on`),
    ...c.off.map(i => `${name(i)} off`),
    ...c.changed.map(i => `${name(i)} changed`),
    ...Object.entries(c.left_out || {}).map(([i, why]) => `${name(i)} left out: ${why}`),
    ...(c.redo || []).map(r => `apply again: ${r}`),
  ];
}

// How many changes the status chip counts from GET /changes: mods on, off and changed, each reason to apply
// again, and the left-out mods still in the game (the next install takes them out).
export const changeCount = c => c.on.length + c.off.length + c.changed.length + (c.redo || []).length + (c.still_in || []).length;
