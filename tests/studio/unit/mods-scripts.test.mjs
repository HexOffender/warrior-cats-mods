// A script mod's card on the Mods page (studio/sections/mods.js) under the DOM shim: what's wrong with its files in
// red before any Apply, a line about how it did when the game last started, and What it said under More.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick } from "../lib/dom.mjs";

const dom = install();

function card(id, name, more = {}) {
  return { id, name, description: "", enabled: true, priority: 0, kinds: ["in-game script"], preset: false, version: "", author: "",
    requires: [], requires_names: [], uses: [], code: true, menu_page: false, pack: false, problem: null, problems: [], needed_by: [],
    game_builds: [], outdated: null, menu_pages: false, script_problems: [], script_run: null, ...more };
}

async function mount(mods, log = {}) {
  dom.routes = {
    "GET /mods": () => mods,
    "GET /settings": () => ({ allow_code_mods: true, data_dir: "C:\\data" }),
    "POST /open": b => ({ opened: "C:\\Game\\ue4ss\\UE4SS.log", body: b }),
  };
  for (const [id, said] of Object.entries(log)) dom.routes[`GET /mods/${id}/log`] = () => said;
  dom.calls.length = 0;
  const wc = await import(dom.studio("lib/wc.js") + "?" + Math.random());
  const page = (await import(dom.studio("sections/mods.js"))).default;
  const root = dom.document.createElement("div");
  dom.body.append(root);
  const handle = await page.mount(root, wc);
  const cardOf = id => root.querySelector(`[data-key="mod:${id}"]`);
  const lines = id => cardOf(id).querySelectorAll("li").map(li => ({ cls: li.className, text: li.textContent }));
  return { root, handle, wc, cardOf, lines };
}

test("a script's problems are red lines on its card, and its last start is a line by how it went", async () => {
  const t = await mount([
    card("broken", "Broken", { script_problems: ['scripts/main.lua, line 1: a "function" is never closed with "end", so the script won\'t run'],
      script_run: { state: "failed", said: "Didn't load when the game last started: scripts/main.lua:3: 'end' expected near <eof>" } }),
    card("tweaks", "Game Tweaks", { script_run: { state: "loaded", said: "Loaded when the game last started" } }),
    card("noisy", "Noisy", { script_run: { state: "errors", said: "Loaded when the game last started, then hit an error: onFrame: boom" } }),
    card("fresh", "Fresh", { script_run: { state: "waiting", said: "Hasn't run since you applied" } }),
    card("never", "Never installed"),
  ]);
  try {
    assert.deepEqual(t.lines("broken"), [
      { cls: "bad", text: 'scripts/main.lua, line 1: a "function" is never closed with "end", so the script won\'t run.' },
      { cls: "bad", text: "Didn't load when the game last started: scripts/main.lua:3: 'end' expected near <eof>." }]);
    assert.deepEqual(t.lines("tweaks"), [{ cls: "ok", text: "Loaded when the game last started." }]);
    assert.equal(t.lines("noisy")[0].cls, "warn");
    assert.deepEqual(t.lines("fresh"), [{ cls: "muted", text: "Hasn't run since you applied." }]);
    assert.deepEqual(t.lines("never"), []);   // a mod never installed has nothing to say about the game
  } finally { t.handle.unmount(); }
});

test("More shows what the script said, newest first, and opens the log file", async () => {
  const said = { log: "C:\\Game\\ue4ss\\UE4SS.log", session: "2026-10-28 09:12:01", run_since_apply: true,
    lines: ["09:13:41  healed Fawnstar", "09:12:04  loaded"], errors: [], state: "loaded" };
  const t = await mount([card("tweaks", "Game Tweaks")], { tweaks: said });
  try {
    t.cardOf("tweaks").querySelector('[aria-label="More about Game Tweaks"]').click();
    await tick();
    await tick();
    const box = t.root.querySelector('[data-key="said:tweaks"]');
    assert.ok(box, "What it said is under More");
    assert.equal(box.querySelector("pre").textContent, "09:13:41  healed Fawnstar\n09:12:04  loaded");
    assert.match(box.querySelector(".note").textContent, /^Newest first, from when the game last started \(2026-10-28 09:12:01\)/);
    box.querySelectorAll("button").find(b => b.textContent === "Open the log file").click();
    await tick();
    assert.deepEqual(dom.calls.filter(c => c.url === "/api/open").map(c => c.body), [{ what: "log" }]);
  } finally { t.handle.unmount(); }
});

test("before the game has made its log, More says so", async () => {
  const t = await mount([card("tweaks", "Game Tweaks")], { tweaks: { log: null, session: null, run_since_apply: false, lines: [] } });
  try {
    t.cardOf("tweaks").querySelector('[aria-label="More about Game Tweaks"]').click();
    await tick();
    await tick();
    assert.match(t.root.querySelector('[data-key="said:tweaks"]').textContent, /Nothing yet: the game makes its log when it starts/);
  } finally { t.handle.unmount(); }
});

test("the cards are read again when the game closes and after an Apply", async () => {
  const mods = [card("tweaks", "Game Tweaks", { script_run: { state: "waiting", said: "Hasn't run since you applied" } })];
  const t = await mount(mods);
  try {
    mods[0] = { ...mods[0], script_run: { state: "loaded", said: "Loaded when the game last started" } };
    t.wc.bus.emit("game", { running: false });
    await tick();
    await tick();
    assert.deepEqual(t.lines("tweaks"), [{ cls: "ok", text: "Loaded when the game last started." }]);
    const before = dom.calls.filter(c => c.url === "/api/mods").length;
    t.wc.bus.emit("installed", {});
    await tick();
    assert.equal(dom.calls.filter(c => c.url === "/api/mods").length, before + 1);
  } finally { t.handle.unmount(); }
});
