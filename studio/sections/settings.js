// Settings and repair: the in-game mod menu's key, button and size, the game's console and whether mods may
// run code (Options), your save backups, removed mods and repairs, and starting an empty mod of your own. The Mods page is for getting set up,
// adding mods and switching them on and off.
export default {
  title: "Settings and repair",
  async mount(root, wc) {
    const { el, api, clear, toast, bus, confirmButton, announce } = wc;
    let options = null, settings = null;
    const optionsBox = el("div", { class: "card" });
    const repairBox = el("div", { class: "card" });
    const makeBox = el("div", { class: "card" });

    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Your mods" }),
        el("h1", { text: "Settings and repair" }),
        el("p", { class: "note", text: "The mod menu, the game's console and mods that run code, your save backups, mods you removed, and a mod of your own to start from." })),
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
          el("span", { class: "muted", text: options.console_available ? "~ or F10 opens it, from the next time the game starts." : "Needs UE4SS." })));
      }
      if (settings) {
        const code = el("input", { type: "checkbox", id: "allow-code", checked: settings.allow_code_mods });
        const setCode = async on => {
          try {
            settings = await api.patch("/settings", { allow_code_mods: on });
            toast(on ? "Mods that run code are allowed. Apply to game to use them." : "Mods that run code are off.");
            await refresh();
            // The side bar's pages change (the Console, mods' own pages): the shell redraws it, without reloading
            // the page, so what's unsaved on other pages stays.
            bus.emit("sections-changed");
            bus.emit("mods-changed", { from: "settings" });
          }
          catch (e) { toast(e.message, "bad"); }
        };
        const warn = el("div", { class: "banner", hidden: true },
          el("strong", { text: "Only for mods from people you trust" }),
          el("span", { text: "Some mods carry code: Python that runs on your computer when you apply mods, or scripts that run in the game. Code can do anything your account can, so allow it only if you trust every such mod you've added." }),
          el("div", { class: "row" },
            el("button", { class: "btn danger", text: "Allow mods that run code", onclick: () => setCode(true) }),
            el("button", { class: "btn ghost", text: "Cancel", onclick: () => { code.checked = false; warn.hidden = true; code.focus(); } })));
        code.addEventListener("change", () => {
          if (code.checked) { warn.hidden = false; code.checked = false; announce(`${warn.children[0].textContent}. ${warn.children[1].textContent}`); } else setCode(false);
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
        const pad = el("select", { id: "ig-pad" }, ...choices(options.pads || [], options.pad, v => v).map(([v, label]) => el("option", { value: v, text: label, selected: v === options.pad })));
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
          el("p", { class: "note", text: "The in-game menu lists your mods, and mods add their pages to it; Menu pages (Get set up, on the Mods page) adds your cat, the world, quests, fights and cheats. In game, A- and A+ in its top bar change its size until the game closes. Opened from a controller, the game pauses while it's open, and the same button or B closes it. Needs UE4SS." }));
      }
    }

    // ---------- backups and repair ----------
    async function renderRepair() {
      clear(repairBox).append(el("h2", { text: "Backups and repair" }));
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
          el("button", { class: "btn small", text: "Back up now", onclick: async () => {
            try { const r = await api.post("/backup"); toast(`Backed up to ${r.name}`); renderRepair(); } catch (e) { toast(e.message, "bad"); }
          } })),
        el("p", { class: "note", text: "Your save is backed up before anything that changes it. Restoring backs up the save you have first." }));
      if (!backups.length) saves.append(el("p", { class: "muted", text: "No backups yet." }));
      for (const n of backups.slice(0, 10)) {
        saves.append(el("div", { class: "row spread line" }, el("span", { class: "mono", text: n }),
          confirmButton("Restore", "Press again to restore", async () => {
            try { const r = await api.post("/restore", { name: n }); toast(`Restored ${r.restored.join(", ")}`); renderRepair(); }
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
          ...takeOut()));
    }

    // "Take all mods out of the game": first, the cats in the save whose names only the mods give (they'd show as
    // <MISSING STRING TABLE ENTRY>). With none, two presses take the mods out, as with any button that can't be
    // undone here; with some, the page says which and offers the Names page instead.
    function takeOut() {
      const label = "Take all mods out of the game", armedLabel = "Press again to take them out";
      const b = el("button", { class: "btn small danger", type: "button", text: label });
      const ask = el("div", { class: "banner", role: "group", "aria-label": "Cats that would lose their names", hidden: true });
      let armed = null;
      const disarm = () => { clearTimeout(armed); armed = null; b.textContent = label; b.classList.remove("armed"); };
      const run = () => { ask.hidden = true; bus.emit("run-task", { path: "/uninstall", title: "Take mods out" }); };
      b.addEventListener("click", async () => {
        if (armed) { disarm(); run(); return; }
        let losing = [];
        try { losing = (await api.get("/names/losing")).losing || []; } catch (e) { /* asked as before */ }
        if (losing.length) {
          const n = losing.length, one = n === 1;
          const said = `${one ? "A cat" : `${n} cats`} in your save ${one ? "has a name" : "have names"} only your mods give (${catsInWords(losing)}). After this ${one ? "it shows" : "they show"} as <MISSING STRING TABLE ENTRY> until you put a backup of your save back, or give ${one ? "it a game name" : "them game names"} on the Names page and Apply first.`;
          clear(ask).append(el("span", { text: said }), el("div", { class: "row" },
            el("button", { class: "btn danger small", type: "button", text: "Take them out anyway", onclick: run }),
            el("a", { class: "btn small", href: "#names", text: "Open Names" })));
          ask.hidden = false;
          announce(said);
          ask.querySelector("button").focus();
          return;
        }
        b.textContent = armedLabel;
        b.classList.add("armed");
        announce(armedLabel);
        armed = setTimeout(disarm, 6000);
      });
      b.addEventListener("blur", () => { if (armed) disarm(); });
      return [el("div", { class: "row" }, b,
        el("span", { class: "muted", text: "Your mods stay here, and key changes come out with them. Save edits stay in your save; restore a save backup to undo those." })), ask];
    }
    // "your cat (Sparkle), Wrenheart, the cat at RiverClan · Warrior · 3 and 2 more", from GET /names/losing.
    function catsInWords(cats) {
      const words = cats.slice(0, 3).map(c => c.player ? (c.name ? `your cat (${c.name})` : "your cat")
        : c.name || `the cat at ${String(c.where || "").split("/").join(" · ")}`);
      if (cats.length > 3) words.push(`${cats.length - 3} more`);
      return words.length === 1 ? words[0] : `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
    }

    // ---------- making your own ----------
    // The Make pages' names come from the shell's list (/info), so this stays true as pages are added.
    let makePages = [];
    function renderMake() {
      const id = el("input", { type: "text", id: "new-mod-id", placeholder: "e.g. my-tweaks", spellcheck: "false" });
      const name = el("input", { type: "text", id: "new-mod-name", placeholder: "My tweaks" });
      const desc = el("input", { type: "text", id: "new-mod-desc", placeholder: "What it changes" });
      const pages = makePages.length ? ` (${makePages.join(", ")})` : "";
      clear(makeBox).append(el("h2", { text: "Make your own mod" }),
        el("p", { class: "note", text: `The pages under Make mods${pages} save into a mod of yours, My mods unless you pick another. Start an empty one here, or from those pages. Save as .zip (under a mod's More) packs one up to share.` }),
        el("form", { class: "row", onsubmit: async e => {
          e.preventDefault();
          try {
            await api.post("/mods", { id: id.value.trim(), name: name.value.trim() || undefined, description: desc.value.trim(), enabled: true });
            toast(`Made ${id.value.trim()}`); id.value = name.value = desc.value = "";
            bus.emit("mods-changed", { from: "settings" });
          } catch (err) { toast(err.message, "bad"); }
        } },
          el("div", { class: "field" }, el("label", { for: "new-mod-id", text: "Folder name" }), id),
          el("div", { class: "field" }, el("label", { for: "new-mod-name", text: "Name" }), name),
          el("div", { class: "field", style: { flex: "1" } }, el("label", { for: "new-mod-desc", text: "Description" }), desc),
          el("button", { class: "btn", type: "submit", text: "Make it", style: { alignSelf: "end" } })));
    }


    async function refresh() {
      let shell = null;
      try { [options, settings, shell] = await Promise.all([api.get("/ingame").catch(() => null), api.get("/settings"), api.get("/info").catch(() => null)]); }
      catch (e) { toast(e.message, "bad"); }
      if (shell) {
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
