// Try Lua in the game (studio/sections/console.js) under the DOM shim, with a scripted API: the strip says each of
// the four states /game/bridge answers with, Run and Inspect wait for a game that's listening, what comes back is
// shown plainly, what was typed is never lost, and the page stops asking while it's hidden.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick } from "../lib/dom.mjs";

const dom = install();
const SAID = {
  listening: "The game is running and listening (in the forest)",
  "not-answering": "The game is running but not answering: it may be loading, or held still behind another window",
  "no-bridge": "The game is running without the studio's connection to it: close the game, press Apply to game, then Play",
  closed: "The game is closed: press Play",
};

// The page mounted over a fresh wc.js, the game in `state`; lua(body) and inspect(body) answer the requests.
async function mount(state = "listening", { lua, inspect } = {}) {
  const bridge = { state };
  dom.routes = {
    "GET /game/bridge": () => ({ alive: bridge.state === "listening", state: bridge.state, said: SAID[bridge.state] }),
    "POST /game/lua": lua || (b => ({ ok: true, result: [42], output: "", ms: 3 })),
    "POST /game/inspect": inspect || (b => ({ ok: true, result: [{ name: "Cat", parents: ["Pawn"], props: [], funcs: [] }] })),
  };
  dom.calls.length = 0;
  const wc = await import(dom.studio("lib/wc.js") + "?" + Math.random());
  const page = (await import(dom.studio("sections/console.js"))).default;
  const root = dom.document.createElement("div");
  dom.body.append(root);
  const handle = await page.mount(root, wc);
  const q = sel => root.querySelector(sel);
  const button = text => root.all().find(n => n.tagName === "BUTTON" && n.textContent === text);
  const calls = route => dom.calls.filter(c => `${c.method} ${c.url.replace(/^\/api/, "")}` === route);
  const out = () => q(".con-out").children.map(c => ({ cls: c.className, text: c.textContent }));
  return { root, handle, q, button, calls, out, bridge, wc, strip: q(".strip"), code: q("#con-code") };
}

test("the strip says each of the four states, and Run and Inspect wait for a game that's listening", async () => {
  for (const state of Object.keys(SAID)) {
    const t = await mount(state);
    try {
      assert.equal(t.strip.textContent, SAID[state]);
      assert.ok(t.strip.classList.contains(state), t.strip.className);
      const listening = state === "listening";
      for (const name of ["Run", "Inspect"]) {
        assert.equal(t.button(name).disabled, !listening, `${name} in ${state}`);
        assert.equal(t.button(name).title, listening ? "" : SAID[state]);
      }
    } finally { t.handle.unmount(); }
  }
});

test("Run while the game isn't listening sends nothing", async () => {
  const t = await mount("no-bridge");
  try {
    t.code.value = "return 1";
    t.button("Run").click();
    await tick();
    assert.equal(t.calls("POST /game/lua").length, 0);
    assert.deepEqual(t.out(), []);
  } finally { t.handle.unmount(); }
});

test("a line's values show plainly: nil as nil, a table as an indented list, the time apart", async () => {
  const t = await mount("listening", { lua: () => ({ ok: true, output: "hi", ms: 7, result: ["nil", "Fawnstar", 3, { name: "Fawn", stats: { Prowess: 20 }, traits: [] }] }) });
  try {
    t.code.value = "return x";
    t.button("Run").click();
    await tick();
    assert.deepEqual(t.calls("POST /game/lua").map(c => c.body), [{ code: "return x" }]);
    assert.deepEqual(t.out(), [
      { cls: "muted", text: "> return x" },
      { cls: "", text: "hi" },
      { cls: "", text: "nil\nFawnstar\n3\nname: Fawn\nstats: \n  Prowess: 20\ntraits: (empty)" },
      { cls: "con-ms", text: "7 ms" },
    ]);
  } finally { t.handle.unmount(); }
});

test("an error comes back as an error line, and what was typed stays", async () => {
  const t = await mount("listening", { lua: () => ({ ok: false, error: "wcmods:1: attempt to call a nil value (global 'nope')", output: "" }) });
  try {
    t.code.value = "nope()";
    t.button("Run").click();
    await tick();
    assert.deepEqual(t.out().at(-1), { cls: "bad", text: "wcmods:1: attempt to call a nil value (global 'nope')" });
    assert.equal(t.code.value, "nope()");
    assert.equal(t.button("Run").disabled, false);
  } finally { t.handle.unmount(); }
});

test("a refused request says why and Run is pressable again", async () => {
  const refused = "The game didn't answer within 15 seconds (it may be loading, or held still behind another window), so the line was taken back: it won't run later";
  const t = await mount("listening", { lua: () => { throw { status: 400, error: refused }; } });
  try {
    t.code.value = "return 1";
    t.button("Run").click();
    await tick();
    await tick();
    assert.deepEqual(t.out().at(-1), { cls: "bad", text: refused });
    assert.equal(t.button("Run").disabled, false);
  } finally { t.handle.unmount(); }
});

test("an empty Object box never asks the game, and Inspect sends the engine's members box", async () => {
  const t = await mount("listening");
  try {
    t.q("#con-expr").value = "  ";
    t.button("Inspect").click();
    await tick();
    assert.equal(t.calls("POST /game/inspect").length, 0);
    assert.ok(t.root.all().some(n => n.textContent === "Type something to look at, e.g. Game.player()"));
    t.q("#con-expr").value = "Game.player()";
    t.q("#con-all").checked = true;
    t.button("Inspect").click();
    await tick();
    assert.deepEqual(t.calls("POST /game/inspect").map(c => c.body), [{ expr: "Game.player()", all: true }]);
  } finally { t.handle.unmount(); }
});

test("an example goes in on a line of its own, keeping what was typed, and says when a page does it without code", async () => {
  const { insertAt, EXAMPLES } = await import(dom.studio("sections/console.js"));
  assert.deepEqual(insertAt("", "return 1"), { value: "return 1", caret: 8 });
  assert.deepEqual(insertAt("local a = 1", "return 2"), { value: "local a = 1\nreturn 2", caret: 20 });
  assert.deepEqual(insertAt("a\nb", "c", 1), { value: "a\nc\nb", caret: 3 });
  const t = await mount("listening");
  try {
    t.code.value = "local mine = 5";
    t.button("Set 6:00").click();
    assert.equal(t.code.value, "local mine = 5\nreturn Game.time.set(6, 0)");
    // Another example still as it was is replaced: two in one box wouldn't run.
    t.code.value = "";
    t.button("Time of day").click();
    assert.equal(t.code.value, "return Game.time.get()");
    t.button("Set 6:00").click();
    assert.equal(t.code.value, "return Game.time.set(6, 0)");
    t.button("Run").click();
    await tick();
    assert.equal(t.out().at(-1).text, EXAMPLES.find(x => x.label === "Set 6:00").instead);
    // No example scans the world (that has crashed the game just after a level loads).
    assert.ok(!EXAMPLES.some(x => /World\.nearby|findAll|FindAllOf/.test(x.code)));
  } finally { t.handle.unmount(); }
});

test("Ctrl+Up and Ctrl+Down go back through the lines run, and back to what was being typed", async () => {
  const t = await mount("listening");
  try {
    for (const line of ["return 1", "return 2"]) {
      t.code.value = line;
      t.button("Run").click();
      await tick();
    }
    t.code.value = "half-typ";
    const key = (k, ctrlKey = true) => t.code.dispatch("keydown", { key: k, ctrlKey });
    key("ArrowUp");
    assert.equal(t.code.value, "return 2");
    key("ArrowUp");
    assert.equal(t.code.value, "return 1");
    key("ArrowUp");
    assert.equal(t.code.value, "return 1");
    key("ArrowDown");
    key("ArrowDown");
    assert.equal(t.code.value, "half-typ");
    key("ArrowUp", false);   // a plain Up moves the cursor, as in any box
    assert.equal(t.code.value, "half-typ");
  } finally { t.handle.unmount(); }
});

test("the page stops asking the game while it's hidden, and says a new state when shown", async () => {
  const t = await mount("closed");
  try {
    const before = t.calls("GET /game/bridge").length;
    t.root.hidden = true;
    t.bridge.state = "listening";
    await t.handle.poll();
    assert.equal(t.calls("GET /game/bridge").length, before);
    assert.equal(t.strip.textContent, SAID.closed);
    t.root.hidden = false;
    await t.handle.poll();
    assert.equal(t.strip.textContent, SAID.listening);
    assert.equal(t.button("Run").disabled, false);
  } finally { t.handle.unmount(); }
});

test("the page's head says it's for people who write scripts, with its help page", async () => {
  const t = await mount("closed");
  try {
    const head = t.q(".section-head");
    assert.equal(head.querySelector(".eyebrow").textContent, "Advanced");
    assert.equal(head.querySelector("h1").textContent, "Try Lua in the game");
    assert.match(head.querySelector(".note").textContent, /^For people who write scripts: .*Nothing here is saved into a mod\./);
    const said = [];
    const off = t.wc.bus.on("help", page => said.push(page));
    head.querySelector("button").click();
    off();
    assert.deepEqual(said, ["console"]);
  } finally { t.handle.unmount(); }
});
