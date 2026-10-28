// The Controls page in a real browser, against a studio over a throwaway folder (lib/studio.mjs) with a made-up
// game and a save whose bindings put Pause on Enter, as the game's saves do: the game's keys come from the build,
// not the save; the build's sentences land on the rows; the capture dialog can bind Escape, Tab and Enter from the
// keyboard and refuses the keys wcmods takes; Save to mod writes what the rows show. Nothing here presses Apply or
// Play. Skipped, with a reason, when no Chromium is found: set WC_BROWSER to one (or WC_REQUIRE_BROWSER=1 to fail).
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { launch } from "../lib/browser.mjs";
import { NO_BROWSER, browserChoice, dataFolder, makeGame, removeFolders, startStudio, warmUp, writeSave } from "../lib/studio.mjs";

const { browserPath, skip } = browserChoice();
// The save's bindings, as tests/unit/conftest.py's `save` fixture has them, with the game's own Pause on Enter.
const SAVE = { acct: { "0": {}, Shared: { General: { CurrentCatSlot: 0 },
  InputKeyboard: { Player_Interact: "0,Player_Interact,E,1.000000.1", Player_Pause: "0,Player_Pause,Enter,1.000000.1" },
  InputGamepad: { Player_Interact: "0,Player_Interact,Gamepad_FaceButton_Bottom,1.000000.1" } } } };

let browser, studio, folders;

before(async () => {
  if (skip) return;
  if (!browserPath) throw new Error(NO_BROWSER);
  folders = dataFolder();
  writeSave(folders.saves, SAVE);
  studio = await startStudio(folders);
  browser = await launch({ browser: browserPath });
  await warmUp(browser, studio.url);
});

after(async () => {
  if (studio) studio.stop();
  if (browser) await browser.close();
  if (folders) await removeFolders(folders);
});

const file = () => {
  const p = path.join(folders.data, "mods", "my-mods", "controls.json");
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf8")) : null;
};
const cell = (row, col) => `tr[data-key="row:${row}"] td:nth-child(${col === "keyboard" ? 2 : 3})`;
// The page, with the build's word on its file in (once "Which keys are free?" has its table). Twice the usual
// wait: the other e2e file runs its own studio and browser at the same time.
async function open(page) {
  await page.goto(studio.url + "#controls", { timeout: 20000 });
  await page.waitFor(() => document.querySelector('[data-page="controls"] tr[data-key="row:Player_Interact"]'), 20000);
  await page.waitFor(() => document.querySelector('details[data-key="free"] table'), 20000);
}
const chip = (page, row, col = "keyboard") => page.evaluate(`document.querySelector(${JSON.stringify(cell(row, col) + " .chip.key")}).textContent.replace(/^.*: /, "")`);
const dialogOpen = page => page.evaluate(() => !!document.querySelector(".capture"));

test("without the script loader the page says so once, and with it the banner goes", { skip }, async () => {
  const page = await browser.page();
  await open(page);
  assert.equal(await page.evaluate(() => document.querySelector('[data-page="controls"] .banner').hidden), false);
  assert.match(await page.text('[data-page="controls"] .banner'), /^Key changes need the script loader\. Get set up, on the Mods page, installs it\./);
  makeGame(folders.game);
  await page.reload({ timeout: 20000 });
  await page.waitFor(() => document.querySelector('[data-page="controls"] .banner')?.hidden === true, 20000);
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("the page shows the game's keys, Pause on Escape whatever the save says, and opens its guide", { skip }, async () => {
  const page = await browser.page();
  await open(page);
  assert.equal(await page.text('[data-page="controls"] h1'), "Controls");
  assert.equal(await chip(page, "Player_Pause"), "Escape");
  assert.equal(await chip(page, "Player_Show_Inventory"), "I");
  assert.match(await page.text(cell("Player_Show_Inventory", "gamepad")), /No controller button for this/);
  // No raw ids on the page, and no "No save found".
  const text = await page.evaluate(() => document.querySelector('[data-page="controls"]').innerText);
  assert.doesNotMatch(text, /Player_|Gamepad_|No save found|python /);
  await page.click({ text: "How this works" });
  await page.waitFor(() => !document.getElementById("help").hidden && document.getElementById("helpTitle").textContent === "Controls");
  await page.press("Escape");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("Change, then F: the cell says what the build will do, and Save to mod writes just that", { skip }, async () => {
  const page = await browser.page();
  await open(page);
  await page.click('button[aria-label="Change the keyboard key for Interact"]');
  await page.waitFor(".capture");
  assert.equal(await page.evaluate(() => document.activeElement.getAttribute("role")), "dialog", "focus starts on the dialog");
  await page.press("f");
  await page.waitFor(() => !document.querySelector(".capture"));
  assert.equal(await chip(page, "Player_Interact"), "F");
  assert.match(await page.text(cell("Player_Interact", "keyboard")), /was E/);
  await page.waitFor(() => /F does Interact\. E still shows the map's legend\./.test(document.querySelector('tr[data-key="row:Player_Interact"]').textContent));
  await page.click({ text: "Save to mod" });
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => /Saved/.test(t.textContent)));
  assert.deepEqual(file(), { keyboard: { Player_Interact: "F" } });
  // Opened again, the saved file shows the same; then Change to I: the inventory loses its key, said on both rows.
  await page.reload({ timeout: 20000 });
  await page.waitFor(() => /F does Interact/.test(document.querySelector('tr[data-key="row:Player_Interact"]')?.textContent), 20000);
  assert.equal(await chip(page, "Player_Interact"), "F");
  await page.click('button[aria-label="Change the keyboard key for Interact"]');
  await page.press("i");
  await page.waitFor(() => /no longer opens the inventory/.test(document.querySelector('tr[data-key="row:Player_Show_Inventory"]').textContent));
  assert.match(await page.text('tr[data-key="row:Player_Interact"]'), /I does Interact and no longer opens the inventory/);
  // Undo goes back to what the file has, F (not the game's E), and focus stays on the row, on its Change.
  await page.click('button[aria-label="Undo the keyboard change to Interact, back to F"]');
  assert.equal(await chip(page, "Player_Interact"), "F");
  assert.equal(await page.evaluate(() => document.activeElement.getAttribute("aria-label")), "Change the keyboard key for Interact");
  assert.equal(await page.count('button[aria-label="Put Interact back on the game\'s key, E"]'), 1, "the game's key is a button away");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("a key that's already a second key isn't taken for another: the dialog says where it is", { skip }, async () => {
  const page = await browser.page();
  await open(page);
  await page.click('button[aria-label="Add another key for Interact"]');
  await page.press("h");
  await page.waitFor(() => !document.querySelector(".capture"));
  await page.click('button[aria-label="Add another key for Drop"]');
  await page.press("h");
  await page.waitFor(() => { const w = document.querySelector(".capture [role=alert]"); return w && !w.hidden; });
  assert.equal(await page.text(".capture [role=alert]"), "H is already a second key for Interact; remove it there first.");
  await page.press("Escape");
  assert.equal(await page.count('button[aria-label="Remove H, the second key for Drop"]'), 0);
  // Removed, focus goes to the row's Add another key, which stays.
  await page.click('button[aria-label="Remove H, the second key for Interact"]');
  assert.equal(await page.evaluate(() => document.activeElement.getAttribute("aria-label")), "Add another key for Interact");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("in the dialog Escape cancels, Tab reaches the Escape button and Enter binds Escape, and Enter itself binds", { skip }, async () => {
  const page = await browser.page();
  await open(page);
  await page.click('button[aria-label="Change the keyboard key for Pounce"]');
  await page.press("Escape");
  assert.equal(await dialogOpen(page), false);
  assert.equal(await chip(page, "Player_Pounce"), "Space");
  await page.click('button[aria-label="Change the keyboard key for Pounce"]');
  await page.press("Tab");
  assert.equal(await page.evaluate(() => document.activeElement.getAttribute("aria-label")), "Use Escape");
  await page.press("Enter");
  await page.waitFor(() => !document.querySelector(".capture"));
  assert.equal(await chip(page, "Player_Pounce"), "Escape");
  await page.waitFor(() => /Escape pounces and no longer opens the pause menu/.test(document.querySelector('tr[data-key="row:Player_Pounce"]').textContent));
  await page.click('button[aria-label="Change the keyboard key for Run"]');
  await page.press("Enter");   // the dialog itself has focus: Enter is the key
  await page.waitFor(() => !document.querySelector(".capture"));
  assert.equal(await chip(page, "Player_Run"), "Enter");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("a key wcmods takes shows its reason and isn't bound; a sideways wheel binds nothing", { skip }, async () => {
  const page = await browser.page();
  await open(page);
  await page.click('button[aria-label="Change the keyboard key for Crouch"]');
  await page.press("Insert", { code: "Insert" });
  await page.waitFor(() => { const w = document.querySelector(".capture [role=alert]"); return w && !w.hidden; });
  assert.equal(await page.text(".capture [role=alert]"), "Insert opens the mod menu (wcmods); pick another key.");
  const { x, y } = await page.middle(".capture-zone");
  await page.send("Input.dispatchMouseEvent", { type: "mouseWheel", x, y, deltaX: 120, deltaY: 0 });
  await page.press("F11", { code: "F11" });
  assert.equal(await dialogOpen(page), true, "still open: nothing was bound");
  await page.press("Escape");
  assert.equal(await chip(page, "Player_Crouch"), "Left Ctrl");
  // The keys that are taken are listed, with where they come from.
  const free = await page.text('details[data-key="free"] table');
  assert.match(free, /Insertopens the mod menuwcmods \(taken\)/);
  assert.match(free, /F11switches between a window and full screenthe game \(taken\)/);
  await page.close();
});

test("the sticks have no Change button, the moving keys say they need the launcher, and the columns go back", { skip }, async () => {
  const page = await browser.page();
  await open(page);
  await page.evaluate(() => { document.querySelector('details[data-key="moving"]').open = true; });
  assert.equal(await page.count('details[data-key="moving"] td:nth-child(3) button'), 0);
  await page.click('button[aria-label="Change the key for Move forward"]');
  await page.press("t");
  await page.waitFor(() => /needs Play with key remaps\.bat/.test(document.querySelector('details[data-key="moving"] tbody tr').textContent));
  await page.waitFor(() => /T moves you forward while you explore, when the game is started with Play with key remaps\.bat/.test(
    document.querySelector('details[data-key="moving"] tbody tr').textContent));
  // A controller preset, then each column's Back to the game's keys, pressed twice: the file is empty.
  await page.click({ text: "Nintendo layout" });
  assert.equal(await chip(page, "Player_Interact", "gamepad"), "B");
  // The build's word on the preset first, so its redraw doesn't land between a column button's two presses.
  await page.waitFor(() => /The controller's B does Interact/.test(document.querySelector(`tr[data-key="row:Player_Interact"] td:nth-child(3)`).textContent));
  // Pressed once, the button stays armed through a redraw (the build answering again in between).
  const kb = 'button[aria-label="Back to the game\'s keys for the keyboard and mouse"]';
  await page.click(kb);
  await page.evaluate(() => { window.__row = document.querySelector('tr[data-key="row:Player_Interact"]'); window.dispatchEvent(new Event("focus")); });
  await page.waitFor(() => document.querySelector('tr[data-key="row:Player_Interact"]') !== window.__row);
  assert.equal(await page.text(kb), "Press again to put every key back");
  await page.click(kb);
  await page.click('button[aria-label="Back to the game\'s buttons for the controller"]');
  await page.click('button[aria-label="Back to the game\'s buttons for the controller"]');
  await page.click({ text: "Save to mod" });
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => /Saved/.test(t.textContent)));
  assert.deepEqual(file(), {});
  // A second key in menus: Confirm also on U.
  await page.reload({ timeout: 20000 });
  await page.waitFor(() => document.querySelector('details[data-key="free"] table'), 20000);
  await page.click('button[aria-label="Add another key for Confirm in menus"]');
  await page.press("u");
  await page.waitFor(() => /In menus, U does what Enter does \(Confirm and Skip\)/.test(document.querySelector('tr[data-key="menu:Enter"]').textContent));
  await page.click({ text: "Save to mod" });
  await page.waitFor(() => !document.querySelector(".target .dirty").textContent);
  assert.deepEqual(file(), { menus: { keys: { U: "Enter" } } });
  // Backspace as a second Confirm: the Back row says Backspace no longer goes back.
  await page.click('button[aria-label="Add another key for Confirm in menus"]');
  await page.click('button[aria-label="Use Backspace"]');
  await page.waitFor(() => /Backspace no longer goes back in menus: in menus it does what Enter does now\. Give Back another key\./.test(
    document.querySelector('tr[data-key="menu:BackSpace"]').textContent));
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("Mouse look saves by itself: the switch, its key and the tilt limits, and its key is kept free", { skip }, async () => {
  const page = await browser.page();
  await open(page);
  const lookFile = () => {
    const p = path.join(folders.data, "mods", "mouse-look", "mouselook.json");
    return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf8")) : null;
  };
  await page.click("#ml-on");
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => /Mouse look on/.test(t.textContent)));
  assert.equal(JSON.parse(fs.readFileSync(path.join(folders.data, "mods", "mouse-look", "mod.json"), "utf8")).enabled, true);
  // The picker and a tilt slider, changed as a person would (a change, then input events): saved, with no toast.
  const toasts = await page.count("#toasts .toast");
  await page.evaluate(() => { const s = document.getElementById("ml-key"); s.value = "F7"; s.dispatchEvent(new Event("change")); });
  await page.evaluate(() => {
    document.querySelector('details[data-key="tilt"]').open = true;
    const lo = document.getElementById("ml-lo");
    for (const v of [10, 20, 30]) { lo.value = v; lo.dispatchEvent(new Event("input")); }
  });
  await page.waitFor(() => document.getElementById("ml-lo").value === "22");   // a degree under the highest, 23
  const end = Date.now() + 5000;
  while (!(lookFile() && lookFile().pitch_min === 22) && Date.now() < end) await new Promise(r => setTimeout(r, 100));
  assert.deepEqual(lookFile(), { toggle_key: "F7", pitch_min: 22, pitch_max: 23 });
  assert.equal(await page.count("#toasts .toast"), toasts, "only the switch says it saved");
  // Its key is kept free: listed, and refused for an action.
  await page.waitFor(() => /F7switches mouse look off and onMouse look \(taken\)/.test(document.querySelector('details[data-key="free"] table').textContent));
  await page.click('button[aria-label="Change the keyboard key for Meow"]');
  await page.press("F7", { code: "F7" });
  assert.equal(await page.text(".capture [role=alert]"), "F7 switches mouse look off and on (Mouse look); pick another key.");
  await page.press("Escape");
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("the status line says not in the game yet after a save, and nothing while there are unsaved changes", { skip }, async () => {
  const page = await browser.page();
  await open(page);   // My mods, saved by the tests above and never applied
  await page.waitFor(() => { const w = document.querySelector(".controls-where"); return w && !w.hidden; }, 20000);
  assert.equal(await page.text(".controls-where"), "Saved, not in the game yet: Apply to game.");
  await page.click('button[aria-label="Change the keyboard key for Meow"]');
  await page.press("n");
  await page.waitFor(() => document.querySelector(".controls-where").hidden);
  await page.click({ text: "Save to mod" });
  await page.waitFor(() => { const w = document.querySelector(".controls-where"); return !w.hidden && /not in the game yet/.test(w.textContent); });
  assert.deepEqual(page.consoleErrors(), []);
  await page.close();
});

test("the Play drawer stays open when remaps need the launcher, and says so", { skip }, async () => {
  const page = await browser.page();
  await open(page);
  // Play answered as the studio does when some changes need Play with key remaps.bat; a real Play would start Steam.
  await page.evaluate(() => {
    const real = window.fetch;
    window.fetch = (url, init) => String(url).endsWith("/api/play")
      ? Promise.resolve(new Response(JSON.stringify({ result: { applied: false, remaps: true }, log: ["starting the game through Steam"] }),
        { status: 200, headers: { "Content-Type": "application/json" } }))
      : real(url, init);
  });
  await page.waitFor(() => !document.getElementById("playBtn").disabled, 20000);
  await page.click("#playBtn");
  await page.waitFor(() => [...document.querySelectorAll("#toasts .toast")].some(t => /only work when you start the game with Play with key remaps\.bat/.test(t.textContent)));
  await new Promise(r => setTimeout(r, 4500));   // after a Play with nothing to say, the drawer goes in 4 s
  assert.equal(await page.evaluate(() => document.getElementById("drawer").hidden), false);
  await page.close();
});
