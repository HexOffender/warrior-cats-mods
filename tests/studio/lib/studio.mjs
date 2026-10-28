// What the end-to-end tests (e2e/) share: a Clan Mod Studio of their own, started on a free port over a
// folder of the test's (`python wcmods.py studio --no-browser --port 0` with WCMODS_DATA), from a copy of
// wcmods of their own, a made-up game in it, and .zips made the way a download would be.
//
//   const folders = dataFolder();          // data (the player's folder), game, saves, temp, under one root,
//                                          // and app, the copy of wcmods the studio runs from
//   makeGame(folders.game);                // the exe and folders that make it the game's (no paks)
//   const studio = await startStudio(folders, { WCMODS_RELEASES: dir });
//   makeZip(path.join(dir, "sandbox-0.4.zip"), { "sandbox/mod.json": { name: "Sandbox mode" } });
//   studio.stop(); await removeFolders(folders);
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { REPO } from "./dom.mjs";

export const EXE = "Wrc-Win64-ShippingDRM.exe";   // config.EXE_NAME: what makes a folder the game's
const PYTHON = process.env.PYTHON || "python";
export const sleep = ms => new Promise(r => setTimeout(r, ms));

// wcmods as the studio runs it (wcmods.py, wcmods/, studio/ and docs/), copied to a folder of its own. Started
// from the repository, the studio would take it for wcmods' folder and move a mods/, wcmods.json or backups/
// kept there (a supported way to keep them) into the test's folder, which is deleted.
function appCopy() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-app-"));
  const skipCache = src => !src.split(path.sep).includes("__pycache__");
  for (const d of ["wcmods", "studio", "docs"]) fs.cpSync(path.join(REPO, d), path.join(root, d), { recursive: true, filter: skipCache });
  fs.copyFileSync(path.join(REPO, "wcmods.py"), path.join(root, "wcmods.py"));
  return root;
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
  const proc = spawn(PYTHON, ["-I", "wcmods.py", "studio", "--no-browser", "--port", String(port)],
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

// A folder of the player's own, with wcmods.json naming a game folder (empty: not the game yet) and a saves
// folder, both made up, so the real game folder and the real save are never used, a temp folder, and a copy
// of wcmods to run the studio from (app). Steam is still read (its registry key and library list, read
// only): once the made-up folder holds the game, Get set up and the Mods page say whether Steam starts
// another copy, and nothing here depends on the answer.
export function dataFolder() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-"));
  const game = path.join(root, "Game"), saves = path.join(root, "Saves"), data = path.join(root, "data");
  const temp = path.join(root, "temp");
  for (const d of [game, saves, data, temp]) fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(data, "wcmods.json"), JSON.stringify({ game_dir: game, save_dir: saves }));
  return { root, game, saves, data, temp, app: appCopy() };
}

export function makeGame(game) {
  const win64 = path.join(game, "Wrc", "Binaries", "Win64");
  fs.mkdirSync(path.join(win64, "ue4ss", "Mods"), { recursive: true });
  fs.mkdirSync(path.join(game, "Wrc", "Content", "Paks"), { recursive: true });
  fs.writeFileSync(path.join(win64, EXE), "");
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
  const r = spawnSync(PYTHON, ["-I", "-c", "import json, sys, zipfile\n" +
    "spec = json.load(sys.stdin)\n" +
    "with zipfile.ZipFile(sys.argv[1], 'w') as z:\n" +
    "    for name, text in spec.items():\n" +
    "        z.writestr(name, text)\n", file], { input: JSON.stringify(spec), encoding: "utf8" });
  if (r.status !== 0) throw new Error(`couldn't make ${file}: ${r.stderr}`);
  return file;
}

// A mod folder in the player's mods: mod.json from `meta` (on, unless it says).
export function makeMod(data, id, meta = {}) {
  const folder = path.join(data, "mods", id);
  fs.mkdirSync(folder, { recursive: true });
  fs.writeFileSync(path.join(folder, "mod.json"), JSON.stringify({ name: id, enabled: true, ...meta }));
  return folder;
}

// A folder gone, once the studio has let go of it.
export async function removeFolder(folder) {
  for (let i = 0; i < 5; i++) {
    try { fs.rmSync(folder, { recursive: true, force: true }); return; } catch (e) { await sleep(300); }
  }
}

// The test's folders (dataFolder's) and its copy of wcmods, gone.
export async function removeFolders(folders) {
  await removeFolder(folders.root);
  await removeFolder(folders.app);
}
