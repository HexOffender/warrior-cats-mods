// Save: change values in your save (level, XP, inventory, settings...). Writes save.json in a mod.
export default {
  title: "Save",
  async mount(root, wc) {
    const { el, api, clear, toast, getPath } = wc;
    let save = null, edits = { set: {}, add: {} };
    try { save = await api.get("/save"); }
    catch (e) {
      root.append(el("div", { class: "error-card" }, el("h2", { text: "No save to edit yet" }), el("p", { text: e.message })));
      return;
    }
    const data = save.data;
    const slot = String(getPath(data, "Shared/General/CurrentCatSlot") ?? 0);
    const P = `${slot}/GameplayProgression`;
    const target = wc.modTarget({
      file: "save.json",
      onLoad: obj => { edits = { set: { ...(obj?.set || {}) }, add: JSON.parse(JSON.stringify(obj?.add || {})) }; delete edits.set._help; render(); },
      getValue: () => ({ _help: "Written by Clan Mod Studio. Applied to your save on install, after a backup.", ...edits }),
    });
    const quick = el("div", { style: { display: "grid", gap: "16px" } });
    const tree = el("div", { class: "card" });
    const out = wc.codePanel("save.json");

    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Save editor" }),
        el("h1", { text: "Save" }),
        el("p", { class: "note", text: `Editing cat slot ${slot}. Changes are saved as save.json in a mod and written to your save when you install (game closed, backup first). Experience rates live in Game data, not here.` })),
      el("div", { class: "banner" }, el("strong", { text: "Not yet confirmed in game" }),
        el("span", { text: "The save has a checksum whose formula isn't known; the tool keeps the original. If the game rejects an edited save, restore the backup from the Mods page." })),
      target.element, quick, tree, out.element);

    // ---------- helpers ----------
    const current = path => (path in edits.set ? edits.set[path] : getPath(data, path));
    function setValue(path, value) {
      if (JSON.stringify(value) === JSON.stringify(getPath(data, path))) delete edits.set[path];
      else edits.set[path] = value;
      target.markDirty(); out.set(edits); render();
    }
    function numberField(label, path, opts = {}) {
      const orig = getPath(data, path);
      if (orig === undefined) return null;
      const id = "sv-" + path.replace(/[^A-Za-z0-9]+/g, "-");
      const inp = el("input", { type: "number", id, value: current(path), step: opts.step || "1", min: opts.min ?? false, max: opts.max ?? false, style: { width: "8rem" } });
      inp.addEventListener("change", () => { const v = Number(inp.value); if (Number.isFinite(v)) setValue(path, opts.int === false ? v : Math.round(v)); });
      return el("div", { class: "field" }, el("label", { for: id, text: label }), inp,
        path in edits.set ? el("span", { class: "was", text: `was ${orig}` }) : null);
    }
    function toggleField(label, path) {
      const orig = getPath(data, path);
      if (typeof orig !== "boolean") return null;
      const id = "sv-" + path.replace(/[^A-Za-z0-9]+/g, "-");
      const inp = el("input", { type: "checkbox", id, checked: !!current(path) });
      inp.addEventListener("change", () => setValue(path, inp.checked));
      return el("label", { class: "row", for: id }, inp, label, path in edits.set ? el("span", { class: "chip warn" }, el("i"), "changed") : null);
    }

    // Stats are one string: "(Prowess=90.000000,Strength=85.000000,...)"
    function statsCard() {
      const path = `${P}/Stats`;
      const orig = getPath(data, path);
      if (typeof orig !== "string") return null;
      const parse = s => Object.fromEntries([...s.matchAll(/(\w+)=(-?[\d.]+)/g)].map(m => [m[1], Number(m[2])]));
      const vals = parse(current(path));
      const fields = Object.entries(vals).map(([k, v]) => {
        const id = `sv-stat-${k}`;
        const inp = el("input", { type: "number", id, value: v, step: "1", style: { width: "6.5rem" } });
        inp.addEventListener("change", () => {
          const next = { ...parse(current(path)), [k]: Number(inp.value) };
          setValue(path, "(" + Object.entries(next).map(([a, b]) => `${a}=${Number(b).toFixed(6)}`).join(",") + ")");
        });
        return el("div", { class: "field" }, el("label", { for: id, text: k }), inp);
      });
      return el("div", { class: "card" }, el("h3", { text: "Combat stats" }),
        el("p", { class: "note", text: "The game may recalculate these when you level up." }), el("div", { class: "row" }, ...fields));
    }

    function inventoryCard(items) {
      const path = `${P}/State/Inventory`;
      const inv = getPath(data, path);
      if (!inv || typeof inv !== "object") return null;
      const added = edits.add[path] || {};
      const rows = Object.entries({ ...inv, ...added }).map(([tag, qty]) => {
        const id = "sv-inv-" + tag.replace(/[^A-Za-z0-9]+/g, "-");
        const isNew = !(tag in inv);
        const val = isNew ? added[tag] : current(`${path}/${tag}`);
        const inp = el("input", { type: "number", id, min: "0", value: val, style: { width: "6rem" } });
        inp.addEventListener("change", () => {
          const v = Math.max(0, Math.round(Number(inp.value) || 0));
          if (isNew) { (edits.add[path] ||= {})[tag] = v; target.markDirty(); out.set(edits); render(); }
          else setValue(`${path}/${tag}`, v);
        });
        return el("div", { class: "row", style: { justifyContent: "space-between" } },
          el("label", { for: id, class: "mono", style: { fontSize: "0.85rem" }, text: tag.replace("Gameplay.Inventory.", "") }),
          el("span", { class: "row" }, inp, isNew ? el("button", { class: "btn ghost small", text: "Remove", "aria-label": `Remove ${tag.replace("Gameplay.Inventory.", "")}`, onclick: () => { delete edits.add[path][tag]; if (!Object.keys(edits.add[path]).length) delete edits.add[path]; target.markDirty(); out.set(edits); render(); } }) : null));
      });
      const pick = el("select", { id: "sv-inv-add", "aria-label": "Item to add" }, ...items.filter(t => !(t in inv) && !(t in added)).map(t => el("option", { value: t, text: t.replace("Gameplay.Inventory.", "") })));
      const qty = el("input", { type: "number", id: "sv-inv-qty", min: "1", value: "1", style: { width: "5rem" }, "aria-label": "Quantity" });
      return el("div", { class: "card" }, el("h3", { text: "Inventory" }), ...rows,
        rows.length ? null : el("p", { class: "muted", text: "Your cat isn't carrying anything." }),
        pick.options.length ? el("div", { class: "row" }, el("span", { class: "lbl", text: "Add" }), pick, qty,
          el("button", { class: "btn small", text: "Add item", onclick: () => { (edits.add[path] ||= {})[pick.value] = Math.max(1, Number(qty.value) || 1); target.markDirty(); out.set(edits); render(); } })) : null);
    }

    let itemTags = [];
    try {
      const tables = await Promise.all(["Consumables.csv", "BarteringCost.csv"].map(n => api.get(`/game/data/${n}`).catch(() => null)));
      itemTags = [...new Set(tables.filter(Boolean).flatMap(t => t.rows.map(r => r[0])).filter(t => t.startsWith("Gameplay.Inventory.")))].sort();
    } catch (e) { /* optional */ }

    // ---------- tree ----------
    function treeNode(value, path, label) {
      if (value && typeof value === "object") {
        const keys = Object.keys(value);
        const d = el("details", {}, el("summary", {}, el("span", { class: "mono", text: label }), el("span", { class: "muted", text: `  ${Array.isArray(value) ? "list" : "group"} · ${keys.length}` })));
        let built = false;
        d.addEventListener("toggle", () => {
          if (!d.open || built) return;
          built = true;
          const box = el("div", { style: { paddingLeft: "16px", display: "grid", gap: "2px" } });
          for (const k of keys.slice(0, 400)) box.append(treeNode(value[k], path ? `${path}/${k}` : k, k));
          if (keys.length > 400) box.append(el("p", { class: "muted", text: `${keys.length - 400} more not shown` }));
          d.append(box);
        });
        return d;
      }
      if (value === null) {
        // An empty value has no type to edit safely; typing here would store a string the game doesn't expect.
        return el("div", { class: "row", style: { gap: "10px" } }, el("span", { class: "mono", style: { fontSize: "0.82rem", minWidth: "12rem" }, text: label }),
          el("span", { class: "muted", text: "empty (not editable here)" }));
      }
      const id = "sv-tree-" + path.replace(/[^A-Za-z0-9]+/g, "-");
      const cur = current(path);
      let control;
      if (typeof value === "boolean") {
        control = el("input", { type: "checkbox", id, checked: !!cur });
        control.addEventListener("change", () => setValue(path, control.checked));
      } else if (typeof value === "number") {
        control = el("input", { type: "number", id, value: cur, step: "any", style: { width: "10rem" } });
        control.addEventListener("change", () => { const v = Number(control.value); if (Number.isFinite(v)) setValue(path, Number.isInteger(value) ? Math.round(v) : v); });
      } else {
        control = el("input", { type: "text", id, value: cur ?? "", style: { width: "min(100%, 34rem)" } });
        control.addEventListener("change", () => setValue(path, control.value));
      }
      return el("div", { class: "row", style: { gap: "10px" } }, el("label", { for: id, class: "mono", style: { fontSize: "0.82rem", minWidth: "12rem" }, text: label }), control,
        path in edits.set ? el("span", { class: "chip warn", title: `was ${JSON.stringify(value)}` }, el("i"), "changed") : null);
    }

    function render() {
      clear(quick).append(
        el("div", { class: "card" }, el("h2", { text: "Your cat" }),
          el("div", { class: "row", style: { alignItems: "flex-start", gap: "18px" } },
            numberField("Level", `${P}/Level`, { min: 1 }),
            numberField("Experience", `${P}/Experience`, { min: 0 }),
            numberField("Health", `${P}/Gameplay.Combat.Character.Cat.Player/State/Health`, { min: 0 }),
            numberField("Stamina", `${P}/Gameplay.Combat.Character.Cat.Player/State/Stamina`, { min: 0 }),
            numberField("Fresh-kill pile", `${P}/FreshKill/Value`, { min: 0 }))),
        statsCard(),
        inventoryCard(itemTags),
        el("div", { class: "card" }, el("h2", { text: "Settings" }),
          el("div", { class: "row", style: { gap: "18px" } },
            ...["Minimap", "Subtitles", "InjurySystem", "ToonShader", "VSync", "HDR"].map(k => toggleField(k === "InjurySystem" ? "Injury system" : k === "ToonShader" ? "Toon shader" : k, `Shared/SettingsData/${k}`))),
          el("div", { class: "row", style: { gap: "18px" } },
            ...[["Master volume", "MasterVolume"], ["Music volume", "MusicVolume"], ["Sound volume", "SoundVolume"], ["Voice volume", "VoiceVolume"]]
              .map(([l, k]) => numberField(l, `Shared/SettingsData/${k}`, { step: "0.05", min: 0, max: 1, int: false })))));
      clear(tree).append(el("h2", { text: "Everything else" }),
        el("p", { class: "note", text: "Browse the whole save. Open a group to see its values; change a value to add it to this mod's edits." }),
        treeNode(data, "", "save"));
      tree.querySelector("details").open = true;
      out.set(edits);
    }

    await target.refresh();
  },
};
