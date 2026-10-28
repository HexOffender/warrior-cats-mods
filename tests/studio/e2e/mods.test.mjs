// The Mods page in a real browser (lib/browser.mjs), on studios of the tests' own (lib/studio.mjs): Get set up
// against a made-up game, with GitHub stood in for by a folder of release .zips (WCMODS_RELEASES), the card of
// the mods that go with Clan Mod Studio, and the page's fixes (Find a mod, the add preview, a mod's name).
// Skipped, with a reason, when no Chromium is found: set WC_BROWSER to one, or WC_REQUIRE_BROWSER=1 (as CI
// does) to fail instead of skipping.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { launch } from "../lib/browser.mjs";
import { browserChoice, dataFolder, makeGame, makeLoader, makeMod, makeZip, removeFolders, requireBrowser, sleep,
  startStudio, takeTurn } from "../lib/studio.mjs";

const { browserPath, skip } = browserChoice();

// Two studios: `fresh` walks Get set up from a made-up game with a save and the script loader; `page` has
// mods of its own for the page's fixes. Each has a folder standing in for GitHub's releases.
let browser, fresh, page, freshFolders, pageFolders, release;

function releases(root, zips) {
  const dir = path.join(root, "releases");
  fs.mkdirSync(dir, { recursive: true });
  for (const [name, files] of Object.entries(zips)) makeZip(path.join(dir, name), files);
  return dir;
}

before(async () => {
  if (skip) return;
  requireBrowser(browserPath);
  release = await takeTurn();   // one end-to-end file at a time
  freshFolders = dataFolder();
  makeGame(freshFolders.game);
  makeLoader(freshFolders.game);
  fs.writeFileSync(path.join(freshFolders.saves, "WrcGame.sav"), "a save");   // Get set up only looks for it
  const freshReleases = releases(freshFolders.root, {
    // Menu pages and Sandbox mode have releases (Sandbox mode's carries examples, which aren't it); Creator
    // palettes and the Emote wheel have none yet.
    "menu-pages-1.0.zip": { "menu-pages/mod.json": { name: "Menu pages", version: "1.0", author: "wcmods" }, "menu-pages/scripts/main.lua": "-- pages" },
    "sandbox-0.4.zip": { "sandbox/mod.json": { name: "Sandbox mode", version: "0.4", author: "wcmods" }, "sandbox/scripts/main.lua": "-- sandbox" },
    "sandbox-story-0.3.zip": { "sandbox-story/mod.json": { name: "A story", version: "0.3" } },
  });
  pageFolders = dataFolder();
  makeGame(pageFolders.game);
  makeMod(pageFolders.data, "palette-dark-forest", { name: "Dark Forest" });
  makeMod(pageFolders.data, "moonlight", { name: "Moonlight" });
  makeMod(pageFolders.data, "clicky", { name: "Clicky" });
  const pageReleases = releases(pageFolders.root, {});
  // One after the other, each kept as soon as it's up, so `after` can end whatever started if another fails.
  fresh = await startStudio(freshFolders, { WCMODS_RELEASES: freshReleases });
  page = await startStudio(pageFolders, { WCMODS_RELEASES: pageReleases });
  browser = await launch({ browser: browserPath });
  const first = await browser.page();   // a cold browser and studio can be slow the first time
  await first.goto(fresh.url, { timeout: 60000 });
  await first.waitFor("#nav button", 60000);
  await first.close();
});

after(async () => {
  for (const s of [fresh, page]) if (s) s.stop();
  if (browser) await browser.close();
  for (const f of [freshFolders, pageFolders]) if (f) await removeFolders(f);
  if (release) release();
});

const stepTitles = p => p.evaluate(() => [...document.querySelectorAll(".setup .step strong")].map(s => s.textContent.replace(/^(Done|To do): /, "")));
const toasts = p => p.evaluate(() => [...document.querySelectorAll("#toasts .toast")].map(t => t.textContent).join(" | "));
const rowChip = (p, id) => p.evaluate(`document.querySelector('[data-key="addon:${id}"] .chip')?.textContent`);
const config = folders => JSON.parse(fs.readFileSync(path.join(folders.data, "wcmods.json"), "utf8"));
// Every request the page makes from now on, in window.calls.
const spy = p => p.evaluate(() => {
  window.calls = [];
  const real = window.fetch;
  window.fetch = (url, init) => { window.calls.push(`${(init && init.method) || "GET"} ${url}`); return real(url, init); };
  return true;
});

test("Get set up: five steps, Add all four says what has no release yet, Allow names the code mods, and the card folds", { skip }, async () => {
  const p = await browser.page();
  await p.goto(fresh.url + "#mods");
  await p.waitFor(() => document.querySelectorAll(".setup .steps li").length === 5);
  await p.waitFor(() => [...document.querySelectorAll(".setup .step.done strong")].some(s => s.textContent.includes("Your save is backed up")));
  assert.deepEqual(await stepTitles(p), ["Found the game", "Your save is backed up", "The script loader is installed",
    "Let mods run their own scripts", "Get the mods that go with Clan Mod Studio"]);
  await p.waitFor(() => document.querySelectorAll(".addons .addon").length === 4);
  assert.deepEqual(await p.evaluate(() => [...document.querySelectorAll(".addons .addon .addon-body strong")].map(s => s.textContent)),
    ["Menu pages", "Sandbox mode", "Creator palettes", "Emote wheel"]);

  await p.click({ text: "Add all four" });
  await p.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.startsWith("Added Menu pages 1.0 and Sandbox mode 0.4.")), 30000);
  const said = await toasts(p);
  assert.match(said, /Creator palettes and Emote wheel have no release yet: the owner of that mod has to publish one/);
  assert.match(said, /Let mods run their own scripts is the next step/);
  assert.doesNotMatch(said, /https?:/, "no addresses in the toast: the rows link to them");
  // The card is drawn again once the page has read the add-ons after the last one: until then a row may still
  // say "Adding …" from the draw during it.
  await p.waitFor(() => document.querySelector('[data-key="addon:emote-wheel"] .chip')?.textContent === "No release yet");
  assert.equal(await rowChip(p, "creator-palettes"), "No release yet");
  assert.equal(await rowChip(p, "menu-pages"), "Needs scripts allowed");
  assert.equal(await p.count('[data-key="addon:emote-wheel"] button'), 0, "nothing to press until a release exists");
  assert.ok(fs.existsSync(path.join(freshFolders.data, "mods", "sandbox", "mod.json")) && !fs.existsSync(path.join(freshFolders.data, "mods", "sandbox-story")));
  assert.equal(config(freshFolders).setup_addons, "added");
  await p.waitFor(() => [...document.querySelectorAll(".setup .step.done strong")].some(s => s.textContent.endsWith("The mods that go with Clan Mod Studio")));

  // Allow asks once, naming the mods in your folder that run code, then patches the setting.
  await p.click({ text: "Allow" });
  await p.waitFor(".setup .code-warning li");
  assert.deepEqual(await p.evaluate(() => [...document.querySelectorAll(".setup .code-warning li")].map(li => li.textContent)),
    ["Menu pages, by wcmods: Your cat, the world, quests, fights and cheats in the in-game menu",
      "Sandbox mode, by wcmods: Shows the cats and questlines you make"]);
  assert.equal(config(freshFolders).allow_code_mods, undefined, "nothing is allowed by the first press");
  await p.click({ text: "Allow mods that run code" });
  await p.waitFor(".setup.folded");
  assert.equal(config(freshFolders).allow_code_mods, true);
  assert.match(await p.text(".setup.folded"), /Set up/);
  await p.waitFor(() => document.querySelector('[data-key="addon:menu-pages"] .chip')?.textContent === "In, 1.0");
  // Show the steps opens it again, every step ticked.
  await p.click({ text: "Show the steps" });
  await p.waitFor(() => document.querySelectorAll(".setup .step.done").length === 5);
  assert.deepEqual(p.consoleErrors(), []);
  await p.close();
});

test("Not now on the add-ons step leaves an Add button on each row of the add-ons card", { skip }, async () => {
  const p = await browser.page();
  await p.goto(page.url + "#mods");
  await p.waitFor(() => [...document.querySelectorAll(".setup .step strong")].some(s => s.textContent.includes("Get the mods that go with Clan Mod Studio")));
  const step = await p.evaluate(() => {
    const li = [...document.querySelectorAll(".setup .step")].find(s => s.textContent.includes("Get the mods that go with Clan Mod Studio"));
    li.querySelector("button.ghost").dataset.test = "addons-not-now";
    return true;
  });
  assert.ok(step);
  await p.click('[data-test="addons-not-now"]');
  await p.waitFor(() => [...document.querySelectorAll(".setup .step.done strong")].some(s => s.textContent.includes("not now")));
  assert.equal(config(pageFolders).setup_addons, "not now");
  assert.deepEqual(await p.evaluate(() => [...document.querySelectorAll(".addons .addon button")].map(b => b.getAttribute("aria-label"))),
    ["Add: Menu pages", "Add: Sandbox mode", "Add: Creator palettes", "Add: Emote wheel"]);
  assert.deepEqual(p.consoleErrors(), []);
  await p.close();
});

test("a focus doesn't ask GitHub about the add-ons; Check for newer versions does", { skip }, async () => {
  const p = await browser.page();
  await p.goto(page.url + "#mods");
  await p.waitFor(() => document.querySelectorAll(".addons .addon").length === 4);
  await spy(p);
  // The shell listens for the window's focus once it has opened the page: focus it until it's heard.
  await p.waitFor(() => { window.dispatchEvent(new Event("focus")); return window.calls.some(c => c === "GET /api/addons"); });
  await sleep(300);
  assert.ok(!(await p.evaluate(() => window.calls)).some(c => c.includes("latest=1")), "a focus asks only the studio");
  await p.click({ text: "Check for newer versions" });
  await p.waitFor(() => window.calls.some(c => c === "GET /api/addons?latest=1"));
  // The stand-in for GitHub has no releases at all: every row says so.
  await p.waitFor(() => [...document.querySelectorAll(".addons .addon .chip")].every(c => c.textContent === "No release yet"));
  await p.close();
});

test("typing Dark Forest keeps the space and the capitals and matches", { skip }, async () => {
  const p = await browser.page();
  await p.goto(page.url + "#mods");
  await p.waitFor('[data-key="mod:moonlight"]');
  await p.type("#mod-search", "D");
  for (const ch of "ark Forest") await p.send("Input.insertText", { text: ch });   // a key at a time, as typing would
  assert.equal(await p.evaluate(() => document.getElementById("mod-search").value), "Dark Forest");
  assert.equal(await p.evaluate(() => document.activeElement.id), "mod-search", "the box keeps the focus");
  assert.deepEqual(await p.evaluate(() => [...document.querySelectorAll(".mod-cards .mod")].map(m => m.dataset.key)), ["mod:palette-dark-forest"]);
  await p.close();
});

test("clicking a mod's name does not switch it", { skip }, async () => {
  const p = await browser.page();
  await p.goto(page.url + "#mods");
  await p.waitFor('[data-key="mod:clicky"]');
  await spy(p);
  await p.click('[data-key="mod:clicky"] .mod-name strong');
  await sleep(300);
  assert.equal(await p.evaluate(() => document.getElementById("mod-on-clicky").checked), true);
  assert.ok(!(await p.evaluate(() => window.calls)).some(c => c.includes("/switch")));
  assert.equal(await p.evaluate(() => document.getElementById("mod-on-clicky").getAttribute("aria-label")), "Clicky");
  await p.close();
});

test("a pack preview does not warn about mods inside the zip, and offers to add a missing add-on", { skip }, async () => {
  const zip = makeZip(path.join(pageFolders.root, "moonlit-path-1.0.zip"), {
    "moonlit-path/mod.json": { name: "The Moonlit Path", pack: true, requires: ["moonlit-cats", "moonlit-colours"] },
    "moonlit-cats/mod.json": { name: "Moonlit cats", requires: ["sandbox"] },
    "moonlit-cats/npcs.json": { npcs: [] },
    "moonlit-colours/mod.json": { name: "Moonlit colours" },
  });
  const p = await browser.page();
  await p.goto(page.url + "#mods");
  await p.waitFor("#mod-file");
  await p.setFiles("#mod-file", [zip]);
  await p.waitFor(() => document.querySelectorAll(".mod.preview").length === 3);
  const notes = await p.evaluate(() => Object.fromEntries([...document.querySelectorAll(".mod.preview")].map(m =>
    [m.querySelector("strong").textContent, [...m.querySelectorAll(".notes li")].map(li => [li.className, li.textContent])])));
  assert.deepEqual(notes["The Moonlit Path"], [["", "Needs Moonlit cats (in this .zip), Moonlit colours (in this .zip), turned on with it."]]);
  assert.equal(notes["Moonlit cats"][0][0], "warn");
  assert.match(notes["Moonlit cats"][0][1], /^Needs Sandbox mode\. You don't have Sandbox mode, so it goes in switched off until you add it\./);
  assert.equal(await p.count('.mod.preview button[data-addon="sandbox"]'), 1);
  await p.click({ text: "Cancel" });
  await p.waitFor("#mod-choose");
  await p.close();
});

test("the preview's Add sends only the ticked mods, each on or off as its box says", { skip }, async () => {
  const zip = makeZip(path.join(pageFolders.root, "three.zip"), {
    "alpha/mod.json": { name: "Alpha" }, "beta/mod.json": { name: "Beta", enabled: false }, "gamma/mod.json": { name: "Gamma" } });
  const p = await browser.page();
  await p.goto(page.url + "#mods");
  await p.waitFor("#mod-file");
  await p.setFiles("#mod-file", [zip]);
  await p.waitFor(() => document.querySelectorAll(".mod.preview").length === 3);
  // Each "Switched on" box starts as the mod ships.
  assert.deepEqual(await p.evaluate(() => ["alpha", "beta", "gamma"].map(i => document.getElementById(`on-${i}`).checked)), [true, false, true]);
  await spy(p);
  await p.click("#pick-alpha");
  await p.click("#pick-beta");
  await p.click("#on-beta");
  await p.click({ text: "Add these" });
  await p.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.startsWith("Added Alpha, Beta.")));
  const sent = (await p.evaluate(() => window.calls)).find(c => c.startsWith("POST /api/mods/add?step=add"));
  assert.match(sent, /ids=alpha%2Cbeta&on=alpha%2Cbeta&/);
  const on = id => JSON.parse(fs.readFileSync(path.join(pageFolders.data, "mods", id, "mod.json"), "utf8")).enabled;
  assert.ok(on("alpha") && on("beta") && !fs.existsSync(path.join(pageFolders.data, "mods", "gamma")));
  assert.deepEqual(p.consoleErrors(), []);
  await p.close();
});

test("one mod with Switch it on unticked goes in switched off, named without its version", { skip }, async () => {
  const zip = makeZip(path.join(pageFolders.root, "Quiet Mod v2.zip"), { "mod.json": { name: "Quiet mod", version: "2" } });
  const p = await browser.page();
  await p.goto(page.url + "#mods");
  await p.waitFor("#mod-file");
  await p.setFiles("#mod-file", [zip]);
  await p.waitFor("#add-on");
  assert.equal(await p.evaluate(() => document.getElementById("add-on").checked), true, "on, as it ships");
  await p.click("#add-on");
  await p.click({ text: "Add to my mods" });
  await p.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.startsWith("Added Quiet mod.")));
  assert.equal(JSON.parse(fs.readFileSync(path.join(pageFolders.data, "mods", "quiet-mod", "mod.json"), "utf8")).enabled, false);
  await p.close();
});
