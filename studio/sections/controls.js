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
    let check = null;          // the last /controls/check answer: lines per row, keys in use, other mods
    let checkFailed = "";
    let ue4ss = !!game.ue4ss;

    const target = wc.modTarget({
      file: "controls.json",
      onLoad: obj => { state = M.normalize(obj, game); render(); recheck(0); },
      getValue: () => M.toJson(state),
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

    // ---------- capture: press the key you want ----------
    // opts: { title, dev ("keyboard" or "gamepad"), where ("play" or "menus") }. onPick(key) gets the key.
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
        const no = M.whyNot(k, check && check.in_use, where, L);
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
      const top = el("div", { class: "row" }, keyChip(key, `${name}, ${devName}`),
        isChanged ? el("span", { class: "chip warn was-key", title: `The game's key: ${L(gk)}` }, el("i", { "aria-hidden": "true" }), `was ${L(gk)}`) : null,
        ...s.marks,
        el("button", { class: "btn small", type: "button", text: "Change", "aria-label": `Change the ${devName} key for ${name}`,
          onclick: () => capture({ title: `${name}: ${dev === "gamepad" ? "controller button" : "key or mouse button"}`, dev },
            k => { if (M.set(state, game, dev, action, k, lower())) edited(); }) }),
        action in state[dev] ? el("button", { class: "btn ghost small", type: "button", text: "Undo",
          "aria-label": `Undo the ${devName} change to ${name}, back to ${L(gk)}`,
          onclick: () => { M.undo(state, game, dev, action, lower()); edited(); } }) : null);
      const td = el("td", { class: `cell${s.warn ? " warned" : isChanged ? " edited" : ""}` }, top, ...s.lines);
      if (dev === "keyboard") td.append(seconds("keys", gk, name, "while you explore"));
      return td;
    }
    // Second keys for a row: each "also on" with its line and a Remove, and Add another key.
    function seconds(section, gk, name, when) {
      const box = el("div", { class: "seconds" });
      for (const p of M.secondKeys(state, section, gk)) {
        const s = said(section, p, "keyboard");
        box.append(el("div", { class: "row" }, el("span", { class: "muted", text: "also on" }), keyChip(p, `${name}, also`), ...s.marks,
          el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove ${L(p)}, the second key for ${name}`,
            onclick: () => { M.remove(state, section, p); edited(); } })), ...s.lines);
      }
      box.append(el("button", { class: "btn ghost small", type: "button", text: "Add another key", "aria-label": `Add another key for ${name}`,
        onclick: () => capture({ title: `${name}: another key (${when})`, dev: "keyboard", where: section === "menus" ? "menus" : "play" },
          k => { if (M.addSecond(state, section, gk, k)) edited(); }) }));
      return box;
    }
    function renderPlay() {
      const resetBtn = dev => wc.confirmButton(`Back to the game's keys`, `Press again to put every ${dev === "gamepad" ? "button" : "key"} back`,
        () => { M.resetDevice(state, game, dev, lower()); edited(); toast(dev === "gamepad" ? "The controller's buttons are the game's again" : "The keys are the game's again"); },
        "btn ghost small");
      const kbReset = resetBtn("keyboard"), padReset = resetBtn("gamepad");
      kbReset.setAttribute("aria-label", "Back to the game's keys for the keyboard and mouse");
      padReset.setAttribute("aria-label", "Back to the game's buttons for the controller");
      clear(playCard).append(
        el("div", { class: "row spread" }, el("h2", { text: "Keys while you play" }),
          el("label", { class: "row lbl", for: "pad-style" }, "Show controller buttons as", styleSel)),
        el("div", { class: "table-wrap", style: { maxHeight: "none" } },
          el("table", { class: "grid-table controls-table" },
            el("thead", {}, el("tr", {}, el("th", { scope: "col", text: "Action" }),
              el("th", { scope: "col" }, el("div", { class: "row spread" }, "Keyboard and mouse", kbReset)),
              el("th", { scope: "col" }, el("div", { class: "row spread" }, "Controller", padReset)))),
            el("tbody", {}, ...M.PLAY_ROWS.map(a => el("tr", { "data-key": `row:${a}` },
              el("th", { scope: "row" }, el("strong", { text: nameOf(a) })), playCell("keyboard", a), playCell("gamepad", a)))))),
        el("div", { class: "row" }, el("span", { class: "lbl", text: "Controller presets" }),
          ...Object.values(M.SWAPS).map(sw => el("button", { class: "chip", type: "button", title: sw.desc, text: sw.name,
            onclick: () => { if (M.swap(state, game, sw.map, lower())) edited(); } })),
          mark("untried")),
        el("p", { class: "note", text: "A second key does what the game's key does while you explore, and nothing in menus. " +
          "Controller buttons, Mouse 4, Mouse 5 and the wheel haven't been tried in the game yet." }));
    }

    // ---------- what the build says that no row shows ----------
    function renderAlso() {
      const lines = [...((check && check.others) || []), ...((check && check.lines) || [])];
      clear(also);
      also.hidden = !lines.length && !checkFailed;
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
      return el("div", { class: "move-key" },
        el("div", { class: "row" }, el("span", { class: "lbl", text: name }), keyChip(now, name),
          now !== gk ? el("span", { class: "chip warn was-key" }, el("i", { "aria-hidden": "true" }), `was ${L(gk)}`) : null,
          now !== gk && !s.marks.length ? mark("launcher") : null, ...s.marks,
          el("button", { class: "btn small", type: "button", text: "Change", "aria-label": `Change the key for ${name}`,
            onclick: () => capture({ title: `${name}: key`, dev: "keyboard" }, pickIt) }),
          now !== gk ? el("button", { class: "btn ghost small", type: "button", text: "Undo", "aria-label": `Undo the change to ${name}, back to ${L(gk)}`,
            onclick: () => pickIt(gk) }) : null),
        ...s.lines);
    }
    function stickCell(action) {
      const loaded = state.gamepad[action];
      const s = loaded ? said("gamepad", action) : null;
      if (!loaded || (s && M.checkRow(check, "gamepad", action)?.status === "same")) {
        return el("span", { class: "muted", text: action.startsWith("Player_Movement") ? "The left stick" : "The right stick" });
      }
      return el("div", {}, el("div", { class: "row" }, keyChip(loaded, "In this file"), mark("cannot"),
        el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove the stick change for ${nameOf(action)}`,
          onclick: () => { M.remove(state, "gamepad", action); edited(); } })), ...(s ? s.lines : []));
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
      clear(menuCard).append(el("h2", { text: "In menus" }),
        el("p", { class: "note", text: "The game's own keys keep working in menus; a key you add here works too. A letter still types on the name screen." }),
        el("div", { class: "table-wrap", style: { maxHeight: "none" } }, el("table", { class: "grid-table controls-table" },
          el("thead", {}, el("tr", {}, el("th", { scope: "col", text: "In menus" }), el("th", { scope: "col", text: "The game's key" }),
            el("th", { scope: "col", text: "Also on" }))),
          el("tbody", {}, ...M.MENU_ROWS.map(r => el("tr", { "data-key": `menu:${r.key}` },
            el("th", { scope: "row" }, el("strong", { text: nameOf(r.command) })),
            el("td", { class: "cell" }, keyChip(r.key)),
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
        el("p", { class: "note", text: "Keys not listed here do nothing in the game, so they're free. The mod menu's key, mouse look's key and " +
          "F11 can't take an action; a mod's key can, but then does both. Keys that mods' own scripts listen on are only known in the " +
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
      capture({ title: "The key you'll press", dev: "keyboard", where }, k => setTimeout(() =>
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
        others.length ? el("div", { class: "stack" }, ...others.map(o => {
          const s = said(o.section, o.name, o.section);
          return el("div", { class: "other", "data-key": `other:${o.section}:${o.name}` },
            el("div", { class: "row" }, el("span", { text: describeEntry(o) }), ...s.marks,
              el("button", { class: "btn ghost small", type: "button", text: "Remove", "aria-label": `Remove ${describeEntry(o)}`,
                onclick: () => { M.remove(state, o.section, o.name); edited(); } })), ...s.lines);
        })) : el("p", { class: "muted", text: "None: every change in this file is on a row above." }),
        el("div", { class: "row" },
          el("button", { class: "btn small", type: "button", text: "Add a key that stands for another while you explore", onclick: () => addPair("keys") }),
          el("button", { class: "btn small", type: "button", text: "Add a key that stands for another in menus", onclick: () => addPair("menus") })),
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
        el("span", { text: "Mouse look: log what it does (in the script loader's log, UE4SS.log)" }));
    }

    // ---------- the whole page ----------
    function renderBanner() {
      clear(banner).append(el("strong", { text: "Key changes need the script loader." }),
        el("span", { text: ` Get set up, on the Mods page, installs it. Until then, start the game with ${LAUNCHER} (keyboard and mouse only).` }),
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
    const offMods = wc.bus.on("mods-changed", () => recheck());
    await Promise.all([target.refresh(), loadMouseLook()]);
    render();
    renderMouse();   // with mouse look's file read
    recheck(0);
    return { unmount() { offInstalled(); offFocus(); offMods(); clearTimeout(timer); looks.flush(); } };
  },
};
