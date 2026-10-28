// lib/studio.mjs's takeTurn, the lock the end-to-end files take turns with, on a lock file of the test's own:
// it's taken and given back; a stale one (a dead process's, an empty one, one that isn't a process id, one
// nobody has touched for long) is taken over; and one held too long gives up with an error naming the lock.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { takeTurn } from "../lib/studio.mjs";

let root, lock;
before(() => { root = fs.mkdtempSync(path.join(os.tmpdir(), "wc-turn-")); lock = path.join(root, "e2e.lock"); });
after(() => { fs.rmSync(root, { recursive: true, force: true }); });
const aged = (text, ms) => { fs.writeFileSync(lock, text); const t = new Date(Date.now() - ms); fs.utimesSync(lock, t, t); };

test("the lock is taken with this process's id, and given back", async () => {
  const release = await takeTurn({ lock });
  assert.equal(fs.readFileSync(lock, "utf8"), String(process.pid));
  release();
  assert.equal(fs.existsSync(lock), false);
});

test("a stale lock is taken over", async () => {
  const dead = spawnSync(process.execPath, ["-e", ""]).pid;   // a process that has ended
  for (const [text, age, what] of [[String(dead), 0, "a dead process's"], ["", 10000, "an empty one"],
    ["not a pid", 0, "one that isn't a process id"], [String(process.ppid), 11 * 60 * 1000, "one nobody touched for 11 minutes"]]) {
    aged(text, age);
    const release = await takeTurn({ lock, wait: 3000 });
    assert.equal(fs.readFileSync(lock, "utf8"), String(process.pid), what);
    release();
  }
});

test("a lock a live process holds, or one being written, is waited for, then given up on with its name", async () => {
  for (const text of [String(process.ppid), ""]) {
    aged(text, 0);
    await assert.rejects(takeTurn({ lock, wait: 500 }), e => e.message.includes(lock) && /waited 1 s for the end-to-end tests' lock/.test(e.message));
  }
  fs.rmSync(lock);
});
