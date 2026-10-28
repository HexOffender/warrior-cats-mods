// A Clan Mod Studio of the end-to-end tests' own (e2e/): `python wcmods.py studio --no-browser --port 0` over a
// folder of its own (WCMODS_DATA), with a made-up game folder and saves folder named in its wcmods.json, so neither
// Steam's game nor the real save is ever looked at.
//
//   const folders = dataFolder();                 // { root, game, saves, data }
//   const studio = await startStudio(folders.data);
//   makeGame(folders.game);                       // the exe and folders, no paks: found, but nothing to read
//   await writeSave(folders.saves, {...});        // WrcGame.sav holding that JSON
//   studio.stop(); removeFolder(folders.root);
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { REPO } from "./dom.mjs";

export const EXE = "Wrc-Win64-ShippingDRM.exe";   // config.EXE_NAME: what makes a folder the game's
export const sleep = ms => new Promise(r => setTimeout(r, ms));
const python = () => process.env.PYTHON || "python";

// A studio started on a free port over `data`; its URL is on the first line it prints.
export async function startStudio(data, env = {}) {
  const proc = spawn(python(), ["-I", "wcmods.py", "studio", "--no-browser", "--port", "0"],
    { cwd: REPO, env: { ...process.env, WCMODS_DATA: data, ...env }, stdio: ["ignore", "pipe", "pipe"] });
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
// folder, both made up.
export function dataFolder() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-e2e-"));
  const game = path.join(root, "Game"), saves = path.join(root, "Saves"), data = path.join(root, "data");
  for (const d of [game, saves, data]) fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(data, "wcmods.json"), JSON.stringify({ game_dir: game, save_dir: saves }));
  return { root, game, saves, data };
}

export function makeGame(game) {
  const win64 = path.join(game, "Wrc", "Binaries", "Win64");
  fs.mkdirSync(path.join(win64, "ue4ss", "Mods"), { recursive: true });
  fs.mkdirSync(path.join(game, "Wrc", "Content", "Paks"), { recursive: true });
  fs.writeFileSync(path.join(win64, EXE), "");
}

// WrcGame.sav in `saves`, holding `data` (the save's JSON), made the way wcmods.selftest makes one. Windows can hold
// a file for a moment after the studio (or a virus scanner) read it: a few tries before giving up.
export async function writeSave(saves, data) {
  const code = "import json, os, sys; sys.path.insert(0, sys.argv[1]); from wcmods.selftest import _small_save; " +
    "from wcmods.formats.save import SAV_NAME; open(os.path.join(sys.argv[2], SAV_NAME), 'wb').write(_small_save(sys.stdin.read()))";
  for (let i = 0; ; i++) {
    const r = spawnSync(python(), ["-I", "-c", code, REPO, saves], { input: JSON.stringify(data), encoding: "utf8" });
    if (r.status === 0) return path.join(saves, "WrcGame.sav");
    if (i >= 10 || !/PermissionError/.test(r.stderr)) throw new Error(`couldn't write the save: ${r.stderr}`);
    await sleep(300);
  }
}

// Take a file or folder away, trying again for a moment while Windows still holds it.
export async function remove(target) {
  for (let i = 0; ; i++) {
    try { fs.rmSync(target, { recursive: true, force: true }); return; } catch (e) {
      if (i >= 10 || !["EPERM", "EBUSY", "ENOTEMPTY"].includes(e.code)) throw e;
      await sleep(300);
    }
  }
}

// The game's colour tables as the palettes script logs them after a launch with the script loader (UE4SS.log's
// TABLE lines), for the pages that show them: `tables` is {FurColors: ["#RRGGBB", ...], ...}.
export function writeTables(game, tables) {
  const lines = Object.entries(tables).map(([t, hexes]) => `[12:00:00] [WCModsCore] TABLE ${t} ${hexes.length} ${hexes.join(" ")}`);
  fs.writeFileSync(path.join(game, "Wrc", "Binaries", "Win64", "ue4ss", "UE4SS.log"), lines.join("\n") + "\n");
}

// The tests' folder, at the end: tried for a moment, then left for the temp folder's own clean-up.
export async function removeFolder(folder) {
  try { await remove(folder); } catch (e) { /* still held: it's in the temp folder */ }
}
