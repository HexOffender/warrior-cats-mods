// lib/browser.mjs's launch() when the browser fails to start, whichever way it fails: nothing is left running
// on its profile, the profile folder is gone, and nothing was written where the tests run (the repository). The
// browser is a fake (fixtures/fake-browser.mjs, run by this node), and on Windows cmd.exe too, which ends at once;
// no Chromium is needed.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { launch } from "./lib/browser.mjs";

const FAKE = fileURLToPath(new URL("./fixtures/fake-browser.mjs", import.meta.url));
const sleep = ms => new Promise(r => setTimeout(r, ms));

let root;
before(() => { root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-launch-")); });
after(() => { fs.rmSync(root, { recursive: true, force: true }); });

// launch() with the system's temp folder (where it makes the profile) set to a folder of the test's own, so
// whatever is left there is this launch's. {error, left: what's in that folder after, pids: the fake's}.
async function failedLaunch(name, options) {
  const temp = fs.mkdtempSync(path.join(root, `${name}-`));
  const pids = path.join(root, `${name}.pids`);
  fs.writeFileSync(pids, "");
  const kept = { TEMP: process.env.TEMP, TMP: process.env.TMP, TMPDIR: process.env.TMPDIR };
  Object.assign(process.env, { TEMP: temp, TMP: temp, TMPDIR: temp });
  let error = null;
  try {
    const browser = await launch(options);
    await browser.close();
  } catch (e) {
    error = e;
  } finally {
    for (const [k, v] of Object.entries(kept)) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
  return { error, left: fs.readdirSync(temp), pids: fs.readFileSync(pids, "utf8").split(/\s+/).filter(Boolean).map(Number) };
}

// Whether a process has ended (within a few seconds: ending one isn't instant on Windows).
async function ended(pid) {
  for (let i = 0; i < 50; i++) {
    try { process.kill(pid, 0); } catch (e) { return e.code === "ESRCH"; }
    await sleep(100);
  }
  return false;
}

const fake = (how, timeout = 3000) => ({ browser: process.execPath, exeArgs: [FAKE, how, path.join(root, `${how}.pids`)], timeout });

test("a browser that ends at once with an error leaves no profile", async () => {
  const r = await failedLaunch("ends", fake("ends"));
  assert.match(String(r.error), /the browser ended \(3\)/);
  assert.deepEqual(r.left, []);
});

test("a launcher that hands off and never says where it listens: launch gives up in time and ends what it left", async () => {
  const r = await failedLaunch("hands-off", fake("hands-off", 2000));
  assert.match(String(r.error), /the browser didn't start in 2 s/);
  assert.equal(r.pids.length, 1);
  assert.equal(await ended(r.pids[0]), true, "the process left on the profile was ended");
  assert.deepEqual(r.left, []);
});

test("a browser whose port nothing answers on: the connection fails, and nothing is left running or on disk", async () => {
  const r = await failedLaunch("dead-port", fake("dead-port"));
  assert.match(String(r.error), /couldn't connect to the browser at ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/fake/);
  assert.equal(r.pids.length, 1);
  assert.equal(await ended(r.pids[0]), true, "the process left on the profile was ended");
  assert.deepEqual(r.left, []);
});

// cmd.exe reads no commands (its input is empty) and ends at once with 0, as a launcher that handed off and never
// said where it listens. Not "C:/Windows/System32/cmd.exe": cmd reads the "/cmd.exe" in its own name as
// "/c md.exe ...", and runs md with the browser's arguments, making a folder for each switch where it was started
// (which is why launch() starts the browser in the temp folder).
test("cmd.exe as the browser leaves no profile, and nothing where the tests run", { skip: process.platform !== "win32" && "Windows only" }, async () => {
  const here = fs.readdirSync(process.cwd());
  const r = await failedLaunch("cmd", { browser: path.join(process.env.SystemRoot || "C:\\Windows", "System32", "cmd.exe"), timeout: 2000 });
  assert.match(String(r.error), /the browser ended \(1\)|the browser didn't start in 2 s/);
  assert.deepEqual(r.left, []);
  assert.deepEqual(fs.readdirSync(process.cwd()).filter(n => !here.includes(n)), [], "nothing new where the tests run");
});

// A browser named with forward slashes (as WC_BROWSER may be written): found and started all the same.
test("a browser path written with forward slashes is started as it is", async () => {
  const r = await failedLaunch("slashes", { ...fake("ends"), browser: process.execPath.split(path.sep).join("/") });
  assert.match(String(r.error), /the browser ended \(3\)/);
  assert.deepEqual(r.left, []);
});
