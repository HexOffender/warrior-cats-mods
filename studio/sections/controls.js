// Controls: rebind keyboard, mouse and controller actions. Writes controls.json in a mod.
const ACTIONS = [
  { id: "Player_Movement_Up", name: "Move back", axis: true },
  { id: "key:W", name: "Move forward", raw: "W" },
  { id: "Player_Movement_Right", name: "Move left", axis: true },
  { id: "key:D", name: "Move right", raw: "D" },
  { id: "Player_Camera_Up", name: "Camera down", axis: true },
  { id: "key:Up", name: "Camera up", raw: "Up" },
  { id: "Player_Camera_Right", name: "Camera left", axis: true },
  { id: "key:Right", name: "Camera right", raw: "Right" },
  { id: "Player_Pounce", name: "Pounce" },
  { id: "Player_Interact", name: "Interact" },
  { id: "Player_Run", name: "Run" },
  { id: "Player_Crouch", name: "Crouch" },
  { id: "Player_Scent_Tracking", name: "Scent tracking" },
  { id: "Player_Drop", name: "Drop" },
  { id: "Player_Friend_Talk", name: "Talk to friend" },
  { id: "Player_Den_Place", name: "Place den decoration" },
  { id: "Player_ReturnToCamp", name: "Return to camp" },
  { id: "Player_Camera_Reset", name: "Reset camera" },
  { id: "Player_Pause", name: "Pause menu" },
];
// The game's own bindings, from a fresh save. Its axis actions list one direction; the other keys
// (rows with `raw`) are built in, so their remaps go in controls.json's "keys" section.
const DEFAULTS = {
  keyboard: { Player_Movement_Up: "S", Player_Movement_Right: "A", Player_Camera_Up: "Down", Player_Camera_Right: "Left",
    "key:W": "W", "key:D": "D", "key:Up": "Up", "key:Right": "Right",
    Player_Pounce: "SpaceBar", Player_Drop: "C", Player_Den_Place: "X", Player_Interact: "E", Player_ReturnToCamp: "X",
    Player_Friend_Talk: "C", Player_Crouch: "LeftControl", Player_Scent_Tracking: "Q", Player_Camera_Reset: "R",
    Player_Run: "LeftShift", Player_Pause: "Enter" },
  gamepad: { Player_Movement_Up: "Gamepad_LeftY", Player_Movement_Right: "Gamepad_LeftX", Player_Camera_Up: "Gamepad_RightY",
    Player_Camera_Right: "Gamepad_RightX", Player_Pounce: "Gamepad_FaceButton_Top", Player_Drop: "Gamepad_FaceButton_Right",
    Player_Den_Place: "Gamepad_FaceButton_Top", Player_Interact: "Gamepad_FaceButton_Bottom", Player_ReturnToCamp: "Gamepad_FaceButton_Top",
    Player_Friend_Talk: "Gamepad_FaceButton_Right", Player_Crouch: "Gamepad_LeftTrigger", Player_Scent_Tracking: "Gamepad_FaceButton_Left",
    Player_Camera_Reset: "Gamepad_LeftShoulder", Player_Run: "Gamepad_RightShoulder", Player_Pause: "Gamepad_Special_Right" },
};
const ALIASES = { a: "Gamepad_FaceButton_Bottom", b: "Gamepad_FaceButton_Right", x: "Gamepad_FaceButton_Left", y: "Gamepad_FaceButton_Top",
  lb: "Gamepad_LeftShoulder", rb: "Gamepad_RightShoulder", lt: "Gamepad_LeftTrigger", rt: "Gamepad_RightTrigger",
  ls: "Gamepad_LeftThumbstick", rs: "Gamepad_RightThumbstick", l3: "Gamepad_LeftThumbstick", r3: "Gamepad_RightThumbstick",
  start: "Gamepad_Special_Right", back: "Gamepad_Special_Left", menu: "Gamepad_Special_Right", view: "Gamepad_Special_Left" };
const SWAPS = {
  nintendo: { name: "Nintendo layout", desc: "Swap A/B and X/Y",
    map: { Gamepad_FaceButton_Bottom: "Gamepad_FaceButton_Right", Gamepad_FaceButton_Right: "Gamepad_FaceButton_Bottom",
      Gamepad_FaceButton_Left: "Gamepad_FaceButton_Top", Gamepad_FaceButton_Top: "Gamepad_FaceButton_Left" } },
  shoulders: { name: "Swap bumpers and triggers", desc: "LB↔LT, RB↔RT",
    map: { Gamepad_LeftShoulder: "Gamepad_LeftTrigger", Gamepad_LeftTrigger: "Gamepad_LeftShoulder",
      Gamepad_RightShoulder: "Gamepad_RightTrigger", Gamepad_RightTrigger: "Gamepad_RightShoulder" } },
  sticks: { name: "Swap sticks", desc: "Move with the right stick",
    map: { Gamepad_LeftX: "Gamepad_RightX", Gamepad_RightX: "Gamepad_LeftX", Gamepad_LeftY: "Gamepad_RightY", Gamepad_RightY: "Gamepad_LeftY" } },
};

export default {
  title: "Controls",
  async mount(root, wc) {
    const { el, api, clear, toast, input } = wc;
    let saved = { keyboard: {}, gamepad: {} };
    let overrides = { keyboard: {}, gamepad: {} };
    let otherKeys = {};   // "keys" entries that aren't one of the built-in rows: extra keys while playing
    let menuKeys = {};    // "menus": {"keys": {...}}, used only while a menu is open
    let style = "xbox";
    try { style = localStorage.getItem("wc-pad-style") || "xbox"; } catch (e) { /* storage blocked */ }

    const target = wc.modTarget({
      file: "controls.json", defaultId: "my-controls", defaultName: "My Controls",
      onLoad: obj => { overrides = normalize(obj); render(); },
      getValue: () => toJson(),
    });
    const table = el("div", { class: "card" });
    const out = wc.codePanel("controls.json");
    const live = el("div", { class: "card" });
    const extraCard = el("div", { class: "card" });
    const menuCard = el("div", { class: "card" });
    const mouse = el("div", { class: "card" });

    try { saved = (await api.get("/game/bindings")).bindings; }
    catch (e) { root.append(el("div", { class: "banner" }, el("strong", { text: "No save found" }), el("span", { text: e.message }))); }

    const styleSel = el("select", { id: "pad-style", "aria-label": "Controller button names" },
      el("option", { value: "xbox", text: "Xbox names" }), el("option", { value: "playstation", text: "PlayStation names" }),
      el("option", { value: "switch", text: "Switch names" }));
    styleSel.value = style;
    styleSel.addEventListener("change", () => { style = styleSel.value; try { localStorage.setItem("wc-pad-style", style); } catch (e) { /* ignore */ } render(); });

    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Button remapper" }),
        el("h1", { text: "Controls" }),
        el("p", { class: "note", text: "Click Change, then press the key, mouse button, wheel or controller button you want, and save to a mod." })),
      el("div", { class: "banner" }, el("strong", { text: "Keyboard and mouse remaps run through the wcmods key remapper." }),
        el("span", { text: " The game ignores edited bindings, so start it with python wcmods.py play: while you play, your keys stand in for the game's. Controller buttons: use Steam Input. If you'd rather not run the remapper, PowerToys Keyboard Manager does the same job (README, \"Remapping keys\")." })),
      target.element,
      el("div", { class: "row" },
        el("span", { class: "eyebrow", text: "Controller presets" }),
        ...Object.entries(SWAPS).map(([id, s]) => el("button", { class: "chip", title: s.desc, onclick: () => swap(s.map), text: s.name })),
        el("button", { class: "chip", onclick: () => resetDevice("gamepad"), text: "Controller defaults" }),
        el("button", { class: "chip", onclick: () => resetDevice("keyboard"), text: "Keyboard defaults" }),
        el("span", { style: { flex: "1" } }),
        el("label", { for: "pad-style", class: "lbl", text: "Show buttons as" }), styleSel),
      mouse, table, extraCard, menuCard, live, out.element);

    // ---------- model ----------
    const RAW = Object.fromEntries(ACTIONS.filter(a => a.raw).map(a => [a.raw, a.id]));
    const padActions = ACTIONS.filter(a => !a.raw);
    function normalize(obj) {
      const o = { keyboard: {}, gamepad: {} };
      for (const dev of ["keyboard", "gamepad"]) {
        for (const [a, k] of Object.entries((obj && obj[dev]) || {})) {
          if (a.startsWith("_")) continue;
          const key = k && typeof k === "object" ? k.key : k;   // {key, ...} from older versions of this page
          o[dev][a] = dev === "gamepad" ? (ALIASES[String(key).toLowerCase()] || key) : key;
        }
      }
      // "keys" maps a key you press to the game key it stands for.
      otherKeys = {};
      for (const [pressed, gameKey] of Object.entries((obj && obj.keys) || {})) {
        if (pressed.startsWith("_")) continue;
        // A built-in key's row holds one key; a second key for the same job is kept as it is.
        if (RAW[gameKey] && !(RAW[gameKey] in o.keyboard)) o.keyboard[RAW[gameKey]] = pressed;
        else otherKeys[pressed] = gameKey;
      }
      menuKeys = {};
      for (const [pressed, gameKey] of Object.entries((obj && obj.menus && obj.menus.keys) || {})) {
        if (!pressed.startsWith("_")) menuKeys[pressed] = gameKey;
      }
      return o;
    }
    const effective = (dev, a) => overrides[dev][a] ?? saved[dev]?.[a] ?? DEFAULTS[dev][a];
    function setKey(dev, a, key) {
      if (key === (saved[dev]?.[a] ?? DEFAULTS[dev][a]) && !(a in overrides[dev])) return;
      overrides[dev][a] = key;
      target.markDirty();
      render();
    }
    function toJson() {
      const o = { _help: "Written by Clan Mod Studio. Keys are Unreal key names. \"keys\" maps a key you press to the game key it stands for." };
      const keyboard = {}, keys = { ...otherKeys };
      for (const [a, k] of Object.entries(overrides.keyboard)) {
        const raw = ACTIONS.find(x => x.id === a)?.raw;
        if (!raw) keyboard[a] = k;
        else if (k !== raw) keys[k] = raw;
      }
      if (Object.keys(keyboard).length) o.keyboard = keyboard;
      if (Object.keys(overrides.gamepad).length) o.gamepad = { ...overrides.gamepad };
      if (Object.keys(keys).length) o.keys = keys;
      if (Object.keys(menuKeys).length) o.menus = { keys: { ...menuKeys } };
      return o;
    }
    function swap(map) {
      for (const { id } of padActions) { const k = effective("gamepad", id); if (map[k]) overrides.gamepad[id] = map[k]; }
      target.markDirty(); render();
    }
    function resetDevice(dev) {
      for (const { id } of dev === "gamepad" ? padActions : ACTIONS) overrides[dev][id] = DEFAULTS[dev][id];
      target.markDirty(); render();
    }
    function conflicts(dev) {
      const rows = dev === "gamepad" ? padActions : ACTIONS;
      const byKey = {};
      for (const { id } of rows) (byKey[effective(dev, id)] ||= []).push(id);
      const designed = {};
      for (const { id } of rows) (designed[DEFAULTS[dev][id]] ||= []).push(id);
      const out = {};
      for (const [k, ids] of Object.entries(byKey)) {
        if (ids.length < 2) continue;
        const byGame = (designed[k] || []).length === ids.length && ids.every(i => designed[k].includes(i));
        for (const i of ids) out[i] = { others: ids.filter(x => x !== i), byGame };
      }
      return out;
    }

    // ---------- view ----------
    const nameOf = id => ACTIONS.find(a => a.id === id)?.name || id;
    function cell(dev, action) {
      if (dev === "gamepad" && action.raw) return el("span", { class: "muted", text: "same stick as the row above" });
      const key = effective(dev, action.id);
      const gameKey = saved[dev]?.[action.id] ?? DEFAULTS[dev][action.id];
      const changed = action.id in overrides[dev] && overrides[dev][action.id] !== gameKey;
      const conflict = conflicts(dev)[action.id];
      const cap = el("span", { class: "chip", style: { fontWeight: "700", fontSize: "0.95rem" }, title: key }, input.keyLabel(key, style));
      const box = el("div", { style: { display: "grid", gap: "4px" } },
        el("div", { class: "row" }, cap,
          changed ? el("span", { class: "chip warn", title: `The game's key: ${input.keyLabel(gameKey, style)}` }, el("i"), "changed") : null,
          el("button", { class: "btn small", text: "Change", "aria-label": `Change ${dev} binding for ${action.name}`, onclick: () => capture(dev, action) }),
          key !== DEFAULTS[dev][action.id] ? el("button", { class: "btn ghost small", text: "Default", title: `Game default: ${input.keyLabel(DEFAULTS[dev][action.id], style)}`, onclick: () => setKey(dev, action.id, DEFAULTS[dev][action.id]) }) : null,
          action.id in overrides[dev] ? el("button", { class: "btn ghost small", text: "Undo", onclick: () => { delete overrides[dev][action.id]; target.markDirty(); render(); } }) : null));
      if (conflict) {
        box.append(el("span", { class: conflict.byGame ? "muted" : "", style: { fontSize: "0.82rem", color: conflict.byGame ? "" : "var(--changed)" },
          text: conflict.byGame ? `Shared with ${conflict.others.map(nameOf).join(", ")} by the game (used in different places)` : `Also bound to ${conflict.others.map(nameOf).join(", ")}` }));
      }
      if (dev === "keyboard" && action.kbNote) box.append(el("span", { class: "muted", style: { fontSize: "0.8rem" }, text: action.kbNote }));
      return box;
    }
    // ---------- mouse look ----------
    // Not a binding: the game never reads the mouse, so this is a UE4SS script with its own settings
    // file in the Mouse Look mod. Changes here save straight to that mod.
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
            description: "Turn and tilt the camera with the mouse while exploring. Needs UE4SS." });
          look.exists = true;
        }
        await api.put(`/mods/${ML.id}/file/${ML.file}`, { text: JSON.stringify(look.settings, null, 2) });
        await api.patch(`/mods/${ML.id}`, { enabled });
        look.enabled = enabled;
        wc.bus.emit("mods-changed");
        toast(`Mouse look ${enabled ? "on" : "off"}. Install mods to apply it.`);
      } catch (e) { toast(e.message, "bad"); }
      renderMouse();
    }
    function renderMouse() {
      const s = look.settings;
      const toggle = el("input", { type: "checkbox", id: "ml-on", checked: look.enabled });
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
      clear(mouse).append(
        el("h2", { text: "Mouse look" }),
        el("label", { class: "row", for: "ml-on" }, toggle, el("strong", { text: "Turn and tilt the camera with the mouse" })),
        el("div", { class: "row" }, el("label", { for: "ml-sens", class: "lbl" }, "Sensitivity ", sensVal), sens,
          el("label", { class: "row", for: "ml-invert" }, inv, "Invert up/down")),
        el("div", { class: "row" }, el("label", { for: "ml-smooth", class: "lbl" }, "Smoothing ", smoothVal), smooth,
          el("span", { class: "muted", text: "How long the camera takes to catch up with the mouse. Off is the most direct; the game eases the arrow keys over about 200 ms." })),
        el("p", { class: "note", text: "While you explore, the mouse turns the camera and the cursor stays hidden. Menus get the cursor back. " +
          (toggleKey ? `Press ${toggleKey} in game to switch it off and on. ` : "") +
          "The arrow keys and the right stick still work. Saved in the Mouse Look mod; needs UE4SS." }));
    }

    function render() {
      renderMouse();
      clear(table).append(el("div", { class: "table-wrap", style: { maxHeight: "none" } },
        el("table", { class: "grid-table" },
          el("thead", {}, el("tr", {}, el("th", { text: "Action" }), el("th", { text: "Keyboard & mouse" }), el("th", { text: "Controller" }))),
          el("tbody", {}, ...ACTIONS.map(a => el("tr", {},
            el("td", {}, el("strong", { text: a.name }), el("div", { class: "muted mono", style: { fontSize: "0.72rem" }, text: a.raw ? `built-in key ${a.raw}` : a.id })),
            el("td", {}, cell("keyboard", a)), el("td", {}, cell("gamepad", a))))))));
      // A built-in row's key (Move forward on T, say) wins over an extra pair for the same key.
      const rowKeys = Object.fromEntries(ACTIONS.filter(a => a.raw && overrides.keyboard[a.id] && overrides.keyboard[a.id] !== a.raw)
        .map(a => [overrides.keyboard[a.id], a.name]));
      renderPairs(extraCard, "Extra keys while playing", "Any key can stand for any game key while you play, " +
        "e.g. Escape for the key that opens the pause menu. The game key then stops working on its own, unless an action above still uses it.", otherKeys, rowKeys);
      renderPairs(menuCard, "In menus", "Used only while the game shows a menu with its cursor (the title screen is confirmed; run " +
        "play --debug to check the pause menu and others), e.g. Escape for the key that closes a menu. The game's own keys keep working too; a letter " +
        "used here also changes typing on the name screen.", menuKeys, {});
      out.set(toJson());
    }

    // ---------- key pairs: extra keys while playing, keys in menus ----------
    // pairs is {key you press: game key}; changes go straight into it. taken: {key: row name} for keys
    // a built-in row already uses, which win over a pair here.
    function renderPairs(box, title, note, pairs, taken) {
      const changed = () => { target.markDirty(); render(); };
      const chip = k => el("span", { class: "chip", style: { fontWeight: "700" }, title: k }, input.keyLabel(k, style));
      const pick = (label, then) => capture("keyboard", { name: `${title}: ${label}` }, then);
      const free = (k, except) => {
        if (k !== except && k in pairs) { toast(`${input.keyLabel(k, style)} is already in this list; change or remove that one first`, "bad"); return false; }
        return true;
      };
      const rows = Object.entries(pairs).map(([pressed, gameKey]) => el("div", { style: { display: "grid", gap: "2px" } },
        el("div", { class: "row" },
          el("span", { class: "muted", text: "Pressing" }), chip(pressed),
          el("button", { class: "btn ghost small", text: "Change", "aria-label": `Change the key you press for ${gameKey}`,
            onclick: () => pick("the key you press", k => { if (k !== pressed && free(k, pressed)) { delete pairs[pressed]; pairs[k] = gameKey; changed(); } }) }),
          el("span", { class: "muted", text: "sends the game" }), chip(gameKey),
          el("button", { class: "btn ghost small", text: "Change", "aria-label": `Change the game key ${pressed} sends`,
            onclick: () => pick("the game's key", k => { pairs[pressed] = k; changed(); }) }),
          el("button", { class: "btn ghost small", text: "Remove", onclick: () => { delete pairs[pressed]; changed(); } })),
        taken[pressed] ? el("span", { style: { fontSize: "0.82rem", color: "var(--changed)" },
          text: `${input.keyLabel(pressed, style)} is also ${taken[pressed]}'s key above, which wins; pick another key` }) : null));
      clear(box).append(el("h2", { text: title }), el("p", { class: "note", text: note }), ...rows,
        el("div", { class: "row" }, el("button", { class: "btn small", text: "Add a key", onclick: () =>
          pick("press the key you want to use", k => free(k) && setTimeout(() =>
            pick(`press the game's key for ${input.keyLabel(k, style)}`, g => { pairs[k] = g; changed(); }), 0)) })));
    }

    // ---------- capture ----------
    // onPick(key) receives the key instead of it being set on an action row (the key-pair lists).
    function capture(dev, action, onPick) {
      const pad = dev === "gamepad";
      const choices = pad ? (action.axis ? input.PAD_AXES : input.PAD_BUTTONS) : [];
      const msg = el("p", { text: pad
        ? (action.axis ? "Move a stick on your controller, or pick one below." : "Press a button on your controller, or pick one below.")
        : "Press a key, click a mouse button here, or scroll. Escape cancels; to use Escape itself, click the Escape button." });
      const padNote = el("p", { class: "muted", style: { fontSize: "0.9rem" } });
      const overlay = el("div", {
        role: "dialog", "aria-modal": "true", "aria-label": `Rebind ${action.name}`,
        style: { position: "fixed", inset: "0", background: "rgba(10,16,13,.55)", display: "grid", placeItems: "center", zIndex: "40", padding: "16px" },
      }, el("div", { class: "card", style: { width: "min(560px, 100%)" } },
        el("h2", { text: `${action.name} · ${pad ? "controller" : "keyboard & mouse"}` }), msg, padNote,
        pad ? el("div", { class: "row" }, ...choices.map(k => el("button", { class: "chip", type: "button", text: input.keyLabel(k, style), title: k, onclick: () => finish(k) }))) : null,
        el("div", { class: "row" }, el("button", { class: "btn", type: "button", text: "Cancel", onclick: () => finish(null) }),
          // Escape is a key worth binding (closing menus), but pressing it here cancels.
          pad ? null : el("button", { class: "btn ghost", type: "button", text: "Escape", title: "Use the Escape key", onclick: () => finish("Escape") }))));
      document.body.append(overlay);
      let raf = 0, done = false;
      const onKey = e => {
        if (pad) { if (e.key === "Escape") finish(null); return; }
        e.preventDefault(); e.stopPropagation();
        if (e.code === "Escape") return finish(null);
        const k = input.keyFromEvent(e);
        if (k) finish(k); else msg.textContent = `That key (${e.code}) isn't one the game understands. Try another.`;
      };
      const onMouse = e => {
        if (pad || e.target.closest("button")) return;
        e.preventDefault();
        if (input.MOUSE[e.button]) finish(input.MOUSE[e.button]);
      };
      const onWheel = e => { if (!pad) { e.preventDefault(); finish(e.deltaY < 0 ? "MouseScrollUp" : "MouseScrollDown"); } };
      window.addEventListener("keydown", onKey, true);
      overlay.addEventListener("mousedown", onMouse);
      overlay.addEventListener("contextmenu", e => e.preventDefault());
      overlay.addEventListener("wheel", onWheel, { passive: false });
      if (pad) {
        let base = null;
        const poll = () => {
          if (done) return;
          let pads = [];
          try { pads = [...(navigator.getGamepads ? navigator.getGamepads() : [])].filter(Boolean); }
          catch (e) { padNote.textContent = "This browser window can't read controllers; pick a button above."; return; }
          if (!pads.length) padNote.textContent = "No controller detected yet. Press any button on it once, or pick a button above.";
          else padNote.textContent = `Listening to ${pads[0].id.replace(/\s*\(.*\)$/, "")}`;
          const now = pads.map(p => ({ b: p.buttons.map(b => b.pressed || b.value > 0.6), a: [...p.axes] }));
          if (base === null) base = now;
          for (let i = 0; i < now.length; i++) {
            if (action.axis) {
              for (let x = 0; x < Math.min(4, now[i].a.length); x++) if (Math.abs(now[i].a[x]) > 0.7) return finish(input.PAD_AXES[x]);
            } else {
              for (let b = 0; b < Math.min(16, now[i].b.length); b++) {
                if (now[i].b[b] && !(base[i] && base[i].b[b])) return finish(input.PAD_BUTTONS[b]);
              }
            }
          }
          raf = requestAnimationFrame(poll);
        };
        raf = requestAnimationFrame(poll);
      }
      overlay.querySelector("button").focus();
      function finish(key) {
        if (done) return;
        done = true;
        cancelAnimationFrame(raf);
        window.removeEventListener("keydown", onKey, true);
        overlay.remove();
        if (key && onPick) onPick(key);
        else if (key) { setKey(dev, action.id, key); toast(`${action.name}: ${input.keyLabel(key, style)}`); }
      }
    }

    // ---------- using the remaps ----------
    function renderLive() {
      clear(live).append(el("h2", { text: "Using your remaps" }),
        el("ol", { style: { margin: "0", paddingLeft: "1.3em", display: "grid", gap: "6px" } },
          el("li", { text: "Save to a mod (top of this page)." }),
          el("li", { text: "Install mods once (top right, game closed). That adds the small script that tells the remapper when you're playing; after that, key changes need no install." }),
          el("li", { text: "Start the game with python wcmods.py play. It stops by itself when the game closes. If the game is already open, use python wcmods.py remap." }),
          el("li", { text: "Your keys work while you play: the game in front and its cursor hidden. Menus and the name screen use only the \"In menus\" list, and other programs keep your normal keys. A key whose action moved stops doing it." }),
          el("li", { text: "Controller buttons: in Steam, right-click the game, then Properties, Controller, and remap them with Steam Input." })),
        el("p", { class: "note", text: "Add --dry-run to see what would be remapped without changing anything. The game ignores edited bindings in its save and its rebinding screen is unfinished on PC, which is why the remapper works from outside the game. Mouse look above doesn't depend on any of this." }));
    }

    await Promise.all([target.refresh(), loadMouseLook()]);
    render();
    renderLive();
  },
};
