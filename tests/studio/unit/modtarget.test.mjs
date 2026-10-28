// The Editing mod bar (wc.modTarget) under the DOM shim: unsaved work is kept when switching mods, when the
// page would close and when the mod list is read again; what keeps a saved file out of the game stays in
// view; whether to turn the mod on after a save is read afresh.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick, Event } from "../lib/dom.mjs";

// A fake studio: two mods, "a" (on, with a names.json) and "b" (off, none), and whatever the test sets.
function fakeApi(state) {
  return async (path, { method, body }) => {
    const m = /^\/mods\/([^/]+)\/file\/([^/]+)$/.exec(path);
    if (path === "/mods" && method === "GET") return state.mods.map(x => ({ ...x }));
    if (path === "/mods" && method === "POST") { state.mods.push({ id: body.id, name: body.name || body.id, enabled: !!body.enabled, kinds: [], problem: null }); return {}; }
    if (m && method === "GET") return state.files[`${m[1]}/${m[2]}`] ? { exists: true, text: JSON.stringify(state.files[`${m[1]}/${m[2]}`]) } : { exists: false, text: null };
    if (m && method === "PUT") { state.files[`${m[1]}/${m[2]}`] = JSON.parse(body.text); state.puts.push(m[1]); return { saved: m[2], requires: [], problems: state.problems }; }
    if (/^\/mods\/[^/]+$/.test(path) && method === "PATCH") { state.patches.push({ id: path.slice(6), body }); return {}; }
    const e = new Error(`no route ${method} ${path}`); e.status = 404; throw e;
  };
}
function fresh() {
  return {
    mods: [{ id: "a", name: "Mod A", enabled: true, kinds: ["names"], problem: null }, { id: "b", name: "Mod B", enabled: false, kinds: [], problem: null }],
    files: { "a/names.json": { prefixes: { remove: ["Moon"] } } }, problems: [], puts: [], patches: [],
  };
}

async function setUp(state = fresh()) {
  const dom = install({ fetch: fakeApi(state) });
  const wc = await import("../../../studio/lib/wc.js?" + Math.random());   // a fresh module per test (its bus is module state)
  const loads = [];
  let value = { prefixes: { remove: ["Moon"] } };
  const target = wc.modTarget({ file: "names.json", share: false, onLoad: (obj, id) => loads.push({ obj, id }), getValue: () => value });
  dom.document.getElementById("main").append(target.element);
  localStorage.setItem("wc-target", "a");
  await target.refresh();
  const select = target.element.querySelector("select");
  const ask = target.element.querySelector(".switch-ask");
  const problems = target.element.querySelector(".problems");
  const button = text => [...ask.querySelectorAll("button")].find(b => b.textContent === text);
  const change = to => { select.value = to; select.dispatchEvent(new Event("change")); return tick(); };
  return { dom, wc, state, target, loads, select, ask, problems, button, change, setValue: v => { value = v; } };
}

test("the bar opens the mod last chosen and its file", async () => {
  const t = await setUp();
  assert.deepEqual(t.loads, [{ obj: { prefixes: { remove: ["Moon"] } }, id: "a" }]);
  assert.equal(t.select.value, "a");
  assert.equal(t.target.dirty, false);
  assert.ok(t.ask.hidden && t.problems.hidden);
});

test("switching mods with unsaved changes asks first, and Stay keeps everything", async () => {
  const t = await setUp();
  t.target.markDirty();
  await t.change("b");
  assert.equal(t.select.value, "a", "the select shows the mod still being edited");
  assert.equal(t.ask.hidden, false);
  assert.deepEqual([...t.ask.querySelectorAll("button")].map(b => b.textContent), ["Save and switch", "Switch without saving", "Stay"]);
  assert.equal(t.dom.document.activeElement, t.button("Save and switch"), "the first choice has focus");
  t.button("Stay").click();
  await tick();
  assert.ok(t.ask.hidden && t.target.dirty && t.loads.length === 1, "nothing loaded, nothing lost");
  assert.equal(t.dom.document.activeElement, t.select);
});

test("Switch without saving drops the changes and opens the other mod", async () => {
  const t = await setUp();
  t.target.markDirty();
  await t.change("b");
  t.button("Switch without saving").click();
  await tick(20);
  assert.equal(t.select.value, "b");
  assert.equal(t.target.dirty, false);
  assert.deepEqual(t.loads.at(-1), { obj: null, id: "b" });
  assert.deepEqual(t.state.puts, [], "nothing was written");
});

test("Save and switch writes the file to the mod it was for, then opens the other", async () => {
  const t = await setUp();
  t.setValue({ prefixes: { remove: ["Sun"] } });
  t.target.markDirty();
  await t.change("b");
  t.button("Save and switch").click();
  await tick(30);
  assert.deepEqual(t.state.puts, ["a"]);
  assert.deepEqual(t.state.files["a/names.json"], { prefixes: { remove: ["Sun"] } });
  assert.equal(t.select.value, "b");
  assert.deepEqual(t.loads.at(-1), { obj: null, id: "b" });
  assert.equal(t.target.dirty, false);
});

test("without unsaved changes, switching just switches", async () => {
  const t = await setUp();
  await t.change("b");
  await tick(10);
  assert.ok(t.ask.hidden);
  assert.deepEqual(t.loads.at(-1), { obj: null, id: "b" });
});

test("refresh and mods-changed read the list again without reloading the file while dirty", async () => {
  const t = await setUp();
  t.target.markDirty();
  t.state.mods[1].name = "Mod B renamed";
  await t.target.refresh();
  assert.equal(t.loads.length, 1, "the file wasn't loaded again");
  assert.equal(t.target.dirty, true);
  assert.ok([...t.select.options].some(o => o.textContent.startsWith("Mod B renamed")), "but the list is fresh");
  t.state.mods[1].name = "Mod B again";
  t.wc.bus.emit("mods-changed");
  await tick(10);
  assert.ok([...t.select.options].some(o => o.textContent.startsWith("Mod B again")));
  assert.equal(t.loads.length, 1);
  // A mod removed while it's being edited stays chosen, marked, until it's saved (which makes it again) or switched.
  t.state.mods.shift();
  t.wc.bus.emit("mods-changed");
  await tick(10);
  assert.equal(t.select.value, "a");
  assert.ok([...t.select.options].some(o => o.value === "a" && o.textContent.includes("(removed)")));
  // Not dirty: refresh loads the file again as before.
  t.state.mods.unshift({ id: "a", name: "Mod A", enabled: true, kinds: ["names"], problem: null });
  t.target.markDirty();   // (marked, so saving isn't needed to clear it)
  await t.change("a");    // same mod: nothing happens
  t.button?.("Stay");
  await t.target.save();
  await t.target.refresh();
  assert.equal(t.loads.length, 3, "a save reloads (1), and so does a refresh while clean (2)");
});

test("what keeps the saved file out of the game stays under the bar until a save that's fine", async () => {
  const t = await setUp();
  t.state.problems = ["names.json: 'hats' should be one of prefixes, suffixes"];
  t.target.markDirty();
  await t.target.save();
  assert.equal(t.problems.hidden, false);
  assert.equal(t.problems.getAttribute("role"), "alert");
  assert.ok(t.problems.textContent.startsWith("Saved, but it can't go in the game yet: names.json: 'hats'"));
  assert.equal(t.target.dirty, false, "it's saved all the same");
  await tick(80);
  assert.ok(t.dom.document.getElementById("shout").textContent.includes("can't go in the game yet"), "and read out");
  t.state.problems = [];
  await t.target.save();
  assert.equal(t.problems.hidden, true);
  assert.equal(t.problems.textContent, "");
});

test("whether to turn the mod on after a save is read afresh, and a broken mod is left alone", async () => {
  const t = await setUp();
  // The bar's list says "a" is on; by the time of the save another page switched it off.
  t.state.mods[0].enabled = false;
  await t.target.save();
  assert.deepEqual(t.state.patches, [{ id: "a", body: { enabled: true } }]);
  // A mod whose mod.json can't be read: the file is saved, but it can't be switched on.
  t.state.patches = [];
  t.state.mods[0].problem = "mod.json isn't valid";
  await t.target.save();
  assert.deepEqual(t.state.patches, []);
});

test("closing the page with unsaved changes is asked about; installedEvent waits for a save", async () => {
  const t = await setUp();
  let heard = 0;
  t.wc.installedEvent(t.target, () => heard++);
  t.wc.bus.emit("installed", {});
  assert.equal(heard, 1);
  t.target.markDirty();
  const leaving = new Event("beforeunload");
  t.dom.window.dispatchEvent(leaving);
  assert.equal(leaving.defaultPrevented, true);
  assert.equal(leaving.returnValue, "");
  t.wc.bus.emit("installed", {});
  assert.equal(heard, 1, "skipped while dirty");
  await t.target.save();
  const staying = new Event("beforeunload");
  t.dom.window.dispatchEvent(staying);
  assert.equal(staying.defaultPrevented, false);
  t.wc.bus.emit("installed", {});
  assert.equal(heard, 2);
});

test("the API's failures are told apart for the shell", async () => {
  const t = await setUp();
  let gone = 0, lost = 0;
  t.wc.bus.on("server-gone", () => gone++);
  t.wc.bus.on("token-lost", () => lost++);
  globalThis.fetch = async () => { throw new TypeError("Failed to fetch"); };
  await assert.rejects(t.wc.api.get("/info"), e => e.code === "gone" && /window was closed/.test(e.message));
  globalThis.fetch = async () => ({ ok: false, status: 403, statusText: "Forbidden", json: async () => ({ error: "missing or wrong studio token; reload the page" }) });
  await assert.rejects(t.wc.api.get("/info"), e => e.code === "token" && e.status === 403);
  globalThis.fetch = async () => ({ ok: false, status: 409, statusText: "Conflict", json: async () => ({ error: "not installing", blocked: [{ title: "Names", mod: "a", text: "bad" }] }) });
  await assert.rejects(t.wc.api.post("/install"), e => e.data.blocked.length === 1 && !e.code);
  assert.deepEqual([gone, lost], [1, 1]);
});
