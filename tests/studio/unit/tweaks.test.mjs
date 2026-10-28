// The Tweaks page (studio/sections/tweaks.js) under the DOM shim, with a scripted API: ticking a box and saving
// writes that tweak (and only the ones that are on), the key picker offers what the server says (never F10,
// F11 or F12, nor a key your mods use, named), the story's scenes wait for their check, and the time box turns
// hours into a clock and back.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick } from "../lib/dom.mjs";

const dom = install();
const DEFAULTS = { keep_stamina_full: false, heal_key: "", hold_time: false, time_of_day: 12.0, min_fresh_kill: 0, skip_scenes: false };

async function mount(file = null, keys = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"], offer = {}) {
  const puts = [];
  const mods = [{ id: "my-mods", name: "My mods", enabled: true, kinds: file ? ["tweaks"] : [], problem: null }];
  dom.routes = {
    "GET /tweaks": () => ({ defaults: DEFAULTS, heal_keys: keys, taken: {}, unchecked: {}, ue4ss: true, ...offer }),
    "GET /mods": () => mods,
    "GET /mods/my-mods/file/tweaks.json": () => (file ? { exists: true, text: JSON.stringify(file) } : { exists: false, text: null }),
    "PUT /mods/my-mods/file/tweaks.json": b => { puts.push(JSON.parse(b.text)); return { saved: "tweaks.json", requires: [], problems: [] }; },
    "PATCH /mods/my-mods": () => ({}),
  };
  dom.calls.length = 0;
  localStorage.clear();
  for (const type of Object.keys(dom.windowListeners)) delete dom.windowListeners[type];
  const wc = await import(dom.studio("lib/wc.js") + "?" + Math.random());
  const page = (await import(dom.studio("sections/tweaks.js"))).default;
  const root = dom.document.createElement("div");
  dom.body.append(root);
  const handle = await page.mount(root, wc);
  const q = sel => root.querySelector(sel);
  const save = async () => { root.all().find(n => n.tagName === "BUTTON" && n.textContent === "Save to mod").click(); await tick(); await tick(); };
  return { root, handle, q, puts, save };
}

test("ticking a box and saving writes that tweak, and only the ones that are on", async () => {
  const t = await mount();
  try {
    const stamina = t.q("#tw-stamina");
    stamina.checked = true;
    stamina.dispatch("change");
    await t.save();
    assert.deepEqual(t.puts, [{ keep_stamina_full: true }]);
  } finally { t.handle.unmount?.(); }
});

test("the heal key picker offers the server's keys, and a held clock writes its hour", async () => {
  const t = await mount({ _help: "Mine.", hold_time: true, time_of_day: 6.5 }, ["F1", "F2", "F3", "F4", "F6", "F7", "F8", "F9"]);
  try {
    const keys = t.q("#tw-key").options.map(o => o.value);
    assert.deepEqual(keys, ["F1", "F2", "F3", "F4", "F6", "F7", "F8", "F9"]);   // F5 is the menu's here
    assert.ok(!keys.includes("F10") && !keys.includes("F11") && !keys.includes("F12"));
    assert.equal(t.q("#tw-key").disabled, true, "the picker waits for its box");
    assert.equal(t.q("#tw-time").value, "06:30");
    const heal = t.q("#tw-heal");
    heal.checked = true;
    heal.dispatch("change");
    const clock = t.q("#tw-time");
    clock.value = "21:15";
    clock.dispatch("change");
    await t.save();
    assert.deepEqual(t.puts, [{ _help: "Mine.", heal_key: "F1", hold_time: true, time_of_day: 21.25 }]);
  } finally { t.handle.unmount?.(); }
});

test("skipping the story's scenes has no row while it waits for its check, and isn't written", async () => {
  const why = { skip_scenes: "it hasn't been checked that skipping keeps the story's steps" };
  const t = await mount({ keep_stamina_full: true, skip_scenes: true }, undefined, { unchecked: why });
  try {
    assert.equal(t.q("#tw-scenes"), null);
    assert.ok(!t.root.all().some(n => n.textContent === "The story"));
    await t.save();
    assert.deepEqual(t.puts, [{ keep_stamina_full: true }]);
  } finally { t.handle.unmount?.(); }
  const checked = await mount(null, undefined, { unchecked: {} });   // the hand check's install
  try { assert.ok(checked.q("#tw-scenes")); } finally { checked.handle.unmount?.(); }
});

test("keys your mods already use are named, and a file's heal key on one of them is said under the row", async () => {
  const taken = { F6: "mouse look's on and off key (mouselook.json)", F3: "a remap to W (the controls.json of Key mod)" };
  const t = await mount({ heal_key: "F6" }, ["F1", "F2", "F4", "F5", "F7", "F8", "F9"], { taken });
  try {
    assert.deepEqual(t.q("#tw-key").options.map(o => o.value), ["F1", "F2", "F4", "F5", "F7", "F8", "F9", "F6"]);
    assert.equal(t.q("#tw-key").value, "F6");
    const clash = t.q("#tw-key-clash");
    assert.equal(clash.hidden, false);
    assert.equal(clash.textContent, "F6 is also mouse look's on and off key (mouselook.json), so pressing it would do both: pick another key.");
    assert.ok(t.root.all().some(n => n.textContent.endsWith("and these are left out as your mods use them: F6 (mouse look's on and off key (mouselook.json)), F3 (a remap to W (the controls.json of Key mod)).")));
    const key = t.q("#tw-key");
    key.value = "F7";
    key.dispatch("change");
    assert.equal(clash.hidden, true, "a free key: nothing to say");
  } finally { t.handle.unmount?.(); }
});

test("hours and the clock turn into each other", async () => {
  const { toClock, fromClock } = await import(dom.studio("sections/tweaks.js"));
  assert.equal(toClock(12), "12:00");
  assert.equal(toClock(6.25), "06:15");
  assert.equal(toClock(23.99), "23:59");
  assert.equal(fromClock("18:30"), 18.5);
  assert.equal(fromClock(""), null);
});
