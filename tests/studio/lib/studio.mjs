// What the end-to-end tests (e2e/*.test.mjs) share: a Clan Mod Studio, `python wcmods.py studio --no-browser
// --port 0`, started over folders of the test's own (WCMODS_DATA, with a made-up game folder and saves folder named
// in its wcmods.json, and a temp folder), so the real game folder, the real save and the repository's own folder
// are never used, run from a copy of wcmods of its own, and the browser that drives it (lib/browser.mjs).
//
//   const { browserPath, skip } = browserChoice();
//   requireBrowser(browserPath);                   // in `before`: no Chromium fails here when it's required
//   const release = await takeTurn();              // in `before`: one end-to-end file at a time
//   const folders = dataFolder();                  // root, game, saves, data, temp, app (a copy of wcmods)
//   const studio = await startStudio(folders);    // studio.url, studio.stop()
//   makeGame(folders.game);                        // the folder holds "the game" now (no paks), or
//   fixtureGame(folders);                          // the made-up game with a few tables, and the tests' save
//   writeMod(folders, "my-mod", { name: "My mod" }, { "npcs.json": {...} });
//   await writeSave(folders.saves, {...});         // WrcGame.sav holding that JSON
//   startStudio(folders, { WCMODS_RELEASES: dir }) // a folder standing in for GitHub's releases, and in it
//   makeZip(path.join(dir, "sandbox-0.4.zip"), { "sandbox/mod.json": { name: "Sandbox mode" } })
//   await removeFolders(folders); release();       // in `after`
//
// Each e2e file is skipped, with a reason, when no Chromium is found: set WC_BROWSER to one, or
// WC_REQUIRE_BROWSER=1 (as CI does) to fail instead of skipping.
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import zlib from "node:zlib";
import { findBrowser } from "./browser.mjs";
import { REPO } from "./dom.mjs";

export const EXE = "Wrc-Win64-ShippingDRM.exe";   // config.EXE_NAME: what makes a folder the game's
export const sleep = ms => new Promise(r => setTimeout(r, ms));
const python = () => process.env.PYTHON || "python";

// The Chromium to drive, and the reason to skip when there's none: none found skips the tests, unless
// WC_REQUIRE_BROWSER=1 (as CI does), when they fail instead (each file's `before` calls requireBrowser).
export function browserChoice() {
  const browserPath = findBrowser();
  const required = process.env.WC_REQUIRE_BROWSER === "1";
  return { browserPath, skip: browserPath || required ? false : "no Chromium found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)" };
}
export const NO_BROWSER = "WC_REQUIRE_BROWSER=1, and no Chromium was found (set WC_BROWSER to msedge.exe, chrome.exe or chromium)";
export function requireBrowser(browserPath) {
  if (!browserPath) throw new Error(NO_BROWSER);
}

// The end-to-end files take turns: node --test runs files side by side, and two studios with a Chromium each
// make a small machine slow enough for the tests' waits to run out. Each file holds this lock from its `before`
// to its `after` (takeTurn() resolves to the release); the holder touches it every few seconds while it holds
// it. A lock that's stale is taken over: its process is gone, it's empty (written by a run that died before it
// said who it was), or nobody has touched it for STALE_MS (a run that hangs). One that stays held longer than
// `wait` ms (WC_E2E_LOCK_WAIT_MIN minutes, 20 by default) gives up with an error that names the lock.
export const LOCK = path.join(os.tmpdir(), "wc-studio-e2e.lock");
const STALE_MS = 10 * 60 * 1000, TOUCH_MS = 10 * 1000, EMPTY_MS = 5 * 1000;
export async function takeTurn({ lock = LOCK, wait = Number(process.env.WC_E2E_LOCK_WAIT_MIN || 20) * 60 * 1000 } = {}) {
  const alive = pid => { try { process.kill(pid, 0); return true; } catch (e) { return e.code === "EPERM"; } };
  const end = Date.now() + wait;
  for (;;) {
    try {
      fs.writeFileSync(lock, String(process.pid), { flag: "wx" });
      const touch = setInterval(() => { try { const now = new Date(); fs.utimesSync(lock, now, now); } catch (e) { /* gone */ } }, TOUCH_MS);
      touch.unref();
      return () => {
        clearInterval(touch);
        try { if (fs.readFileSync(lock, "utf8") === String(process.pid)) fs.rmSync(lock); } catch (e) { /* gone */ }
      };
    } catch (e) {
      if (e.code !== "EEXIST") throw e;
      let text = null, age = 0;
      try { text = fs.readFileSync(lock, "utf8").trim(); age = Date.now() - fs.statSync(lock).mtimeMs; } catch (e2) { continue; /* just removed */ }
      const pid = Number(text);
      const stale = (text === "" && age > EMPTY_MS) || (pid > 0 && !alive(pid)) || (text !== "" && !(pid > 0)) || age > STALE_MS;
      if (stale) { try { fs.rmSync(lock); } catch (e2) { /* another took it over */ } continue; }
      if (Date.now() > end) {
        throw new Error(`waited ${wait >= 60000 ? `${Math.round(wait / 60000)} minutes` : `${Math.round(wait / 1000)} s`} for the end-to-end tests' lock ${lock}, held by process ${text || "(none written)"}; ` +
          "if no other test run is going, delete that file");
      }
      await sleep(200);
    }
  }
}

// wcmods as the studio runs it (wcmods.py, wcmods/, studio/ and docs/), copied into `root`/app (a folder of its
// own when no root is given). Started from the repository, the studio would take it for wcmods' folder and move
// a mods/, wcmods.json or backups/ kept there (a supported way to keep them) into the test's folder, which is
// deleted.
export function appCopy(root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-app-"))) {
  const app = path.join(root, "app");
  const skipCache = src => !src.split(path.sep).includes("__pycache__");
  for (const d of ["wcmods", "studio", "docs"]) fs.cpSync(path.join(REPO, d), path.join(app, d), { recursive: true, filter: skipCache });
  fs.copyFileSync(path.join(REPO, "wcmods.py"), path.join(app, "wcmods.py"));
  return app;
}

// A studio started over the test's folders (on a free port, or `port`), from `root` (a copy of wcmods, the
// folders' own unless said); its URL is on the first line it prints. The game counts as closed
// (WCMODS_FAKE_RUNNING=0) unless `env` says otherwise, whether or not the real one is running on this machine;
// its temp folder (the inbox a dropped mod waits in) is the test's, not the one a studio of the player's would
// share.
export async function startStudio(folders, env = {}, { root = folders.app, port = 0 } = {}) {
  // The game's crash reports are looked for in the test's own folder too (none, unless a test leaves one).
  const own = { ...process.env, WCMODS_DATA: folders.data, WCMODS_FAKE_RUNNING: "0", TEMP: folders.temp, TMP: folders.temp,
    TMPDIR: folders.temp, WCMODS_CRASHES: path.join(folders.root, "Crashes"), ...env };
  // A build number a developer set to try an update, and a folder standing in for GitHub: only a test's own.
  for (const k of ["WCMODS_GAME_BUILD", "WCMODS_RELEASES"]) if (!(k in env)) delete own[k];
  const proc = spawn(python(), ["-I", "wcmods.py", "studio", "--no-browser", "--port", String(port)],
    { cwd: root, env: own, stdio: ["ignore", "pipe", "pipe"] });
  let out = "", err = "";
  proc.stdout.on("data", d => { out += d; });
  proc.stderr.on("data", d => { err += d; });
  // On Windows `python` may be a launcher with the real interpreter under it: the whole tree goes.
  const stop = () => {
    if (proc.exitCode !== null) return;
    if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(proc.pid), "/T", "/F"], { stdio: "ignore" });
    else proc.kill();
  };
  const end = Date.now() + 30000;
  for (;;) {
    const m = /running at (http:\/\/127\.0\.0\.1:\d+\/)/.exec(out);
    if (m) return { url: m[1], proc, stop, output: () => out + err };
    if (proc.exitCode !== null) throw new Error(`the studio ended (${proc.exitCode}): ${out}${err}`);
    if (Date.now() > end) { stop(); throw new Error(`the studio didn't say where it runs in 30 s: ${out}${err}`); }
    await sleep(50);
  }
}

// A first load, with time to spare: a cold browser and studio have taken 15 s on CI, and every test's own
// waits are 10 s.
export async function warmUp(browser, url) {
  const page = await browser.page();
  await page.goto(url, { timeout: 60000 });
  await page.waitFor("#nav button", 60000);
  await page.close();
}

// A folder of the player's own, with wcmods.json naming a game folder (empty: not the game yet) and a saves
// folder, both made up, so the real game folder and the real save are never used, a temp folder, and a copy
// of wcmods to run the studio from. `settings` go in wcmods.json too. Steam is still read (its registry key
// and library list, read only): once the made-up folder holds the game, Get set up and the Mods page say
// whether Steam starts another copy, and nothing here depends on the answer.
// `app` is the copy of wcmods a studio over these folders runs from, inside `root`: removing root takes it too.
export function dataFolder(settings = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-"));
  const game = path.join(root, "Game"), saves = path.join(root, "Saves"), data = path.join(root, "data");
  const temp = path.join(root, "temp");
  for (const d of [game, saves, data, temp]) fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(data, "wcmods.json"), JSON.stringify({ game_dir: game, save_dir: saves, ...settings }));
  return { root, game, saves, data, temp, app: appCopy(root) };
}

// The folder holds the game now: its exe, UE4SS's mods folder and the paks folder (no paks).
export function makeGame(game) {
  const win64 = path.join(game, "Wrc", "Binaries", "Win64");
  fs.mkdirSync(path.join(win64, "ue4ss", "Mods"), { recursive: true });
  fs.mkdirSync(path.join(game, "Wrc", "Content", "Paks"), { recursive: true });
  fs.writeFileSync(path.join(win64, EXE), "");
}

// WrcGame.sav in `saves`, holding `data` (the save's JSON), as the game lays it out (through wcmods' own writer,
// the one tests/unit/unit_helpers.py's write_save uses); its path. Windows can hold a file for a moment after the
// studio (or a virus scanner) read it: a few tries before giving up. Written by the time it returns, so a test
// may await it or not.
const pause = ms => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
export function writeSave(saves, data) {
  const code = "import json, os, sys; sys.path.insert(0, sys.argv[1]); from wcmods.selftest import _small_save; " +
    "from wcmods.formats.save import SAV_NAME; open(os.path.join(sys.argv[2], SAV_NAME), 'wb').write(_small_save(sys.stdin.read()))";
  for (let i = 0; ; i++) {
    const r = spawnSync(python(), ["-I", "-c", code, REPO, saves], { input: JSON.stringify(data), encoding: "utf8" });
    if (r.status === 0) return path.join(saves, "WrcGame.sav");
    if (i >= 10 || !/PermissionError/.test(r.stderr)) throw new Error(`couldn't write the save: ${r.stderr}`);
    pause(300);
  }
}

// The game's colour tables as the palettes script logs them after a launch with the script loader (UE4SS.log's
// TABLE lines), for the pages that show them: `tables` is {FurColors: ["#RRGGBB", ...], ...}.
export function writeTables(game, tables) {
  const lines = Object.entries(tables).map(([t, hexes]) => `[12:00:00] [WCModsCore] TABLE ${t} ${hexes.length} ${hexes.join(" ")}`);
  fs.writeFileSync(path.join(game, "Wrc", "Binaries", "Win64", "ue4ss", "UE4SS.log"), lines.join("\n") + "\n");
}

// A mod in the player's mods folder: mod.json (on, unless `meta` says) and files ({name: text or JSON-able}).
export function writeMod(folders, id, meta = {}, files = {}) {
  const dir = path.join(folders.data, "mods", id);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "mod.json"), JSON.stringify({ name: id, enabled: true, ...meta }));
  for (const [name, value] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(dir, name)), { recursive: true });
    fs.writeFileSync(path.join(dir, name), typeof value === "string" ? value : JSON.stringify(value, null, 2));
  }
  return dir;
}
export const readJson = file => JSON.parse(fs.readFileSync(file, "utf8"));

// Take a file or folder away, trying again for a moment while Windows (a studio that used it, a virus scanner)
// still holds it; anything else, or still held after that, is thrown.
export async function remove(target) {
  for (let i = 0; ; i++) {
    try { fs.rmSync(target, { recursive: true, force: true }); return; } catch (e) {
      if (i >= 10 || !["EPERM", "EBUSY", "ENOTEMPTY"].includes(e.code)) throw e;
      await sleep(300);
    }
  }
}
// The tests' folder, at the end: tried for a moment, then left for the temp folder's own clean-up.
export async function removeFolder(folder) {
  try { await remove(folder); } catch (e) { /* still held: it's in the temp folder */ }
}
// Everything dataFolder made: the player's folder stand-in, with the copy of wcmods its studios ran from.
export async function removeFolders(folders) {
  if (!folders) return;
  await removeFolder(folders.root);
  if (folders.app && fs.existsSync(folders.app)) await removeFolder(folders.app);   // a copy made outside root
}

// The made-up game with a few of the game's tables (tests/studio/fixtures/game.py) and, with saves, the tests'
// save (your cat in slot 1, level 5, 62 in the fresh-kill pile, two herbs and four moss).
export function fixtureGame({ game, saves }) {
  const args = ["-I", path.join(REPO, "tests", "studio", "fixtures", "game.py"), game, ...(saves ? [saves] : [])];
  const r = spawnSync(python(), args, { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`the made-up game wasn't made: ${r.stdout}${r.stderr}`);
}

// The save the studio wrote, as JSON (through wcmods' own codec).
export function readSave(saves) {
  const code = "import sys, json; sys.path.insert(0, sys.argv[1]); from wcmods.formats.save import SaveGame; " +
    "print(SaveGame.load(sys.argv[2]).json_text)";
  const r = spawnSync(python(), ["-I", "-c", code, REPO, path.join(saves, "WrcGame.sav")], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(r.stderr);
  return JSON.parse(r.stdout);
}

// A small PNG of one colour, w x h, to choose as a picture.
export function pngFile(file, w = 32, h = 32, rgba = [200, 60, 160, 255]) {
  const chunk = (type, data) => {
    const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const out = Buffer.alloc(12 + data.length);
    out.writeUInt32BE(data.length, 0);
    body.copy(out, 4);
    out.writeUInt32BE(zlib.crc32(body), 8 + data.length);
    return out;
  };
  const head = Buffer.alloc(13);
  head.writeUInt32BE(w, 0); head.writeUInt32BE(h, 4); head[8] = 8; head[9] = 6;
  const row = Buffer.concat([Buffer.from([0]), Buffer.from(Array.from({ length: w }, () => rgba).flat())]);
  const raw = Buffer.concat(Array.from({ length: h }, () => row));
  fs.writeFileSync(file, Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", head),
    chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]));
  return file;
}

// The script loader's two files in the made-up game, as Install it would leave them (ue4ss.loader_installed).
export function makeLoader(game) {
  const win64 = path.join(game, "Wrc", "Binaries", "Win64");
  fs.mkdirSync(path.join(win64, "ue4ss"), { recursive: true });
  fs.writeFileSync(path.join(win64, "dwmapi.dll"), "MZ");
  fs.writeFileSync(path.join(win64, "ue4ss", "UE4SS.dll"), "MZ");
}

// A .zip at `file` holding `files` ({path inside: text, or a value written as JSON}), written by Python's
// zipfile as any download would be.
export function makeZip(file, files) {
  const spec = Object.fromEntries(Object.entries(files).map(([k, v]) => [k, typeof v === "string" ? v : JSON.stringify(v)]));
  const r = spawnSync(python(), ["-I", "-c", "import json, sys, zipfile\n" +
    "spec = json.load(sys.stdin)\n" +
    "with zipfile.ZipFile(sys.argv[1], 'w') as z:\n" +
    "    for name, text in spec.items():\n" +
    "        z.writestr(name, text)\n", file], { input: JSON.stringify(spec), encoding: "utf8" });
  if (r.status !== 0) throw new Error(`couldn't make ${file}: ${r.stderr}`);
  return file;
}

// A mod folder in the player's folder `data`: mod.json from `meta` (on, unless it says); writeMod's.
export const makeMod = (data, id, meta = {}) => writeMod({ data }, id, meta);
