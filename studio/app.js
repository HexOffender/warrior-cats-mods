import * as wc from "./lib/wc.js";

const { el, api, clear, toast, bus } = wc;
const nav = document.getElementById("nav");
const main = document.getElementById("main");
const statusBox = document.getElementById("status");
const loaded = {};   // section id -> { pane, module, handle }
let info = null;
let active = null;

// A status chip. What it means (tip) shows on hover and keyboard focus, and screen readers hear it there.
function chip(text, kind, tip) {
  return el("span", { class: `chip ${kind}`, "data-tip": tip || false, "data-said": text, tabindex: tip ? "0" : false },
    el("i", { "aria-hidden": "true" }), text, tip ? el("span", { class: "sr-only", text: `: ${tip}` }) : null);
}
// A chip that does something when pressed (Restart the studio).
function chipButton(text, kind, tip, onclick) {
  return el("button", { class: `chip ${kind}`, type: "button", "data-tip": tip || false, "data-said": text, onclick },
    el("i", { "aria-hidden": "true" }), text, tip ? el("span", { class: "sr-only", text: `: ${tip}` }) : null);
}
// The status is redrawn only when it says something new, and screen readers are told just the chips that
// are new ("2 changes to apply"), not the whole line with its explanations.
let statusSaid = null;
function setStatus(chips) {
  const said = chips.map(c => `${c.className}|${c.textContent}`).join("\n");
  if (said === statusSaid) return;
  const before = new Set([...statusBox.querySelectorAll("[data-said]")].map(c => c.dataset.said));
  const fresh = chips.map(c => c.dataset.said).filter(t => !before.has(t));
  if (statusSaid !== null && fresh.length) wc.announce(fresh.join(". "));
  statusSaid = said;
  clear(statusBox).append(...chips);
}

const installBtn = document.getElementById("installBtn");
const playBtn = document.getElementById("playBtn");
let busy = false;   // a build, install or Play is running: the buttons wait for it
let gone = false;   // the studio's server stopped answering: the page waits for it and reloads

async function refreshStatus() {
  let changes = null;
  try {
    [info, changes] = await Promise.all([api.get("/info"), api.get("/changes").catch(() => null)]);
  } catch (e) {
    if (e.code === "gone") serverGone();
    else if (e.code !== "token") setStatus([chip("Studio not answering", "bad", e.message)]);
    installBtn.disabled = playBtn.disabled = true;
    return null;
  }
  if (gone) { location.reload(); return null; }   // it's back: this page is from before
  const waiting = changes ? changes.on.length + changes.off.length + changes.changed.length + (changes.redo || []).length : 0;
  setStatus([
    chip(info.game_running ? "Game running" : "Game closed", info.game_running ? "warn" : "good",
      info.game_running ? "Close the game to apply mods" : ""),
    info.game_build && info.game_build.build && !info.game_build.verified
      ? chip("Game updated", "warn", `Build ${info.game_build.build}. Mods made for the older version are left out until they're updated; the Mods page says more.`)
      : null,
    info.ue4ss ? null : chip("No script loader", "warn", "Most mods need the script loader, the add-on that lets mods run in the game (UE4SS): Get set up, on the Mods page, installs it"),
    info.save_found ? null : chip("No save yet", "warn", "Start the game once, so there's a save"),
    info.warning ? chip("Settings were reset", "warn", info.warning) : null,
    info.code_changed
      ? chipButton("Restart the studio", "bad", "Clan Mod Studio was updated while it was open. Press this to open the new version before applying; the page comes back by itself.", restartStudio)
      : null,
    info.install_outdated
      ? chip("Apply again", "warn", "The mods in the game were made by an older Clan Mod Studio, and the game can't find them. Apply to game makes them again.")
      : changes && changes.any
        ? chip(changes.installed ? `${waiting} change${waiting === 1 ? "" : "s"} to apply` : "Not applied yet", "warn", "Apply to game puts them in")
        // /changes reads wcmods.json afresh (an install from the command line shows at once); /info may not.
        : (changes ? changes.installed : info.installed)
          ? chip("Game up to date", "good")
          : chip("Nothing installed", ""),
  ].filter(Boolean));
  // Off while the game runs, before the game is found, and while one of them is working.
  const why = !info.game_dir ? "Find the game first: Get set up, on the Mods page" : info.game_running ? "Close the game first" : "";
  syncSections();   // the pages may have changed (code mods allowed, a mod with a page turned on or off)
  installBtn.disabled = !!why || busy;
  installBtn.title = why || "Build your mods and put them in the game";
  // Play applies what's waiting first, then starts the game through Steam (remaps work inside the game).
  playBtn.disabled = !!why || busy;
  playBtn.textContent = info.game_running ? "Playing" : changes && changes.any ? "Apply and play" : "Play";
  playBtn.title = info.game_running ? "The game is running" : why || "Start the game" + (changes && changes.any ? ", after putting your changes in" : "");
  return info;
}

// ---------- the server gone, or this page from before a restart ----------
// Every API call that can't reach the server says so (wc.js): the buttons go off, a card says what to do, and
// the page asks every 3 s until the server answers, then reloads (the new server has a new token).
let goneCard = null;
function serverGone() {
  if (gone) return;
  gone = true;
  setStatus([chip("Studio closed", "bad", "Clan Mod Studio's black window was closed. Double-click Clan Mod Studio again; this page comes back by itself.")]);
  installBtn.disabled = playBtn.disabled = true;
  goneCard = el("div", { class: "error-card", role: "alert" },
    el("h2", { text: "Clan Mod Studio's black window was closed" }),
    el("p", { text: "Double-click Clan Mod Studio again. This page comes back by itself once it's open." }));
  main.prepend(goneCard);
  const again = async () => {
    if (await serverUp()) { location.reload(); return; }
    setTimeout(again, 3000);
  };
  setTimeout(again, 3000);
}
async function serverUp() {
  try { return (await fetch("/", { cache: "no-store" })).ok; } catch (e) { return false; }
}
// A 403 for the token means this page is older than the server (the studio restarted): reload once. The
// moment is kept, so a page that's still refused after reloading doesn't loop.
let reloading = false;
bus.on("token-lost", () => {
  if (reloading) return;
  reloading = true;
  let last = 0;
  try { last = Number(sessionStorage.getItem("wc-token-reload") || 0); sessionStorage.setItem("wc-token-reload", String(Date.now())); } catch (e) { /* storage blocked */ }
  if (Date.now() - last < 15000) {
    setStatus([chip("Open the studio again", "bad", "This page isn't the one the studio knows. Close it and open Clan Mod Studio again.")]);
    return;
  }
  location.reload();
});
bus.on("server-gone", serverGone);

// Restart the studio (after wcmods was updated under it): the server starts a fresh one in a new window and
// stops; this page waits for the new one, then reloads.
async function restartStudio() {
  let r;
  try { r = await api.post("/restart"); } catch (e) { toast(e.message, "bad"); return; }
  if (!r || !r.restarting) return;
  toast("Restarting Clan Mod Studio… this page comes back by itself.");
  setStatus([chip("Restarting…", "warn", "A new Clan Mod Studio window is opening")]);
  installBtn.disabled = playBtn.disabled = true;
  gone = true;   // nothing else reloads or complains while it's away
  await new Promise(res => setTimeout(res, 1500));
  for (;;) {
    if (await serverUp()) { location.reload(); return; }
    await new Promise(res => setTimeout(res, 1000));
  }
}

// The side bar: managing mods first, then the pages for making them. Made again only when the pages
// change (a mod with a page of its own turned on or off); opening a page moves aria-current, so the
// button you pressed keeps focus.
const GROUPS = { play: "Your mods", make: "Make mods" };
let navMade = "";
function renderNav() {
  const pages = info.sections.map(s => `${s.id}|${s.title}|${s.group || ""}|${s.from_mod || ""}`).join("\n");
  if (pages !== navMade) {
    navMade = pages;
    clear(nav);
    const rank = s => Object.keys(GROUPS).indexOf(s.group || "make");
    let last = null;
    for (const s of [...info.sections].sort((a, b) => rank(a) - rank(b))) {
      const g = s.group || "make";
      if (g !== last) {
        nav.append(el("span", { class: "nav-group", "aria-hidden": "true", text: GROUPS[g] || g }));
        last = g;
      }
      nav.append(el("button", { id: `nav-${s.id}`, onclick: () => open(s.id, true) },
        s.title, s.from_mod ? el("small", { text: "mod" }, el("span", { class: "sr-only", text: " page" })) : null));
    }
  }
  for (const b of nav.querySelectorAll("button")) {
    if (b.id === `nav-${active}`) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  }
}
// The pages /info lists now: new ones go in the side bar, and a page that's gone (code mods turned off, a
// mod with a page removed) is taken down, with the first page opened if it was the one showing.
function syncSections() {
  if (!active) return;
  const ids = new Set(info.sections.map(s => s.id));
  for (const [sid, entry] of Object.entries(loaded)) {
    if (ids.has(sid)) continue;
    try { entry.handle?.unmount?.(); } catch (e) { console.error(e); }
    entry.pane.remove();
    delete loaded[sid];
  }
  renderNav();
  if (!ids.has(active)) open(info.sections[0].id);
}

// asked: the player chose the page (not the studio opening on it), so screen readers are told.
async function open(id, asked = false) {
  const spec = info.sections.find(s => s.id === id) || info.sections[0];
  active = spec.id;
  document.title = `${spec.title} · Clan Mod Studio`;
  if (asked) wc.announce(`${spec.title} page`);
  try { localStorage.setItem("wc-section", active); } catch (e) { /* storage blocked */ }
  try { history.replaceState(null, "", "#" + active); } catch (e) { /* ignore */ }
  renderNav();
  for (const [sid, entry] of Object.entries(loaded)) entry.pane.hidden = sid !== active;
  if (loaded[active]) return;
  const pane = el("div", { class: "section" }, el("p", { class: "muted", text: `Loading ${spec.title}…` }));
  main.append(pane);
  loaded[active] = { pane };
  try {
    const mod = await import(spec.module);
    const section = mod.default;
    clear(pane);
    loaded[spec.id].handle = await section.mount(pane, wc);
  } catch (e) {
    // Sections load independently: one failing doesn't take the others down.
    console.error(e);
    clear(pane).append(el("div", { class: "error-card" },
      el("h2", { text: `${spec.title} couldn't load` }),
      el("p", { text: e.message }),
      el("p", { class: "note", text: spec.from_mod ? `This page comes from the mod "${spec.from_mod}".` : "The other sections still work." }),
      el("button", { class: "btn", text: "Try again", onclick: () => { pane.remove(); delete loaded[spec.id]; open(spec.id, true); } })));
  }
}

// ---------- build / install ----------
// The log of an install shows in a panel: what it did in a sentence at the top (read out as it changes),
// then the log as it comes (the page asks the server what's been logged every half second while a task
// runs). Opening it takes focus there (its heading, then Close and the log), and closing it, with Close or
// Escape, puts focus back where it was.
const drawer = document.getElementById("drawer");
const drawerLog = document.getElementById("drawerLog");
const drawerTitle = document.getElementById("drawerTitle");
const drawerSummary = document.getElementById("drawerSummary");
let drawerBack = null;
function showDrawer() {
  if (drawer.hidden) drawerBack = wc.keepPlace();
  drawer.hidden = false;
  drawerTitle.focus();
}
function hideDrawer() {
  if (drawer.hidden) return;
  const inside = drawer.contains(document.activeElement);
  drawer.hidden = true;
  if (inside && drawerBack) drawerBack();
}
document.getElementById("drawerClose").addEventListener("click", hideDrawer);
drawer.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); hideDrawer(); } });

// The build's report, line by line, for the log.
function summarize(manifest) {
  const lines = [];
  for (const rep of Object.values(manifest.sections || {})) {
    if (!rep.mods.length && !rep.errors.length) continue;
    lines.push(`[${rep.status}] ${rep.title}: ${rep.mods.map(i => nameIn(manifest, i)).join(", ") || "no mods"}`);
    for (const e of rep.errors) lines.push(`    ${e}`);
  }
  for (const w of manifest.warnings || []) lines.push(`warning: ${w}`);
  return lines;
}
const nameIn = (manifest, id) => (manifest.names || {})[id] || id;
// What the build did, in plain words: the mods that went in by name, or the first thing that kept one out.
function plainSummary(manifest) {
  const bad = [];
  for (const rep of Object.values(manifest.sections || {})) {
    if (rep.status === "ok") continue;
    for (const [mod, text] of rep.failed || rep.errors.map(e => [null, e])) bad.push([mod ? nameIn(manifest, mod) : rep.title, text]);
  }
  if (bad.length) {
    const more = bad.length > 1 ? ` (${bad.length - 1} more problem${bad.length > 2 ? "s" : ""} in the log)` : "";
    return `Couldn't put ${bad[0][0]} in: ${bad[0][1]}${more}`;
  }
  const ids = manifest.mods || [], warnings = (manifest.warnings || []).length;
  const said = ids.length ? `Put ${ids.length} mod${ids.length === 1 ? "" : "s"} in the game: ${ids.map(i => nameIn(manifest, i)).join(", ")}.`
    : "Put the mod menu in the game, with no mods on.";
  return said + (warnings ? ` ${warnings} warning${warnings === 1 ? "" : "s"}.` : "");
}
const manifestOf = r => r && r.result && (r.result.sections ? r.result : r.result.manifest && r.result.manifest.sections ? r.result.manifest : null);

// While a task runs under the server's lock, what it has logged so far shows in the drawer.
let polling = null;
function pollProgress() {
  const tick = async () => {
    let p;
    try { p = await api.get("/progress"); } catch (e) { return; }
    if (!polling) return;
    if (p.lines.length) drawerLog.textContent = p.lines.join("\n");
    else if (p.running) drawerLog.textContent = "Working…";
  };
  polling = setInterval(tick, 500);
}
function stopPolling() { clearInterval(polling); polling = null; }

let hideLater = null;
async function runTask(path, title, body = {}) {
  if (busy) return;
  busy = true;
  clearTimeout(hideLater);
  installBtn.disabled = playBtn.disabled = true;
  drawerTitle.textContent = title;
  drawerSummary.textContent = `${title}…`;
  showDrawer();
  drawerLog.textContent = "Working…";
  drawer.querySelector(".force")?.remove();
  pollProgress();
  try {
    const r = await api.post(path, body);
    stopPolling();
    const manifest = manifestOf(r);
    drawerLog.textContent = [...(manifest ? summarize(manifest) : []), "", ...r.log].join("\n").trim() || "Done.";
    const trouble = manifest ? (manifest.warnings || []).length > 0 || Object.values(manifest.sections || {}).some(s => s.status !== "ok") : false;
    drawerSummary.textContent = manifest ? plainSummary(manifest)
      : path === "/play" ? "Started the game; nothing needed applying first."
      : path === "/uninstall" ? "Took every mod out of the game. Your mods are still here." : "Done.";
    toast(path === "/play" ? "Starting the game…" : `${title}: done`);
    // After Play the log gets out of the way, unless it has something to say.
    if (path === "/play" && !trouble) hideLater = setTimeout(hideDrawer, 4000);
    bus.emit("installed", r.result);
    if (path === "/palettes/apply") bus.emit("mods-changed");   // it turned mods on and off
  } catch (e) {
    stopPolling();
    drawerSummary.textContent = e.message;
    drawerLog.textContent = e.message;
    toast(e.message, "bad");
    // Some mods didn't build (wcmods.pipeline.InstallBlocked): the rest can go in without them.
    if ((path === "/install" || path === "/play" || path === "/palettes/apply") && e.data && e.data.blocked) {
      drawerLog.textContent = e.data.blocked.map(b => `${b.title}: ${b.mod ? b.mod + ": " : ""}${b.text}`).join("\n");
      drawer.append(el("div", { class: "row force", style: { padding: "0 14px 14px" } },
        wc.confirmButton("Apply the rest anyway", "Press again: the failed mods' earlier changes are removed",
          () => runTask(path, title, { ...body, force: true }), "btn danger")));
    }
  }
  busy = false;
  await refreshStatus();
}
installBtn.addEventListener("click", () => runTask("/install", "Apply to game"));
playBtn.addEventListener("click", () => runTask("/play", "Play"));
bus.on("apply", () => runTask("/install", "Apply to game"));
bus.on("run-task", ({ path, title, body }) => runTask(path, title, body));
bus.on("mods-changed", () => refreshStatus());
bus.on("sections-changed", () => refreshStatus());

// The last Apply's log (last-apply.log in your files' folder), back in the drawer.
document.getElementById("lastApplyBtn").addEventListener("click", async () => {
  let r;
  try { r = await api.get("/last-apply"); } catch (e) { toast(e.message, "bad"); return; }
  clearTimeout(hideLater);
  drawerTitle.textContent = `${r.title} (${r.when})`;
  drawerSummary.textContent = r.summary[0] || "";
  drawerLog.textContent = [...r.summary.slice(1), ...(r.summary.length > 1 ? [""] : []), r.log].join("\n").trim() || "Nothing was logged.";
  drawer.querySelector(".force")?.remove();
  showDrawer();
});

// ---------- help ----------
// The guide (docs/guide/*.md, rendered by the server) in a panel like the log's: only the tags the renderer
// makes go in, links to other pages of the guide open in the panel, and the rest open in a new tab.
const help = document.getElementById("help");
const helpBody = document.getElementById("helpBody");
const helpTitle = document.getElementById("helpTitle");
const helpOpen = document.getElementById("helpOpen");
let helpBack = null;
const ALLOWED = new Set(["H1", "H2", "H3", "H4", "P", "UL", "OL", "LI", "STRONG", "EM", "CODE", "PRE", "A", "IMG", "HR", "BLOCKQUOTE"]);
function sanitize(html) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const walk = node => {
    for (const kid of [...node.childNodes]) {
      if (kid.nodeType === Node.TEXT_NODE) continue;
      if (kid.nodeType !== Node.ELEMENT_NODE || !ALLOWED.has(kid.tagName)) { kid.replaceWith(...kid.childNodes); continue; }
      for (const a of [...kid.attributes]) {
        const ok = (kid.tagName === "A" && a.name === "href" && /^(\/help\/|#|https?:\/\/)/.test(a.value))
          || (kid.tagName === "A" && (a.name === "target" || a.name === "rel"))
          || (kid.tagName === "IMG" && a.name === "src" && a.value.startsWith("/help/images/"))
          || (kid.tagName === "IMG" && a.name === "alt") || (/^H[1-4]$/.test(kid.tagName) && a.name === "id");
        if (!ok) kid.removeAttribute(a.name);
      }
      walk(kid);
    }
  };
  walk(doc.body);
  return [...doc.body.childNodes];
}
async function openHelp(page = "") {
  let r;
  try { r = await api.get(`/help/${encodeURIComponent(page || "index")}`); }
  catch (e) { toast(e.message, "bad"); return; }
  helpTitle.textContent = r.title;
  helpOpen.href = `/help/${encodeURIComponent(r.page)}`;
  clear(helpBody).append(...sanitize(r.html));
  if (help.hidden) helpBack = wc.keepPlace();
  help.hidden = false;
  helpBody.scrollTop = 0;
  helpTitle.focus();
}
function hideHelp() {
  if (help.hidden) return;
  const inside = help.contains(document.activeElement);
  help.hidden = true;
  if (inside && helpBack) helpBack();
}
helpBody.addEventListener("click", e => {
  const a = e.target.closest("a[href]");
  if (!a) return;
  const href = a.getAttribute("href");
  if (href.startsWith("/help/")) { e.preventDefault(); openHelp(href.slice(6).split("#")[0]); }
  else if (href.startsWith("#")) { e.preventDefault(); helpBody.querySelector(`[id="${CSS.escape(href.slice(1))}"]`)?.scrollIntoView(); }
});
document.getElementById("helpBtn").addEventListener("click", () => openHelp(""));
document.getElementById("helpClose").addEventListener("click", hideHelp);
help.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); hideHelp(); } });
bus.on("help", page => openHelp(page));

// ---------- boot ----------
wc.keepFocus();
// The skip link focuses the page without changing the address (#main isn't a section).
document.querySelector(".skip").addEventListener("click", e => { e.preventDefault(); wc.focusMain(); });
(async () => {
  if (!await refreshStatus()) {
    if (!gone) {
      main.append(el("div", { class: "error-card" }, el("h2", { text: "Can't reach the studio server" }),
        el("p", { text: "Start it with: python wcmods.py studio" })));
    }
    return;
  }
  let first = location.hash.slice(1);
  if (!info.sections.some(s => s.id === first)) {
    try { first = localStorage.getItem("wc-section"); } catch (e) { first = null; }
  }
  await open(info.sections.some(s => s.id === first) ? first : info.sections[0].id);
  window.addEventListener("hashchange", () => {
    const id = location.hash.slice(1);
    if (id !== active && info.sections.some(s => s.id === id)) open(id);
  });
  setInterval(refreshStatus, 15000);
  await checkSetup();
  // Coming back to the studio (after the game, or after dropping a mod on its launcher): look again.
  window.addEventListener("focus", () => { refreshStatus(); checkSetup(); bus.emit("focus"); });
})();

// Whatever page is open: the first safety copy of the save as soon as there's one, and a mod dropped on
// the launcher, which the Mods page offers to add.
async function checkSetup() {
  let s;
  try { s = await api.get("/setup"); } catch (e) { return; }
  if (s.save.ok && !s.backup.ok) {
    try { if ((await api.post("/setup/backup")).name) toast("Made a safety copy of your save."); } catch (e) { /* the step stays undone */ }
  }
  if (s.inbox && active !== "mods" && info.sections.some(x => x.id === "mods")) await open("mods");
}
