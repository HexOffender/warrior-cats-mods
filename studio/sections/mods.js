// Mods: turn mods on and off, set priority, create mods, install, and manage save backups.
export default {
  title: "Mods",
  async mount(root, wc) {
    const { el, api, clear, toast, bus, confirmButton } = wc;
    const list = el("div", { class: "card" });
    const backupsBox = el("div", { class: "card" });
    const ingameBox = el("div", { class: "card" });
    const KIND_LABEL = { files: "replacement files", palette: "palette", controls: "controls", "mouse look": "mouse look", data: "game data",
      save: "save edits", code: "custom code", "studio page": "studio page", names: "names", cats: "your cat's colours",
      "cooked content": "cooked content (paks)" };

    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Mod manager" }),
        el("h1", { text: "Mods" }),
        el("p", { class: "note", text: "Each mod is a folder in mods/. Turn mods on or off here, then use Install mods (top right) with the game closed. When two mods change the same thing, the higher priority wins." })),
      list,
      ingameBox,
      newModCard(),
      el("div", { class: "card" },
        el("h2", { text: "Remove everything" }),
        el("p", { class: "note", text: "Removes the installed mod files from the game. Control remaps and save edits stay in your save; restore a backup below to undo those." }),
        el("div", { class: "row" }, confirmButton("Uninstall mods", "Click again to uninstall", () => bus.emit("run-task", { path: "/uninstall", title: "Uninstall" }), "btn danger"))),
      backupsBox);

    async function renderList() {
      const mods = await api.get("/mods");
      clear(list).append(el("div", { class: "row spread" }, el("h2", { text: `Your mods (${mods.length})` }),
        el("span", { class: "muted", text: `${mods.filter(m => m.enabled).length} on` })));
      if (!mods.length) list.append(el("p", { class: "empty", text: "No mods yet. Create one below, or save a palette, controls, game data or save edits from their pages." }));
      for (const m of mods) {
        const toggle = el("input", { type: "checkbox", id: `mod-on-${m.id}`, checked: m.enabled, "aria-label": `Turn ${m.name} on` });
        toggle.addEventListener("change", async () => {
          try { await api.patch(`/mods/${encodeURIComponent(m.id)}`, { enabled: toggle.checked }); toast(`${m.name} ${toggle.checked ? "on" : "off"}. Install mods to apply.`); bus.emit("mods-changed"); }
          catch (e) { toast(e.message, "bad"); toggle.checked = !toggle.checked; }
        });
        const prio = el("input", { type: "number", id: `mod-prio-${m.id}`, value: m.priority, style: { width: "5.5rem" }, "aria-label": `Priority of ${m.name}` });
        prio.addEventListener("change", async () => {
          try { await api.patch(`/mods/${encodeURIComponent(m.id)}`, { priority: Number(prio.value) || 0 }); bus.emit("mods-changed"); renderList(); }
          catch (e) { toast(e.message, "bad"); }
        });
        list.append(el("div", { class: "row", style: { borderTop: "1px solid var(--line)", paddingTop: "10px", alignItems: "flex-start" } },
          toggle,
          el("div", { style: { flex: "1", minWidth: "220px", display: "grid", gap: "4px" } },
            el("label", { for: `mod-on-${m.id}` }, el("strong", { text: m.name }), el("span", { class: "muted mono", text: `  ${m.id}` })),
            m.description ? el("span", { class: "muted", text: m.description }) : null,
            el("div", { class: "row" }, ...m.kinds.map(k => el("span", { class: "chip", text: KIND_LABEL[k] || k })))),
          el("div", { class: "field" }, el("label", { for: `mod-prio-${m.id}`, text: "Priority" }), prio)));
      }
    }

    function newModCard() {
      const id = el("input", { type: "text", id: "new-mod-id", placeholder: "e.g. my-tweaks", spellcheck: "false" });
      const name = el("input", { type: "text", id: "new-mod-name", placeholder: "My tweaks" });
      const desc = el("input", { type: "text", id: "new-mod-desc", placeholder: "What it changes" });
      return el("form", {
        class: "card", onsubmit: async e => {
          e.preventDefault();
          try {
            await api.post("/mods", { id: id.value.trim(), name: name.value.trim() || undefined, description: desc.value.trim(), enabled: true });
            toast(`Created ${id.value.trim()}`); id.value = name.value = desc.value = "";
            bus.emit("mods-changed"); renderList();
          } catch (err) { toast(err.message, "bad"); }
        },
      }, el("h2", { text: "New mod" }),
        el("div", { class: "row" },
          el("div", { class: "field" }, el("label", { for: "new-mod-id", text: "Folder name" }), id),
          el("div", { class: "field" }, el("label", { for: "new-mod-name", text: "Name" }), name),
          el("div", { class: "field", style: { flex: "1" } }, el("label", { for: "new-mod-desc", text: "Description" }), desc)),
        el("div", { class: "row" }, el("button", { class: "btn primary", type: "submit", text: "Create mod" }),
          el("span", { class: "note", text: "Then add content from the Palettes, Controls, Game data or Save pages." })));
    }

    async function renderBackups() {
      const names = await api.get("/backups");
      clear(backupsBox).append(
        el("div", { class: "row spread" }, el("h2", { text: "Save backups" }),
          el("button", { class: "btn", text: "Back up now", onclick: async () => {
            try { const r = await api.post("/backup"); toast(`Backed up to ${r.name}`); renderBackups(); } catch (e) { toast(e.message, "bad"); }
          } })),
        el("p", { class: "note", text: "A backup is made automatically before any install that edits your save. Restoring also backs up the current save first." }));
      if (!names.length) { backupsBox.append(el("p", { class: "empty", text: "No backups yet." })); return; }
      for (const n of names.slice(0, 12)) {
        backupsBox.append(el("div", { class: "row spread", style: { borderTop: "1px solid var(--line)", paddingTop: "8px" } },
          el("span", { class: "mono", text: n }),
          confirmButton("Restore", "Click again to restore", async () => {
            try { const r = await api.post("/restore", { name: n }); toast(`Restored ${r.restored.join(", ")}`); renderBackups(); }
            catch (e) { toast(e.message, "bad"); }
          }, "btn small")));
      }
    }

    // In game: the game's console, cheats at start and the mod menu's key (wcmods.json; wcmods/ingame.py).
    async function renderIngame() {
      let o;
      try { o = await api.get("/ingame"); } catch (e) { clear(ingameBox).append(el("p", { class: "note", text: e.message })); return; }
      const save = async change => {
        try { o = await api.patch("/ingame", change); toast("Saved."); } catch (e) { toast(e.message, "bad"); }
        renderIngame();
      };
      const cheats = el("input", { type: "checkbox", id: "ig-cheats", checked: o.cheats });
      cheats.addEventListener("change", () => save({ cheats: cheats.checked }));
      const consoleBox = el("input", { type: "checkbox", id: "ig-console", checked: o.console, disabled: !o.console_available });
      consoleBox.addEventListener("change", () => save({ console: consoleBox.checked }));
      const NAMES = { INS: "Insert", HOME: "Home", END: "End", DEL: "Delete", PAGE_UP: "Page Up", PAGE_DOWN: "Page Down" };
      const key = el("select", { id: "ig-key", "aria-label": "Mod menu key" },
        ...o.menu_keys.map(k => el("option", { value: k, text: NAMES[k] || k, selected: k === o.menu_key })));
      key.addEventListener("change", () => save({ menu_key: key.value }));
      const SIZES = [[0.8, "Small"], [1, "Normal"], [1.25, "Large"], [1.5, "Larger"], [1.8, "Largest"]];
      if (!SIZES.some(([v]) => v === o.menu_scale)) SIZES.push([o.menu_scale, `x${o.menu_scale}`]);
      const sizeSel = el("select", { id: "ig-size", "aria-label": "Mod menu size" },
        ...SIZES.map(([v, label]) => el("option", { value: String(v), text: label, selected: v === o.menu_scale })));
      sizeSel.addEventListener("change", () => save({ menu_scale: Number(sizeSel.value) }));
      clear(ingameBox).append(
        el("h2", { text: "In game" }),
        el("p", { class: "note", text: `${NAMES[o.menu_key] || o.menu_key} opens the mod menu in game (with UE4SS): your mods, what's nearby, live settings, and cheats.` }),
        el("div", { class: "row" }, el("label", { for: "ig-key", class: "lbl", text: "Mod menu key" }), key,
          el("label", { for: "ig-size", class: "lbl", text: "Menu size" }), sizeSel),
        el("label", { class: "row", for: "ig-cheats" }, cheats,
          el("strong", { text: "Cheats on when the game starts" }),
          el("span", { class: "muted", text: "The menu's Cheats page switches them on and off while you play: god mode, fly, ghost, cat size, game speed, console cheat commands." })),
        el("label", { class: "row", for: "ig-console" }, consoleBox,
          el("strong", { text: "Game console" }),
          el("span", { class: "muted", text: o.console_available ? "~ or F10 opens it, from the next time the game starts." : "Needs UE4SS." })),
        el("p", { class: "note", text: "The menu key, size and cheats setting apply when you next install mods. In game, A- and A+ in the menu's top bar change its size for the session." }));
    }

    const off = [bus.on("mods-changed", renderList), bus.on("installed", renderBackups)];
    await Promise.all([renderList(), renderBackups(), renderIngame()]);
    return { unmount() { off.forEach(f => f()); } };
  },
};
