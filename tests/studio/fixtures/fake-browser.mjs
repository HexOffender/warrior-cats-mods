// A stand-in for a browser that fails to start, for browser.test.mjs. launch() runs it as
// `node fake-browser.mjs <how> <pids file> <a browser's arguments>`; it finds the profile in --user-data-dir=
// and fails as <how> says:
//   ends       ends at once with 3, as a browser that can't start does;
//   hands-off  leaves a process of its own on the profile and ends with 0, as Edge's launcher does, and
//              nothing ever says where it listens (launch waits until its time is up);
//   dead-port  the same, but writes the port file first, naming a port nothing listens on (the connection
//              fails after the browser "started").
// The process left behind holds a file in the profile open and runs until it's ended; its pid goes in the
// pids file, for the test to check it's gone.
import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";

const [how, pids, ...args] = process.argv.slice(2);
const dir = args.find(a => a.startsWith("--user-data-dir=")).slice("--user-data-dir=".length);

function handOff() {
  const code = `require("fs").openSync(${JSON.stringify(path.join(dir, "lockfile"))}, "w"); setInterval(() => {}, 1000);`;
  const child = spawn(process.execPath, ["-e", code, "--", `--user-data-dir=${dir}`],
    { detached: true, stdio: "ignore", windowsHide: true });
  child.unref();
  fs.appendFileSync(pids, `${child.pid}\n`);
}

if (how === "ends") {
  process.exit(3);
} else if (how === "hands-off") {
  handOff();
  process.exit(0);
} else if (how === "dead-port") {
  handOff();
  const server = net.createServer().listen(0, "127.0.0.1", () => {
    const { port } = server.address();
    server.close(() => {
      fs.writeFileSync(path.join(dir, "DevToolsActivePort"), `${port}\n/devtools/browser/fake\n`);
      process.exit(0);
    });
  });
} else {
  console.error(`fake-browser: no such way to fail: ${how}`);
  process.exit(2);
}
