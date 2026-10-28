// The strip at the top of the Characters and Questlines pages (story.js sandboxStrip, stripWords) under the DOM
// shim: one line for each thing the studio says about Sandbox mode (on, off, kept out by "Allow mods that run
// code", missing, too old for the fixed looks the cats use), what each button does, and the way to see them.
import { test } from "node:test";
import assert from "node:assert/strict";
import { install, tick } from "../lib/dom.mjs";

const dom = install();
const story = await import(dom.studio("lib/story.js"));

// What GET /story/sandbox answers (wcmods/story.py sandbox()), changed by `over`.
const answer = over => ({ state: "on", version: "0.5", name: "Sandbox mode", needs: { look: "0.5", slots: "0.5" }, newest: "0.5",
  older: [], releases: "https://github.com/HexOffender/wcmods-sandbox/releases", code_allowed: true, ...over });

test("each state of Sandbox mode has its own words", () => {
  assert.deepEqual(story.stripWords(answer()), { kind: "good", title: "Sandbox mode 0.5 is on", text: "It brings your cats and questlines into the game." });
  const off = story.stripWords(answer({ state: "off" }));
  assert.equal(off.title, "Sandbox mode is off");
  assert.equal(off.button, "Turn it on");
  const noCode = story.stripWords(answer({ state: "no-code" }));
  assert.equal(noCode.title, "Sandbox mode is in, but mods that run code aren't allowed, so it can't run");
  assert.match(noCode.text, /Allow them on Settings and repair, then Apply to game/);
  assert.equal(noCode.settings, true);
  const missing = story.stripWords(answer({ state: "missing", version: null, code_allowed: false }));
  assert.equal(missing.title, "You'll need Sandbox mode");
  assert.match(missing.text, /download sandbox-0\.5\.zip from its releases page and drop it on the Mods page\./);
  assert.match(missing.text, /allow mods that run code on Settings and repair too/);
  assert.equal(missing.link, "https://github.com/HexOffender/wcmods-sandbox/releases");
  assert.doesNotMatch(story.stripWords(answer({ state: "missing", version: null })).text, /run code/);
});

test("a Sandbox mode too old for the fixed looks the cats use says so; one the cats don't need doesn't", () => {
  const old = answer({ version: "0.4", older: ["look", "slots"] });
  const said = story.stripWords(old, ["look", "slots"]);
  assert.equal(said.title, "Your fixed looks need Sandbox mode 0.5 or newer; you have 0.4");
  assert.match(said.text, /the game makes their look up each time/);
  assert.equal(story.stripWords(old, []).title, "Sandbox mode 0.4 is on");
  // Off and too old: the version first (turning it on wouldn't be enough).
  assert.match(story.stripWords({ ...old, state: "off" }, ["look"]).title, /^Your fixed looks need/);
});

test("the strip asks the studio, draws the line and the way to see them, and opens the guide's page", async () => {
  dom.routes = { "GET /story/sandbox": () => answer({ state: "missing", version: null }) };
  const wc = await import(dom.studio("lib/wc.js"));
  const helps = [];
  const off = wc.bus.on("help", p => helps.push(p));
  const strip = story.sandboxStrip({ help: "characters", route: "To see them: Apply to game, Play." });
  const line = strip.element.children[0];
  assert.equal(line.hidden, true, "nothing said before the studio has answered");
  await strip.refresh();
  assert.equal(line.hidden, false);
  assert.equal(line.className, "banner");
  assert.match(line.textContent, /^You'll need Sandbox mode/);
  assert.equal(line.querySelector("a").getAttribute("href"), "https://github.com/HexOffender/wcmods-sandbox/releases");
  assert.match(strip.element.textContent, /To see them: Apply to game, Play\./);
  strip.element.querySelectorAll("button").find(b => b.textContent === "How this works").click();
  assert.deepEqual(helps, ["characters"]);
  off();
  // The studio couldn't be asked: no line rather than a wrong one.
  dom.routes = {};
  await strip.refresh();
  assert.equal(line.hidden, true);
});

test("Turn it on switches Sandbox mode on, says so and asks again", async () => {
  let on = false;
  const posts = [];
  dom.routes = {
    "GET /story/sandbox": () => answer({ state: on ? "on" : "off" }),
    "POST /mods/sandbox/switch": b => { posts.push(b); on = true; return { changed: [{ id: "sandbox", name: "Sandbox mode", on: true }], blocked_by: [] }; },
  };
  const strip = story.sandboxStrip({ help: "questlines", route: "To play them." });
  await strip.refresh();
  const line = strip.element.children[0];
  assert.match(line.textContent, /^Sandbox mode is off/);
  line.querySelectorAll("button").find(b => b.textContent === "Turn it on").click();
  await tick(10);
  assert.deepEqual(posts, [{ on: true }]);
  assert.equal(line.className, "banner info");
  assert.match(line.textContent, /^Sandbox mode 0\.5 is on/);
  assert.match(dom.byId.toasts.textContent, /Turned on Sandbox mode\. Apply to game to use it\./);
});

test("update() redraws the line for the fields the page's cats use, without asking again", async () => {
  let asked = 0;
  dom.routes = { "GET /story/sandbox": () => { asked++; return answer({ version: "0.4", older: ["look", "slots"] }); } };
  const strip = story.sandboxStrip({ help: "characters", route: "" });
  await strip.refresh();
  const line = strip.element.children[0];
  assert.match(line.textContent, /^Sandbox mode 0\.4 is on/);
  strip.update(["look", "slots"]);
  assert.match(line.textContent, /^Your fixed looks need Sandbox mode 0\.5 or newer; you have 0\.4/);
  strip.update([]);
  assert.match(line.textContent, /^Sandbox mode 0\.4 is on/);
  assert.equal(asked, 1);
});
