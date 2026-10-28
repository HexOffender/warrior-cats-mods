// Choosing which game in the save a page changes, in a real browser, over a save of the test's own with three games
// (never the player's): your 1st game (slot 0) and your 5th (slot 4, the game played last, a Sandbox mode game) each
// with a ThunderClan apprentice of the very same name, and your 3rd (slot 2) a RiverClan medicine cat. The Save page
// starts on the game played last, a change made in another game goes into that game only, and the list keeps every
// game's changes, each under its game; Your cat writes "player" for the cat in the game being played and "0/player"
// for your cat in your 1st game. Both say which game they're on. Skipped, with a reason, when no Chromium is found.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { launch } from "../lib/browser.mjs";
import { browserChoice, dataFolder, makeGame, readSave, removeFolders, requireBrowser, sleep, startStudio, takeTurn,
  warmUp, writeSave } from "../lib/studio.mjs";

const { browserPath, skip } = browserChoice();
let browser, studio, folders, release;

const CAT = (clan, role, prefix, suffix, fields) =>
  `(ClanType=${clan},Role=${role},PrefixNameId="${prefix}",SuffixNameId="${suffix}",${fields})`;
const GAME = (cat, level, npc) => ({ GameplayProgression: { Level: level, Experience: 10 * level,
  "Gameplay.Combat.Character.Cat.Player": { Customization: cat } },
  ...(npc ? { NPCData: { Clans: { ThunderClan: { Warrior: [npc] } } } } : {}) });
const SAVE = current => ({ acct: {
  0: GAME(CAT("ThunderClan", "Apprentice", "STR_CAT_NAME6", "_PAW", "FurColorIdx=3,TailIdx=1"), 3,
    CAT("ThunderClan", "Warrior", "STR_CAT_NAME7", "_HEART", "FurColorIdx=4")),
  2: GAME(CAT("RiverClan", "MedicineCat", "STR_CAT_NAME9", "_WING", "FurColorIdx=5,TailIdx=7"), 7),
  4: GAME(CAT("ThunderClan", "Apprentice", "STR_CAT_NAME6", "_PAW", "FurColorIdx=8,TailIdx=2"), 1,
    CAT("ThunderClan", "Warrior", "STR_CAT_NAME10", "_FUR", "FurColorIdx=6")),
  Shared: { General: { CurrentCatSlot: current }, SettingsData: { MasterVolume: 1 } } } });

before(async () => {
  if (skip) return;
  requireBrowser(browserPath);
  release = await takeTurn();   // one end-to-end file at a time
  folders = dataFolder();
  makeGame(folders.game);
  await writeSave(folders.saves, SAVE(4));
  // Sandbox mode's list of its games, beside the saves (pipeline.saved_folder), as the mod writes it.
  fs.mkdirSync(path.join(folders.root, "WCMods"), { recursive: true });
  fs.writeFileSync(path.join(folders.root, "WCMods", "sandbox.json"),
    JSON.stringify({ cats: [{ slot: 4, clan: "ThunderClan", prefix: "STR_CAT_NAME6", made: "2026-10-27T10:00:00Z" }] }));
  studio = await startStudio(folders);
  browser = await launch({ browser: browserPath });
  await warmUp(browser, studio.url);
});

after(async () => {
  if (studio) studio.stop();
  if (browser) await browser.close();
  if (folders) await removeFolders(folders);
  if (release) release();
});

const SLOW = 30000;
const choose = (page, selector, value) => page.evaluate(`(s => { s.value = ${JSON.stringify(value)}; s.dispatchEvent(new Event("change")); })(document.querySelector(${JSON.stringify(selector)}))`);
const options = (page, selector) => page.evaluate(`[...document.querySelector(${JSON.stringify(selector)}).options].map(o => [o.value, o.textContent])`);
// Close a page, saying yes to "Leave site?" when it asks (a page left asking holds up the browser's other pages).
async function leave(page) {
  const off = page.c.on(msg => {
    if (msg.sessionId === page.sessionId && msg.method === "Page.javascriptDialogOpening") {
      page.send("Page.handleJavaScriptDialog", { accept: true }).catch(() => { /* already gone */ });
    }
  });
  try { await page.close(); await sleep(300); } finally { off(); }
}

// ---------- the Save page ----------
async function openSave() {
  const page = await browser.page();
  await page.goto(studio.url + "#save", { timeout: SLOW });
  await page.waitFor('.section[data-page="save"][data-ready]', SLOW);
  return page;
}
const pending = page => page.evaluate(() => [...document.querySelectorAll("#save-pending > h3, #save-pending > .changes li > span:first-child")].map(s => s.textContent));
const level = page => page.evaluate(() => document.querySelector('#save-cat input[type="number"]').value);
async function setLevel(page, value) {
  await page.evaluate(`(n => { n.value = ${JSON.stringify(String(value))}; n.dispatchEvent(new Event("change")); })(document.querySelector('#save-cat input[type="number"]'))`);
}

test("the Save page starts on the game played last, and says each game by its number", { skip }, async () => {
  const page = await openSave();
  assert.equal(await page.evaluate(() => document.getElementById("save-game-pick").value), "4");
  assert.deepEqual(await options(page, "#save-game-pick"), [
    ["0", "1st game: ThunderClan, level 3"], ["2", "3rd game: RiverClan, level 7"],
    ["4", "5th game: ThunderClan, level 1, Sandbox mode, played last"]]);
  assert.equal(await page.text("#save-cat h2"), "Your cat in your 5th game");
  assert.equal(await level(page), "1");
  assert.doesNotMatch(await page.text('.section[data-page="save"]'), /\bnull\b|undefined|NaN/);
  assert.deepEqual(page.consoleErrors(), []);
  await leave(page);
});

test("a level changed in another game goes into that game only, and the list keeps it under its game", { skip }, async () => {
  const page = await openSave();
  await choose(page, "#save-game-pick", "0");
  await page.waitFor(() => document.querySelector("#save-cat h2").textContent === "Your cat in your 1st game");
  assert.equal(await level(page), "3", "the 1st game's level");
  await setLevel(page, 9);
  await page.waitFor(() => document.querySelectorAll("#save-pending > .changes li").length === 1);
  assert.deepEqual(await pending(page), ["Your 1st game (the game chosen above)", "your 1st game's cat's level: 3 -> 9"]);
  // Back to the 5th game: the change to the 1st stays in the list, under its game.
  await choose(page, "#save-game-pick", "4");
  await page.waitFor(() => document.querySelector("#save-cat h2").textContent === "Your cat in your 5th game");
  assert.equal(await level(page), "1");
  assert.deepEqual(await pending(page), ["Your 1st game", "your 1st game's cat's level: 3 -> 9"]);
  await setLevel(page, 4);
  await page.waitFor(() => document.querySelectorAll("#save-pending > .changes li").length === 2);
  assert.deepEqual(await pending(page), ["Your 1st game", "your 1st game's cat's level: 3 -> 9",
    "Your 5th game (the game chosen above)", "your cat's level: 1 -> 4"]);
  // The buttons name the game too: the save has more than one.
  assert.equal(await page.count(`[aria-label="Remove your cat's level in your 5th game from the list"]`), 1);
  await page.click("#save-now");
  await page.waitFor(() => document.querySelectorAll("#save-done .changes > li").length === 2, 15000);
  const saved = readSave(folders.saves).acct;
  assert.equal(saved["0"].GameplayProgression.Level, 9);
  assert.equal(saved["4"].GameplayProgression.Level, 4);
  assert.equal(saved["2"].GameplayProgression.Level, 7, "the 3rd game is as it was");
  assert.deepEqual(await page.evaluate(() => [...document.querySelectorAll("#save-done > h3")].map(h => h.textContent)),
    ["Your 1st game", "Your 5th game"]);
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => / made, in your 1st game and your 5th game\./.test(t.textContent)));
  // The share fold says where a shared change goes.
  assert.match(await page.text("#save-share-games"), /it goes into their game with the same number/);
  assert.deepEqual(page.consoleErrors(), []);
  await leave(page);
});

test("the game chosen is kept while the game played last is the same, and follows it when another was played", { skip }, async () => {
  let page = await openSave();
  await choose(page, "#save-game-pick", "2");
  await page.waitFor(() => document.querySelector("#save-cat h2").textContent === "Your cat in your 3rd game");
  await page.reload();
  await page.waitFor('.section[data-page="save"][data-ready]', SLOW);
  assert.equal(await page.evaluate(() => document.getElementById("save-game-pick").value), "2", "kept in this tab");
  await leave(page);
  // The 1st game played since: the page opens on it.
  await writeSave(folders.saves, { ...SAVE(0) });
  page = await openSave();
  assert.equal(await page.evaluate(() => document.getElementById("save-game-pick").value), "0");
  assert.match((await options(page, "#save-game-pick"))[0][1], /^1st game: ThunderClan, level 3, played last$/);
  await leave(page);
  await writeSave(folders.saves, SAVE(4));
});

// ---------- Your cat ----------
const CATP = '[data-page="cat"]';
async function openCat() {
  const page = await browser.page();
  await page.goto(studio.url + "#cat", { timeout: SLOW });
  await page.waitFor(`${CATP} select[aria-label="Which game"]`, SLOW);
  await page.waitFor(() => document.querySelector('[data-page="cat"] .target select')?.options.length > 0);
  return page;
}
const catsJson = () => path.join(folders.data, "mods", "my-mods", "cats.json");
async function saveToMod(page, check) {
  await page.evaluate(`[...document.querySelectorAll('${CATP} button')].find(b => b.textContent.trim() === "Save to mod").click()`);
  const end = Date.now() + 10000;
  for (;;) {
    try { const doc = JSON.parse(fs.readFileSync(catsJson(), "utf8")); if (check(doc)) return doc; } catch (e) { /* not yet */ }
    if (Date.now() > end) throw new Error(`cats.json didn't come to be as expected: ${fs.existsSync(catsJson()) ? fs.readFileSync(catsJson(), "utf8") : "missing"}`);
    await sleep(50);
  }
}

test("Your cat writes \"player\" for the game being played, and \"0/player\" for your 1st game's cat, naming each", { skip }, async () => {
  fs.mkdirSync(path.dirname(catsJson()), { recursive: true });
  fs.writeFileSync(path.join(path.dirname(catsJson()), "mod.json"), JSON.stringify({ name: "My mods", enabled: true }));
  const page = await openCat();
  // The default: whichever game is being played at Apply.
  assert.equal(await page.evaluate(`document.querySelector('${CATP} select[aria-label="Which game"]').value`), "player");
  assert.equal(await page.text("#cat-who-title"), "Your cat, in the game you're playing");
  assert.equal(await page.text("#cat-now-title"), "In your save now: your 5th game, the game you played last");
  assert.deepEqual((await options(page, `${CATP} select[aria-label="Which game"]`)).map(([, t]) => t), [
    "The cat in the game you're playing (whichever it is when you Apply)",
    "Your cat, your 1st game", "Your cat, your 3rd game", "Your cat, your 5th game, Sandbox mode, played last"]);
  await choose(page, `${CATP} select[aria-label="Tail"]`, "4");
  let doc = await saveToMod(page, d => d.player?.look?.tail === 4);
  assert.equal(doc.cats, undefined, "nothing under cats");
  // Your 1st game's cat: its own entry, by its slot, and what it has now.
  await choose(page, `${CATP} select[aria-label="Which game"]`, "0/player");
  await page.waitFor(() => document.getElementById("cat-who-title")?.textContent === "Your cat in your 1st game");
  assert.equal(await page.text("#cat-now-title"), "In your save now: your 1st game");
  assert.match(await page.text(`${CATP} .cat-top .card:last-child ul`), /Colours: coat 3/);
  assert.match(await page.text("#cat-who-note"), /^Only your cat in your 1st game changes, whichever game you're playing/);
  await choose(page, `${CATP} select[aria-label="Tail"]`, "6");
  doc = await saveToMod(page, d => d.cats?.["0/player"]?.look?.tail === 6);
  assert.equal(doc.player.look.tail, 4, "the game being played's look stays as it was");
  assert.doesNotMatch(await page.text(CATP), /\bnull\b|undefined|NaN/);
  // The other cats show their games.
  const groups = await page.evaluate(`[...document.querySelectorAll('${CATP} select[aria-label="Whose look"] optgroup')].map(g => g.label)`);
  assert.ok(groups.includes("ThunderClan, your 5th game") && groups.includes("ThunderClan, your 1st game"), groups.join(" | "));
  assert.deepEqual(page.consoleErrors(), []);
  await leave(page);
});
