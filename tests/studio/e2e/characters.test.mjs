// The Characters page in a real browser (lib/browser.mjs), against a studio over a folder of its own with a
// made-up game folder and a Sandbox mode mod that's off: the strip, adding a cat while the page loads, typing
// a name without losing your place, "At one spot" with no spot, saving (which turns Sandbox mode on), the
// strip's own button, removing a cat that a quest names, the strip following the Editing mod, and a mod whose
// cats can't be read. Skipped, with a reason, when no Chromium is found.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { launch } from "../lib/browser.mjs";
import { browserChoice, dataFolder, makeGame, readJson, removeFolders, requireBrowser, startStudio, takeTurn,
  writeMod } from "../lib/studio.mjs";

const { browserPath, skip } = browserChoice();

let browser, studio, folders, release;
const SLOW = 30000;   // a page's first load, while the other e2e files start their own browser and studio beside this one
const toastSaid = (page, text) => page.waitFor(new Function(`return [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.includes(${JSON.stringify(text)}))`));
const stripLine = page => page.evaluate(() => document.querySelector(".sandbox-strip .banner")?.textContent || "");
const sandboxMeta = () => path.join(folders.data, "mods", "sandbox", "mod.json");

before(async () => {
  if (skip) return;
  requireBrowser(browserPath);
  release = await takeTurn();   // one end-to-end file at a time
  folders = dataFolder({ allow_code_mods: true });
  makeGame(folders.game);
  writeMod(folders, "sandbox", { name: "Sandbox mode", version: "0.5", enabled: false }, { "scripts/main.lua": "" });
  studio = await startStudio(folders);
  browser = await launch({ browser: browserPath });
  const page = await browser.page();   // a first load, with time to spare (a cold browser and studio)
  await page.goto(studio.url, { timeout: 60000 });
  await page.waitFor("#nav button", 60000);
  await page.close();
});

after(async () => {
  if (studio) studio.stop();
  if (browser) await browser.close();
  await removeFolders(folders);
  if (release) release();
});

async function openCharacters() {
  const page = await browser.page();
  await page.goto(studio.url + "#npcs", { timeout: SLOW });
  await page.waitFor(() => [...document.querySelectorAll("button")].some(b => b.textContent === "Add a cat" && !b.disabled), SLOW);
  await page.waitFor(() => (b => b && !b.hidden)(document.querySelector(".sandbox-strip .banner")), SLOW);
  return page;
}

test("Add a cat pressed while the page is still loading waits, and nothing goes wrong", { skip }, async () => {
  const page = await browser.page();
  await page.goto(studio.url + "#npcs", { timeout: SLOW });
  // Pressed the moment it's on the page, before the mod's file is read: it waits (and used to throw a ReferenceError).
  const wasHeld = await page.evaluate(() => new Promise(done => {
    const t = setInterval(() => {
      const b = [...document.querySelectorAll("button")].find(x => x.textContent === "Add a cat");
      if (b) { clearInterval(t); const held = b.disabled; b.click(); done(held); }
    }, 1);
  }));
  await page.waitFor(() => [...document.querySelectorAll("button")].some(b => b.textContent === "Add a cat" && !b.disabled), SLOW);
  assert.equal(wasHeld, true, "Add is held back until the mod's file is read");
  assert.equal(await page.evaluate(() => document.querySelectorAll(".pick").length), 0, "the press while it was held added nothing");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("the page says Sandbox mode is off, with its button, and how to see the cats in the game", { skip }, async () => {
  const page = await openCharacters();
  assert.match(await stripLine(page), /^Sandbox mode is off/);
  assert.ok(await page.evaluate(() => [...document.querySelectorAll(".sandbox-strip button")].some(b => b.textContent === "Turn it on")));
  assert.match(await page.text(".sandbox-strip p.note"), /Sandbox Mode on the main menu/);
  assert.match(await page.text(".section-head .note"), /Talk prompt \(E by default, or A on a controller\)/);
  // How this works opens the guide's Characters page.
  await page.click({ text: "How this works" });
  await page.waitFor(() => !document.getElementById("help").hidden && document.querySelector("#helpBody h1"));
  assert.equal(await page.text("#helpTitle"), "Characters");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("tab_out_of_name_lands_on_title, and a click from the name to the title needs one click", { skip }, async () => {
  const page = await openCharacters();
  await page.click({ text: "Add a cat" });
  await page.waitFor(() => document.activeElement?.dataset.focus === "cat:name");
  await page.type('[data-focus="cat:name"]', "Mossfoot");   // a new cat's name is chosen: typing replaces it
  assert.equal(await page.evaluate(() => document.querySelector('[data-focus="cat:name"]').value), "Mossfoot");
  assert.equal(await page.text(".pick[aria-current] strong"), "Mossfoot", "the list says the name as it's typed");
  await page.press("Tab");
  assert.equal(await page.evaluate(() => document.activeElement?.dataset.focus), "cat:title");
  await page.type('[data-focus="cat:title"]', "Elder");
  // Back to the name, then one click on the title: it's there, not lost to a redraw.
  await page.click('[data-focus="cat:name"]');
  await page.type('[data-focus="cat:name"]', "!");
  await page.click('[data-focus="cat:title"]');
  assert.equal(await page.evaluate(() => document.activeElement?.dataset.focus), "cat:title");
  assert.equal(await page.evaluate(() => document.querySelector('[data-focus="cat:name"]').value), "Mossfoot!");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("at_one_spot_without_numbers_shows_not_ready, eye_swatch_keeps_the_place_radio, and a save turns Sandbox mode on", { skip }, async () => {
  const page = await openCharacters();
  await page.click({ text: "Add a cat" });
  await page.waitFor(() => document.activeElement?.dataset.focus === "cat:name");
  await page.type('[data-focus="cat:name"]', "Mossfoot");
  assert.equal(await page.evaluate(() => document.querySelector('[data-focus="look:same"]').checked), true, "a new cat keeps its look");
  await page.click('[data-focus="place:spot"]');
  await page.waitFor(() => [...document.querySelectorAll(".banner")].some(b => !b.hidden && b.textContent.includes("At one spot, but no spot is filled in yet")));
  await page.click('button[aria-label="Eye colour 3"]');
  assert.equal(await page.evaluate(() => document.querySelector('[data-focus="place:spot"]').checked), true);
  assert.equal(await page.evaluate(() => document.querySelector('button[aria-label="Eye colour 3"]').getAttribute("aria-checked")), "true");
  assert.ok(await page.evaluate(() => [...document.querySelectorAll("button")].some(b => b.textContent === "Use where my cat is standing")));
  // Saved: the spot not chosen yet is kept as null, the mod uses Sandbox mode, and Sandbox mode came on with it.
  await page.click({ text: "Save to mod" });
  await toastSaid(page, "Turned Sandbox mode on too.");
  const cat = readJson(path.join(folders.data, "mods", "my-mods", "npcs.json")).npcs[0];
  assert.equal(cat.name, "Mossfoot");
  assert.equal(cat.at, null);
  assert.equal(cat.eyes, 3);
  assert.ok(cat.look && cat.slots, "a fixed look");
  const meta = readJson(path.join(folders.data, "mods", "my-mods", "mod.json"));
  assert.deepEqual(meta.uses, ["sandbox"]);
  assert.ok(!(meta.requires || []).length);
  assert.equal(readJson(sandboxMeta()).enabled, true);
  await page.waitFor(() => /^Sandbox mode 0\.5 is on/.test(document.querySelector(".sandbox-strip .banner").textContent));
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("the strip says a Sandbox mode too old for fixed looks, and Turn it on switches it on", { skip }, async () => {
  fs.writeFileSync(sandboxMeta(), JSON.stringify({ name: "Sandbox mode", version: "0.4", enabled: false }));
  let page = await openCharacters();
  assert.match(await stripLine(page), /^Your fixed looks need Sandbox mode 0\.5 or newer; you have 0\.4/);
  await page.close();
  fs.writeFileSync(sandboxMeta(), JSON.stringify({ name: "Sandbox mode", version: "0.5", enabled: false }));
  page = await openCharacters();
  assert.match(await stripLine(page), /^Sandbox mode is off/);
  await page.click({ text: "Turn it on" });
  await page.waitFor(() => /^Sandbox mode 0\.5 is on/.test(document.querySelector(".sandbox-strip .banner").textContent));
  assert.equal(readJson(sandboxMeta()).enabled, true);
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("removing a cat a quest names says which quest to change", { skip }, async () => {
  const dir = path.join(folders.data, "mods", "my-mods");
  fs.writeFileSync(path.join(dir, "quests.json"), JSON.stringify({ quests: [{ id: "moss", title: "Moss for Mossfoot",
    giver: readJson(path.join(dir, "npcs.json")).npcs[0].id, steps: [{ do: "talk", lines: ["Hi"] }] }] }));
  const page = await openCharacters();
  await page.waitFor(() => document.querySelector(".pick strong")?.textContent === "Mossfoot");
  await page.click({ text: "Remove Mossfoot" });
  await page.click({ text: "Press again to remove" });
  await toastSaid(page, "Removed Mossfoot. Moss for Mossfoot names them: choose another cat there before Apply.");
  assert.equal(await page.text(".dirty"), "Unsaved changes");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

// The tests below choose other mods: the page opens on the last one chosen, so they come last.
async function chooseMod(page, id, catName) {
  await page.evaluate(`(() => { const s = document.querySelector(".target select"); s.value = ${JSON.stringify(id)}; s.dispatchEvent(new Event("change")); })()`);
  await page.waitFor(new Function(`return document.querySelector(".target select").value === ${JSON.stringify(id)}
    && document.querySelector(".pick strong")?.textContent === ${JSON.stringify(catName)}`), SLOW);
}

test("the strip follows the Editing mod: fixed looks say Sandbox mode is too old, a mod without them doesn't", { skip }, async () => {
  fs.writeFileSync(sandboxMeta(), JSON.stringify({ name: "Sandbox mode", version: "0.4", enabled: true }));
  writeMod(folders, "fixed-looks", { name: "Fixed looks", uses: ["sandbox"] },
    { "npcs.json": { npcs: [{ id: "fern", name: "Fern", look: { body: 2 }, slots: { fur: 3 } }] } });
  writeMod(folders, "random-looks", { name: "Random looks", uses: ["sandbox"] }, { "npcs.json": { npcs: [{ id: "ash", name: "Ash" }] } });
  const page = await openCharacters();
  await chooseMod(page, "random-looks", "Ash");
  assert.match(await stripLine(page), /^Sandbox mode 0\.4 is on/);
  await chooseMod(page, "fixed-looks", "Fern");
  assert.match(await stripLine(page), /^Your fixed looks need Sandbox mode 0\.5 or newer; you have 0\.4/);
  await chooseMod(page, "random-looks", "Ash");
  assert.match(await stripLine(page), /^Sandbox mode 0\.4 is on/, "the words for the other mod's cats go with it");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("a mod whose cats can't be read says so, and Add comes back all the same", { skip }, async () => {
  writeMod(folders, "unreadable", { name: "Unreadable" });
  fs.writeFileSync(path.join(folders.data, "mods", "unreadable", "npcs.json"), Buffer.from([0xff, 0xfe, 0x7b, 0x7d]));   // not UTF-8
  const page = await openCharacters();
  await page.evaluate(() => localStorage.setItem("wc-target", "unreadable"));
  await page.reload();
  await toastSaid(page, "The mod's cats couldn't be read");
  await page.waitFor(() => [...document.querySelectorAll("button")].some(b => b.textContent === "Add a cat" && !b.disabled), SLOW);
  await page.evaluate(() => localStorage.setItem("wc-target", "my-mods"));
  await page.close();
});
