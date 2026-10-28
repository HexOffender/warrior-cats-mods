// The Tweaks page (studio/sections/tweaks.js) under the DOM shim, with a scripted API: ticking a box and saving
// writes that tweak (and only the ones that are on), the key picker offers what the server says (never F10 or
// F11, nor the mod menu's key), and the time box turns hours into a clock and back.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick } from "../lib/dom.mjs";

const dom = install();
const DEFAULTS = { keep_stamina_full: false, heal_key: "", hold_time: false, time_of_day: 12.0, min_fresh_kill: 0, skip_scenes: false };

async function mount(file = null, keys = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F12"]) {
  const puts = [];
  const mods = [{ id: "my-mods", name: "My mods", enabled: true, kinds: file ? ["tweaks"] : [], problem: null }];
  dom.routes = {
    "GET /tweaks": () => ({ defaults: DEFAULTS, heal_keys: keys, ue4ss: true }),
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
  const t = await mount({ _help: "Mine.", hold_time: true, time_of_day: 6.5 }, ["F1", "F2", "F3", "F4", "F6", "F7", "F8", "F9", "F12"]);
  try {
    const keys = t.q("#tw-key").options.map(o => o.value);
    assert.deepEqual(keys, ["F1", "F2", "F3", "F4", "F6", "F7", "F8", "F9", "F12"]);   // F5 is the menu's here
    assert.ok(!keys.includes("F10") && !keys.includes("F11"));
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

test("hours and the clock turn into each other", async () => {
  const { toClock, fromClock } = await import(dom.studio("sections/tweaks.js"));
  assert.equal(toClock(12), "12:00");
  assert.equal(toClock(6.25), "06:15");
  assert.equal(toClock(23.99), "23:59");
  assert.equal(fromClock("18:30"), 18.5);
  assert.equal(fromClock(""), null);
});
