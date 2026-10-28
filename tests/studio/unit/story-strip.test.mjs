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
  // The studio hasn't heard of a release: no file named, as the version the fields need may not be out.
  assert.match(missing.text, /download its newest \.zip from its releases page and drop it on the Mods page\./);
  assert.doesNotMatch(missing.text, /sandbox-0\.5/);
  assert.match(missing.text, /allow mods that run code on Settings and repair too/);
  assert.equal(missing.link, "https://github.com/HexOffender/wcmods-sandbox/releases");
  assert.doesNotMatch(story.stripWords(answer({ state: "missing", version: null })).text, /run code/);
  // GitHub said 0.4 is the newest (Check for newer versions, or an add): that's the file to download.
  assert.match(story.stripWords(answer({ state: "missing", version: null, released: "0.4" })).text,
    /download sandbox-0\.4\.zip from its releases page/);
});

test("fixed looks that need a Sandbox mode that isn't released yet say so, and never name its .zip", () => {
  // 0.4 in your mods, 0.4 the newest release, and the cats' fixed looks need 0.5.
  const notOut = story.stripWords(answer({ version: "0.4", older: ["look", "slots"], released: "0.4" }), ["look", "slots"]);
  assert.equal(notOut.title, "Your fixed looks need Sandbox mode 0.5, which isn't out yet; you have 0.4");
  assert.equal(notOut.text, "Until it's out the game makes their look up each time. Your cats go in all the same.");
  assert.doesNotMatch(notOut.title + notOut.text, /\.zip|Get the latest/);
  assert.equal(notOut.link, "https://github.com/HexOffender/wcmods-sandbox/releases");
  // Older still: the same.
  assert.match(story.stripWords(answer({ version: "0.3", older: ["look"], released: "0.4" }), ["look"]).title, /^Your fixed looks need Sandbox mode 0\.5, which isn't out yet; you have 0\.3$/);
  // Once 0.5 is out (or something newer), it's named, with Get the latest.
  for (const released of ["0.5", "0.5.0", "0.6"]) {
    const out = story.stripWords(answer({ version: "0.4", older: ["look"], released }), ["look"]);
    assert.equal(out.title, "Your fixed looks need Sandbox mode 0.5 or newer; you have 0.4", released);
    assert.match(out.text, new RegExp(`Sandbox mode ${released.replace(/\./g, "\\.")} is out: press Get the latest on its row on the Mods page, or download sandbox-${released.replace(/\./g, "\\.")}\\.zip`));
    assert.equal(out.mods, true);
  }
  // Nothing heard from GitHub: no file name, and the way to find out.
  const unknown = story.stripWords(answer({ version: "0.4", older: ["look"] }), ["look"]);
  assert.equal(unknown.title, "Your fixed looks need Sandbox mode 0.5 or newer; you have 0.4");
  assert.equal(unknown.text, "Until then the game makes their look up each time. To see whether 0.5 is out, press Check for newer versions on the Mods page; Get the latest then brings it.");
  assert.equal(unknown.mods, true);
  // A release that isn't a plain version can't be compared: named as it is, never said to be too old.
  assert.match(story.stripWords(answer({ version: "0.4", older: ["look"], released: "beta" }), ["look"]).title, /or newer/);
});

test("a Sandbox mode too old for the fixed looks the cats use says so; one the cats don't need doesn't", () => {
  const old = answer({ version: "0.4", older: ["look", "slots"] });
  const said = story.stripWords(old, ["look", "slots"]);
  assert.equal(said.title, "Your fixed looks need Sandbox mode 0.5 or newer; you have 0.4");
  assert.match(said.text, /the game makes their look up each time/);
  assert.equal(story.stripWords(old, []).title, "Sandbox mode 0.4 is on");
  // Off and too old: the version first (turning it on wouldn't be enough).
  assert.match(story.stripWords({ ...old, state: "off" }, ["look"]).title, /^Your fixed looks need/);
  // The version is what the fields the cats use need, not the newest any field needs.
  const later = answer({ version: "0.4", needs: { look: "0.5", slots: "0.6" }, newest: "0.6", older: ["look", "slots"] });
  assert.equal(story.stripWords(later, ["look"]).title, "Your fixed looks need Sandbox mode 0.5 or newer; you have 0.4");
  assert.equal(story.stripWords(later, ["look", "slots"]).title, "Your fixed looks need Sandbox mode 0.6 or newer; you have 0.4");
  assert.match(story.stripWords({ ...later, released: "0.6" }, ["look"]).text, /download sandbox-0\.6\.zip/, "the newest release is the one to get");
});

test("a Sandbox mode a game update holds back says Use it anyway on the Mods page", () => {
  const own = story.stripWords(answer({ state: "held-back", held: "made for an older version of the game" }));
  assert.equal(own.kind, "warn");
  assert.equal(own.title, "Sandbox mode is left out since the game's update");
  assert.match(own.text, /made for an older version of the game.*on the Mods page, its card has Use it anyway…, then Apply to game\./);
  assert.equal(own.mods, true);
  const other = story.stripWords(answer({ state: "held-back", held: "needs Menu pages, made for an older version of the game" }));
  assert.match(other.text, /^It needs Menu pages, made for an older version of the game, so nothing shows your cats and questlines until you use that one anyway/);
  // Too old as well: the version first, as with off.
  assert.match(story.stripWords(answer({ state: "held-back", held: "made for an older version of the game", version: "0.4", older: ["look"] }), ["look"]).title,
    /^Your fixed looks need Sandbox mode 0\.5/);
});

test("laterVersion compares versions as numbers", () => {
  assert.equal(story.laterVersion("0.9", "0.10"), "0.10");
  assert.equal(story.laterVersion("0.5.0", "0.5"), "0.5.0");
  assert.equal(story.laterVersion("v1.0", "0.9"), "v1.0");
  assert.equal(story.laterVersion(null, "0.5"), "0.5");
  assert.equal(story.laterVersion("beta", "0.4"), "0.4");
  assert.equal(story.laterVersion("beta", undefined), null);
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

test("the held-back line links the Mods page", async () => {
  dom.routes = { "GET /story/sandbox": () => answer({ state: "held-back", held: "made for an older version of the game" }) };
  const strip = story.sandboxStrip({ help: "characters", route: "" });
  await strip.refresh();
  const line = strip.element.children[0];
  assert.match(line.textContent, /^Sandbox mode is left out since the game's update/);
  assert.equal(line.querySelector("a").getAttribute("href"), "#mods");
  assert.equal(line.querySelector("a").textContent, "Open the Mods page");
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
