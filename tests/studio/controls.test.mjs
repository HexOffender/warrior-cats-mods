// The Controls page's model (studio/lib/controls.js) over the game's keys as GET /game/keys serves them
// (fixtures/game-keys.json, which tests/unit/test_repo.py keeps in step with wcmods/keymap.py): what a row shows,
// what each button writes into controls.json, the keys a creator can't or shouldn't pick, and the capture
// dialog's keys. The input names come from studio/lib/wc.js, through the DOM shim.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { install, REPO } from "./lib/dom.mjs";

const dom = install();
const wc = await import(dom.studio("lib/wc.js"));
const M = await import(dom.studio("lib/controls.js"));
const game = JSON.parse(fs.readFileSync(path.join(REPO, "tests", "studio", "fixtures", "game-keys.json"), "utf8"));
const fresh = (obj = null) => M.normalize(obj, game);
const json = s => M.toJson(s);

// ---------- the game's keys, and what a reset writes ----------
test("the Pause row's game key is Escape, and setting it to Escape is not a change", () => {
  const s = fresh();
  assert.equal(M.effective(s, game, "keyboard", "Player_Pause"), "Escape");
  assert.equal(M.set(s, game, "keyboard", "Player_Pause", "Escape"), false);
  assert.deepEqual(json(s), {});
});

test("keyboard reset writes nothing", () => {
  const s = fresh({ keyboard: { Player_Interact: "F", Player_Pause: "Enter", Player_Movement_Up: "K" }, keys: { T: "W", H: "E" } });
  assert.equal(M.resetDevice(s, game, "keyboard"), true);
  assert.deepEqual(json(s), {});
});

test("controller reset writes nothing, and leaves a stick entry for its own Remove", () => {
  const s = fresh({ gamepad: { Player_Run: "LT", Player_Interact: "y" } });
  M.resetDevice(s, game, "gamepad");
  assert.deepEqual(json(s), {});
  const sticks = fresh({ gamepad: { Player_Movement_Up: "Gamepad_RightY" } });
  M.resetDevice(sticks, game, "gamepad");
  assert.deepEqual(json(sticks), { gamepad: { Player_Movement_Up: "Gamepad_RightY" } });
});

test("undo removes the override and nothing else", () => {
  const s = fresh({ keyboard: { Player_Interact: "F", Player_Run: "G" }, menus: { keys: { U: "Enter" } } });
  M.undo(s, game, "keyboard", "Player_Interact");
  assert.deepEqual(json(s), { keyboard: { Player_Run: "G" }, menus: { keys: { U: "Enter" } } });
});

test("a change to the game's key removes the entry", () => {
  const s = fresh({ keyboard: { Player_Interact: "F" } });
  assert.equal(M.set(s, game, "keyboard", "Player_Interact", "e"), true);
  assert.deepEqual(json(s), {});
});

test("undo writes the game's key when a lower mod sets the action", () => {
  // Another mod, earlier in the list, puts Interact on G: this mod's "back to E" has to be written to win.
  const s = fresh({ keyboard: { Player_Interact: "F" } });
  M.undo(s, game, "keyboard", "Player_Interact", [["keyboard", "Player_Interact"]]);
  assert.deepEqual(json(s), { keyboard: { Player_Interact: "E" } });
  assert.equal(M.changed(s, game, "keyboard", "Player_Interact"), false);
});

test("a loaded entry equal to the game's key is kept", () => {
  const s = fresh({ keyboard: { Player_Interact: "E" } });
  assert.equal(M.changed(s, game, "keyboard", "Player_Interact"), false);
  assert.deepEqual(json(s), { keyboard: { Player_Interact: "E" } });
});

test("a file of the old Keyboard defaults shows one change, Pause on Enter", () => {
  const old = { keyboard: { ...game.keyboard, Player_Pause: "Enter" } };
  for (const a of ["Player_Show_Inventory", "Player_Show_Quest", "Player_Show_Map", "Player_Growl"]) delete old.keyboard[a];
  const s = fresh(old);
  const changed = M.PLAY_ROWS.concat(game.axes).filter(a => M.changed(s, game, "keyboard", a));
  assert.deepEqual(changed, ["Player_Pause"]);
  assert.equal(M.gameKey(game, "keyboard", "Player_Pause"), "Escape");
  M.undo(s, game, "keyboard", "Player_Pause");
  assert.ok(!("Player_Pause" in json(s).keyboard));
});

test("Interact on Enter leaves the Pause row alone", () => {
  const s = fresh();
  M.set(s, game, "keyboard", "Player_Interact", "Enter");
  assert.equal(M.effective(s, game, "keyboard", "Player_Pause"), "Escape");
  assert.equal(M.changed(s, game, "keyboard", "Player_Pause"), false);
});

// ---------- reading files ----------
test("normalize accepts L2 and {key: F}, drops null, and keeps notes", () => {
  const s = fresh({ _help: "mine", keyboard: { Player_Interact: { key: "f" }, Player_Run: null, Player_Crouch: ["C"] },
    gamepad: { Player_Run: "L2", Player_Drop: "circle" }, keys: { _x: "y", t: "W" }, menus: { keys: { u: "Enter" } } });
  assert.deepEqual(json(s), { _help: "mine", keyboard: { Player_Interact: "F" },
    gamepad: { Player_Run: "Gamepad_LeftTrigger", Player_Drop: "Gamepad_FaceButton_Right" }, keys: { _x: "y", T: "W" }, menus: { keys: { U: "Enter" } } });
  assert.deepEqual(json(fresh(["not", "an", "object"])), {});
});

test("notes inside each section are kept, and what the build can't read is said before a save drops it", () => {
  const file = { _help: "top", keyboard: { _why: "for left-handers", Player_Interact: "F", Player_Run: null },
    gamepad: { _note: "pad" }, keys: { _x: 1, T: "W", Y: [1] }, menus: { _m: "outer", keys: { _k: "inner", U: "Enter" }, extra: 1 },
    mouse: { Player_Pounce: "LeftMouseButton" } };
  const s = fresh(file);
  assert.deepEqual(json(s), { _help: "top", keyboard: { _why: "for left-handers", Player_Interact: "F" }, gamepad: { _note: "pad" },
    keys: { _x: 1, T: "W" }, menus: { _m: "outer", keys: { _k: "inner", U: "Enter" } } });
  const name = a => (game.names[a] || [a])[0];
  assert.deepEqual(M.droppedSaid(s, name), [
    'The part called "mouse": the game reads only keyboard, gamepad, keys and menus.',
    "Run (keyboard): null isn't a key's name.",
    '"Y" in "keys": [1] isn\'t a key\'s name.',
    'In "menus", "extra": the menus part holds only "keys".',
  ]);
  // Notes alone keep their section; a file with nothing left out says nothing.
  assert.deepEqual(json(fresh({ menus: { _m: "only" } })), { menus: { _m: "only" } });
  assert.deepEqual(M.droppedSaid(fresh({ keyboard: { Player_Interact: "F" } })), []);
  assert.deepEqual(M.droppedSaid(fresh({ keyboard: 5 })), ['The part called "keyboard", which should hold keys by name and doesn\'t.']);
});

test("keys T:W and Y:W round-trip (row T, extra pair Y)", () => {
  const file = { keys: { T: "W", Y: "W" } };
  const s = fresh(file);
  assert.equal(M.rawKey(s, "W"), "T");
  assert.deepEqual(M.unshown(s, game), [{ section: "keys", name: "Y" }]);
  assert.deepEqual(json(s), file);
  M.setRaw(s, "W", "W");   // the row back on W: its pair goes, the extra stays
  assert.deepEqual(json(s), { keys: { Y: "W" } });
  assert.equal(M.rawKey(s, "W"), "Y");
});

test("pairs and entries without a row round-trip under For mod makers", () => {
  const file = { keyboard: { Button_Skip: "G", Player_Play: "N" }, gamepad: { Player_Show_Map: "Gamepad_DPad_Up" },
    keys: { J: "Enter", Gamepad_DPad_Left: "M" }, menus: { keys: { I: "Up" } } };
  const s = fresh(file);
  assert.deepEqual(M.unshown(s, game).map(o => `${o.section}:${o.name}`).sort(),
    ["gamepad:Player_Show_Map", "keyboard:Button_Skip", "keyboard:Player_Play", "keys:Gamepad_DPad_Left", "keys:J", "menus:I"]);
  assert.deepEqual(json(s), file);
  M.remove(s, "keys", "J");
  assert.ok(!("J" in json(s).keys));
});

// ---------- the controller ----------
test("swap(nintendo) maps A/B and X/Y and leaves the sticks", () => {
  const s = fresh();
  M.swap(s, game, M.SWAPS.nintendo.map);
  assert.equal(M.effective(s, game, "gamepad", "Player_Interact"), "Gamepad_FaceButton_Right");
  assert.equal(M.effective(s, game, "gamepad", "Player_Drop"), "Gamepad_FaceButton_Bottom");
  assert.equal(M.effective(s, game, "gamepad", "Player_Pounce"), "Gamepad_FaceButton_Left");
  assert.equal(M.effective(s, game, "gamepad", "Player_Scent_Tracking"), "Gamepad_FaceButton_Top");
  for (const a of game.axes) assert.ok(!(a in s.gamepad), a);
  M.swap(s, game, M.SWAPS.nintendo.map);   // twice is the game's layout again: nothing written
  assert.deepEqual(json(s), {});
});

test("swap never touches an axis row, and a stick can't be set", () => {
  const s = fresh();
  M.swap(s, game, { Gamepad_LeftY: "Gamepad_RightY", Gamepad_RightY: "Gamepad_LeftY" });
  assert.deepEqual(json(s), {});
  assert.equal(M.set(s, game, "gamepad", "Player_Movement_Up", "Gamepad_RightY"), false);
  assert.deepEqual(json(s), {});
});

test("a loaded stick entry is kept until Remove", () => {
  const s = fresh({ gamepad: { Player_Camera_Up: "Gamepad_LeftY" } });
  M.swap(s, game, M.SWAPS.shoulders.map);
  M.resetDevice(s, game, "gamepad");
  assert.deepEqual(json(s), { gamepad: { Player_Camera_Up: "Gamepad_LeftY" } });
  M.undo(s, game, "gamepad", "Player_Camera_Up");
  assert.deepEqual(json(s), {});
});

test("a cannot item is never written: no controller button for Inventory", () => {
  const s = fresh();
  assert.equal(M.gameKey(game, "gamepad", "Player_Show_Inventory"), null);
  assert.equal(M.set(s, game, "gamepad", "Player_Show_Inventory", "Gamepad_DPad_Up"), false);
  assert.deepEqual(json(s), {});
});

// ---------- more rows and second keys ----------
test("inventory row writes keyboard Player_Show_Inventory", () => {
  const s = fresh();
  assert.ok(M.PLAY_ROWS.includes("Player_Show_Inventory"));
  M.set(s, game, "keyboard", "Player_Show_Inventory", "O");
  assert.deepEqual(json(s), { keyboard: { Player_Show_Inventory: "O" } });
});

test("second key writes keys H:E even when the action moved to F", () => {
  const s = fresh({ keyboard: { Player_Interact: "F" } });
  M.addSecond(s, "keys", M.gameKey(game, "keyboard", "Player_Interact"), "h");
  assert.deepEqual(json(s), { keyboard: { Player_Interact: "F" }, keys: { H: "E" } });
  assert.deepEqual(M.secondKeys(s, "keys", "E"), ["H"]);
  assert.deepEqual(M.unshown(s, game), []);
});

test("removing a second key removes only the pair", () => {
  const s = fresh({ keyboard: { Player_Interact: "F" }, keys: { H: "E", T: "W" } });
  M.remove(s, "keys", "H");
  assert.deepEqual(json(s), { keyboard: { Player_Interact: "F" }, keys: { T: "W" } });
});

test("a second key for Drop shows on Talk to a friend too, since C does both", () => {
  const s = fresh();
  M.addSecond(s, "keys", M.gameKey(game, "keyboard", "Player_Drop"), "V");
  assert.deepEqual(M.secondKeys(s, "keys", M.gameKey(game, "keyboard", "Player_Friend_Talk")), ["V"]);
});

test("a key that stands for another isn't taken over: the dialog says where it is", () => {
  // H as a second Interact, then as a second Drop: refused, and H still interacts.
  const s = fresh();
  const E = M.gameKey(game, "keyboard", "Player_Interact"), C = M.gameKey(game, "keyboard", "Player_Drop");
  assert.equal(M.addSecond(s, "keys", E, "H"), true);
  assert.equal(M.pairTaken(s, game, "keys", "h", C), "H is already a second key for Interact; remove it there first.");
  assert.equal(M.addSecond(s, "keys", C, "H"), false);
  assert.deepEqual(json(s), { keys: { H: "E" } });
  assert.equal(M.pairTaken(s, game, "keys", "H", E), null, "the same pair again is nothing to refuse");
  // As a moving key: the same.
  assert.match(M.pairTaken(s, game, "keys", "H", "W"), /^H is already a second key for Interact/);
  assert.equal(M.setRaw(s, "W", "H"), false);
  assert.deepEqual(json(s), { keys: { H: "E" } });
  // A moving key, then a second key on it; a second key for C names both of C's actions.
  M.setRaw(s, "W", "T");
  assert.equal(M.pairTaken(s, game, "keys", "T", E), "T is already the key for Move forward; give that another key first.");
  M.addSecond(s, "keys", C, "V");
  assert.equal(M.pairTaken(s, game, "keys", "V", E), "V is already a second key for Drop and Talk to a friend; remove it there first.");
  // For mod makers' pair, whose game key comes next: any pair the key already makes.
  M.addSecond(s, "keys", "Enter", "J");
  assert.equal(M.pairTaken(s, game, "keys", "J", null), "J already stands for Enter while you explore; remove it under For mod makers first.");
  // In menus: Confirm also on U, then U for Back.
  M.addSecond(s, "menus", "Enter", "U");
  assert.equal(M.pairTaken(s, game, "menus", "U", "BackSpace", k => wc.input.keyLabel(k)),
    "U is already a second key for Confirm in menus; remove it there first.");
  assert.equal(M.addSecond(s, "menus", "BackSpace", "U"), false);
  assert.equal(M.pairTaken(s, game, "menus", "H", "BackSpace"), null, "a menus pair is its own: H in play doesn't count");
});

test("Undo puts back what the file had, not the game's key", () => {
  // A mod loaded with Interact on F, changed to G: Undo gives F back, and Save keeps it.
  const s = fresh({ keyboard: { Player_Interact: "F" }, keys: { T: "W" } });
  const loaded = M.clone(s);
  M.set(s, game, "keyboard", "Player_Interact", "G");
  assert.equal(M.differs(s, loaded, "keyboard", "Player_Interact"), true);
  assert.equal(M.revert(s, loaded, "keyboard", "Player_Interact"), true);
  assert.deepEqual(json(s), { keyboard: { Player_Interact: "F" }, keys: { T: "W" } });
  assert.equal(M.differs(s, loaded, "keyboard", "Player_Interact"), false);
  // A row the file didn't have: Undo takes the entry away.
  M.set(s, game, "keyboard", "Player_Run", "B");
  M.revert(s, loaded, "keyboard", "Player_Run");
  assert.ok(!("Player_Run" in json(s).keyboard));
  // A moving key: back to the file's T.
  M.setRaw(s, "W", "Y");
  assert.equal(M.differsRaw(s, loaded, "W"), true);
  assert.equal(M.revertRaw(s, loaded, "W"), true);
  assert.deepEqual(json(s).keys, { T: "W" });
});

test("confirm also on U writes a menus pair", () => {
  const s = fresh();
  const confirm = M.MENU_ROWS.find(r => r.command === "Button_Confirm");
  M.addSecond(s, "menus", confirm.key, "U");
  assert.deepEqual(json(s), { menus: { keys: { U: "Enter" } } });
  assert.equal(M.addSecond(s, "menus", confirm.key, "Enter"), false, "the game's own key is no second key");
});

// ---------- keys that are taken ----------
const inUse = [
  { key: "Insert", does: "opens the mod menu", from: "wcmods", taken: "refuse" },
  { key: "Gamepad_Special_Left", does: "opens the mod menu", from: "wcmods", taken: "refuse" },
  { key: "F11", does: "switches between a window and full screen", from: "the game", taken: "refuse" },
  { key: "T", does: "opens the emote wheel", from: "Emote wheel", taken: "warn" },
  { key: "E", does: "Interact", from: "the game", taken: null },
];

test("whyNot(key) refuses the menu key, its pad button and F11 with a sentence", () => {
  assert.deepEqual(M.whyNot("Insert", inUse), { refuse: "Insert opens the mod menu (wcmods); pick another key." });
  assert.ok(M.whyNot("Gamepad_Special_Left", inUse, "play", k => wc.input.keyLabel(k)).refuse.startsWith("View opens the mod menu"));
  assert.ok(M.whyNot("F11", inUse).refuse.startsWith("F11 switches between a window and full screen"));
});

test("whyNot allows T with a warning, and the game's own keys freely", () => {
  assert.deepEqual(M.whyNot("T", inUse), { warn: "T also opens the emote wheel (Emote wheel), and will do both while that mod is on." });
  assert.equal(M.whyNot("E", inUse), null);
  assert.equal(M.whyNot("G", inUse), null);
});

test("a mouse button is refused in menus with a sentence, and allowed for an action", () => {
  assert.match(M.whyNot("ThumbMouseButton", inUse, "menus").refuse, /^In menus a click goes to the button under the cursor/);
  assert.equal(M.whyNot("ThumbMouseButton", inUse, "play"), null);
});

// ---------- the capture dialog's keys ----------
test("in the capture dialog Escape cancels, Tab moves, and Enter presses a focused button or is the key", () => {
  const k = wc.input.keyFromEvent;
  assert.deepEqual(M.captureKey({ code: "Escape", key: "Escape" }, true, k), { do: "cancel" });
  assert.deepEqual(M.captureKey({ code: "Tab", key: "Tab", shiftKey: true }, false, k), { do: "move", back: true });
  assert.deepEqual(M.captureKey({ code: "Enter", key: "Enter" }, true, k), { do: "press" });
  assert.deepEqual(M.captureKey({ code: "Enter", key: "Enter" }, false, k), { do: "bind", key: "Enter" });
  assert.deepEqual(M.captureKey({ code: "Space", key: " " }, false, k), { do: "bind", key: "SpaceBar" });
  assert.deepEqual(M.captureKey({ code: "KeyF", key: "f" }, true, k), { do: "bind", key: "F" });
  assert.deepEqual(M.captureKey({ code: "F13", key: "F13" }, false, k), { do: "unknown" });
});

test("keyFromEvent: F12 is F12, F13 and F24 are null", () => {
  assert.equal(wc.input.keyFromEvent({ code: "F12" }), "F12");
  assert.equal(wc.input.keyFromEvent({ code: "F13" }), null);
  assert.equal(wc.input.keyFromEvent({ code: "F24" }), null);
});

// ---------- the build's word, on its rows ----------
test("check lines land on their rows", () => {
  const check = { rows: { keyboard: { Player_Interact: { key: "F", status: "game", line: "F does Interact.", notes: [] } } } };
  assert.equal(M.checkRow(check, "keyboard", "Player_Interact").line, "F does Interact.");
  assert.equal(M.checkRow(check, "keys", "H"), null);
  assert.equal(M.checkRow(null, "keyboard", "Player_Interact"), null);
});

test("every play row has a name from the game's names, and none shows a raw id", () => {
  for (const a of M.PLAY_ROWS) assert.ok(game.names[a] && !/_/.test(game.names[a][0]), a);
  for (const r of M.MENU_ROWS) assert.ok(game.names[r.command], r.command);
  for (const r of M.MOVE_ROWS) for (const k of r.keys) assert.ok(game.names[k.raw ? `key:${k.raw}` : k.action], r.name);
});

// ---------- mouse look ----------
// Timers the test moves on by hand: run() fires what's due.
function handTimers() {
  let next = 1;
  const due = new Map();
  return { set: (f) => { const id = next++; due.set(id, f); return id; }, clear: id => due.delete(id),
    run() { const fs = [...due.values()]; due.clear(); for (const f of fs) f(); }, get waiting() { return due.size; } };
}

test("mouse look saves are queued and debounced: three quick changes are one save, the last one", async () => {
  const saved = [], timers = handTimers();
  const q = M.saveQueue(async job => { saved.push(job); }, 300, timers);
  q.push({ settings: { sensitivity: 1.1 }, enabled: true });
  q.push({ settings: { sensitivity: 1.2 }, enabled: true });
  q.push({ settings: { sensitivity: 1.3 }, enabled: true });
  assert.equal(timers.waiting, 1);
  timers.run();
  await q.flush();
  assert.deepEqual(saved, [{ settings: { sensitivity: 1.3 }, enabled: true, switched: false }]);
});

test("a mouse look save never starts while another is under way", async () => {
  const order = [], timers = handTimers();
  let release;
  const q = M.saveQueue(job => new Promise(ok => {
    order.push(`start ${job.settings.n}`);
    if (job.settings.n === 1) release = () => { order.push("end 1"); ok(); }; else { order.push(`end ${job.settings.n}`); ok(); }
  }), 300, timers);
  q.push({ settings: { n: 1 } });
  timers.run();
  q.push({ settings: { n: 2 } });
  timers.run();
  await new Promise(r => setTimeout(r, 0));
  assert.deepEqual(order, ["start 1"]);
  release();
  await q.flush();
  assert.deepEqual(order, ["start 1", "end 1", "start 2", "end 2"]);
});

test("only a switch change toasts: the switch stays said when a slider moves right after it", async () => {
  const saved = [], timers = handTimers();
  const q = M.saveQueue(async job => { saved.push(job.switched); }, 300, timers);
  q.push({ settings: {}, enabled: true, switched: true });
  q.push({ settings: { smoothing: 50 }, enabled: true });
  timers.run();
  q.push({ settings: { smoothing: 60 }, enabled: true });
  timers.run();
  await q.flush();
  assert.deepEqual(saved, [true, false]);
});

test("tilt sliders keep the lowest under the highest, in whole degrees from -89 to 89", () => {
  assert.deepEqual(M.tilt(-20, 23), [-20, 23]);
  assert.deepEqual(M.tilt(30, 23, "min"), [22, 23], "the lowest moved up past the highest: it stops a degree under");
  assert.deepEqual(M.tilt(-20, -30, "max"), [-20, -19], "the highest moved down past the lowest: it stops a degree over");
  assert.deepEqual(M.tilt(89, 89, "min"), [88, 89]);
  assert.deepEqual(M.tilt(-89, -89, "max"), [-89, -88]);
  assert.deepEqual(M.tilt(-100, 100.4), [-89, 89]);
  assert.deepEqual(M.tilt("-20.4", "23.6"), [-20, 24]);
});
