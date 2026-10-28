// The Editing mod bar (wc.modTarget) under the DOM shim: unsaved work is kept when switching mods, when the
// page would close and when the mod list is read again; what keeps a saved file out of the game stays in
// view; whether to turn the mod on after a save is read afresh; and the API's failures are told apart.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick } from "../lib/dom.mjs";

const dom = install();

// A fake studio: two mods, "a" (on, with a names.json) and "b" (off, none), and whatever the test changes.
function fresh() {
  return {
    mods: [{ id: "a", name: "Mod A", enabled: true, kinds: ["names"], problem: null }, { id: "b", name: "Mod B", enabled: false, kinds: [], problem: null }],
    files: { "a/names.json": { prefixes: { remove: ["Moon"] } } }, problems: [], notes: [], puts: [], patches: [],
  };
}
function routes(state) {
  const file = id => () => state.files[`${id}/names.json`] ? { exists: true, text: JSON.stringify(state.files[`${id}/names.json`]) } : { exists: false, text: null };
  const put = id => b => { state.files[`${id}/names.json`] = JSON.parse(b.text); state.puts.push(id); return { saved: "names.json", requires: [], problems: state.problems, notes: state.notes }; };
  const patch = id => b => { state.patches.push({ id, body: b }); return {}; };
  const out = {
    "GET /mods": () => state.mods.map(x => ({ ...x })),
    "POST /mods": b => { state.mods.push({ id: b.id, name: b.name || b.id, enabled: !!b.enabled, kinds: [], problem: null }); return {}; },
  };
  for (const id of ["a", "b", "c", "my-mods"]) {
    out[`GET /mods/${id}/file/names.json`] = file(id);
    out[`PUT /mods/${id}/file/names.json`] = put(id);
    out[`PATCH /mods/${id}`] = patch(id);
  }
  return out;
}

async function setUp(state = fresh()) {
  dom.routes = routes(state);
  dom.calls.length = 0;
  for (const type of Object.keys(dom.windowListeners)) delete dom.windowListeners[type];   // the last test's bars
  localStorage.clear();
  const wc = await import(dom.studio("lib/wc.js") + "?" + Math.random());   // a fresh module per test (its bus is module state)
  const loads = [];
  let value = { prefixes: { remove: ["Moon"] } };
  const target = wc.modTarget({ file: "names.json", share: false, onLoad: (obj, id) => loads.push({ obj, id }), getValue: () => value });
  dom.byId.main.append(target.element);
  localStorage.setItem("wc-target", "a");
  await target.refresh();
  const select = target.element.querySelector("select");
  const ask = target.element.querySelector(".switch-ask");
  const problems = target.element.querySelector(".problems");
  const button = text => [...ask.querySelectorAll("button")].find(b => b.textContent === text);
  const change = to => { select.value = to; select.dispatch("change"); return tick(); };
  return { wc, state, target, loads, select, ask, problems, button, change, setValue: v => { value = v; } };
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
  assert.equal(document.activeElement, t.button("Save and switch"), "the first choice has focus");
  t.button("Stay").click();
  await tick();
  assert.ok(t.ask.hidden && t.target.dirty && t.loads.length === 1, "nothing loaded, nothing lost");
  assert.equal(document.activeElement, t.select);
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
  // Saved: the mod is made again (POST /mods) and the file written; a refresh while clean loads the file as before.
  await t.target.save();
  assert.ok(t.state.mods.some(m => m.id === "a") && t.state.puts.includes("a"));
  assert.equal(t.loads.length, 1, "a save doesn't read the file back: the page holds what it saved");
  await t.target.refresh();
  assert.equal(t.loads.length, 2, "a refresh while clean loads the file");
});

test("a change made while a save is under way stays on the page, unsaved, and onSaved hears what was saved", async () => {
  const state = fresh();
  dom.routes = routes(state);
  for (const type of Object.keys(dom.windowListeners)) delete dom.windowListeners[type];
  localStorage.clear();
  localStorage.setItem("wc-target", "a");
  const wc = await import(dom.studio("lib/wc.js") + "?" + Math.random());
  const loads = [], heard = [];
  let value = { prefixes: { remove: ["Sun"] } }, release;
  const target = wc.modTarget({ file: "names.json", share: false, onLoad: obj => loads.push(obj), getValue: () => value, onSaved: v => heard.push(v) });
  dom.byId.main.append(target.element);
  await target.refresh();
  // The PUT waits until the test lets it answer; meanwhile the creator changes something.
  const put = dom.routes["PUT /mods/a/file/names.json"];
  dom.routes["PUT /mods/a/file/names.json"] = b => new Promise(ok => { release = () => ok(put(b)); });
  target.markDirty();
  const saving = target.save();
  await tick(5);
  value = { prefixes: { remove: ["Sun", "Moon"] } };
  target.markDirty();
  release();
  assert.equal(await saving, true);
  assert.deepEqual(state.files["a/names.json"], { prefixes: { remove: ["Sun"] } }, "what was on the page when Save was pressed");
  assert.equal(loads.length, 1, "not read back over the change");
  assert.equal(target.dirty, true, "the change made meanwhile is still to be saved");
  assert.deepEqual(heard, [{ prefixes: { remove: ["Sun"] } }]);
  assert.equal(target.element.querySelector(".dirty").textContent, "Unsaved changes");
  // settleNew: the entries just saved keep their ids; one added since still follows its name.
  const list = [{ id: "a", _new: true }, { id: "b", _new: true }, { id: "c" }];
  wc.settleNew(list, [{ id: "a" }, { id: "c" }]);
  assert.deepEqual(list, [{ id: "a" }, { id: "b", _new: true }, { id: "c" }]);
});

test("New mod with unsaved changes makes the mod, then asks the same question", async () => {
  const t = await setUp();
  t.target.markDirty();
  const box = t.target.element.querySelector('input[aria-label="New mod folder name"]');
  box.value = "c";
  [...t.target.element.querySelectorAll("button")].find(b => b.textContent === "Create").click();
  await tick(20);
  assert.ok(t.state.mods.some(m => m.id === "c"), "made");
  assert.equal(t.ask.hidden, false, "and asked about the unsaved work before opening it");
  assert.equal(t.select.value, "a");
  t.button("Switch without saving").click();
  await tick(20);
  assert.equal(t.select.value, "c");
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
  assert.ok(dom.byId.shout.textContent.includes("can't go in the game yet"), "and read out");
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
  const leaving = { type: "beforeunload", defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
  window.dispatchEvent(leaving);
  assert.equal(leaving.defaultPrevented, true);
  assert.equal(leaving.returnValue, "");
  t.wc.bus.emit("installed", {});
  assert.equal(heard, 1, "skipped while dirty");
  await t.target.save();
  const staying = { type: "beforeunload", defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
  window.dispatchEvent(staying);
  assert.equal(staying.defaultPrevented, false);
  t.wc.bus.emit("installed", {});
  assert.equal(heard, 2);
});

test("what Apply would leave out of a file that's fine shows under the bar until the next save", async () => {
  const t = await setUp();
  const notes = t.target.element.querySelector(".save-notes");
  assert.equal(notes.hidden, true);
  t.state.notes = ["Pattern colour 25 is also added by Dark Forest, which is later in the Mods list, so its colour shows"];
  await t.target.save();
  assert.equal(notes.hidden, false);
  assert.equal(t.problems.hidden, true, "a note isn't a problem: the file goes in");
  assert.deepEqual(notes.querySelectorAll("li").map(li => li.textContent), t.state.notes);
  assert.equal(notes.getAttribute("role"), "status");
  t.state.notes = [];
  await t.target.save();
  assert.equal(notes.hidden, true);
});

test("an Apply with unsaved changes says they aren't in the game yet, until they're saved", async () => {
  const t = await setUp();
  const status = () => t.target.element.querySelector(".dirty").textContent;
  t.wc.bus.emit("installed", {});
  assert.equal(status(), "", "nothing unsaved: nothing to say");
  t.target.markDirty();
  assert.equal(status(), "Unsaved changes");
  t.wc.bus.emit("installed", {});
  assert.equal(status(), "Not in the game yet: Save to mod, then Apply");
  t.target.markDirty();   // another change: still not in the game
  assert.equal(status(), "Not in the game yet: Save to mod, then Apply");
  await t.target.save();
  assert.equal(status(), "");
  t.target.markDirty();
  assert.equal(status(), "Unsaved changes", "the next change is just unsaved again");
});

test("coming back to the window re-reads a file changed outside the page, only while nothing is unsaved", async () => {
  const t = await setUp();
  t.wc.bus.emit("focus");
  await tick(20);
  assert.equal(t.loads.length, 1, "unchanged on disk: not loaded again");
  t.state.files["a/names.json"] = { prefixes: { remove: ["Star"] } };   // the game's own menu saved it, say
  t.target.markDirty();
  t.wc.bus.emit("focus");
  await tick(20);
  assert.equal(t.loads.length, 1, "unsaved changes here: they stay, and Save decides");
  await t.change("b");   // leave the changes behind, then come back to "a"
  t.button("Switch without saving").click();
  await tick(20);
  await t.change("a");
  await tick(20);
  assert.deepEqual(t.loads.at(-1).obj, { prefixes: { remove: ["Star"] } });
  t.state.files["a/names.json"] = { prefixes: { remove: ["Leaf"] } };
  t.wc.bus.emit("focus");
  await tick(20);
  assert.deepEqual(t.loads.at(-1), { obj: { prefixes: { remove: ["Leaf"] } }, id: "a" }, "read again, as it is now");
  assert.ok([...dom.byId.toasts.querySelectorAll("span")].some(s => s.textContent.includes("was changed outside this page")));
});

test("a change made while the file is read again (after an Apply) stays on the page", async () => {
  const t = await setUp();
  const read = dom.routes["GET /mods/a/file/names.json"];
  let reading = null;
  dom.routes["GET /mods/a/file/names.json"] = async () => { await new Promise(r => { reading = r; }); return read(); };
  try {
    const refreshing = t.target.refresh();   // what installedEvent does on a page with nothing unsaved
    while (!reading) await tick(5);
    t.target.markDirty();                    // a click on the page just then
    reading();
    await refreshing;
    assert.equal(t.loads.length, 1, "the page's state wasn't replaced by the file");
    assert.equal(t.target.dirty, true, "and the change is still to be saved");
  } finally {
    dom.routes["GET /mods/a/file/names.json"] = read;
  }
});

test("what a save wrote is the file as it is: coming back to the window doesn't read it again", async () => {
  const t = await setUp();
  t.setValue({ prefixes: { remove: ["Sun"] } });
  t.target.markDirty();
  await t.target.save();
  const toasts = dom.byId.toasts.querySelectorAll("span").length;
  t.wc.bus.emit("focus");
  await tick(20);
  assert.equal(t.loads.length, 1, "not loaded again");
  assert.ok(![...dom.byId.toasts.querySelectorAll("span")].slice(toasts).some(s => s.textContent.includes("changed outside")));
});

const REFUSED = { ok: false, status: 403, statusText: "Forbidden", json: async () => ({ error: "missing or wrong studio token; reload the page" }) };
const OK = body => ({ ok: true, status: 200, statusText: "OK", json: async () => body });
const PAGE = tok => ({ ok: true, status: 200, url: "", text: async () => `<html><head><meta name="wc-token" content="${tok}">` });

test("the API's failures are told apart for the shell", async () => {
  const t = await setUp();
  let gone = 0, lost = 0;
  t.wc.bus.on("server-gone", () => gone++);
  t.wc.bus.on("token-lost", () => lost++);
  const real = globalThis.fetch;
  try {
    // Refused for its token, and the studio's page can't be had either: said as "token".
    globalThis.fetch = async url => (url === "/" ? { ok: false, status: 404 } : REFUSED);
    await assert.rejects(t.wc.api.get("/info"), e => e.code === "token" && e.status === 403);
    globalThis.fetch = async () => ({ ok: false, status: 409, statusText: "Conflict", json: async () => ({ error: "not installing", blocked: [{ title: "Names", mod: "a", text: "bad" }] }) });
    await assert.rejects(t.wc.api.post("/install"), e => e.data.blocked.length === 1 && !e.code);
  } finally {
    globalThis.fetch = real;
  }
  assert.deepEqual([gone, lost], [0, 1]);
});

test("a page from before the studio restarted takes up its new token and carries on", async () => {
  const t = await setUp();
  let lost = 0;
  t.wc.bus.on("token-lost", () => lost++);
  const real = globalThis.fetch, sent = [];
  try {
    globalThis.fetch = async (url, init = {}) => {
      if (url === "/") return PAGE("new-token");
      sent.push({ url, token: init.headers["X-WC-Token"], body: init.body });
      return init.headers["X-WC-Token"] === "new-token" ? OK({ saved: "names.json" }) : REFUSED;
    };
    assert.deepEqual(await t.wc.api.put("/mods/a/file/names.json", { text: "{}" }), { saved: "names.json" });
    assert.deepEqual(sent.map(s => s.token), ["test-token", "new-token"], "refused once, then asked again with the new token");
    assert.equal(sent[1].body, sent[0].body, "the same request");
    await t.wc.api.get("/mods");
    assert.equal(sent.at(-1).token, "new-token", "and every request after it");
  } finally {
    globalThis.fetch = real;
  }
  assert.equal(lost, 0, "nothing for the shell to do");
});

test("the studio is gone only when it can't be reached twice, a few seconds apart", async t0 => {
  t0.mock.timers.enable({ apis: ["setTimeout"] });
  const t = await setUp();
  let gone = 0;
  t.wc.bus.on("server-gone", () => gone++);
  const real = globalThis.fetch;
  const flush = async () => { for (let i = 0; i < 5; i++) await new Promise(r => setImmediate(r)); };
  try {
    // A blip: the request fails, but the studio answers when asked again.
    globalThis.fetch = async () => { throw new TypeError("Failed to fetch"); };
    await assert.rejects(t.wc.api.get("/info"), e => e.code === "gone" && /window was closed/.test(e.message));
    await assert.rejects(t.wc.api.get("/changes"), e => e.code === "gone");   // one check for both
    globalThis.fetch = async url => (url === "/" ? PAGE("test-token") : OK({}));
    t0.mock.timers.tick(t.wc.RECHECK_MS);
    await flush();
    assert.equal(gone, 0, "not gone: it answered");
    // Gone: it fails again when asked a few seconds later.
    globalThis.fetch = async () => { throw new TypeError("Failed to fetch"); };
    await assert.rejects(t.wc.api.get("/info"));
    t0.mock.timers.tick(t.wc.RECHECK_MS - 1);
    await flush();
    assert.equal(gone, 0, "not before the second try");
    t0.mock.timers.tick(1);
    await flush();
    assert.equal(gone, 1);
    assert.equal(await t.wc.reconnect(), false);
    globalThis.fetch = async url => (url === "/" ? PAGE("third-token") : OK({}));
    assert.equal(await t.wc.reconnect(), true, "and back");
  } finally {
    globalThis.fetch = real;
    t0.mock.timers.reset();
  }
});

test("unsaved changes are known to the shell, page by page, until they're saved", async () => {
  const t = await setUp();
  assert.equal(t.wc.anyDirty(), false);
  t.target.markDirty();
  assert.equal(t.wc.anyDirty(), true);
  assert.deepEqual(t.wc.dirtyTargets().map(x => x.file), ["names.json"]);
  await t.target.save();
  assert.equal(t.wc.anyDirty(), false);
  // A bar that's no longer on the page (its page was taken down) doesn't count.
  t.target.markDirty();
  t.target.element.remove();
  assert.equal(t.wc.anyDirty(), false);
});

test("importing a file over unsaved changes asks first, as switching mods does", async () => {
  dom.routes = routes(fresh());
  for (const type of Object.keys(dom.windowListeners)) delete dom.windowListeners[type];
  localStorage.clear();
  localStorage.setItem("wc-target", "a");
  const wc = await import(dom.studio("lib/wc.js") + "?" + Math.random());
  const loads = [];
  const target = wc.modTarget({ file: "names.json", onLoad: (obj, id) => loads.push({ obj, id }), getValue: () => ({ prefixes: {} }) });
  dom.byId.main.append(target.element);
  await target.refresh();
  const picker = target.element.querySelector("input[type=\"file\"]");
  const ask = target.element.querySelector(".switch-ask");
  const choose = async (name, obj) => { picker._files = [{ name, text: async () => JSON.stringify(obj) }]; picker.dispatch("change"); await tick(10); };
  await choose("theirs.json", { prefixes: { add: ["Sky"] } });
  assert.deepEqual(loads.at(-1), { obj: { prefixes: { add: ["Sky"] } }, id: "a" }, "nothing unsaved: loaded at once");
  assert.equal(target.dirty, true);
  await choose("other.json", { prefixes: { add: ["Moss"] } });
  assert.equal(loads.length, 2, "not loaded yet");
  assert.equal(ask.hidden, false);
  assert.deepEqual([...ask.querySelectorAll("button")].map(b => b.textContent), ["Save and load", "Load without saving", "Stay"]);
  assert.match(ask.textContent, /Save them to Mod A before loading other\.json/);
  [...ask.querySelectorAll("button")].find(b => b.textContent === "Stay").click();
  await tick();
  assert.equal(loads.length, 2, "Stay keeps the page as it was");
  await choose("other.json", { prefixes: { add: ["Moss"] } });
  [...ask.querySelectorAll("button")].find(b => b.textContent === "Load without saving").click();
  await tick(10);
  assert.deepEqual(loads.at(-1), { obj: { prefixes: { add: ["Moss"] } }, id: "a" });
  assert.equal(target.dirty, true, "what was loaded is unsaved in its turn");
});
