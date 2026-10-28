// The Items page in a real browser (lib/browser.mjs), on a studio without the game: /api/game/items is served
// from fixtures/game-items.json, and the routes that draw the game's pictures and shapes fail, as the page
// allows. The first picture into a mod not made yet is kept, Tab from Name reaches Description, a Kind round
// trip brings the model back, and the cards come in the creator's order with the 3D fold closed.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { launch } from "../lib/browser.mjs";
import { e2eBrowser, needBrowser, takeTurn, startStudio, dataFolder, removeFolders, pngFile } from "../lib/studio.mjs";

const { browserPath, skip } = e2eBrowser();
const GAME_ITEMS = JSON.parse(fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "fixtures", "game-items.json"), "utf8"));

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

// The Items page with the game's items from the fixture, its mod list in.
async function itemsPage() {
  const page = await browser.page();
  await page.route("/api/game/items", GAME_ITEMS);
  await page.goto(studio.url + "#items");
  await page.waitFor(() => document.querySelector('.target select[aria-label="Mod that stores items.json"]')?.options.length > 0);
  // The mod's file is in once its items.json shows in the panel at the foot of the page.
  await page.waitFor(() => document.querySelector('[aria-label="items.json"] pre')?.textContent);
  return page;
}
const json = page => page.evaluate(() => JSON.parse(document.querySelector('[aria-label="items.json"] pre').textContent));
const setSelect = (page, label, value) => page.evaluate(`(() => { const s = document.querySelector('select[aria-label="${label}"]');
  s.value = ${JSON.stringify(value)}; s.dispatchEvent(new Event("change")); })()`);

test("without the game's files the page says it needs them, under its head with the help link", { skip }, async () => {
  const page = await browser.page();
  await page.goto(studio.url + "#items");
  await page.waitFor(() => document.querySelector('.section[data-page="items"] .error-card'));
  assert.match(await page.text('.section[data-page="items"] .error-card'), /Couldn't read the game's items.*needs the game's files/s);
  assert.equal(await page.text('.section[data-page="items"] h1'), "Items");
  assert.ok(await page.evaluate(() => [...document.querySelectorAll('.section[data-page="items"] .section-head button')].some(b => b.textContent === "How this works")));
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("first upload into a new mod is kept, in the file and on the item", { skip }, async () => {
  const page = await itemsPage();
  assert.match(await page.evaluate(() => document.querySelector(".target select").selectedOptions[0].textContent), /My mods \(new\)/);
  await page.click({ text: "Add an item" });
  await page.waitFor('input[aria-label="Name"]');
  await page.evaluate(() => { document.querySelector('input[aria-label="Name"]').value = ""; });
  await page.type('input[aria-label="Name"]', "Moon Herb");
  await page.type('[data-key="editor:item"] textarea[aria-label="Description"]', "Heals a cat under the full moon.");
  // The icon's picture, chosen before the mod exists: choosing it saves the mod first, which reads the file again.
  await page.setFiles('[data-key="editor:item"] input[type="file"][accept^="image"]', [pngFile(path.join(folders.root, "moon.png"))]);
  await page.waitFor(() => document.querySelector('[aria-label="items.json"] pre').textContent.includes('"icon": "pictures/MoonHerb-icon.png"'), 15000);
  const shown = (await json(page)).items[0];
  assert.deepEqual([shown.id, shown.name, shown.description, shown.icon], ["MoonHerb", "Moon Herb", "Heals a cat under the full moon.", "pictures/MoonHerb-icon.png"]);
  assert.equal(await page.evaluate(() => document.querySelector('select[aria-label="Icon"]').value), "own", "the editor shows the item that has it");
  await page.click({ text: "Save to mod" });
  await page.waitFor(() => document.querySelector(".target .dirty").textContent === "");
  const mod = path.join(folders.data, "mods", "my-mods");
  const saved = JSON.parse(fs.readFileSync(path.join(mod, "items.json"), "utf8")).items[0];
  assert.equal(saved.icon, "pictures/MoonHerb-icon.png");
  assert.equal(saved.name, "Moon Herb");
  assert.ok(fs.existsSync(path.join(mod, "pictures", "MoonHerb-icon.png")));
  assert.equal(await page.evaluate(() => document.querySelector(".problems").hidden), true, "nothing keeps it out of the game");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("tab from Name lands on Description, and the list's label follows the name as it's typed", { skip }, async () => {
  const page = await itemsPage();
  await page.click({ text: "Add an item" });
  await page.waitFor('input[aria-label="Name"]');
  await page.evaluate(() => { document.querySelector('input[aria-label="Name"]').value = ""; });
  await page.type('input[aria-label="Name"]', "Tea Leaf");
  assert.equal(await page.evaluate(() => document.querySelector('.pick[aria-current="true"] strong').textContent), "Tea Leaf");
  await page.press("Tab");
  assert.equal(await page.evaluate(() => document.activeElement.getAttribute("aria-label")), "Description");
  // A description still to write is marked, on the card and in the list.
  assert.equal(await page.evaluate(() => [...document.querySelectorAll(".field-problem")].some(n => !n.hidden && /without a description/.test(n.textContent))), true);
  assert.match(await page.text('.pick[aria-current="true"]'), /needs a description/);
  // A name left empty goes back to the item's id when the box is left.
  await page.evaluate(() => { const n = document.querySelector('input[aria-label="Name"]'); n.value = ""; n.dispatchEvent(new Event("input")); n.focus(); });
  await page.press("Tab");
  assert.equal(await page.evaluate(() => document.querySelector('input[aria-label="Name"]').value), "TeaLeaf");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("kind round trip keeps the model: Herb with a model on the ground, Accessory, Herb again", { skip }, async () => {
  const page = await itemsPage();
  await page.click({ text: "Add an item" });
  await page.waitFor('[data-key="items:advanced"]');
  assert.equal(await page.evaluate(() => document.querySelector('[data-key="items:advanced"]').open), false, "closed for a plain herb");
  await page.click('[data-key="items:advanced"] summary');
  await page.waitFor('[data-key="items:advanced"] input[type="file"][accept=".obj,.glb,.gltf"]');
  const obj = path.join(folders.root, "pebble.obj");
  fs.writeFileSync(obj, "v 0 0 0\nv 0.1 0 0\nv 0 0.1 0\nf 1 2 3\n");
  await page.setFiles('[data-key="items:advanced"] input[type="file"][accept=".obj,.glb,.gltf"]', [obj]);
  await page.waitFor(() => /"model": "models\//.test(document.querySelector('[aria-label="items.json"] pre').textContent), 15000);
  const model = (await json(page)).items.at(-1).model;
  await setSelect(page, "Kind", "accessory");
  await page.waitFor(() => document.querySelector('select[aria-label="A new look of"]'));
  const worn = (await json(page)).items.at(-1);
  assert.equal(worn.model, undefined, "an accessory doesn't lie on the ground");
  assert.deepEqual(worn.texture, { tint: "#a8c4ff" }, "a new look starts in a colour of its own");
  await setSelect(page, "Kind", "consumable");
  await page.waitFor(() => document.querySelector('select[aria-label="What it does"]'));
  const back = (await json(page)).items.at(-1);
  assert.equal(back.model, model, "the model is back");
  assert.equal(back.texture, undefined, "and the accessory's colour is put aside in its turn");
  assert.equal(await page.evaluate(() => document.querySelector('[data-key="items:advanced"]').open), true, "the fold opens for an item with a model");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("card order: everyday cards first, the 3D fold closed, and what a herb does in plain words", { skip }, async () => {
  const page = await itemsPage();
  await page.click({ text: "Add an item" });
  await page.waitFor('select[aria-label="What it does"]');
  const titles = () => page.evaluate(() => [...document.querySelectorAll('[data-key="editor:item"] h3')].map(h => h.textContent));
  assert.deepEqual(await titles(), ["What it is", "Icon", "Using it", "The medicine cat's recipe", "Starting with some",
    "Advanced: a 3D model of your own (needs Blender)"]);
  assert.equal(await page.evaluate(() => document.querySelector('[data-key="items:advanced"]').open), false);
  assert.doesNotMatch(await page.text('[data-key="editor:item"]'), /\bnull\b|undefined/, "nothing left out shows as a word");
  const effects = await page.evaluate(() => [...document.querySelector('select[aria-label="What it does"]').options].map(o => o.textContent));
  assert.deepEqual(effects, ["The same as Marigold Petal: Heals 50 health", "Cures Poisoned (Yarrow Leaves)",
    "Whole team +50% Strength for the fight (Juniper Poultice)", "Heals 25 health (Horsetail Stalks)", "Heals 50 health (Marigold Petal)"]);
  assert.match(await page.text('[data-key="editor:item"] .card p.muted'), /^Used anywhere, for you$/);
  // Choosing a team's effect makes it that herb's: who it's for and when.
  await setSelect(page, "What it does", "Gameplay.Effect.Consumable.Buff.Strength.1");
  await page.waitFor(() => /for your whole team/.test(document.querySelector('[data-key="editor:item"] .card p.muted').textContent));
  const herb = (await json(page)).items.at(-1);
  assert.deepEqual([herb.target, herb.combat, herb.exploring, herb.fight_only], ["OwnerTeam", true, false, true]);
  // The recipe offers this mod's own materials after the game's.
  await page.evaluate(() => { document.querySelector('input[aria-label="Name"]').value = ""; });
  await setSelect(page, "Kind", "accessory");
  await page.waitFor(() => document.querySelector('select[aria-label="A new look of"]'));
  assert.deepEqual(await titles(), ["What it is", "Icon", "The medicine cat's recipe", "Starting with some", "Look",
    "Advanced: a 3D model of your own (needs Blender)"]);
  const looks = await page.evaluate(() => [...document.querySelector('select[aria-label="A new look of"]').options].map(o => o.textContent));
  assert.deepEqual(looks, ["Black BloodClan Collar", "Red BloodClan Collar"], "every look of a neck accessory, no head ones");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("a recipe can ask for a material the same mod adds", { skip }, async () => {
  const page = await itemsPage();
  await page.click({ text: "Add an item" });
  await page.waitFor('select[aria-label="Kind"]');
  await setSelect(page, "Kind", "material");
  await page.waitFor(() => !document.querySelector('select[aria-label="What it does"]'));
  await page.click({ text: "Add an item" });
  await page.waitFor('select[aria-label="Add a material to the recipe"]');
  const groups = await page.evaluate(() => [...document.querySelectorAll('select[aria-label="Add a material to the recipe"] optgroup')]
    .map(g => [g.label, [...g.querySelectorAll("option")].map(o => o.textContent)]));
  assert.equal(groups[0][0], "The game's materials");
  assert.deepEqual(groups[1], ["Your materials", ["New herb"]], "the material made just now, by its name");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

// An Apply's result, as the shell hands it to the pages ("installed" on wc's bus): the build's manifest.
const emitInstalled = (page, manifest) => page.evaluate(`(async () => {
  const wc = await import("/studio/lib/wc.js");
  wc.bus.emit("installed", ${JSON.stringify(manifest)});
})()`);

test("status after apply: a chip on each item, its line, and the count at the top", { skip }, async () => {
  const page = await itemsPage();   // my-mods, with Moon Herb saved by the first upload's test
  const tag = "Gameplay.Inventory.Consumable.MoonHerb";
  const base = { built: "2026-10-28T10:00:00", mods: ["my-mods"], sections: { items: { status: "ok", mods: ["my-mods"], errors: [], failed: [] } } };
  await emitInstalled(page, { ...base, notes: { items: { items: { "my-mods/MoonHerb": tag } } },
    warnings: ["items: my-mods: MoonHerb: no save yet to give it in; start the game once, then install again"] });
  await page.waitFor(() => document.querySelector(".pick .chip.good"));
  assert.equal(await page.text(".pick .chip.good"), "In the game");
  assert.match(await page.text(".banner[role=status]"), /^Last Apply: 1 of 1 item went in\.$/);
  assert.equal(await page.text('[data-key="editor:item"] .card p.note'), "In the game; no save to give it in yet.");
  // The next Apply left it out: the chip, the line and the count follow.
  await emitInstalled(page, { ...base, notes: { items: { items: {} } },
    warnings: ["items: my-mods: MoonHerb: the game already has an item called MoonHerb: give yours another name"] });
  await page.waitFor(() => document.querySelector(".pick .chip.bad"));
  assert.equal(await page.text(".pick .chip.bad"), "Left out");
  assert.match(await page.text(".banner[role=status]"),
    /0 of 1 item went in\. Moon Herb was left out: the game already has an item called MoonHerb: give yours another name\./);
  assert.match(await page.text('[data-key="editor:item"] .card .field-problem'), /^Left out of the game: the game already has an item called MoonHerb/);
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});
