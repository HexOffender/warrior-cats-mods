// The Questlines page in a real browser (lib/browser.mjs), against a studio over a folder of its own with a
// made-up game folder: opening on a mod that isn't made yet asks for none of its files, a first questline
// with a mod's cat, a circle of "Starts after" said and the box that would close one disabled, objectives
// left for the build to fill in, Start every questline over, mods chosen quickly one after another, and a
// mod whose questlines can't be read. Skipped, with a reason, when no Chromium.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { launch } from "../lib/browser.mjs";
import { browserPath, skip, startStudio, dataFolder, makeGame, writeMod, readJson, removeFolders } from "../lib/studio.mjs";

let browser, studio, folders;
const SLOW = 30000;   // a page's first load, while the other e2e files start their own browser and studio beside this one
const toastSaid = (page, text) => page.waitFor(new Function(`return [...document.querySelectorAll("#toasts .toast")].some(t => t.textContent.includes(${JSON.stringify(text)}))`));
const questsFile = () => path.join(folders.data, "mods", "story", "quests.json");

before(async () => {
  if (skip) return;
  if (!browserPath) throw new Error("WC_REQUIRE_BROWSER=1, and no Chromium was found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)");
  folders = dataFolder();
  makeGame(folders.game);
  writeMod(folders, "story", { name: "Story", uses: ["sandbox"] },
    { "npcs.json": { npcs: [{ id: "mossfoot", name: "Mossfoot", lines: [] }, { id: "sparrowpaw", name: "Sparrowpaw", lines: [] }] } });
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
});

async function openQuestlines(mod) {
  const page = await browser.page();
  await page.goto(studio.url + "#quests", { timeout: SLOW });
  await page.waitFor(() => [...document.querySelectorAll("button")].some(b => b.textContent === "Add a questline" && !b.disabled), SLOW);
  if (mod) {
    await page.evaluate(`(() => { const s = document.querySelector(".target select"); s.value = ${JSON.stringify(mod)}; s.dispatchEvent(new Event("change")); })()`);
    // Its cats are in once the "no cats yet" note has gone.
    await page.waitFor(new Function(`return document.querySelector(".target select").value === ${JSON.stringify(mod)}
      && [...document.querySelectorAll(".banner")].find(b => b.textContent.startsWith("This mod has no cats yet"))?.hidden`));
  }
  return page;
}

test("opening on My mods before it's made asks for none of its files", { skip }, async () => {
  const page = await openQuestlines();
  assert.equal(await page.evaluate(() => document.querySelector(".target select").value), "my-mods");
  await page.waitFor(() => (b => b && !b.hidden)(document.querySelector(".sandbox-strip .banner")), SLOW);
  const asked = await page.evaluate(() => performance.getEntriesByType("resource").map(e => e.name).filter(n => n.includes("/api/mods/my-mods/")));
  assert.deepEqual(asked, []);
  assert.match(await page.text(".sandbox-strip .banner"), /^You'll need Sandbox mode/);
  assert.match(await page.text(".sandbox-strip p.note"), /objective panel on the left and on the mod menu's Questlines page/);
  assert.ok(await page.evaluate(() => [...document.querySelectorAll(".banner")].some(b => !b.hidden && b.textContent.startsWith("This mod has no cats yet"))));
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("a first questline: the giver's talk step is there, typing the title keeps your place, and objectives are left to the build", { skip }, async () => {
  const page = await openQuestlines("story");
  await page.click({ text: "Add a questline" });
  await page.waitFor(() => document.activeElement?.dataset.focus === "quest:title");
  await page.type('[data-focus="quest:title"]', "Moss for Mossfoot");
  assert.equal(await page.text(".pick[aria-current] strong"), "Moss for Mossfoot");
  await page.click('[data-focus="quest:about"]');
  assert.equal(await page.evaluate(() => document.activeElement?.dataset.focus), "quest:about", "one click, not lost to a redraw");
  assert.equal(await page.evaluate(() => document.querySelector('select[aria-label="Given by"]').value), "mossfoot");
  // The first step is a talk with Mossfoot, not ready until it has a line.
  await page.waitFor(() => document.querySelector(".step-card.not-ready .step-problem")?.textContent.includes("What do they say?"));
  await page.type(".step-card textarea", "Bring me two moss?");
  await page.waitFor(() => !document.querySelector(".step-card.not-ready"));
  assert.equal(await page.evaluate(() => document.querySelector('.step-card input[aria-label="Step 1\'s objective"]').placeholder), "Talk to Mossfoot");
  await page.click({ text: "Save to mod" });
  await toastSaid(page, "Saved quests.json in story.");
  const saved = readJson(questsFile()).quests[0];
  assert.equal(saved.id, "moss-for-mossfoot");
  assert.deepEqual(saved.steps, [{ do: "talk", npc: "mossfoot", lines: ["Bring me two moss?"] }], "no objective written: the build fills it in");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("circle_in_starts_after_is_said_and_the_box_disabled", { skip }, async () => {
  fs.writeFileSync(questsFile(), JSON.stringify({ quests: [
    { id: "a", title: "Moss for Mossfoot", giver: "mossfoot", after: [], steps: [{ do: "talk", lines: ["Hi"] }] },
    { id: "b", title: "Herbs", giver: "sparrowpaw", after: ["a"], steps: [{ do: "talk", lines: ["Hi"] }] }] }));
  const page = await openQuestlines("story");
  await page.waitFor(() => document.querySelectorAll(".pick").length === 2);
  // On the first quest, Herbs already waits for it: ticking Herbs would make a circle, so the box is off and says why.
  const box = await page.evaluate(() => {
    const label = [...document.querySelectorAll("label")].find(l => l.textContent.startsWith("Herbs"));
    const input = label.querySelector("input");
    return { disabled: input.disabled, why: label.title, said: label.textContent };
  });
  assert.deepEqual(box, { disabled: true, why: "Herbs already waits for this quest", said: "Herbs(Herbs already waits for this quest)" });
  // A circle made in the file by hand is said at the top of each quest in it.
  fs.writeFileSync(questsFile(), JSON.stringify({ quests: [
    { id: "a", title: "Moss for Mossfoot", giver: "mossfoot", after: ["b"], steps: [{ do: "talk", lines: ["Hi"] }] },
    { id: "b", title: "Herbs", giver: "sparrowpaw", after: ["a"], steps: [{ do: "talk", lines: ["Hi"] }] }] }));
  await page.reload();
  await page.waitFor(() => [...document.querySelectorAll(".banner")].some(b => !b.hidden && b.textContent.includes("Starts after goes round in a circle: Moss for Mossfoot → Herbs → Moss for Mossfoot")));
  // Unticked, the note goes.
  await page.click('[data-focus="after:b"]');
  await page.waitFor(() => ![...document.querySelectorAll(".banner")].some(b => !b.hidden && b.textContent.includes("circle")));
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("Start every questline over clears the sandbox cats' quests and keeps where their cats stand", { skip }, async () => {
  const progress = path.join(folders.root, "WCMods", "sandbox-story.json");   // beside the saves folder
  fs.mkdirSync(path.dirname(progress), { recursive: true });
  fs.writeFileSync(progress, JSON.stringify({ 3: { quests: { "story/a": { step: 2, got: 0 } }, cats: { "story/mossfoot": { at: [1, 2, 3] } } } }));
  const page = await openQuestlines("story");
  await page.click({ text: "Start every questline over" });
  await page.click({ text: "Press again to start every mod's questlines over" });
  await toastSaid(page, "Every mod's questlines start over, for 1 sandbox cat.");
  assert.deepEqual(readJson(progress), { 3: { quests: {}, cats: { "story/mossfoot": { at: [1, 2, 3] } } } });
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

// The tests below choose other mods: the page opens on the last one chosen, so they come last.
test("mods chosen one after another (arrow keys in the select) end on the last one's cats and quests", { skip }, async () => {
  writeMod(folders, "nocats", { name: "No cats" });
  const page = await openQuestlines("story");
  await page.waitFor(() => document.querySelectorAll(".pick").length > 0);
  // story -> nocats -> story -> nocats, at once: story's files (its quests, then its cats) come back last. The
  // page's requests are counted, to know when everything they started has come back and been drawn.
  await page.evaluate(() => {
    const real = window.fetch;
    window.inflight = 0;
    window.fetch = (...args) => { window.inflight++; return real(...args).finally(() => { window.inflight--; }); };
    const s = document.querySelector(".target select");
    for (const id of ["nocats", "story", "nocats"]) { s.value = id; s.dispatchEvent(new Event("change")); }
  });
  for (let quiet = 0, looks = 0; quiet < 3 && looks < 150; looks++) {   // nothing in flight three looks running, 100 ms apart
    await page.evaluate(() => new Promise(done => setTimeout(done, 100)));
    quiet = await page.evaluate(() => window.inflight) === 0 ? quiet + 1 : 0;
  }
  assert.equal(await page.evaluate(() => document.querySelector(".target select").value), "nocats");
  assert.ok(await page.evaluate(() => [...document.querySelectorAll(".banner")].some(b => !b.hidden && b.textContent.startsWith("This mod has no cats yet"))),
    "nocats' (no) cats, not story's");
  assert.equal(await page.evaluate(() => document.querySelectorAll(".pick").length), 0, "nocats' (no) quests, not story's");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("a mod whose questlines can't be read says so, and Add comes back all the same", { skip }, async () => {
  writeMod(folders, "unreadable", { name: "Unreadable" });
  fs.writeFileSync(path.join(folders.data, "mods", "unreadable", "quests.json"), Buffer.from([0xff, 0xfe, 0x7b, 0x7d]));   // not UTF-8
  const page = await openQuestlines();
  await page.evaluate(() => localStorage.setItem("wc-target", "unreadable"));
  await page.reload();
  await toastSaid(page, "The mod's questlines couldn't be read");
  await page.waitFor(() => [...document.querySelectorAll("button")].some(b => b.textContent === "Add a questline" && !b.disabled), SLOW);
  await page.evaluate(() => localStorage.setItem("wc-target", "story"));
  await page.close();
});
