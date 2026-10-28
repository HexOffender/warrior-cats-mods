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
let gone = false;   // the studio's server stopped answering: the page waits for it to come back
let restarting = false;   // Restart the studio was pressed: the page waits for the new one, and nothing else asks
let failure = null;   // why the last status refresh failed: "gone", "token" (the shell's own cards say those), "error"

// One status refresh at a time: asked for while one is under way (the window coming back to the front, a save,
// the 15 s tick), it's made once more when that one ends, never piled up beside it.
let refreshing = null, refreshAgain = false;
function refreshStatus() {
  if (refreshing) { refreshAgain = true; return refreshing; }
  refreshing = refreshStatusNow().finally(() => {
    refreshing = null;
    if (refreshAgain) { refreshAgain = false; refreshStatus(); }
  });
  return refreshing;
}
async function refreshStatusNow() {
  if (restarting) return null;
  let changes = null;
  try {
    [info, changes] = await Promise.all([api.get("/info"), api.get("/changes").catch(() => null)]);
  } catch (e) {
    failure = e.code || "error";
    if (e.code !== "token" && e.code !== "gone") setStatus([chip("Studio not answering", "bad", e.message)]);
    installBtn.disabled = playBtn.disabled = true;
    return null;
  }
  if (restarting) return null;   // asked before Restart was pressed: the status says it's restarting now
  if (gone) { back(); return null; }   // it answers again: this page is from before it went
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
// A request that can't reach the server, and the same a few seconds later (wc.js says "server-gone" then, not
// at the first): the buttons go off, a card says what to do, and the page asks every 3 s until the server
// answers. Then a page with nothing unsaved reloads, to be the new studio's own; one with unsaved changes stays
// as it is, with the new studio's token (wc.reconnect), so they can still be saved.
let goneCard = null;
function serverGone() {
  if (gone || restarting) return;   // while restarting it's meant to be away: restartStudio says when it's too long
  gone = true;
  setStatus([chip("Studio closed", "bad", "Clan Mod Studio's black window was closed. Double-click Clan Mod Studio again; this page comes back by itself.")]);
  installBtn.disabled = playBtn.disabled = true;
  goneCard = el("div", { class: "error-card", role: "alert" },
    el("h2", { text: "Clan Mod Studio's black window was closed" }),
    el("p", { text: wc.anyDirty()
      ? "Double-click Clan Mod Studio again. Your unsaved changes stay on this page: save them once it's open."
      : "Double-click Clan Mod Studio again. This page comes back by itself once it's open." }));
  main.prepend(goneCard);
  const again = async () => {
    if (!gone) return;
    if (await wc.reconnect()) { back(); return; }
    setTimeout(again, 3000);
  };
  setTimeout(again, 3000);
}
function back() {
  if (!gone) return;   // the status refresh and the card's own asking can both find it back
  if (!wc.anyDirty()) { location.reload(); return; }
  gone = false;
  goneCard?.remove();
  goneCard = null;
  statusSaid = null;
  toast("Clan Mod Studio is open again. Your unsaved changes are still here: save them.");
  refreshStatus();
}
// A 403 for the token that reading the studio's page again didn't fix: reload once, unless that would lose
// unsaved changes. The moment is kept, so a page that's still refused after reloading doesn't loop.
let reloading = false;
bus.on("token-lost", () => {
  if (reloading) return;
  const stuck = () => setStatus([chip("Open the studio again", "bad", wc.anyDirty()
    ? "The studio doesn't know this page any more, so it can't save it. Copy what you changed somewhere safe, then close the page and open Clan Mod Studio again."
    : "This page isn't the one the studio knows. Close it and open Clan Mod Studio again.")]);
  if (wc.anyDirty()) { stuck(); return; }
  reloading = true;
  let last = 0;
  try { last = Number(sessionStorage.getItem("wc-token-reload") || 0); sessionStorage.setItem("wc-token-reload", String(Date.now())); } catch (e) { /* storage blocked */ }
  if (Date.now() - last < 15000) { stuck(); return; }
  location.reload();
});
bus.on("server-gone", serverGone);

// Restart the studio (after wcmods was updated under it): the server starts a fresh one in a new window and
// stops; this page waits for the new one, then reloads. Not over unsaved changes: the reload would lose them.
// A new studio that hasn't answered in RESTART_WAIT is said as one that's gone.
const RESTART_WAIT = 30000;
async function restartStudio() {
  const dirty = unsavedPages();
  if (dirty.length) {
    toast(`Save your changes first (${dirty.join(", ")}), then press Restart the studio: restarting reloads the page.`, "bad");
    return;
  }
  let r;
  try { r = await api.post("/restart"); } catch (e) { toast(e.message, "bad"); return; }
  if (!r || !r.restarting) return;
  toast("Restarting Clan Mod Studio… this page comes back by itself.");
  setStatus([chip("Restarting…", "warn", "A new Clan Mod Studio window is opening")]);
  installBtn.disabled = playBtn.disabled = true;
  restarting = true;   // nothing else reloads or complains while it's away
  const end = Date.now() + RESTART_WAIT;
  await new Promise(res => setTimeout(res, 1500));
  while (Date.now() < end) {
    if (await wc.reconnect()) { location.reload(); return; }
    await new Promise(res => setTimeout(res, 1000));
  }
  restarting = false;
  serverGone();   // it didn't come back: the card says what to do, and the page goes on waiting for it
}
// The pages with unsaved changes, by their titles in the side bar.
function unsavedPages() {
  const bars = wc.dirtyTargets();
  const titles = Object.entries(loaded).filter(([, entry]) => bars.some(t => entry.pane.contains(t.element)))
    .map(([sid]) => (info.sections.find(s => s.id === sid) || {}).title || sid);
  return bars.length && !titles.length ? ["this page"] : titles;
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
  // data-page: styles.css gives the page its glyph and, on the cat pages, its Clan's colour.
  const pane = el("div", { class: "section", "data-page": spec.id }, el("p", { class: "muted", text: `Loading ${spec.title}…` }));
  main.append(pane);
  loaded[active] = { pane };
  try {
    const [mod] = await Promise.all([import(spec.module), pageStyles(spec.id)]);
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

// A page's own stylesheet, studio/sections/<id>.css, linked once when the page first opens and ready before it
// draws. Only the pages that have one are listed: the server answers a missing file with a 404, which the
// browser would log as an error.
const PAGE_STYLES = new Set(["mods", "items", "npcs", "quests", "data", "save"]);
const styled = {};   // section id -> Promise that settles when its stylesheet has loaded
function pageStyles(id) {
  if (!PAGE_STYLES.has(id)) return Promise.resolve();
  return styled[id] ||= new Promise(done => {
    const link = el("link", { rel: "stylesheet", href: `/studio/sections/${id}.css`, onload: done, onerror: done });
    document.head.append(link);
  });
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
const manifestOf = r => r && r.result && (r.result.sections ? r.result : r.result.manifest && r.result.manifest.sections ? r.result.manifest : null);

// While a task runs under the server's lock, what it has logged so far shows in the drawer. The task has an id
// of the page's own, so while it waits for another (from another tab) the drawer says so, and never shows that
// one's log, or the last one's, as this one's.
let polling = null;
function pollProgress(task) {
  const tick = async () => {
    let p;
    try { p = await api.get("/progress"); } catch (e) { return; }
    if (!polling) return;
    if (p.id !== task) drawerLog.textContent = p.running && p.title ? `Waiting for ${p.title} to finish…` : "Working…";
    else if (p.lines.length) drawerLog.textContent = p.lines.join("\n");
    else drawerLog.textContent = "Working…";
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
  const task = Math.random().toString(36).slice(2, 10);
  pollProgress(task);
  try {
    const r = await api.post(path, { ...body, task });
    stopPolling();
    const manifest = manifestOf(r);
    drawerLog.textContent = [...(manifest ? summarize(manifest) : []), "", ...r.log].join("\n").trim() || "Done.";
    // Something to read: a warning (the build's, or one Play logged itself), a part that didn't build, or
    // remaps that need the old key remapper.
    const trouble = (manifest ? (manifest.warnings || []).length > 0 || Object.values(manifest.sections || {}).some(s => s.status !== "ok") : false)
      || r.log.some(line => line.startsWith("warning: ")) || !!(r.result && r.result.remaps && r.result.remaps.length);
    // The sentence is the server's (studio.task_summary), as last-apply.log has it.
    drawerSummary.textContent = r.summary
      || (path === "/uninstall" ? "Took every mod out of the game. Your mods are still here." : "Done.");
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
// page may end in #heading (a link between the guide's pages): the panel opens there.
async function openHelp(page = "") {
  const [name, anchor] = String(page).split("#");
  let r;
  try { r = await api.get(`/help/${encodeURIComponent(name || "index")}`); }
  catch (e) { toast(e.message, "bad"); return; }
  helpTitle.textContent = r.title;
  helpOpen.href = `/help/${encodeURIComponent(r.page)}${anchor ? "#" + encodeURIComponent(anchor) : ""}`;
  clear(helpBody).append(...sanitize(r.html));
  if (help.hidden) helpBack = wc.keepPlace();
  help.hidden = false;
  helpBody.scrollTop = 0;
  helpTitle.focus();
  if (anchor) helpBody.querySelector(`[id="${CSS.escape(anchor)}"]`)?.scrollIntoView();
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
  if (href.startsWith("/help/")) { e.preventDefault(); openHelp(href.slice(6)); }
  else if (href.startsWith("#")) { e.preventDefault(); helpBody.querySelector(`[id="${CSS.escape(href.slice(1))}"]`)?.scrollIntoView(); }
});
document.getElementById("helpBtn").addEventListener("click", () => openHelp(""));
document.getElementById("helpClose").addEventListener("click", hideHelp);
help.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); hideHelp(); } });
bus.on("help", page => openHelp(page));

// ---------- day and night ----------
// The toggle sets data-theme on <html> and remembers it; with nothing remembered the page follows the system
// (index.html's head script applies the saved choice before the stylesheet loads). aria-pressed says whether
// the page is dark now, whichever way it got there.
const root = document.documentElement, themeBtn = document.getElementById("themeBtn");
const isNight = () => { const cs = getComputedStyle(root).colorScheme; return cs ? cs === "dark" : matchMedia("(prefers-color-scheme: dark)").matches; };
function setTheme(t) {   // "dark", "light", or "" to follow the system again
  if (t) root.dataset.theme = t; else delete root.dataset.theme;
  try { t ? localStorage.setItem("wc-theme", t) : localStorage.removeItem("wc-theme"); } catch (e) { /* storage blocked */ }
  themeBtn.setAttribute("aria-pressed", String(isNight()));
}
themeBtn.addEventListener("click", () => setTheme(isNight() ? "light" : "dark"));
themeBtn.setAttribute("aria-pressed", String(isNight()));
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (!root.dataset.theme) themeBtn.setAttribute("aria-pressed", String(isNight())); });

// ---------- boot ----------
wc.keepFocus();
// The skip link focuses the page without changing the address (#main isn't a section).
document.querySelector(".skip").addEventListener("click", e => { e.preventDefault(); wc.focusMain(); });
(async () => {
  if (!await refreshStatus()) {
    if (failure === "error") {
      main.append(el("div", { class: "error-card" }, el("h2", { text: "Clan Mod Studio isn't answering" }),
        el("p", { text: "Double-click Clan Mod Studio (in the wcmods folder) to open it again, then reload this page." })));
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
  // Coming back to the studio (after the game, or after dropping a mod on its launcher): look again.
  window.addEventListener("focus", () => { refreshStatus(); checkSetup(); bus.emit("focus"); });
  await checkSetup();
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
