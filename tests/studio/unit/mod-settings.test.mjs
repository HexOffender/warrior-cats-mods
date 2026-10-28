// A script's settings on its mod's card (studio/lib/scriptsettings.js and the Settings block in
// studio/sections/mods.js) under the DOM shim: the rows the mod menu's page would have, "_help_<key>" under its
// row and "_min_"/"_max_" its bounds, and a Save that writes the file back in its own order with 12.0 still 12.0.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick } from "../lib/dom.mjs";

const dom = install();
const TEXT = `{
  "_help": "Game Tweaks' settings. Change them on the mod's card in Clan Mod Studio, or on its page in the mod menu (Insert).",
  "keep_stamina_full": false,
  "heal_key": "F5",
  "_help_heal_key": "A key UE4SS knows: F1 to F12, a letter, SPACE. Empty for none.",
  "time_of_day": 12.0,
  "_min_time_of_day": 0,
  "_max_time_of_day": 24,
  "min_fresh_kill": 20,
  "tint": "#ffcc00",
  "spots": [[1, 2], [3, 4]]
}
`;

test("the rows are the mod menu's: a note, a switch, text with its help, a bounded number, a whole number, a colour, a list", async () => {
  const s = await import(dom.studio("lib/scriptsettings.js"));
  const data = s.read(TEXT);
  assert.deepEqual(data.order, ["_help", "keep_stamina_full", "heal_key", "_help_heal_key", "time_of_day", "_min_time_of_day",
    "_max_time_of_day", "min_fresh_kill", "tint", "spots"]);
  assert.deepEqual([...data.floats], ["time_of_day"]);
  const rows = s.rows(data);
  assert.deepEqual(rows.map(r => [r.kind, r.label || r.value.slice(0, 13)]), [
    ["note", "Game Tweaks' "], ["switch", "Keep stamina full"], ["text", "Heal key"], ["number", "Time of day"],
    ["number", "Min fresh kill"], ["colour", "Tint"], ["nested", "Spots"]]);
  assert.equal(rows[2].help, "A key UE4SS knows: F1 to F12, a letter, SPACE. Empty for none.");
  assert.deepEqual([rows[3].whole, rows[3].step, rows[3].min, rows[3].max], [false, 0.1, 0, 24]);
  assert.deepEqual([rows[4].whole, rows[4].step, rows[4].min, rows[4].max], [true, 1, undefined, undefined]);
  assert.equal(s.problem(rows[3], "25"), "Time of day should be at most 24");
  assert.equal(s.problem(rows[4], "2.5"), "Min fresh kill should be a whole number");
  assert.equal(s.problem(rows[3], "6.5"), null);
});

test("written back, the file keeps its order, its untouched values as they were, and its 12.0", async () => {
  const s = await import(dom.studio("lib/scriptsettings.js"));
  const data = s.read(TEXT);
  assert.equal(s.write(data), TEXT);   // as it was, to the character
  assert.equal(s.write({ ...data, values: { ...data.values, time_of_day: 18 } }).includes('"time_of_day": 18.0,'), true);
  assert.equal(s.write({ ...data, values: { ...data.values, spots: [[5, 6]] } }).endsWith('"spots": [\n    [\n      5,\n      6\n    ]\n  ]\n}\n'), true);
  assert.throws(() => s.read("[1, 2]"), /should hold an object/);
  assert.throws(() => s.read('{"a": 1,}'), /isn't valid JSON/);
});

test("the Settings block on a script's card shows the rows and saves 12.0, in the file's order", async () => {
  const puts = [];
  dom.routes = {
    "GET /mods": () => [{ id: "game-tweaks", name: "Game Tweaks", description: "", enabled: true, priority: 0, kinds: ["in-game script"],
      preset: false, version: "", author: "", requires: [], requires_names: [], uses: [], code: true, menu_page: true, pack: false,
      problem: null, problems: [], needed_by: [], game_builds: [], outdated: null, menu_pages: false, script_problems: [],
      script_run: null, settings_card: true }],
    "GET /settings": () => ({ allow_code_mods: true, data_dir: "C:\\data" }),
    "GET /mods/game-tweaks/file/settings.json": () => ({ exists: true, text: TEXT }),
    "GET /mods/game-tweaks/log": () => ({ log: null, lines: [] }),
    "PUT /mods/game-tweaks/file/settings.json": b => { puts.push(b.text); return { saved: "settings.json", problems: [] }; },
  };
  const wc = await import(dom.studio("lib/wc.js") + "?" + Math.random());
  const page = (await import(dom.studio("sections/mods.js"))).default;
  const root = dom.document.createElement("div");
  dom.body.append(root);
  const handle = await page.mount(root, wc);
  try {
    root.querySelector('[aria-label="More about Game Tweaks"]').click();
    await tick(); await tick();
    const box = root.querySelector('[data-key="settings:game-tweaks"]');
    const labels = box.querySelectorAll("label").map(l => l.textContent);
    assert.deepEqual(labels, ["Keep stamina full", "Heal key", "Time of day", "Min fresh kill", "Tint"]);
    const time = box.querySelectorAll("input").find(i => i.attrs.type === "number" && i.attrs.max === "24");
    assert.equal(time.attrs.min, "0");
    assert.ok(box.all().some(n => n.textContent === "A key UE4SS knows: F1 to F12, a letter, SPACE. Empty for none."));
    // Change the switch only: Time of day goes back as 12.0, everything in its place.
    const sw = box.querySelectorAll("input").find(i => i.attrs.type === "checkbox");
    sw.checked = true;
    sw.dispatch("change");
    assert.ok(box.all().some(n => n.textContent === "Unsaved changes"));
    box.querySelectorAll("button").find(b => b.textContent === "Save settings").click();
    await tick(); await tick();
    assert.equal(puts.length, 1);
    assert.equal(puts[0], TEXT.replace('"keep_stamina_full": false', '"keep_stamina_full": true'));
    // A number out of its bounds isn't saved.
    root.querySelector('[aria-label="More about Game Tweaks"]');
    await tick(); await tick();
    const again = root.querySelector('[data-key="settings:game-tweaks"]');
    const t2 = again.querySelectorAll("input").find(i => i.attrs.type === "number" && i.attrs.max === "24");
    t2.value = "30";
    t2.dispatch("input");
    again.querySelectorAll("button").find(b => b.textContent === "Save settings").click();
    await tick();
    assert.equal(puts.length, 1, "Time of day 30 is refused before it's saved");
  } finally { handle.unmount(); }
});
