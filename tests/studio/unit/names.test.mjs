// The Names page (studio/sections/names.js and names-logic.js) under the DOM shim, with a scripted studio
// behind it: GET /names and POST /names/preview answer as wcmods/studio.py's names_preview does, from the
// test's own small game and save. The planner itself is tested in tests/unit/test_names.py.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick, Element } from "../lib/dom.mjs";

const dom = install();
const logic = await import(dom.studio("sections/names-logic.js"));

// ---------- a small game, as GET /names gives it ----------
const P = (text, id, w) => ({ row: "1", text, id, weights: { ThunderClan: 0, RiverClan: 0, ShadowClan: 0, WindClan: 0, OutOfClans: 0, ...w } });
const S = (text, id, w) => ({ row: "1", text, id, weights: { Kit: 0, Apprentice: 0, Warrior: 0, Deputy: 0, Leader: 0, ...w } });
const GAME = {
  prefixes: [P("Wood", "STR_CAT_NAME1", { ThunderClan: 0.04 }), P("Otter", "STR_CAT_NAME53", { RiverClan: 0.05 }), P("Ripple", "STR_CAT_NAME60", { RiverClan: 0.02 })],
  suffixes: [S("kit", "_KIT", { Kit: 1 }), S("paw", "_PAW", { Apprentice: 1 }), S("heart", "_HEART", { Warrior: 0.1, Deputy: 0.1 }),
    S("star", "_STAR", { Leader: 1 }), S("storm", "_STORM", { Warrior: 0.1 })],
  rogues: [{ row: "1", label: "Fury", id: "STR_ROGUE_CAT_NAME_5", text: "Fury" }, { row: "2", label: "Storm", id: "STR_ROGUE_CAT_NAME_16", text: "Storm" }],
  banned: [{ row: "1", name: "Woodstar", prefix: "STR_CAT_NAME1", suffix: "_STAR" }],
  iconic: { STR_CAT_NAME_ICONIC_8: "Rock" },
};
const FINAL = { prefixes: GAME.prefixes.map(p => p.text), suffixes: GAME.suffixes.map(s => s.text), rogues: GAME.rogues.map(r => r.text) };
const cat = (target, name, role, extra = {}) => ({
  target, slot: "0", current: true, player: target === "player", where: target === "player" ? "you" : target, roles: [], role, name,
  with_mods: name, how: null, mod_named: false, name_known: true, was: name, before: "", ...extra });
const CATS = () => [
  cat("player", "Otterpaw", "Apprentice"),
  cat("Outsiders/0", "Fury", "RogueCat"),
  cat("RiverClan/Warrior/0", "Woodheart", "Warrior"),
  cat("RiverClan/Warrior/1", "Sparkle", "Warrior", { mod_named: true, name_known: false, was: "STR_CAT_NAME_WCM_FIXED_SPARKLE_HEART", before: "Rippleheart" }),
];

// The studio behind the page. A cats entry is found by the cat's place or name, as the planner finds it; what the
// rename works out as is "fixed", or "own-prefix" with "grows with rank", unless the test says (state.how).
function fresh(extra = {}) {
  return { file: null, cats: CATS(), how: {}, notes: [], losing: () => [], previews: [], delays: [], names: null, saveProblem: null, final: FINAL,
           puts: [], ...extra };
}
function answer(state, spec) {
  const entries = spec.cats || {};
  const cats = state.cats.map(c => {
    const key = Object.keys(entries).find(k => k === c.target || (c.name_known && k.toLowerCase() === c.name.toLowerCase()));
    if (!key) return { ...c };
    const v = entries[key], { text, grows } = logic.entryText(v);
    const how = state.how[text] || (grows ? "own-prefix" : "fixed");
    return { ...c, how, with_mods: how === "none" ? c.name : grows ? `${text}paw` : text };
  });
  return { ...GAME, final: state.final, cats, current_slot: "0", save_problem: state.saveProblem, renames: [], losing_text: state.losing(spec),
           names_hits: state.hits || {}, warnings: state.notes.map(n => n.text), notes: state.notes, changed_names: state.changedNames || 0,
           changed_texts: state.changedTexts || 0 };
}
function routes(state) {
  return {
    "GET /names": () => { if (state.names) return state.names(); return answer(state, {}); },
    "POST /names/preview": async body => {
      state.previews.push(body);
      const wait = state.delays.shift() || 0;
      if (wait) await tick(wait);
      return answer(state, body.spec || {});
    },
    "GET /mods": () => [{ id: "mine", name: "Mine", enabled: true, kinds: ["names"], problem: null }],
    "GET /mods/mine/file/names.json": () => state.file ? { exists: true, text: JSON.stringify(state.file) } : { exists: false, text: null },
    "PUT /mods/mine/file/names.json": b => { state.puts.push(JSON.parse(b.text)); return { saved: "names.json", requires: [], problems: [] }; },
  };
}

let last = null;   // the page open now, so the next test closes it (its timers would call the next test's studio)
async function open(state = fresh()) {
  if (last) { last.handle?.unmount?.(); last = null; }
  dom.routes = routes(state);
  dom.calls.length = 0;
  for (const type of Object.keys(dom.windowListeners)) delete dom.windowListeners[type];
  localStorage.clear();
  localStorage.setItem("wc-target", "mine");
  const wc = await import(dom.studio("lib/wc.js") + "?" + Math.random());   // a fresh module per page (its bus is module state)
  const page = (await import(dom.studio("sections/names.js") + "?" + Math.random())).default;
  const root = new Element("div");
  dom.byId.main.append(root);
  const p = { wc, root, state, q: sel => root.querySelector(sel), all: sel => root.querySelectorAll(sel) };
  p.handle = await page.mount(root, wc);
  last = p;
  await tick(20);
  p.box = name => p.q(`input[aria-label="New name for ${name}"]`);
  p.grows = name => p.q(`input[aria-label="${name}'s new name grows with rank"]`);
  p.row = target => p.q(`tr[data-key="cat:${target}"]`);
  p.json = () => JSON.parse(p.q("pre").textContent);
  p.type = async (input, text) => { input.focus(); input.value = text; input.dispatch("input"); input.dispatch("change"); await tick(420); };
  return p;
}
const lineOf = (p, target) => p.row(target).querySelectorAll("div").find(d => d.className.startsWith("names-line"))?.textContent;
const afterOf = (p, target) => p.row(target).querySelector("td.names-after").textContent;

// ---------- the page ----------
test("the page says it's reading the game's names, and a read that fails goes up for app.js to offer Try again", async () => {
  const state = fresh({ names: () => { throw { status: 400, error: "Clan Mod Studio hasn't found the game yet: Get set up, on the Mods page, asks where it is" }; } });
  dom.routes = routes(state);
  const wc = await import(dom.studio("lib/wc.js") + "?" + Math.random());
  const page = (await import(dom.studio("sections/names.js") + "?" + Math.random())).default;
  const root = new Element("div");
  await assert.rejects(page.mount(root, wc), /^Error: Clan Mod Studio hasn't found the game yet/);
  assert.match(root.textContent, /Reading the game's names…/);
  assert.equal(root.querySelector(".target"), null, "nothing half drawn: no Editing-mod bar");
  // Try again (app.js mounts the page afresh) once the game is found.
  const p = await open(fresh());
  assert.ok(p.box("Otterpaw") && !/Reading the game's names/.test(p.root.textContent));
});

test("the head has the page's title, its three rules, the help link and the Cat 1 fold", async () => {
  const p = await open();
  assert.equal(p.q("h1").textContent, "Names");
  assert.equal(p.q(".section-head").querySelector("p").textContent, "Rename your cats, the names new cats get, and the words the game shows.");
  assert.deepEqual(p.q(".names-rules").children.map(li => li.textContent), [
    "Renames change the English text.",
    "New names (a new prefix, a name of your own) are text this mod adds, so keep the mod on.",
    "Cat renames go into your save when you Apply, after a backup."]);
  assert.equal(p.q(".names-missing").querySelector("summary").textContent, "If a cat shows as Cat 1 or <MISSING STRING TABLE ENTRY>");
  let asked = null;
  p.wc.bus.on("help", page => { asked = page; });
  p.q(".section-head").querySelector("button").click();
  assert.equal(asked, "names");
});

test("a save that can't be read says so, and Try again reads it again", async () => {
  const state = fresh({ saveProblem: "Couldn't read your save: it's cut short, or not laid out the way wcmods expects (the game may be writing it just now). The cats list is empty until it can be read" });
  state.cats = [];
  const p = await open(state);
  const card = p.q('[data-key="names:cats"]');
  assert.match(card.textContent, /Couldn't read your save: it's cut short/);
  state.saveProblem = null;
  state.cats = CATS();
  card.querySelectorAll("button").find(b => b.textContent === "Try again").click();
  await tick(30);
  assert.ok(p.box("Otterpaw"), "the cats are listed once the save reads");
});

test("a save that stops reading between previews is said too, not left as No save yet", async () => {
  const state = fresh();
  state.cats = [];
  const p = await open(state);
  assert.match(p.q('[data-key="names:cats"]').textContent, /No save yet/);
  state.saveProblem = "Couldn't open your save (Permission denied). The cats list is empty until it can be read";
  await p.type(p.q('input[aria-label="New text for Otter"]'), "Moth");
  assert.match(p.q('[data-key="names:cats"]').textContent, /Couldn't open your save \(Permission denied\)/);
});

test("a name that isn't a prefix + suffix says it stays the same at every rank, and the file has it plain", async () => {
  const p = await open();
  await p.type(p.box("Otterpaw"), "Sparkle");
  assert.equal(lineOf(p, "player"), "Sparkle at every rank");
  assert.equal(afterOf(p, "player"), "Sparkle");
  assert.equal(p.json().cats.player, "Sparkle");
  assert.equal(p.grows("Otterpaw").parent.hidden, false, "a clan cat's name of its own can grow with rank");
});

test("grows with rank writes a prefix entry, and the line says the name it has now", async () => {
  const p = await open();
  await p.type(p.box("Otterpaw"), "Sparkle");
  p.grows("Otterpaw").checked = true;
  p.grows("Otterpaw").dispatch("change");
  await tick(420);
  assert.deepEqual(p.json().cats.player, { prefix: "Sparkle" });
  assert.equal(lineOf(p, "player"), "Sparklepaw now; the end changes with each rank");
  assert.match(p.grows("Otterpaw").parent.textContent, /grows with rank \(Sparklekit, Sparklepaw…\)/);
});

test("a rogue or loner has no grows with rank, and neither has a prefix + suffix", async () => {
  const p = await open(fresh({ how: { Otterheart: "parts" } }));
  await p.type(p.box("Fury"), "Moonlight");
  assert.equal(p.grows("Fury").parent.hidden, true);
  await p.type(p.box("Woodheart"), "Otterheart");
  assert.equal(p.grows("Woodheart").parent.hidden, true);
  assert.equal(lineOf(p, "RiverClan/Warrior/0"), "Otter + heart: grows with rank");
});

test("an old fixed entry fills the box and stays as written until the box changes", async () => {
  const p = await open(fresh({ file: { cats: { Woodheart: { fixed: "Sparkle" }, player: { name: "Otterheart" } } } }));
  assert.equal(p.box("Woodheart").value, "Sparkle");
  assert.equal(p.grows("Woodheart").checked, false);
  assert.equal(p.box("Otterpaw").value, "Otterheart");
  assert.deepEqual(p.json().cats, { Woodheart: { fixed: "Sparkle" }, player: { name: "Otterheart" } });
  await p.type(p.box("Woodheart"), "Sparkly");
  assert.deepEqual(p.json().cats, { Woodheart: "Sparkly", player: { name: "Otterheart" } });
});

test("a rename the game would have no text for shows a no-text mark and the planner's sentence", async () => {
  const said = "Woodheart would have no text in the game as 'Otter', so it keeps its name; pick a name the game has, or a name of your own";
  const p = await open(fresh({ how: { Otter: "none" }, notes: [{ where: "cats.Woodheart", text: said }] }));
  await p.type(p.box("Woodheart"), "Otter");
  assert.match(afterOf(p, "RiverClan/Warrior/0"), /^no textkeeps its name$/);
  assert.equal(lineOf(p, "RiverClan/Warrior/0"), said);
});

test("names written in another case or by ID fill the right boxes, and the file keeps one key each", async () => {
  const p = await open(fresh({ file: { prefixes: { rename: { otter: "Moth", STR_CAT_NAME1: "Oak", Ottr: "X" }, remove: ["RIPPLE"], weights: { Otter: { RiverClan: 0.1 } } },
                                        banned: { remove: ["woodstar"], clear: false } } }));
  assert.equal(p.q('input[aria-label="New text for Otter"]').value, "Moth");
  assert.equal(p.q('input[aria-label="New text for Wood"]').value, "Oak");
  assert.equal(p.q('input[aria-label="Remove Ripple"]').checked, true);
  const file = p.json();
  assert.deepEqual(file.prefixes, { rename: { Otter: "Moth", Wood: "Oak", Ottr: "X" }, remove: ["Ripple"], weights: { Otter: { RiverClan: 0.1 } } });
  assert.deepEqual(file.banned, { remove: ["Woodstar"], clear: false });
  assert.ok(dom.byId.toasts.textContent.includes("aren't in the game's lists") && dom.byId.toasts.textContent.includes("Ottr"));
});

test("the Find box keeps its text through Add, and Reset shows only on a row with a change", async () => {
  const p = await open();
  const find = p.q('input[aria-label="Find a prefix"]');
  find.value = "ott";
  find.dispatch("input");
  p.q('input[aria-label="New prefix"]').value = "Sparrow";
  p.all("button").find(b => b.textContent === "Add prefix").click();
  await tick(10);
  assert.equal(p.q('input[aria-label="Find a prefix"]').value, "ott");
  const shown = p.q('[data-key="names:prefixes"]').querySelectorAll("tr").filter(tr => tr.dataset.name && !tr.hidden).map(tr => tr.dataset.name);
  assert.deepEqual(shown, ["otter"]);
  assert.equal(p.q('button[aria-label="Reset Otter"]').hidden, true);
  const otter = p.q('input[aria-label="New text for Otter"]');
  otter.value = "Moth";
  otter.dispatch("change");
  assert.equal(p.q('button[aria-label="Reset Otter"]').hidden, false);
  p.q('button[aria-label="Reset Otter"]').click();
  assert.equal(otter.value, "");
  assert.deepEqual(p.json().prefixes, { add: { Sparrow: {} } });
});

test("rows update in place after a preview, so the box being typed in keeps its place", async () => {
  const p = await open();
  const box = p.box("Woodheart");
  await p.type(box, "Sparkle");
  assert.equal(document.activeElement, box);
  assert.ok(p.root.contains(box), "the same box, not one drawn again");
  assert.equal(p.state.previews.length, 2);   // the one on opening, and the one after typing
});

test("taking out an earlier rename asks first when a cat would lose its name for it", async () => {
  const losing = spec => (spec.cats || {}).Ripplestorm ? [] : [{ target: "RiverClan/Warrior/1", name: "Sparkle", key: "STR_CAT_NAME_WCM_FIXED_SPARKLE_HEART" }];
  const p = await open(fresh({ file: { cats: { Ripplestorm: { fixed: "Sparkle" }, Nobody: "Otterheart" } }, losing }));
  const earlier = p.q(".names-earlier");
  assert.match(earlier.textContent, /Earlier renames.*Ripplestorm → Sparkle.*Nobody → Otterheart/);
  // One that no cat needs goes at once.
  earlier.querySelector('button[aria-label="Forget the rename of Nobody"]').click();
  await tick(20);
  assert.equal(p.json().cats.Nobody, undefined);
  // One a cat needs asks.
  p.q('button[aria-label="Forget the rename of Ripplestorm"]').click();
  await tick(20);
  const ask = p.q('[aria-label="Forget this rename?"]');
  assert.equal(ask.hidden, false);
  assert.match(ask.textContent, /Forget this rename\? Sparkle would show as <MISSING STRING TABLE ENTRY> until you give it another name\./);
  ask.querySelectorAll("button").find(b => b.textContent === "Keep it").click();
  assert.deepEqual(p.json().cats.Ripplestorm, { fixed: "Sparkle" });
  p.q('button[aria-label="Forget the rename of Ripplestorm"]').click();
  await tick(20);
  p.q('[aria-label="Forget this rename?"]').querySelectorAll("button").find(b => b.textContent === "Forget it").click();
  assert.equal(p.json().cats?.Ripplestorm, undefined);
});

test("a cat a mod named says so, and Give it a game name offers the name it had", async () => {
  const losing = () => [{ target: "RiverClan/Warrior/1", name: "Sparkle", key: "STR_CAT_NAME_WCM_FIXED_SPARKLE_HEART" }];
  const p = await open(fresh({ losing }));
  const row = p.row("RiverClan/Warrior/1");
  assert.match(row.textContent, /name from a mod that's off/);
  assert.match(afterOf(p, "RiverClan/Warrior/1"), /no textshows as <MISSING STRING TABLE ENTRY>/);
  assert.match(p.q(".names-losing").textContent, /A cat would show as <MISSING STRING TABLE ENTRY> after the next Apply/);
  row.querySelector('button[aria-label="Give Sparkle a game name"]').click();
  assert.equal(p.box("Sparkle").value, "Rippleheart");
  // By its place, with the IDs it has now as "was": its name isn't known while its mod is off.
  assert.deepEqual(p.json().cats["RiverClan/Warrior/1"], { name: "Rippleheart", was: "STR_CAT_NAME_WCM_FIXED_SPARKLE_HEART" });
});

test("after an Apply the cats are read again, even with changes not saved", async () => {
  const p = await open();
  await p.type(p.box("Otterpaw"), "Sparkle");
  assert.equal(p.q(".target").querySelector(".dirty").textContent, "Unsaved changes");
  p.state.cats[2].name = p.state.cats[2].with_mods = p.state.cats[2].was = "Stormheart";   // renamed in the save by the Apply
  p.wc.bus.emit("installed", {});
  await tick(30);
  assert.ok(p.box("Stormheart"), "the cat is listed by its new name");
  assert.equal(p.box("Otterpaw").value, "Sparkle", "the change not saved is still there");
  assert.equal(p.q(".target").querySelector(".dirty").textContent, "Unsaved changes");
  assert.ok(!dom.calls.slice(-3).some(c => c.url.includes("/file/names.json")), "the file isn't read again over the changes");
});

test("a late answer to an older preview doesn't win over a newer one", async () => {
  const state = fresh();
  const p = await open(state);
  state.delays.push(300, 0);   // the first preview after this is slow, the next quick
  const box = p.box("Otterpaw");
  box.value = "Old"; box.dispatch("change");
  await tick(380);   // the slow preview has gone out
  box.value = "New"; box.dispatch("change");
  await tick(700);   // both are back, the slow one last
  assert.equal(lineOf(p, "player"), "New at every rank");
});

test("What this does says names and texts apart, and the ban list and Any name read after the renames", async () => {
  const state = fresh({ changedNames: 2, changedTexts: 54, hits: { Rock: { cats: ["the cameo cat Rock"], elsewhere: ["the material Rock"] } },
                        final: { ...FINAL, prefixes: ["Lion", "Otter", "Ripple"] } });
  const p = await open(state);
  await p.type(p.q('input[aria-label="New text for Rock"]'), "Pebble");
  assert.equal(p.q(".names-summary").querySelector("p").textContent, "2 names and 54 texts in the game change or are added.");
  assert.equal(p.q('[data-key="names:banned"]').querySelector("button").textContent, "Lionstar");
  assert.match(p.q('input[aria-label="New text for Rock"]').closest("tr").textContent, /also changes the material Rock/);
});

test("the prefix row a new part copies says the clans it's given out in", async () => {
  const p = await open(fresh({ file: { prefixes: { add: { Sparrow: { like: "otter" } } } } }));
  const row = p.q('button[aria-label="Remove Sparrow"]').closest("tr");
  assert.match(row.textContent, /used like Otter.*River/);
  assert.deepEqual(p.json().prefixes.add, { Sparrow: { like: "Otter" } });
});

// ---------- the logic ----------
test("catKey names a cat by its name only when that's safe, else by its place", () => {
  const cats = CATS();
  const count = logic.countNames(cats);
  assert.deepEqual(cats.map(c => logic.catKey(c, count)), ["player", "Fury", "Woodheart", "RiverClan/Warrior/1"]);
  const twins = [cat("RiverClan/Warrior/0", "Woodheart", "Warrior"), cat("RiverClan/Warrior/1", "Woodheart", "Warrior")];
  assert.deepEqual(twins.map(c => logic.catKey(c, logic.countNames(twins))), ["RiverClan/Warrior/0", "RiverClan/Warrior/1"]);
  const elsewhere = cat("1/RiverClan/Warrior/0", "Duskfang", "Warrior", { current: false, slot: "1" });
  assert.equal(logic.catKey(elsewhere, logic.countNames([elsewhere])), "1/RiverClan/Warrior/0");
  assert.equal(logic.entryKeyFor(cats[2], { woodheart: "X" }, count), "woodheart");
  assert.equal(logic.entryKeyFor(cats[3], { "RiverClan/Warrior/1": { name: "X", was: "Y" } }, count), "RiverClan/Warrior/1");
  assert.equal(logic.entryKeyFor(cats[3], { Sparkle: "X" }, count), null, "a name made up from IDs never finds an entry by name");
});

test("catEntry writes a plain name, a prefix, or a place with what the cat is called now", () => {
  const c = cat("RiverClan/Warrior/1", "Sparkle", "Warrior", { was: "STR_X" });
  assert.equal(logic.catEntry("  Moth  ", false, "Woodheart", c), "Moth");
  assert.deepEqual(logic.catEntry("Moth", true, "Woodheart", c), { prefix: "Moth" });
  assert.deepEqual(logic.catEntry("Moth", false, "RiverClan/Warrior/1", c), { name: "Moth", was: "STR_X" });
  assert.deepEqual(logic.catEntry("Moth", true, "1/RiverClan/Warrior/1", c), { prefix: "Moth", was: "STR_X" });
  assert.equal(logic.catEntry("Moth", false, "1/player", c), "Moth");
  assert.equal(logic.catEntry("  ", false, "player", c), undefined);
  assert.deepEqual([logic.entryText({ fixed: "A" }), logic.entryText({ prefix: "B" }), logic.entryText("C"), logic.entryText(null)],
    [{ text: "A", grows: false }, { text: "B", grows: true }, { text: "C", grows: false }, { text: "", grows: false }]);
});

test("splitName finds the prefix and suffix a name is made of, after the page's renames", () => {
  assert.deepEqual(logic.splitName("otterHEART", GAME), ["Otter", "heart"]);
  assert.equal(logic.splitName("Otterhart", GAME), null);
  assert.deepEqual(logic.splitName("Lionstar", GAME, { ...FINAL, prefixes: ["Lion", "Otter", "Ripple"] }), ["Lion", "star"]);
  assert.equal(logic.textOf(GAME, "STR_CAT_NAME1", "_STAR", { ...FINAL, prefixes: ["Lion", "Otter", "Ripple"] }), "Lionstar");
  assert.ok(logic.catNames(GAME).includes("Rippleheart") && logic.catNames(GAME).includes("Rock") && logic.catNames(GAME).includes("Fury"));
});

test("the line under a cat's box says how its new name works", () => {
  const c = how => cat("player", "Otterpaw", "Apprentice", { how, with_mods: "Sparklepaw" });
  assert.equal(logic.outcomeLine(c("parts"), "Otterheart", GAME), "Otter + heart: grows with rank");
  assert.equal(logic.outcomeLine(c("fixed"), "Sparkle", GAME), "Sparkle at every rank");
  assert.equal(logic.outcomeLine(c("rogue"), "Storm", GAME), "a rogue name");
  assert.equal(logic.outcomeLine(c("own-prefix"), "Sparkle", GAME), "Sparklepaw now; the end changes with each rank");
  assert.equal(logic.outcomeLine(c("none"), "Otter", GAME, null, "why"), "why");
  assert.equal(logic.outcomeLine(c(null), "Sparkle", GAME), "");
  assert.equal(logic.outcomeLine(c("fixed"), "", GAME), "");
  assert.equal(logic.canGrow(cat("Outsiders/0", "Fury", "RogueCat"), "Moon", GAME), false);
  assert.equal(logic.canGrow(c(null), "Otterheart", GAME), false);
  assert.equal(logic.canGrow(c(null), "Moon", GAME), true);
});

test("gameNameFor offers the name a cat had, else a game name for its rank, else a rogue name", () => {
  const sparkle = cat("RiverClan/Warrior/1", "Sparkle", "Warrior", { before: "rippleheart" });
  assert.equal(logic.gameNameFor(sparkle, {}, GAME), "Rippleheart");
  const named = cat("RiverClan/Warrior/1", "Sparkle", "Warrior");
  assert.equal(logic.gameNameFor(named, { Otterheart: { fixed: "Sparkle" } }, GAME), "Otterheart");
  assert.equal(logic.gameNameFor(named, { "RiverClan/Warrior/1": { name: "Sparkle", was: "Woodstorm" } }, GAME), "Woodstorm");
  assert.equal(logic.gameNameFor(named, {}, GAME), "Otterheart", "RiverClan's first prefix, a warrior's first suffix");
  assert.equal(logic.gameNameFor(cat("RiverClan/Apprentice/0", "Glowpaw", "Apprentice"), {}, GAME), "Otterpaw");
  assert.equal(logic.gameNameFor(cat("Outsiders/0", "Moss", "RogueCat", { before: "storm" }), {}, GAME), "Storm");
  assert.equal(logic.gameNameFor(cat("Outsiders/0", "Moss", "RogueCat"), {}, GAME), "Fury");
});

test("readNames and writeNames keep what the page doesn't edit as written", () => {
  const file = { _help: "x", prefixes: { rename: { otter: "Moth" }, weights: { Otter: { RiverClan: 0.1 } } }, banned: { clear: true, add: ["Otterheart"] },
                 text: { STR_BOT_NAME_1: "Hi" }, cats: { player: { fixed: "Sparkle" } }, rogues: { rename: { fury: "Rage" }, add: ["Moss"] } };
  const { spec, extra, unplaced } = logic.readNames(file, GAME);
  assert.deepEqual(unplaced, []);
  assert.deepEqual(logic.writeNames(spec, extra), {
    _help: "Written by Clan Mod Studio. See docs/formats.md, names.json.",
    prefixes: { rename: { Otter: "Moth" }, weights: { Otter: { RiverClan: 0.1 } } }, rogues: { rename: { Fury: "Rage" }, add: ["Moss"] },
    banned: { add: ["Otterheart"], clear: true }, cats: { player: { fixed: "Sparkle" } }, text: { STR_BOT_NAME_1: "Hi" } });
  // Two keys for one name: the later wins, as in the build.
  assert.deepEqual(logic.readNames({ prefixes: { rename: { otter: "Moth", Otter: "Mink" } } }, GAME).spec.prefixes.rename, { Otter: "Mink" });
});

test("ranks, story roles and games read as words", () => {
  assert.equal(logic.rankWords("MedicineCat"), "Medicine cat");
  assert.equal(logic.roleWords("TheAgingLeader"), "the aging leader");
  assert.equal(logic.roleWords("ThunderClanDeputy"), "ThunderClan deputy");
  assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 22].map(logic.ordinal), ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd"]);
  assert.equal(logic.slotHeading("1", [cat("1/player", "Duskfang", "Warrior", { player: true })]), "Your 2nd game (Duskfang's)");
  assert.equal(logic.whereWords(cat("RiverClan/Leader/0", "Guststar", "Leader", { roles: ["TheAgingLeader"] })),
    "RiverClan · Leader · 0 · story role: the aging leader");
  assert.equal(logic.summary({ changed_names: 1, changed_texts: 1, renames: [{ from: "A", to: "B" }] }),
    "1 name and 1 text in the game change or are added; 1 cat renamed in your save: A → B.");
  assert.equal(logic.summary({}), "Nothing changes yet: rename something below.");
});

// ---------- Settings and repair: taking every mod out ----------
async function openSettings(losing) {
  if (last) { last.handle?.unmount?.(); last = null; }
  const tasks = [];
  dom.routes = {
    "GET /ingame": () => null, "GET /settings": () => ({ allow_code_mods: false, data_dir: "x" }), "GET /info": () => ({ sections: [] }),
    "GET /backups": () => [], "GET /mods/removed": () => [], "GET /names/losing": () => ({ losing }),
  };
  const wc = await import(dom.studio("lib/wc.js") + "?" + Math.random());
  wc.bus.on("run-task", t => tasks.push(t.path));
  const page = (await import(dom.studio("sections/settings.js") + "?" + Math.random())).default;
  const root = new Element("div");
  last = { handle: await page.mount(root, wc) };
  const button = text => root.querySelectorAll("button").find(b => b.textContent === text);
  return { root, tasks, button };
}

test("Take all mods out asks first when cats would lose their names, and offers the Names page", async () => {
  const s = await openSettings([{ target: "player", where: "player", name: "Sparkle", player: true, current: true },
                                { target: "Wrenheart", where: "RiverClan/Warrior/0", name: "Wrenheart", player: false, current: true }]);
  s.button("Take all mods out of the game").click();
  await tick(20);
  const ask = s.root.querySelector('[aria-label="Cats that would lose their names"]');
  assert.equal(ask.hidden, false);
  assert.equal(ask.querySelector("span").textContent, "2 cats in your save have names only your mods give (your cat (Sparkle) and Wrenheart). " +
    "After this they show as <MISSING STRING TABLE ENTRY> until you put a backup of your save back, or give them game names on the Names page and Apply first.");
  assert.equal(ask.querySelector("a").getAttribute("href"), "#names");
  assert.deepEqual(s.tasks, []);
  s.button("Take them out anyway").click();
  assert.deepEqual(s.tasks, ["/uninstall"]);
});

test("Take all mods out with no cat to lose takes two presses, as before", async () => {
  const s = await openSettings([]);
  s.button("Take all mods out of the game").click();
  await tick(20);
  assert.ok(s.button("Press again to take them out"));
  assert.deepEqual(s.tasks, []);
  s.button("Press again to take them out").click();
  assert.deepEqual(s.tasks, ["/uninstall"]);
});
