// Settings and repair: the in-game mod menu's key, button and size, the game's console and whether mods may
// run code (Options), your save backups, removed mods and repairs, and starting an empty mod of your own. The Mods page is for getting set up,
// adding mods and switching them on and off.
export default {
  title: "Settings and repair",
  async mount(root, wc) {
    const { el, api, clear, toast, bus, confirmButton, announce } = wc;
    let options = null, settings = null, codeMods = [], saveFound = true;
    const optionsBox = el("div", { class: "card" });
    const repairBox = el("div", { class: "card" });
    const makeBox = el("div", { class: "card" });

    root.append(
      wc.pageHead({ eyebrow: "Your mods", title: "Settings and repair", help: "help:settings",
        lede: "The mod menu, the game's console and mods that run code, your save backups, mods you removed, and a mod of your own to start from." }),
      optionsBox, repairBox, makeBox);

    function renderOptions() {
      clear(optionsBox).append(el("h2", { text: "Options" }));
      if (options) {
        const consoleBox = el("input", { type: "checkbox", id: "ig-console", checked: options.console, disabled: !options.console_available });
        consoleBox.addEventListener("change", async () => {
          try { options = await api.patch("/ingame", { console: consoleBox.checked }); toast("Saved."); } catch (e) { toast(e.message, "bad"); }
          renderOptions();
        });
        optionsBox.append(el("label", { class: "row", for: "ig-console" }, consoleBox, el("strong", { text: "Game console" }),
          el("span", { class: "muted", text: options.console_available ? "~ or F10 opens it, from the next time the game starts."
            : options.console_why === "no console mod in it" ? "The script loader here has no console mod in it: installing it again (Get set up, on the Mods page) puts it in."
              : "Needs the script loader (Get set up, on the Mods page)." })));
      }
      if (settings) {
        const code = el("input", { type: "checkbox", id: "allow-code", checked: settings.allow_code_mods });
        const setCode = async on => {
          try {
            settings = await api.patch("/settings", { allow_code_mods: on });
            toast(on ? "Allowed. Press Apply to game (top right) to put them in." : "Mods that run code are off. Apply to game takes them out of the game.");
            await refresh();
            // The side bar's pages change (the Console, mods' own pages): the shell redraws it, without reloading
            // the page, so what's unsaved on other pages stays.
            bus.emit("sections-changed");
            bus.emit("mods-changed", { from: "settings" });
          }
          catch (e) { toast(e.message, "bad"); }
        };
        // The same warning Get set up shows (wc.codeWarning), naming your mods that run code.
        const warn = wc.codeWarning(codeMods);
        warn.hidden = true;
        warn.append(el("div", { class: "row" },
          el("button", { class: "btn danger", text: "Allow mods that run code", onclick: () => setCode(true) }),
          el("button", { class: "btn ghost", text: "Cancel", onclick: () => { code.checked = false; warn.hidden = true; code.focus(); } })));
        code.addEventListener("change", () => {
          if (code.checked) { warn.hidden = false; code.checked = false; announce(`Only for mods from people you trust. ${wc.CODE_WARNING}`); } else setCode(false);
        });
        optionsBox.append(el("label", { class: "row", for: "allow-code" }, code, el("strong", { text: "Allow mods that run code" }),
          el("span", { class: "muted", text: "In-game scripts, build steps and studio pages that mods bring. Off unless you turn it on." })), warn);
      }
      if (options) {
        // The mod menu's window (wcmods/menusettings.py, in wcmods.json), with the choices from wcmods as
        // [value, label] pairs. Any Unreal key name works for the pad in wcmods.json, and any size within its
        // limits: one the lists haven't got shows as it is.
        const save = async change => {
          try {
            options = await api.patch("/ingame", change);
            toast("cheats" in change ? "Saved. It applies from the next time the game starts." : "Saved. Apply to game to use it.");
            bus.emit("mods-changed", { from: "settings" });
          }
          catch (e) { toast(e.message, "bad"); }
          renderOptions();
        };
        const choices = (list, value, label) => list.some(([v]) => v === value) ? list : [...list, [value, label(value)]];
        const key = el("select", { id: "ig-key" }, ...options.keys.map(([v, label]) => el("option", { value: v, text: label, selected: v === options.key })));
        key.addEventListener("change", () => save({ key: key.value }));
        const pad = el("select", { id: "ig-pad" }, ...choices(options.pads || [], options.pad, v => wc.input.keyLabel(v)).map(([v, label]) => el("option", { value: v, text: label, selected: v === options.pad })));
        pad.addEventListener("change", () => save({ pad: pad.value }));
        const size = el("select", { id: "ig-size" }, ...choices(options.sizes || [], options.size, v => `x${v}`).map(([v, label]) => el("option", { value: String(v), text: label, selected: v === options.size })));
        size.addEventListener("change", () => save({ size: Number(size.value) }));
        // Menu pages' setting (its settings.json), while that mod is in your mods.
        const cheats = options.cheats === null ? null : el("input", { type: "checkbox", id: "ig-cheats", checked: options.cheats });
        if (cheats) cheats.addEventListener("change", () => save({ cheats: cheats.checked }));
        optionsBox.append(
          el("h3", { text: "The mod menu" }),
          el("div", { class: "row" }, el("label", { for: "ig-key", class: "lbl", text: "Opens with" }), key,
            el("label", { for: "ig-pad", class: "lbl", text: "or on a controller" }), pad,
            el("label", { for: "ig-size", class: "lbl", text: "Size" }), size),
          cheats ? el("label", { class: "row", for: "ig-cheats" }, cheats, el("strong", { text: "Cheats on when the game starts" }),
            el("span", { class: "muted", text: "Menu pages' Cheats page switches them on and off while you play." })) : null,
          el("p", { class: "note", text: "The in-game menu lists your mods, and mods add their pages to it; Menu pages adds your cat, the world, quests, fights and cheats (the Mods page's card of the mods that go with Clan Mod Studio adds it). In game, A- and A+ in its top bar change its size until the game closes. Opened from a controller, the game pauses while it's open, and the same button or B closes it. Needs the script loader." }));
      }
    }

    // ---------- backups and repair ----------
    async function renderRepair() {
      // The game's last crash since the last Apply, at the top, with the mod it was in when one was.
      let crash = null;
      try { crash = (await api.get("/crash")).crash; } catch (e) { /* no card */ }
      clear(repairBox).append(el("h2", { text: "Backups and repair" }), crash ? wc.crashCard(crash) : null);
      if (settings && settings.data_dir) {
        repairBox.append(el("div", { class: "row" },
          el("span", { class: "muted" }, "Your mods, settings and backups are in ", el("span", { class: "mono", text: settings.data_dir }),
            ", outside Clan Mod Studio's folder, so updating it leaves them alone."),
          el("button", { class: "btn small", text: "Open the folder", onclick: async () => {
            try { await api.post("/open", { what: "data" }); } catch (e) { toast(e.message, "bad"); }
          } })));
      }
      let backups = [], removed = [];
      try { [backups, removed] = await Promise.all([api.get("/backups"), api.get("/mods/removed")]); } catch (e) { /* shown empty */ }
      const saves = el("div", { class: "stack" },
        el("div", { class: "row spread" }, el("h3", { text: "Save backups" }),
          el("div", { class: "row" },
            saveFound ? null : el("span", { class: "muted", text: "No save yet: start the game once and get into the forest." }),
            el("button", { class: "btn small", text: "Back up now", disabled: !saveFound, onclick: async () => {
              try { const r = await api.post("/backup"); toast(`Backed up: ${r.label}.`); renderRepair(); } catch (e) { toast(e.message, "bad"); }
            } }))),
        el("p", { class: "note", text: "Your save is backed up before anything that changes it. Restoring backs up the save you have first." }));
      if (!backups.length) saves.append(el("p", { class: "muted", text: "No backups yet." }));
      for (const b of backups.slice(0, 10)) {
        saves.append(el("div", { class: "row spread line" }, el("span", { title: b.name, text: b.label }),
          confirmButton("Restore", "Press again to restore", async () => {
            try {
              const r = await api.post("/restore", { name: b.name });
              // Restoring is how save edits are undone: nothing asks to apply again, but the next Apply would.
              toast("Put your save back as it was." + (r.before_label ? ` The one you had is kept too (${r.before_label}).` : "")
                + " The next Apply puts your mods' save changes back; to keep them out, turn those mods off first.");
              renderRepair();
            }
            catch (e) { toast(e.message, "bad"); }
          }, "btn small")));
      }
      const gone = el("div", { class: "stack" }, el("h3", { text: "Removed and replaced mods" }));
      if (!removed.length) gone.append(el("p", { class: "muted", text: "None." }));
      for (const r of removed.slice(0, 10)) {
        gone.append(el("div", { class: "row spread line" },
          el("span", {}, el("strong", { text: r.title }), el("span", { class: "muted", text: ` ${r.why} ${r.when.replace("T", " ")}` })),
          el("button", { class: "btn small", text: "Put it back", onclick: async () => {
            try { await api.post("/mods/restore", { name: r.name }); toast(`${r.title} is back (off).`); bus.emit("mods-changed", { from: "settings" }); renderRepair(); }
            catch (e) { toast(e.message, "bad"); }
          } })));
      }
      repairBox.append(saves, gone,
        el("div", { class: "stack" }, el("h3", { text: "If something's wrong" }),
          el("div", { class: "row" },
            el("button", { class: "btn small", text: "Check my mods", onclick: () => bus.emit("run-task", { path: "/build", title: "Check mods" }) }),
            el("span", { class: "muted", text: "Builds them without installing, to see what each one does and any problems." })),
          el("div", { class: "row" },
            confirmButton("Take all mods out of the game", "Press again to take them out", () => bus.emit("run-task", { path: "/uninstall", title: "Take mods out" }), "btn small danger"),
            el("span", { class: "muted", text: "Your mods stay here. Control remaps and save edits stay in your save; restore a save backup to undo those. To play without mods, start the game from Steam: Play here puts your mods back in." }))));
    }

    // ---------- making your own ----------
    // The Make pages' names come from the shell's list (/info), so this stays true as pages are added.
    let makePages = [];
    function renderMake() {
      // A name is all it takes: the folder is made from it (GET /mods/new-id), and shown under the box.
      const name = el("input", { type: "text", id: "new-mod-name", placeholder: "My tweaks" });
      const folder = el("span", { class: "muted", id: "new-mod-folder", "aria-live": "polite" });
      let asking = 0;
      name.addEventListener("input", async () => {
        const mine = ++asking, typed = name.value.trim();
        if (!typed) { folder.textContent = ""; return; }
        try {
          const r = await api.get(`/mods/new-id?name=${encodeURIComponent(typed)}`);
          if (mine === asking) folder.textContent = `Its folder: mods/${r.id}`;
        } catch (e) { /* said when it's made */ }
      });
      const pages = makePages.length ? ` (${makePages.join(", ")})` : "";
      clear(makeBox).append(el("h2", { text: "Make your own mod" }),
        el("p", { class: "note", text: `The pages under Make mods${pages} save into a mod of yours, My mods unless you pick another. Start an empty one here, or from those pages. Save as .zip (under a mod's More) packs one up to share.` }),
        el("form", { class: "row", onsubmit: async e => {
          e.preventDefault();
          if (!name.value.trim()) { toast("Give it a name", "bad"); name.focus(); return; }
          try {
            const m = await api.post("/mods", { name: name.value.trim(), enabled: true });
            toast(`Made ${m.name}, in mods/${m.id}. Pick it in the Editing mod bar on any Make page.`);
            name.value = "";
            folder.textContent = "";
            bus.emit("mods-changed", { from: "settings" });
          } catch (err) { toast(err.message, "bad"); }
        } },
          el("div", { class: "field", style: { flex: "1" } }, el("label", { for: "new-mod-name", text: "Name" }), name, folder),
          el("button", { class: "btn", type: "submit", text: "Make it", style: { alignSelf: "end" } })));
    }


    async function refresh() {
      let shell = null;
      let found = [], extra = { addons: [] };
      try {
        [options, settings, shell, found, extra] = await Promise.all([api.get("/ingame").catch(() => null), api.get("/settings"),
          api.get("/info").catch(() => null), api.get("/mods").catch(() => []), api.get("/addons").catch(() => ({ addons: [] }))]);
      }
      catch (e) { toast(e.message, "bad"); }
      // Your mods that run code, for the warning; one that goes with Clan Mod Studio says what it's for.
      codeMods = found.filter(m => m.code).map(m => ({ ...m, about: (extra.addons.find(a => a.id === m.id) || {}).about }));
      if (shell) {
        saveFound = !!shell.save_found;
        const titles = shell.sections.filter(s => (s.group || "make") === "make" && !s.from_mod && s.id !== "console").map(s => s.title);
        if (titles.join("|") !== makePages.join("|")) { makePages = titles; renderMake(); }
      }
      renderOptions();
      await renderRepair();
    }

    renderMake();
    const off = [
      bus.on("installed", () => renderRepair()),
      bus.on("mods-changed", d => { if (!d || d.from !== "settings") renderRepair(); }),
    ];
    await refresh();
    return { unmount() { off.forEach(f => f()); } };
  },
};
