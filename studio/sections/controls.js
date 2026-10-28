// Controls: which key, mouse button or controller button does what in the game. Writes controls.json in a mod.
// What each row shows and writes is studio/lib/controls.js (the model); the game's keys come from the build
// (GET /game/keys), and what Apply will do with the file, in words, from the build too (POST /controls/check),
// so the page and Apply can't disagree. Mouse look is its own card, saved straight into the Mouse Look mod.
import * as M from "../lib/controls.js";

const LAUNCHER = "Play with key remaps.bat";
const MARKS = {
  launcher: { cls: "warn", text: `needs ${LAUNCHER}` },
  cannot: { cls: "bad", text: "won't reach the game" },
  overridden: { cls: "warn", text: "another mod wins" },
  untried: { cls: "", text: "not tried in the game yet" },
};

export default {
  title: "Controls",
  async mount(root, wc) {
    const { el, api, clear, toast, input } = wc;
    let style = "xbox";
    try { style = localStorage.getItem("wc-pad-style") || "xbox"; } catch (e) { /* storage blocked */ }
    const L = k => input.keyLabel(k, style);

    let game;
    try { game = await api.get("/game/keys"); }
    catch (e) {
      root.append(el("div", { class: "error-card" }, el("h2", { text: "Controls couldn't load" }), el("p", { text: e.message })));
      return {};
    }
    const names = game.names;
    const nameOf = action => (names[action] || [null])[0] || `the entry "${action}"`;
    let state = M.normalize(null, game);
    let loaded = M.clone(state);   // the file as it was loaded or last saved: what Undo puts a row back to
    let check = null;          // the last /controls/check answer: lines per row, keys in use, other mods
    let checkFailed = "";
    let ue4ss = !!game.ue4ss;

    const target = wc.modTarget({
      file: "controls.json",
      onLoad: obj => { state = M.normalize(obj, game); loaded = M.clone(state); render(); recheck(0); refreshWhere(); },
      getValue: () => M.toJson(state),
      // Saved: the file is what was saved, so Undo goes back to that from now on.
      onSaved: saved => { loaded = M.normalize(saved, game); render(); },
    });
    const lower = () => (check && check.lower) || [];
    // Every change: unsaved until Save to mod, drawn now, and checked against the build a moment later.
    const edited = () => { target.markDirty(); render(); recheck(); refreshWhere(); };

    // ---------- in the game yet? ----------
    // One line under the Editing mod bar, for a mod that's on and has nothing unsaved (the bar says the rest):
    // whether what's saved went in with the last Apply (GET /changes, what the Apply button counts).
    const whereLine = el("p", { class: "controls-where", role: "status", hidden: true });
    let whereAsked = 0;
    async function refreshWhere() {
      const n = ++whereAsked, id = target.current;
      const mod = (target.mods || []).find(m => m.id === id);
      if (target.dirty || !mod || !mod.enabled) { whereLine.hidden = true; return; }
      let changes;
      try { changes = await api.get("/changes"); } catch (e) { whereLine.hidden = true; return; }
      if (n !== whereAsked || target.dirty) return;
      // Left out by Apply (changes.left_out, {id: why}, and held_back, their ids: made for an older version of the
      // game, needing a newer Clan Mod Studio, or needing one of those): not in the game, whatever Apply does.
      // Waiting: the mod is new or changed since the last Apply, or that Apply has to be made again
      // (changes.redo: the game updated, the script loader came in), which the Apply button counts too.
      const why = (changes.left_out || {})[id];
      const held = !!why || (changes.held_back || []).includes(id);
      const waiting = held || changes.on.includes(id) || changes.changed.includes(id) || (changes.redo || []).length > 0;
      whereLine.textContent = !held ? (waiting ? "Saved, not in the game yet: Apply to game." : "In the game since your last Apply.")
        : !why || /^made for an older version/.test(why)
          ? "Not in the game: this mod was made for an older version of the game. The Mods page says how to use it anyway."
          : `Not in the game: Apply leaves this mod out, as it ${why}. The Mods page says more.`;
      whereLine.classList.toggle("waiting", waiting);
      whereLine.hidden = false;
    }

    // ---------- the build's word on the file ----------
    let timer = null, asked = 0;
    function recheck(delay = 250) {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const n = ++asked;
        try {
          const r = await api.post("/controls/check", { mod: target.current || "my-mods", controls: M.toJson(state) });
          if (n !== asked) return;   // a newer change was checked after this one
          check = r; checkFailed = ""; ue4ss = !!r.ue4ss;
        } catch (e) {
          if (n !== asked) return;
          checkFailed = e.message;
        }
        render();
      }, delay);
    }

    // ---------- the page's parts ----------
    const banner = el("div", { class: "banner", role: "note" });
    const playCard = el("div", { class: "card", "data-key": "play" });
    const also = el("div", { class: "card controls-also", "data-key": "also" });
    const moveFold = el("details", { class: "card fold", "data-key": "moving" });
    const menuCard = el("div", { class: "card", "data-key": "menus" });
    const freeFold = el("details", { class: "card fold", "data-key": "free" });
    const mouse = el("div", { class: "card", "data-key": "mouse" });
    const makerFold = el("details", { class: "card fold", "data-key": "makers" });
    const out = wc.codePanel("controls.json");
    const styleSel = el("select", { id: "pad-style", "aria-label": "Show controller buttons as" },
      el("option", { value: "xbox", text: "Xbox" }), el("option", { value: "playstation", text: "PlayStation" }),
      el("option", { value: "switch", text: "Switch" }));
    styleSel.value = style;
    styleSel.addEventListener("change", () => {
      style = styleSel.value;
      try { localStorage.setItem("wc-pad-style", style); } catch (e) { /* storage blocked */ }
      render();
    });
    root.append(
      wc.pageHead({ eyebrow: "Keys and buttons", title: "Controls",
        lede: "Change which key does what. Save to a mod, Apply to game, then play as usual.", help: "help:controls" }),
      banner, target.element, whereLine, playCard, also, moveFold, menuCard, freeFold, mouse, makerFold);

    // ---------- small parts ----------
    const keyChip = (k, what) => el("span", { class: "chip key", title: what ? `${what}: ${L(k)}` : L(k) },
      what ? el("span", { class: "sr-only", text: `${what}: ` }) : null, L(k));
    const mark = (kind, extra = "") => el("span", { class: `chip mark ${MARKS[kind].cls}` }, el("i", { "aria-hidden": "true" }), MARKS[kind].text + extra);
    // What the build says about one entry: the line, then its warnings; and the marker for its status.
    function said(section, name, dev = section) {
      const row = M.checkRow(check, section, name);
      if (!row) return { marks: [], lines: [] };
      const marks = [];
      if (MARKS[row.status] && row.status !== "untried") marks.push(mark(row.status));
      if (row.status === "game" && (dev === "gamepad" || M.UNTRIED.includes(row.key))) marks.push(mark("untried"));
      const lines = [];
      if (row.line) lines.push(el("p", { class: "said", text: row.line }));
      for (const n of row.notes) lines.push(el("p", { class: "said warn", text: n.endsWith(".") ? n : n + "." }));
      return { marks, lines, warn: row.notes.length > 0 || row.status === "cannot" };
    }

    // After a button that goes away with the redraw (Undo, Remove), focus goes to the row's button that stays
    // (its Change, or Add another key), found by its data-focus.
    const focusOn = key => root.querySelector(`[data-focus="${CSS.escape(key)}"]`)?.focus({ preventScroll: true });

    // ---------- capture: press the key you want ----------
    // The studio's key dialog (wc.captureKey), with this page's extras: the keys the dialog uses itself as buttons,
    // a box where a click or the wheel picks a mouse button (not for a controller, nor in menus, where a mouse
    // button is refused), and the alert line saying why a key can't be used.
    // opts: { title, dev ("keyboard" or "gamepad"), where ("play" or "menus"), taken(key): a sentence when the
    // key can't be used here (it already stands for another key), or null }. onPick(key) gets the key.
    async function capture(opts, onPick) {
      const pad = opts.dev === "gamepad", where = opts.where || "play";
      const k = await wc.captureKey({
        title: opts.title, pad, where, style,
        message: pad ? "Press a button on your controller, or pick one below. Escape cancels."
          : "Press the key you want. Escape cancels; to use Escape, Tab, Enter, Space or Backspace themselves, press its button below.",
        chips: pad ? [] : ["Escape", "Tab", "Enter", "SpaceBar", "BackSpace", ...(where === "menus" ? [] : ["MiddleMouseButton", ...M.UNTRIED])],
        zone: !pad && where !== "menus",
        why: key => {
          const taken = opts.taken ? opts.taken(key) : null;
          return taken ? { refuse: taken } : M.whyNot(key, check && check.in_use, where, L);
        },
      });
      if (k) onPick(k);
    }

    // ---------- keys while you play ----------
    function playCell(dev, action) {
      const name = nameOf(action);
      const gk = M.gameKey(game, dev, action);
      const devName = dev === "gamepad" ? "controller" : "keyboard";
      if (!gk) return el("td", { class: "cell" }, el("span", { class: "muted", text: "No controller button for this in the game" }));
      const key = M.effective(state, game, dev, action);
      const isChanged = M.changed(state, game, dev, action);
      const s = action in state[dev] ? said(dev, action) : { marks: [], lines: [] };
      // Still on the game's key, but another change took that key: the build's sentence says so here.
      const lost = check && check.lost && check.lost[dev] && check.lost[dev][action];
      if (lost) { s.lines.push(el("p", { class: "said warn", text: lost })); s.warn = true; }
      const changeKey = `change:${dev}:${action}`;
      const was = loaded[dev][action] ?? gk;   // what Undo puts back: the file's key, or the game's
      const top = el("div", { class: "row" }, keyChip(key, `${name}, ${devName}`),
        isChanged ? el("span", { class: "chip warn was-key", title: `The game's key: ${L(gk)}` }, el("i", { "aria-hidden": "true" }), `was ${L(gk)}`) : null,
        ...s.marks,
        el("button", { class: "btn small", type: "button", text: "Change", "aria-label": `Change the ${devName} key for ${name}`, "data-focus": changeKey,
          onclick: () => capture({ title: `${name}: ${dev === "gamepad" ? "controller button" : "key or mouse button"}`, dev },
            k => { if (M.set(state, game, dev, action, k, lower())) edited(); }) }),
        // Changed on the page: Undo, back to what the file has. Not changed here but not the game's key either
        // (the file has it): Back to the game's key.
        M.differs(state, loaded, dev, action) ? el("button", { class: "btn ghost small", type: "button", text: "Undo",
          "aria-label": `Undo the ${devName} change to ${name}, back to ${L(was)}`,
          onclick: () => { M.revert(state, loaded, dev, action); edited(); focusOn(changeKey); } })
          : isChanged ? el("button", { class: "btn ghost small", type: "button", text: `Back to ${L(gk)}`,
            "aria-label": `Put ${name} back on the game's ${dev === "gamepad" ? "button" : "key"}, ${L(gk)}`,
            onclick: () => { M.undo(state, game, dev, action, lower()); edited(); focusOn(changeKey); } }) : null);
      const td = el("td", { class: `cell${s.warn ? " warned" : isChanged ? " edited" : ""}` }, top, ...s.lines);
      if (dev === "keyboard") td.append(seconds("keys", gk, name, "while you explore"));
      return td;
    }
    // Second keys for a row: each "also on" with its line and a Remove, and Add another key. A key that already
    // stands for another is refused in the capture dialog, with where it is.
    function seconds(section, gk, name, when) {
      const box = el("div", { class: "seconds" });
      const addKey = `add:${section}:${name}`;
      for (const p of M.secondKeys(state, section, gk)) {
        const s = said(section, p, "keyboard");
        box.append(el("div", { class: "row" }, el("span", { class: "muted", text: "also on" }), keyChip(p, `${name}, also`), ...s.marks,
          el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove ${L(p)}, the second key for ${name}`,
            onclick: () => { M.remove(state, section, p); edited(); focusOn(addKey); } })), ...s.lines);
      }
      box.append(el("button", { class: "btn ghost small", type: "button", text: "Add another key", "aria-label": `Add another key for ${name}`,
        "data-focus": addKey,
        onclick: () => capture({ title: `${name}: another key (${when})`, dev: "keyboard", where: section === "menus" ? "menus" : "play",
          taken: k => M.pairTaken(state, game, section, k, gk, L) },
        k => { if (M.addSecond(state, section, gk, k)) edited(); }) }));
      return box;
    }
    // The card is made once: its column buttons ("Back to the game's keys", pressed twice) stay the same
    // elements, so a redraw between the two presses (the build's answer coming in) doesn't undo the first.
    const resetBtn = dev => wc.confirmButton(`Back to the game's keys`, `Press again to put every ${dev === "gamepad" ? "button" : "key"} back`,
      () => { M.resetDevice(state, game, dev, lower()); edited(); toast(dev === "gamepad" ? "The controller's buttons are the game's again" : "The keys are the game's again"); },
      "btn ghost small");
    const kbReset = resetBtn("keyboard"), padReset = resetBtn("gamepad");
    kbReset.setAttribute("aria-label", "Back to the game's keys for the keyboard and mouse");
    padReset.setAttribute("aria-label", "Back to the game's buttons for the controller");
    const playRows = el("tbody");
    playCard.append(
      el("div", { class: "row spread" }, el("h2", { text: "Keys while you play" }),
        el("label", { class: "row lbl", for: "pad-style" }, "Show controller buttons as", styleSel)),
      el("div", { class: "table-wrap", style: { maxHeight: "none" } },
        el("table", { class: "grid-table controls-table" },
          el("thead", {}, el("tr", {}, el("th", { scope: "col", text: "Action" }),
            el("th", { scope: "col" }, el("div", { class: "row spread" }, "Keyboard and mouse", kbReset)),
            el("th", { scope: "col" }, el("div", { class: "row spread" }, "Controller", padReset)))),
          playRows)),
      el("div", { class: "row" }, el("span", { class: "lbl", text: "Controller presets" }),
        ...Object.values(M.SWAPS).map(sw => el("button", { class: "chip", type: "button", title: sw.desc, text: sw.name,
          onclick: () => { if (M.swap(state, game, sw.map, lower())) edited(); } })),
        mark("untried")),
      el("p", { class: "note", text: "A second key does what the game's key does while you explore, and nothing in menus. " +
        "Controller buttons, Mouse 4, Mouse 5 and the wheel haven't been tried in the game yet." }));
    function renderPlay() {
      clear(playRows).append(...M.PLAY_ROWS.map(a => el("tr", { "data-key": `row:${a}` },
        el("th", { scope: "row" }, el("strong", { text: nameOf(a) })), playCell("keyboard", a), playCell("gamepad", a))));
    }

    // ---------- what the build says that no row shows ----------
    function renderAlso() {
      const lines = [...((check && check.others) || []), ...((check && check.lines) || [])];
      // What the file had that the build can't read: the page left it out, so Save to mod writes it without.
      const dropped = M.droppedSaid(state, nameOf);
      clear(also);
      also.hidden = !lines.length && !checkFailed && !dropped.length;
      if (dropped.length) {
        also.append(el("h3", { text: "Left out when you save" }),
          el("p", { class: "said warn", text: "This file has entries the game can't use. Save to mod writes it without them:" }),
          el("ul", { class: "notes" }, ...dropped.map(t => el("li", { text: t }))));
      }
      if (checkFailed) also.append(el("p", { class: "said warn", text: `What Apply would do couldn't be worked out: ${checkFailed}` }));
      if (lines.length) also.append(el("h3", { text: "Also in this build" }), el("ul", { class: "notes" }, ...lines.map(t => el("li", { text: t }))));
    }

    // ---------- moving and the camera ----------
    function moveKey(k, i) {
      const sub = k.raw ? `key:${k.raw}` : k.action;
      const name = nameOf(sub);
      const gk = k.raw || M.gameKey(game, "keyboard", k.action);
      const now = k.raw ? M.rawKey(state, k.raw) : M.effective(state, game, "keyboard", k.action);
      const s = k.raw ? (M.rowPair(state, k.raw) ? said("keys", M.rowPair(state, k.raw)) : { marks: [], lines: [] })
        : (k.action in state.keyboard ? said("keyboard", k.action) : { marks: [], lines: [] });
      const pickIt = key => { if (k.raw ? M.setRaw(state, k.raw, key) : M.set(state, game, "keyboard", k.action, key, lower())) edited(); };
      const changeKey = `change:move:${sub}`;
      // Undo: back to what the file has for it (its key there, or the game's).
      const undoable = k.raw ? M.differsRaw(state, loaded, k.raw) : M.differs(state, loaded, "keyboard", k.action);
      const was = k.raw ? M.rawKey(loaded, k.raw) : M.effective(loaded, game, "keyboard", k.action);
      const undo = () => {
        if (k.raw ? M.revertRaw(state, loaded, k.raw) : M.revert(state, loaded, "keyboard", k.action)) { edited(); focusOn(changeKey); }
        else toast(M.pairTaken(state, game, "keys", was, k.raw, L) || `${L(was)} can't be put back here.`, "bad");
      };
      return el("div", { class: "move-key" },
        el("div", { class: "row" }, el("span", { class: "lbl", text: name }), keyChip(now, name),
          now !== gk ? el("span", { class: "chip warn was-key" }, el("i", { "aria-hidden": "true" }), `was ${L(gk)}`) : null,
          now !== gk && !s.marks.length ? mark("launcher") : null, ...s.marks,
          el("button", { class: "btn small", type: "button", text: "Change", "aria-label": `Change the key for ${name}`, "data-focus": changeKey,
            onclick: () => capture({ title: `${name}: key`, dev: "keyboard",
              taken: key => (k.raw ? M.pairTaken(state, game, "keys", key, k.raw, L) : null) }, pickIt) }),
          undoable ? el("button", { class: "btn ghost small", type: "button", text: "Undo", "aria-label": `Undo the change to ${name}, back to ${L(was)}`,
            onclick: undo })
            : now !== gk ? el("button", { class: "btn ghost small", type: "button", text: `Back to ${L(gk)}`,
              "aria-label": `Put ${name} back on the game's key, ${L(gk)}`, onclick: () => { pickIt(gk); focusOn(changeKey); } }) : null),
        ...s.lines);
    }
    function stickCell(action) {
      const inFile = state.gamepad[action];
      const s = inFile ? said("gamepad", action) : null;
      if (!inFile || (s && M.checkRow(check, "gamepad", action)?.status === "same")) {
        return el("span", { class: "muted", text: action.startsWith("Player_Movement") ? "The left stick" : "The right stick" });
      }
      return el("div", {}, el("div", { class: "row" }, keyChip(inFile, "In this file"), mark("cannot"),
        el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove the stick change for ${nameOf(action)}`,
          onclick: () => { M.remove(state, "gamepad", action); edited(); focusOn(`change:move:${action}`); } })), ...(s ? s.lines : []));
    }
    function renderMoving() {
      const open = moveFold.open;
      clear(moveFold).append(
        el("summary", {}, el("h2", { text: "Moving and the camera" }), el("span", { class: "muted", text: "Only with Play with key remaps.bat, or Steam for the sticks" })),
        el("p", { class: "note", text: "The game reads these keys itself, so Apply can't change them. For the keyboard, start the game " +
          `with ${LAUNCHER} after Apply. For the sticks, use Steam's controller settings (right-click the game in Steam, then ` +
          "Properties, Controller); stick speed and inverting are in the game's own Settings, Player Configuration." }),
        el("div", { class: "table-wrap", style: { maxHeight: "none" } }, el("table", { class: "grid-table controls-table" },
          el("thead", {}, el("tr", {}, el("th", { scope: "col", text: "Moving" }), el("th", { scope: "col", text: "Keyboard" }),
            el("th", { scope: "col", text: "Controller" }))),
          el("tbody", {}, ...M.MOVE_ROWS.map(r => el("tr", { "data-key": `move:${r.name}` }, el("th", { scope: "row" }, el("strong", { text: r.name })),
            el("td", { class: "cell" }, ...r.keys.map(moveKey)), el("td", { class: "cell" }, stickCell(r.stick))))))));
      moveFold.open = open;
    }

    // ---------- in menus ----------
    function renderMenus() {
      // The game's key loses its own job when it's added to another row (Backspace as a second Confirm no
      // longer goes back): the build's sentence says so under it.
      const lostIn = key => check && check.lost && check.lost.menus && check.lost.menus[key];
      clear(menuCard).append(el("h2", { text: "In menus" }),
        el("p", { class: "note", text: "A key you add here does that job in menus too, and the game's keys keep theirs. A key you add " +
          "gives up its own job in menus, though: Backspace added to Confirm no longer goes back. A letter still types on the name screen." }),
        el("div", { class: "table-wrap", style: { maxHeight: "none" } }, el("table", { class: "grid-table controls-table" },
          el("thead", {}, el("tr", {}, el("th", { scope: "col", text: "In menus" }), el("th", { scope: "col", text: "The game's key" }),
            el("th", { scope: "col", text: "Also on" }))),
          el("tbody", {}, ...M.MENU_ROWS.map(r => el("tr", { "data-key": `menu:${r.key}` },
            el("th", { scope: "row" }, el("strong", { text: nameOf(r.command) })),
            el("td", { class: `cell${lostIn(r.key) ? " warned" : ""}` }, keyChip(r.key),
              lostIn(r.key) ? el("p", { class: "said warn", text: lostIn(r.key) }) : null),
            el("td", { class: "cell" }, seconds("menus", r.key, `${nameOf(r.command)} in menus`, "in menus"))))))));
    }

    // ---------- which keys are free ----------
    function renderFree() {
      const open = freeFold.open;
      const inUse = (check && check.in_use) || [];
      // wcmods' own and mods' keys first, then the keyboard's, the mouse's and the controller's.
      const kind = k => (k.startsWith("Gamepad_") ? 2 : M.MOUSE_KEYS.includes(k) ? 1 : 0);
      const rank = e => (e.taken === "refuse" ? 0 : e.taken === "warn" ? 1 : 2) * 3 + kind(e.key);
      const sorted = [...inUse].sort((a, b) => rank(a) - rank(b) || L(a.key).localeCompare(L(b.key)));
      const keyCell = k => k.startsWith("Gamepad_") ? el("span", { class: "row" }, keyChip(k), el("span", { class: "muted", text: "controller" })) : keyChip(k);
      clear(freeFold).append(
        el("summary", {}, el("h2", { text: "Which keys are free?" }), el("span", { class: "muted", text: "What each key does before your changes" })),
        el("p", { class: "note", text: "Keys not listed here do nothing in the game, so they're free. The mod menu's key, mouse look's key (while it's on) " +
          "and F11 can't take an action; a mod's key can, but then does both. Keys that mods' own scripts listen on are only known in the " +
          "game: the mod menu's Overview lists them." }),
        sorted.length ? el("div", { class: "table-wrap" }, el("table", { class: "grid-table" },
          el("thead", {}, el("tr", {}, el("th", { scope: "col", text: "Key" }), el("th", { scope: "col", text: "What it does" }),
            el("th", { scope: "col", text: "Where from" }))),
          el("tbody", {}, ...sorted.map(e => el("tr", {}, el("td", {}, keyCell(e.key)), el("td", { text: e.does }),
            el("td", { text: e.taken === "refuse" ? `${e.from} (taken)` : e.from }))))))
          : el("p", { class: "muted", text: "Working it out…" }));
      freeFold.open = open;
    }

    // ---------- for mod makers ----------
    function describeEntry({ section, name }) {
      const to = state[section][name];
      if (section === "keyboard") return `${nameOf(name)} on ${L(to)}`;
      if (section === "gamepad") return `${nameOf(name)} on ${L(to)} (controller)`;
      return `${L(name)} standing for ${L(to)}${section === "menus" ? " in menus" : " while you explore"}`;
    }
    function addPair(section) {
      const where = section === "menus" ? "menus" : "play";
      capture({ title: "The key you'll press", dev: "keyboard", where, taken: k => M.pairTaken(state, game, section, k, null, L) },
        k => setTimeout(() =>
          capture({ title: `The game's key ${L(k)} stands for`, dev: "keyboard", where }, g => {
            if (M.addSecond(state, section, M.norm(g), k)) edited();
          }), 0));
    }
    function renderMakers() {
      const open = makerFold.open;
      const others = M.unshown(state, game);
      out.set(M.toJson(state));
      clear(makerFold).append(
        el("summary", {}, el("h2", { text: "For mod makers" }), el("span", { class: "muted", text: "The file itself, and what no row shows" })),
        el("h3", { text: "Other changes in this file" }),
        others.length ? el("div", { class: "stack" }, ...others.map((o, i) => {
          const s = said(o.section, o.name, o.section);
          // Removed, focus goes to the next one's Remove (the list closes up), else to an Add button.
          const next = others[i + 1] ? `remove:${others[i + 1].section}:${others[i + 1].name}` : `pair:${o.section === "menus" ? "menus" : "keys"}`;
          return el("div", { class: "other", "data-key": `other:${o.section}:${o.name}` },
            el("div", { class: "row" }, el("span", { text: describeEntry(o) }), ...s.marks,
              el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove ${describeEntry(o)}`,
                "data-focus": `remove:${o.section}:${o.name}`,
                onclick: () => { M.remove(state, o.section, o.name); edited(); focusOn(next); } })), ...s.lines);
        })) : el("p", { class: "muted", text: "None: every change in this file is on a row above." }),
        el("div", { class: "row" },
          el("button", { class: "btn small", type: "button", text: "Add a key that stands for another while you explore", "data-focus": "pair:keys",
            onclick: () => addPair("keys") }),
          el("button", { class: "btn small", type: "button", text: "Add a key that stands for another in menus", "data-focus": "pair:menus",
            onclick: () => addPair("menus") })),
        el("p", { class: "note", text: "A key standing for another does that key's jobs instead of its own: T for W, or H as a second Interact. " +
          "How the file is written is in the guide's last part and in the file formats, on GitHub." }),
        el("h3", { text: "Mouse look" }), lookDebug(),
        out.element);
      makerFold.open = open;
    }

    // ---------- mouse look ----------
    // Not a binding: the game never reads the mouse, so this is a script with its own settings file in the Mouse
    // Look mod. Changes here save straight to that mod, one at a time (M.saveQueue): a slider is saved once it
    // has stopped moving, and only the on/off switch says so.
    const ML = { id: "mouse-look", file: "mouselook.json" };
    const LOOK = game.mouselook;   // its defaults and the keys that can switch it off and on (wcmods/mouselook.py)
    let look = { exists: false, enabled: false, settings: {} };
    let tiltOpen = false, mouseFor = null;
    const setting = k => look.settings[k] ?? LOOK.defaults[k];
    async function loadMouseLook() {
      try {
        const m = (await api.get("/mods")).find(x => x.id === ML.id);
        look = { exists: !!m, enabled: !!m?.enabled, settings: {} };
        if (m) {
          const r = await api.get(`/mods/${ML.id}/file/${ML.file}`);
          if (r.exists) look.settings = JSON.parse(r.text);   // every key it had stays (its _help too)
        }
      } catch (e) { toast(`Mouse look: ${e.message}`, "bad"); }
    }
    const looks = M.saveQueue(async job => {
      try {
        if (!look.exists) {
          await api.post("/mods", { id: ML.id, name: "Mouse Look", priority: 5, enabled: false,
            description: "Turn and tilt the camera with the mouse while exploring. Needs the script loader." });
          look.exists = true;
        }
        await api.put(`/mods/${ML.id}/file/${ML.file}`, { text: JSON.stringify(job.settings, null, 2) });
        if (job.switched) await api.patch(`/mods/${ML.id}`, { enabled: job.enabled });
        wc.bus.emit("mods-changed");
        if (job.switched) toast(`Mouse look ${job.enabled ? "on" : "off"}. Apply to game to use it.`);
        recheck(0);   // its key is one the Controls page keeps free
      } catch (e) {
        toast(e.message, "bad");
        await loadMouseLook();   // the card shows what's saved
        renderMouse();
      }
    });
    const saveLook = (switched = false) => looks.push({ settings: { ...look.settings }, enabled: look.enabled, switched });
    function renderMouse() {
      mouseFor = ue4ss;
      const toggle = el("input", { type: "checkbox", class: "switch", id: "ml-on", checked: look.enabled, disabled: !ue4ss && !look.enabled });
      toggle.addEventListener("change", () => { look.enabled = toggle.checked; saveLook(true); });
      const sensitivity = Number(setting("sensitivity"));
      const sensVal = el("strong", { text: `×${sensitivity.toFixed(2)}` });
      // The slider stretches to fit a value set by hand in mouselook.json (0.05-10), so it never clamps it.
      // min and max come before value: a range input clamps its value to the range it has at the time.
      const sens = el("input", { type: "range", id: "ml-sens", min: String(Math.min(0.2, sensitivity)),
        max: String(Math.max(3, sensitivity)), step: "0.05", value: sensitivity });
      sens.addEventListener("input", () => { look.settings.sensitivity = Number(sens.value); sensVal.textContent = `×${look.settings.sensitivity.toFixed(2)}`; saveLook(); });
      const inv = el("input", { type: "checkbox", id: "ml-invert", checked: !!setting("invert") });
      inv.addEventListener("change", () => { look.settings.invert = inv.checked; saveLook(); });
      // How long the camera takes to catch up with the mouse (0-1000 ms; the game eases its own over ~200).
      const smoothText = v => v > 0 ? `${Math.round(v)} ms` : "off";
      const smoothing = Number(setting("smoothing"));
      const smoothVal = el("strong", { text: smoothText(smoothing) });
      const smooth = el("input", { type: "range", id: "ml-smooth", min: "0", max: String(Math.max(300, smoothing)),
        step: "10", value: smoothing });
      smooth.addEventListener("input", () => { look.settings.smoothing = Number(smooth.value); smoothVal.textContent = smoothText(look.settings.smoothing); saveLook(); });
      // Switches off and on with: an F key wcmods leaves free (the mod menu's key can be one), or none.
      const keySel = lookKeys = el("select", { id: "ml-key", "aria-label": "Mouse look switches off and on with" },
        el("option", { value: "", text: "no key" }), ...LOOK.toggle_keys.map(k => el("option", { value: k, text: k })));
      keySel.value = setting("toggle_key");
      keySel.addEventListener("change", () => { look.settings.toggle_key = keySel.value; saveLook(); });
      markLookKeys();
      // Tilt limits, in a fold: few need them. The slider that moves gives way to the other (M.tilt).
      const [lo, hi] = M.tilt(setting("pitch_min"), setting("pitch_max"));
      const deg = v => `${v}°`;
      const loVal = el("strong", { text: deg(lo) }), hiVal = el("strong", { text: deg(hi) });
      const loIn = el("input", { type: "range", id: "ml-lo", min: "-89", max: "89", step: "1", value: lo });
      const hiIn = el("input", { type: "range", id: "ml-hi", min: "-89", max: "89", step: "1", value: hi });
      const moved = which => {
        const [a, b] = M.tilt(loIn.value, hiIn.value, which);
        loIn.value = a; hiIn.value = b; loVal.textContent = deg(a); hiVal.textContent = deg(b);
        look.settings.pitch_min = a; look.settings.pitch_max = b;
        saveLook();
      };
      loIn.addEventListener("input", () => moved("min"));
      hiIn.addEventListener("input", () => moved("max"));
      const tiltFold = el("details", { class: "fold", "data-key": "tilt" },
        el("summary", {}, el("h3", { text: "Tilt limits" }), el("span", { class: "muted", text: "How far down and up the camera tilts" })),
        el("div", { class: "row" }, el("label", { for: "ml-lo", class: "lbl" }, "Lowest tilt ", loVal), loIn),
        el("div", { class: "row" }, el("label", { for: "ml-hi", class: "lbl" }, "Highest tilt ", hiVal), hiIn),
        el("p", { class: "note", text: `The game's own: ${deg(LOOK.defaults.pitch_min)} and ${deg(LOOK.defaults.pitch_max)}.` }));
      tiltFold.open = tiltOpen;
      tiltFold.addEventListener("toggle", () => { tiltOpen = tiltFold.open; });
      clear(mouse).append(...[
        el("div", { class: "row spread" }, el("h2", { text: "Mouse look" }),
          el("span", { class: "muted", text: "Saves by itself into the Mouse Look mod; needs the script loader." })),
        el("label", { class: "row", for: "ml-on" }, toggle, el("strong", { text: "Turn and tilt the camera with the mouse" })),
        !ue4ss ? el("p", { class: "said warn", text: "Mouse look needs the script loader: Get set up, on the Mods page, installs it." }) : null,
        el("div", { class: "row" }, el("label", { for: "ml-sens", class: "lbl" }, "Sensitivity ", sensVal), sens,
          el("label", { class: "row", for: "ml-invert" }, inv, "Invert up/down")),
        el("div", { class: "row" }, el("label", { for: "ml-smooth", class: "lbl" }, "Smoothing ", smoothVal), smooth,
          el("span", { class: "muted", text: "How long the camera takes to catch up with the mouse. Off is the most direct; the game eases the arrow keys over about 200 ms." })),
        el("div", { class: "row" }, el("label", { for: "ml-key", class: "lbl", text: "Switches off and on with" }), keySel,
          el("span", { class: "muted", text: "Press it in the game while you explore." })),
        tiltFold,
        el("p", { class: "note", text: "While you explore, the mouse turns the camera and the cursor stays hidden. Menus get the cursor back. " +
          "The arrow keys and the right stick still work." }),
      ].filter(Boolean));
    }
    // The picker's F keys that wcmods takes for something else (the mod menu's key), from the last check: shown
    // with what they do, and not offered. Done in place, so the card isn't drawn again under the pointer.
    let lookKeys = null;
    function markLookKeys() {
      if (!lookKeys) return;
      const busy = Object.fromEntries(((check && check.in_use) || [])
        .filter(e => e.taken === "refuse" && e.from !== "Mouse look").map(e => [e.key, e.does]));
      for (const o of lookKeys.options) {
        const taken = o.value && busy[o.value] && o.value !== lookKeys.value;
        o.disabled = !!taken;
        o.textContent = taken ? `${o.value} (${busy[o.value]})` : (o.value || "no key");
      }
    }
    // Under For mod makers: mouse look's log, for finding out why it does what it does.
    function lookDebug() {
      const box = el("input", { type: "checkbox", id: "ml-debug", checked: !!setting("debug") });
      box.addEventListener("change", () => { look.settings.debug = box.checked; saveLook(); });
      return el("label", { class: "row", for: "ml-debug" }, box,
        el("span", { text: "Mouse look: log what it does (in the script loader's log)" }));
    }

    // ---------- the whole page ----------
    function renderBanner() {
      clear(banner).append(el("strong", { text: "Key changes need the script loader." }),
        el("span", { text: ` Get set up, on the Mods page, installs it. Until then, some changes work when you start the game with ${LAUNCHER} ` +
          "(keyboard and mouse only); each row says whether it does." }),
        el("a", { href: "#mods", text: "Open the Mods page" }));
      banner.hidden = ue4ss;
    }
    function render() {
      renderBanner();
      renderPlay();
      renderAlso();
      renderMoving();
      renderMenus();
      renderFree();
      if (mouseFor !== ue4ss) renderMouse(); else markLookKeys();
      renderMakers();
    }

    // After an Apply (or Get set up), what the build says may have changed: read the file again and ask again.
    const offInstalled = wc.installedEvent(target, () => { target.refresh().then(() => recheck(0)).catch(() => {}); });
    const offFocus = wc.bus.on("focus", () => recheck(0));
    // A mod turned on or off elsewhere; and an Apply (above) changes what's in the game.
    const offMods = wc.bus.on("mods-changed", () => { recheck(); setTimeout(refreshWhere, 0); });
    await Promise.all([target.refresh(), loadMouseLook()]);
    render();
    renderMouse();   // with mouse look's file read
    recheck(0);
    return { unmount() { offInstalled(); offFocus(); offMods(); clearTimeout(timer); looks.flush(); } };
  },
};
