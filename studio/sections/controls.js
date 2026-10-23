// Controls: rebind keyboard, mouse and controller actions. Writes controls.json in a mod.
const ACTIONS = [
  { id: "Player_Movement_Up", name: "Move forward / back", axis: true, kbNote: "Sets the back key. The forward key isn't stored in the save, so the game keeps its own." },
  { id: "Player_Movement_Right", name: "Move left / right", axis: true, kbNote: "Sets the left key. The right key isn't stored in the save, so the game keeps its own." },
  { id: "Player_Camera_Up", name: "Camera up / down", axis: true, kbNote: "Sets the camera-down key. Its opposite isn't stored in the save." },
  { id: "Player_Camera_Right", name: "Camera left / right", axis: true, kbNote: "Sets the camera-left key. Its opposite isn't stored in the save." },
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
// The game's own bindings, from a fresh save.
const DEFAULTS = {
  keyboard: { Player_Movement_Up: "S", Player_Movement_Right: "A", Player_Camera_Up: "Down", Player_Camera_Right: "Left",
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
    let savedScales = { keyboard: {}, gamepad: {} };
    let axes = new Set(ACTIONS.filter(a => a.axis).map(a => a.id));
    // An override is a key name, or {key, scale} for axis actions (scale = direction and sensitivity).
    let overrides = { keyboard: {}, gamepad: {} };
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
    const mouse = el("div", { class: "card" });

    try {
      const b = await api.get("/game/bindings");
      saved = b.bindings;
      savedScales = b.scales || savedScales;
      if (b.axes) axes = new Set(b.axes);
    }
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
        el("p", { class: "note", text: "Click Change, then press the key, mouse button, wheel or controller button you want. Save to a mod, then Install mods with the game closed. Your save is backed up before it's changed." })),
      target.element,
      el("div", { class: "row" },
        el("span", { class: "eyebrow", text: "Controller presets" }),
        ...Object.entries(SWAPS).map(([id, s]) => el("button", { class: "chip", title: s.desc, onclick: () => swap(s.map), text: s.name })),
        el("button", { class: "chip", onclick: () => resetDevice("gamepad"), text: "Controller defaults" }),
        el("button", { class: "chip", onclick: () => resetDevice("keyboard"), text: "Keyboard defaults" }),
        el("span", { style: { flex: "1" } }),
        el("label", { for: "pad-style", class: "lbl", text: "Show buttons as" }), styleSel),
      mouse, table, live, out.element);

    // ---------- model ----------
    function normalize(obj) {
      const o = { keyboard: {}, gamepad: {} };
      for (const dev of ["keyboard", "gamepad"]) {
        for (const [a, k] of Object.entries((obj && obj[dev]) || {})) {
          if (a.startsWith("_")) continue;
          const key = k && typeof k === "object" ? k.key : k;
          const norm = dev === "gamepad" ? (ALIASES[String(key).toLowerCase()] || key) : key;
          o[dev][a] = k && typeof k === "object" && typeof k.scale === "number" ? { key: norm, scale: k.scale } : norm;
        }
      }
      return o;
    }
    const keyOf = v => (v && typeof v === "object" ? v.key : v);
    const defaultScale = (dev, a) => (axes.has(a) && dev === "keyboard" ? -1 : 1);
    const effective = (dev, a) => keyOf(overrides[dev][a]) ?? saved[dev]?.[a] ?? DEFAULTS[dev][a];
    const effScale = (dev, a) => {
      const o = overrides[dev][a];
      if (o && typeof o === "object" && typeof o.scale === "number") return o.scale;
      return savedScales[dev]?.[a] ?? defaultScale(dev, a);
    };
    // Keyboard axis entries hold the negative direction (Left arrow at -1), so a key set here always
    // goes back to -1, undoing a mouse-look scale.
    const withScale = (dev, a, key) => (axes.has(a) && dev === "keyboard" ? { key, scale: -1 } : key);
    function setKey(dev, a, key) {
      const v = withScale(dev, a, key);
      const same = key === (saved[dev]?.[a] ?? DEFAULTS[dev][a]) && effScale(dev, a) === (typeof v === "object" ? v.scale : effScale(dev, a));
      if (same && !(a in overrides[dev])) return;
      overrides[dev][a] = v;
      target.markDirty();
      render();
    }
    const isChanged = (dev, a) => a in overrides[dev] &&
      (keyOf(overrides[dev][a]) !== saved[dev]?.[a] || effScale(dev, a) !== (savedScales[dev]?.[a] ?? defaultScale(dev, a)));
    function toJson() {
      const o = { _help: "Written by Clan Mod Studio. Keys are Unreal key names." };
      for (const dev of ["keyboard", "gamepad"]) if (Object.keys(overrides[dev]).length) o[dev] = { ...overrides[dev] };
      return o;
    }
    function swap(map) {
      for (const { id } of ACTIONS) { const k = effective("gamepad", id); if (map[k]) overrides.gamepad[id] = map[k]; }
      target.markDirty(); render();
    }
    function resetDevice(dev) {
      for (const { id } of ACTIONS) overrides[dev][id] = withScale(dev, id, DEFAULTS[dev][id]);
      target.markDirty(); render();
    }
    function conflicts(dev) {
      const byKey = {};
      for (const { id } of ACTIONS) (byKey[effective(dev, id)] ||= []).push(id);
      const designed = {};
      for (const { id } of ACTIONS) (designed[DEFAULTS[dev][id]] ||= []).push(id);
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
      const key = effective(dev, action.id);
      const changed = isChanged(dev, action.id);
      const isMouseAxis = key === "MouseX" || key === "MouseY";
      const conflict = conflicts(dev)[action.id];
      const cap = el("span", { class: "chip", style: { fontWeight: "700", fontSize: "0.95rem" }, title: key }, input.keyLabel(key, style));
      const box = el("div", { style: { display: "grid", gap: "4px" } },
        el("div", { class: "row" }, cap,
          isMouseAxis ? el("span", { class: "chip", title: "Sensitivity (negative = inverted)", text: `×${effScale(dev, action.id)}` }) : null,
          changed ? el("span", { class: "chip warn", title: `In your save: ${saved[dev]?.[action.id]}` }, el("i"), "changed") : null,
          el("button", { class: "btn small", text: "Change", "aria-label": `Change ${dev} binding for ${action.name}`, onclick: () => capture(dev, action) }),
          key !== DEFAULTS[dev][action.id] || effScale(dev, action.id) !== defaultScale(dev, action.id) ? el("button", { class: "btn ghost small", text: "Default", title: `Game default: ${input.keyLabel(DEFAULTS[dev][action.id], style)}`, onclick: () => setKey(dev, action.id, DEFAULTS[dev][action.id]) }) : null,
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
      const sensVal = el("strong", { text: `×${Number(s.sensitivity).toFixed(1)}` });
      const sens = el("input", { type: "range", id: "ml-sens", min: "0.2", max: "3", step: "0.1", value: s.sensitivity });
      sens.addEventListener("input", () => { s.sensitivity = Number(sens.value); sensVal.textContent = `×${s.sensitivity.toFixed(1)}`; });
      sens.addEventListener("change", () => saveMouseLook(look.enabled));
      const inv = el("input", { type: "checkbox", id: "ml-invert", checked: !!s.invert });
      inv.addEventListener("change", () => { s.invert = inv.checked; saveMouseLook(look.enabled); });
      const toggleKey = s.toggle_key ?? "F6";
      clear(mouse).append(
        el("h2", { text: "Mouse look" }),
        el("label", { class: "row", for: "ml-on" }, toggle, el("strong", { text: "Turn and tilt the camera with the mouse" })),
        el("div", { class: "row" }, el("label", { for: "ml-sens", class: "lbl" }, "Sensitivity ", sensVal), sens,
          el("label", { class: "row", for: "ml-invert" }, inv, "Invert up/down")),
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
            el("td", {}, el("strong", { text: a.name }), el("div", { class: "muted mono", style: { fontSize: "0.72rem" }, text: a.id })),
            el("td", {}, cell("keyboard", a)), el("td", {}, cell("gamepad", a))))))));
      out.set(toJson());
    }

    // ---------- capture ----------
    function capture(dev, action) {
      const pad = dev === "gamepad";
      const choices = pad ? (action.axis ? input.PAD_AXES : input.PAD_BUTTONS) : [];
      const msg = el("p", { text: pad
        ? (action.axis ? "Move a stick on your controller, or pick one below." : "Press a button on your controller, or pick one below.")
        : "Press a key, click a mouse button here, or scroll. Esc cancels." });
      const padNote = el("p", { class: "muted", style: { fontSize: "0.9rem" } });
      const overlay = el("div", {
        role: "dialog", "aria-modal": "true", "aria-label": `Rebind ${action.name}`,
        style: { position: "fixed", inset: "0", background: "rgba(10,16,13,.55)", display: "grid", placeItems: "center", zIndex: "40", padding: "16px" },
      }, el("div", { class: "card", style: { width: "min(560px, 100%)" } },
        el("h2", { text: `${action.name} · ${pad ? "controller" : "keyboard & mouse"}` }), msg, padNote,
        pad ? el("div", { class: "row" }, ...choices.map(k => el("button", { class: "chip", type: "button", text: input.keyLabel(k, style), title: k, onclick: () => finish(k) }))) : null,
        el("div", { class: "row" }, el("button", { class: "btn", type: "button", text: "Cancel", onclick: () => finish(null) }))));
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
        if (key) { setKey(dev, action.id, key); toast(`${action.name}: ${input.keyLabel(key, style)}`); }
      }
    }

    // ---------- checking it in game ----------
    function renderLive() {
      clear(live).append(el("h2", { text: "Check it in game" }),
        el("ol", { style: { margin: "0", paddingLeft: "1.3em", display: "grid", gap: "6px" } },
          el("li", { text: "Save to a mod, then Install mods (top right) with the game closed." }),
          el("li", { text: "Start the game, load your cat, and press a key you changed." }),
          el("li", { text: "If the game resets or won't load your save, restore the backup from the Mods page. The install made one first." })),
        el("p", { class: "note", text: "The game keeps these bindings in your save, but in testing it didn't use an edited one (moving Reset camera to T had no effect), so remaps may not take effect yet. Mouse look above doesn't depend on them." }));
    }

    await Promise.all([target.refresh(), loadMouseLook()]);
    render();
    renderLive();
  },
};
