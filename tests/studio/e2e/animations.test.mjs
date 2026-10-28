// The Animations page in a real browser (lib/browser.mjs), on a studio without the game: the game's sequences
// are served from fixtures/anim-sequences-cat.json. The key dialog cancels on Escape and on a click outside,
// a keystroke on another page is never taken, a name left empty goes back to the id, and one of the game's
// animations becomes an emote, or plays in another's place, with no file at all.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { launch } from "../lib/browser.mjs";
import { e2eBrowser, needBrowser, takeTurn, startStudio, dataFolder, removeFolders } from "../lib/studio.mjs";

const { browserPath, skip } = e2eBrowser();
const SEQS = JSON.parse(fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "fixtures", "anim-sequences-cat.json"), "utf8"));

let browser, studio, folders, release;

before(async () => {
  if (skip) return;
  needBrowser(browserPath);
  release = await takeTurn();   // one end-to-end file at a time
  folders = dataFolder();
  studio = await startStudio(folders);
  browser = await launch({ browser: browserPath });
  // A first load, with time to spare: a cold browser and studio are slow, and every test's own waits are 10 s.
  const page = await browser.page();
  await page.goto(studio.url, { timeout: 60000 });
  await page.waitFor("#nav button", 60000);
  await page.close();
});

after(async () => {
  if (studio) studio.stop();
  if (browser) await browser.close();
  if (folders) await removeFolders(folders);
  if (release) release();
});

// The Animations page with the game's cat sequences from the fixture (the longer route first: the shorter one's
// pattern matches both), its file loaded.
async function animationsPage({ sequences = true } = {}) {
  const page = await browser.page();
  if (sequences) {
    await page.route("/api/game/anim-sequences", SEQS);
    await page.route("/api/game/anim-sequence", url => SEQS.facts[new URL(url).searchParams.get("name")] || null);
  }
  await page.goto(studio.url + "#animations");
  await page.waitFor(() => document.querySelector('[aria-label="animations.json"] pre')?.textContent);
  return page;
}
const json = page => page.evaluate(() => JSON.parse(document.querySelector('[aria-label="animations.json"] pre').textContent));
const editor = '[data-key="editor:animation"]';
const keyChip = page => page.text(`${editor} .chip`);
const dialogOpen = page => page.evaluate(() => !!document.querySelector('[role="dialog"]'));
async function add(page) {
  await page.click({ text: "Add an animation" });
  await page.waitFor(`${editor} input[aria-label="Name"]`);
}
// Choose a value in a select, once it's there and the game's list is in it (10 s).
async function choose(page, label, value) {
  const sel = JSON.stringify(`select[aria-label="${label}"]`);
  await page.evaluate(`(async () => {
    for (let n = 0; n < 200; n++) {
      const s = document.querySelector(${sel});
      if (s && !s.disabled) { s.value = ${JSON.stringify(value)}; s.dispatchEvent(new Event("change")); return; }
      await new Promise(r => setTimeout(r, 50));
    }
    throw new Error(${JSON.stringify(`no ${label} to choose in`)});
  })()`);
}

test("without the game's files the list of the game's animations says so, and the rest of the page works", { skip }, async () => {
  const page = await animationsPage({ sequences: false });
  await add(page);
  await page.waitFor(() => /Couldn't read the game's animations/.test(document.querySelector('[data-key="editor:animation"]').textContent));
  assert.equal(await page.text('.section[data-page="animations"] h1'), "Animations");
  assert.ok(await page.evaluate(() => [...document.querySelectorAll('.section[data-page="animations"] .section-head button')].some(b => b.textContent === "How this works")));
  assert.match(await page.text('.pick[aria-current="true"]'), /needs an animation/);
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("the key dialog cancels on Escape and on a click outside, and takes a key pressed in it", { skip }, async () => {
  const page = await animationsPage();
  await add(page);
  assert.equal(await keyChip(page), "No key");
  assert.doesNotMatch(await page.text(editor), /\bnull\b|undefined/, "nothing left out shows as a word");
  await page.click({ text: "Press a key…" });
  await page.waitFor('[role="dialog"]');
  await page.press("Escape");
  await page.waitFor(async () => !document.querySelector('[role="dialog"]'));
  assert.equal(await keyChip(page), "No key", "Escape cancels: it isn't the key");
  await page.click({ text: "Press a key…" });
  await page.waitFor('[role="dialog"]');
  await page.send("Input.dispatchMouseEvent", { type: "mousePressed", x: 4, y: 4, button: "left", clickCount: 1 });
  await page.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: 4, y: 4, button: "left", clickCount: 1 });
  await page.waitFor(() => !document.querySelector('[role="dialog"]'));
  assert.equal(await keyChip(page), "No key", "a click outside cancels");
  await page.click({ text: "Press a key…" });
  await page.waitFor('[role="dialog"]');
  await page.press("Tab");
  assert.equal(await dialogOpen(page), true, "Tab moves among the dialog's buttons, and isn't a key");
  await page.press("F7");
  await page.waitFor(() => !document.querySelector('[role="dialog"]'));
  assert.equal(await keyChip(page), "F7");
  assert.equal((await json(page)).animations.at(-1).key, "F7");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("a keystroke on another page is never taken as the key", { skip }, async () => {
  const page = await animationsPage();
  await add(page);
  await page.click({ text: "Press a key…" });
  await page.waitFor('[role="dialog"]');
  await page.evaluate(() => { location.hash = "#npcs"; });
  await page.waitFor(() => !document.querySelector('[role="dialog"]'));
  await page.waitFor('.section[data-page="npcs"]:not([hidden]) .target select');
  await page.press("g");
  await page.press("F8");
  await page.evaluate(() => { location.hash = "#animations"; });
  await page.waitFor('.section[data-page="animations"]:not([hidden])');
  assert.equal(await keyChip(page), "No key");
  assert.equal((await json(page)).animations.at(-1).key, undefined);
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("a blank name goes back to the id when the box is left", { skip }, async () => {
  const page = await animationsPage();
  await add(page);
  const id = (await json(page)).animations.at(-1).id;
  await page.evaluate(() => { const n = document.querySelector('[data-key="editor:animation"] input[aria-label="Name"]'); n.focus(); n.value = ""; n.dispatchEvent(new Event("input")); });
  await page.press("Tab");
  assert.equal(await page.evaluate(() => document.querySelector('[data-key="editor:animation"] input[aria-label="Name"]').value), id);
  assert.equal((await json(page)).animations.at(-1).name, id);
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("game emote flow: one of the game's animations on a key, and another in a game animation's place, with no file", { skip }, async () => {
  const page = await animationsPage();
  await add(page);
  await page.evaluate(() => { document.querySelector('[data-key="editor:animation"] input[aria-label="Name"]').value = ""; });
  await page.type('[data-key="editor:animation"] input[aria-label="Name"]', "Yawn");
  const groups = await page.evaluate(async () => {
    const s = document.querySelector('select[aria-label="The game\'s animation"]');
    while (s.disabled) await new Promise(r => setTimeout(r, 50));
    return [...s.querySelectorAll("optgroup")].map(g => [g.label, [...g.querySelectorAll("option")].map(o => o.textContent)]);
  });
  assert.deepEqual(groups.map(g => g[0]), ["Everyday", "Photo poses", "All of them"]);
  assert.deepEqual(groups[0][1], ["Idle (A_CatMaster_Idle_1)", "Run (A_CatMaster_Run_1)", "Stretch (A_CatMaster_Stretch_1)",
    "Trot (A_CatMaster_Trot_1)", "Yawn (A_CatMaster_Yawn_1)"]);
  assert.deepEqual(groups[1][1], ["Feral Frenzy (A_CatMaster_Pose_Photo_Mode_1)"]);
  assert.ok(!groups[2][1].some(t => t.includes("Meow_1")), "the additive one isn't offered");
  await choose(page, "The game's animation", "A_CatMaster_Yawn_1");
  await page.waitFor(() => /Yawn: 3\.13 s\./.test(document.querySelector('[data-key="editor:animation"]').textContent));
  await page.click({ text: "Press a key…" });
  await page.waitFor('[role="dialog"]');
  await page.press("F7");
  await page.waitFor(() => document.querySelector('[data-key="editor:animation"] .chip')?.textContent === "F7");
  assert.deepEqual((await json(page)).animations.at(-1), { id: "Yawn", name: "Yawn", game: "A_CatMaster_Yawn_1", emote: true, key: "F7" });
  assert.doesNotMatch(await page.text(editor), /\bnull\b|undefined/, "nothing left out shows as a word");
  assert.match(await page.text('.pick[aria-current="true"]'), /Yawn emote \(F7\)/);

  // Second try: every cat trots with the run.
  await add(page);
  await page.evaluate(() => { document.querySelector('[data-key="editor:animation"] input[aria-label="Name"]').value = ""; });
  await page.type('[data-key="editor:animation"] input[aria-label="Name"]', "Run as the trot");
  await choose(page, "The game's animation", "A_CatMaster_Run_1");
  // Its facts come in a moment later, and move what's below them: clicked once they're in.
  await page.waitFor(() => /Run: 0\.63 s\./.test(document.querySelector('[data-key="editor:animation"]').textContent));
  await page.click('input[aria-label="Plays where the game plays one of its own"]');
  await choose(page, "The game's animation it plays in place of", "A_CatMaster_Trot_1");
  await page.waitFor(() => /plays Run where the game played Trot \(0\.47 s; fitted to its 15 keys\)/.test(document.querySelector('[data-key="editor:animation"]').textContent));
  assert.deepEqual((await json(page)).animations.at(-1), { id: "RunAsTheTrot", name: "Run as the trot", game: "A_CatMaster_Run_1", replaces: "A_CatMaster_Trot_1" });
  assert.equal(await page.evaluate(() => [...document.querySelectorAll('[data-key="editor:animation"] h3')].some(h => h.textContent === "How it plays")), false,
    "it plays as the game played the one it replaces");
  assert.match(await page.text('.pick[aria-current="true"]'), /in place of Trot/);
  await page.click({ text: "Save to mod" });
  await page.waitFor(() => document.querySelector(".target .dirty").textContent === "");
  const saved = JSON.parse(fs.readFileSync(path.join(folders.data, "mods", "my-mods", "animations.json"), "utf8")).animations;
  assert.deepEqual(saved.filter(a => a.game).map(a => a.id), ["Yawn", "RunAsTheTrot"]);
  assert.ok(saved.every(a => !a.file), "no file at all");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});
