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
      onLoad: obj => { state = M.normalize(obj, game); loaded = M.clone(state); render(); recheck(0); },
      getValue: () => M.toJson(state),
      // Saved: the file is what was saved, so Undo goes back to that from now on.
      onSaved: saved => { loaded = M.normalize(saved, game); render(); },
    });
    const lower = () => (check && check.lower) || [];
    // Every change: unsaved until Save to mod, drawn now, and checked against the build a moment later.
    const edited = () => { target.markDirty(); render(); recheck(); };

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
      banner, target.element, playCard, also, moveFold, menuCard, freeFold, mouse, makerFold);

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
    // opts: { title, dev ("keyboard" or "gamepad"), where ("play" or "menus"), taken(key): a sentence when the
    // key can't be used here (it already stands for another key), or null }. onPick(key) gets the key.
    function capture(opts, onPick) {
      const pad = opts.dev === "gamepad", where = opts.where || "play";
      const back = wc.keepPlace();
      const msg = el("p", { id: "capture-msg", text: pad
        ? "Press a button on your controller, or pick one below. Escape cancels."
        : "Press the key you want. Escape cancels; to use Escape, Tab, Enter, Space or Backspace themselves, press its button below." });
      const why = el("p", { class: "said warn", role: "alert", hidden: true });
      const padNote = el("p", { class: "muted" });
      const use = k => el("button", { class: "chip", type: "button", text: L(k), "aria-label": `Use ${L(k)}`, onclick: () => pick(k) });
      const extra = pad ? input.PAD_BUTTONS
        : ["Escape", "Tab", "Enter", "SpaceBar", "BackSpace", ...(where === "menus" ? [] : ["MiddleMouseButton", ...M.UNTRIED])];
      const zone = pad || where === "menus" ? null
        : el("div", { class: "capture-zone", text: "Or click a mouse button, or turn the wheel, here" });
      const box = el("div", { class: "card capture", role: "dialog", "aria-modal": "true", "aria-labelledby": "capture-title",
        "aria-describedby": "capture-msg", tabindex: "-1" },
        el("h2", { id: "capture-title", text: opts.title }), msg, zone, why, padNote,
        el("div", { class: "row" }, ...extra.map(use)),
        el("div", { class: "row" }, el("button", { class: "btn", type: "button", text: "Cancel", onclick: () => finish(null) })));
      const overlay = el("div", { class: "capture-overlay" }, box);
      document.body.append(overlay);
      let raf = 0, done = false;
      const buttons = () => [...box.querySelectorAll("button")];
      function move(backwards) {
        const bs = buttons(), at = bs.indexOf(document.activeElement);
        bs[at < 0 ? (backwards ? bs.length - 1 : 0) : (at + (backwards ? -1 : 1) + bs.length) % bs.length].focus();
      }
      function pick(k) {
        const taken = opts.taken ? opts.taken(k) : null;
        const no = taken ? { refuse: taken } : M.whyNot(k, check && check.in_use, where, L);
        if (no && no.refuse) { why.hidden = false; why.textContent = no.refuse; wc.announce(no.refuse, "bad"); return; }
        finish(k, no && no.warn);
      }
      const onKey = e => {
        const onButton = document.activeElement && document.activeElement.tagName === "BUTTON" && box.contains(document.activeElement);
        const act = M.captureKey(e, onButton, input.keyFromEvent);
        if (act.do === "press") return;   // the button that has focus does its own job
        e.preventDefault(); e.stopPropagation();
        if (act.do === "cancel") return finish(null);
        if (act.do === "move") return move(act.back);
        if (pad) return;   // a controller's button is pressed on the controller
        if (act.do === "unknown") { msg.textContent = "That key isn't one the game knows. Try a letter, a number, an F key or an arrow."; return; }
        pick(act.key);
      };
      zone?.addEventListener("mousedown", e => { e.preventDefault(); if (input.MOUSE[e.button]) pick(input.MOUSE[e.button]); });
      zone?.addEventListener("contextmenu", e => e.preventDefault());
      zone?.addEventListener("wheel", e => {
        e.preventDefault();
        if (e.deltaY !== 0) pick(e.deltaY < 0 ? "MouseScrollUp" : "MouseScrollDown");   // a sideways wheel: nothing
      }, { passive: false });
      window.addEventListener("keydown", onKey, true);
      if (pad) {
        let base = null;
        const poll = () => {
          if (done) return;
          let pads = [];
          try { pads = [...(navigator.getGamepads ? navigator.getGamepads() : [])].filter(Boolean); }
          catch (e) { padNote.textContent = "This browser window can't read controllers; pick a button above."; return; }
          padNote.textContent = pads.length ? `Listening to ${pads[0].id.replace(/\s*\(.*\)$/, "")}`
            : "No controller found yet. Press any button on it once, or pick a button above.";
          const now = pads.map(p => p.buttons.map(b => b.pressed || b.value > 0.6));
          if (base === null) base = now;
          for (let i = 0; i < now.length; i++) {
            for (let b = 0; b < Math.min(16, now[i].length); b++) if (now[i][b] && !(base[i] && base[i][b])) return pick(input.PAD_BUTTONS[b]);
          }
          raf = requestAnimationFrame(poll);
        };
        raf = requestAnimationFrame(poll);
      }
      box.focus();
      function finish(k, warning) {
        if (done) return;
        done = true;
        cancelAnimationFrame(raf);
        window.removeEventListener("keydown", onKey, true);
        overlay.remove();
        back();
        if (k) {
          onPick(k);
          if (warning) toast(warning);
        }
      }
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
        out.element);
      makerFold.open = open;
    }

    // ---------- mouse look ----------
    // Not a binding: the game never reads the mouse, so this is a script with its own settings file in the Mouse
    // Look mod. Changes here save straight to that mod.
    const ML = { id: "mouse-look", file: "mouselook.json" };
    let look = { exists: false, enabled: false, settings: { sensitivity: 1, invert: false } };
    async function loadMouseLook() {
      try {
        const m = (await api.get("/mods")).find(x => x.id === ML.id);
        look = { exists: !!m, enabled: !!m?.enabled, settings: { sensitivity: 1, invert: false } };
        if (m) {
          const r = await api.get(`/mods/${ML.id}/file/${ML.file}`);
          if (r.exists) Object.assign(look.settings, JSON.parse(r.text));
        }
      } catch (e) { toast(`Mouse look: ${e.message}`, "bad"); }
    }
    async function saveMouseLook(enabled) {
      try {
        if (!look.exists) {
          await api.post("/mods", { id: ML.id, name: "Mouse Look", priority: 5, enabled: false,
            description: "Turn and tilt the camera with the mouse while exploring. Needs the script loader." });
          look.exists = true;
        }
        await api.put(`/mods/${ML.id}/file/${ML.file}`, { text: JSON.stringify(look.settings, null, 2) });
        await api.patch(`/mods/${ML.id}`, { enabled });
        look.enabled = enabled;
        wc.bus.emit("mods-changed");
        toast(`Mouse look ${enabled ? "on" : "off"}. Apply to game to use it.`);
        recheck(0);   // its key is one the Controls page keeps free
      } catch (e) { toast(e.message, "bad"); }
      renderMouse();
    }
    function renderMouse() {
      const s = look.settings;
      const toggle = el("input", { type: "checkbox", class: "switch", id: "ml-on", checked: look.enabled, disabled: !ue4ss && !look.enabled });
      toggle.addEventListener("change", () => saveMouseLook(toggle.checked));
      const sensVal = el("strong", { text: `×${Number(s.sensitivity).toFixed(2)}` });
      // The slider stretches to fit a value set by hand in mouselook.json (0.05-10), so it never clamps it.
      // min and max come before value: a range input clamps its value to the range it has at the time.
      const sens = el("input", { type: "range", id: "ml-sens", min: String(Math.min(0.2, s.sensitivity)),
        max: String(Math.max(3, s.sensitivity)), step: "0.05", value: s.sensitivity });
      sens.addEventListener("input", () => { s.sensitivity = Number(sens.value); sensVal.textContent = `×${s.sensitivity.toFixed(2)}`; });
      sens.addEventListener("change", () => saveMouseLook(look.enabled));
      const inv = el("input", { type: "checkbox", id: "ml-invert", checked: !!s.invert });
      inv.addEventListener("change", () => { s.invert = inv.checked; saveMouseLook(look.enabled); });
      // How long the camera takes to catch up with the mouse (0-1000 ms; the game eases its own over ~200).
      const smoothText = v => v > 0 ? `${Math.round(v)} ms` : "off";
      const smoothing = Number(s.smoothing ?? 0);
      const smoothVal = el("strong", { text: smoothText(smoothing) });
      const smooth = el("input", { type: "range", id: "ml-smooth", min: "0", max: String(Math.max(300, smoothing)),
        step: "10", value: smoothing });
      smooth.addEventListener("input", () => { s.smoothing = Number(smooth.value); smoothVal.textContent = smoothText(s.smoothing); });
      smooth.addEventListener("change", () => saveMouseLook(look.enabled));
      const toggleKey = s.toggle_key ?? "F6";
      clear(mouse).append(...[
        el("div", { class: "row spread" }, el("h2", { text: "Mouse look" }),
          el("span", { class: "muted", text: "Saves by itself into the Mouse Look mod; needs the script loader." })),
        el("label", { class: "row", for: "ml-on" }, toggle, el("strong", { text: "Turn and tilt the camera with the mouse" })),
        !ue4ss ? el("p", { class: "said warn", text: "Mouse look needs the script loader: Get set up, on the Mods page, installs it." }) : null,
        el("div", { class: "row" }, el("label", { for: "ml-sens", class: "lbl" }, "Sensitivity ", sensVal), sens,
          el("label", { class: "row", for: "ml-invert" }, inv, "Invert up/down")),
        el("div", { class: "row" }, el("label", { for: "ml-smooth", class: "lbl" }, "Smoothing ", smoothVal), smooth,
          el("span", { class: "muted", text: "How long the camera takes to catch up with the mouse. Off is the most direct; the game eases the arrow keys over about 200 ms." })),
        el("p", { class: "note", text: "While you explore, the mouse turns the camera and the cursor stays hidden. Menus get the cursor back. " +
          (toggleKey ? `Press ${toggleKey} in the game to switch it off and on. ` : "") + "The arrow keys and the right stick still work." }),
      ].filter(Boolean));
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
      renderMouse();
      renderMakers();
    }

    // After an Apply (or Get set up), what the build says may have changed: read the file again and ask again.
    const offInstalled = wc.installedEvent(target, () => { target.refresh().then(() => recheck(0)).catch(() => {}); });
    const offFocus = wc.bus.on("focus", () => recheck(0));
    const offMods = wc.bus.on("mods-changed", () => recheck());
    await Promise.all([target.refresh(), loadMouseLook()]);
    render();
    recheck(0);
    return { unmount() { offInstalled(); offFocus(); offMods(); clearTimeout(timer); } };
  },
};
