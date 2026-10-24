// Mods: get set up (the first time), add mods you've downloaded, switch them on and off, and apply them
// to the game. The mod menu is a mod here too (its settings are on its card); mods say in mod.json what
// they need ("requires") or work with ("uses"). Backups, removed mods and repairs are at the bottom.
export default {
  title: "Mods",
  async mount(root, wc) {
    const { el, api, clear, toast, bus, confirmButton, announce } = wc;
    const KIND = {
      files: "Replaces game files", "cooked content": "New models or textures", "mod menu": "The in-game menu",
      palette: "Colours", controls: "Controls", "mouse look": "Mouse look", data: "Game rules and numbers",
      names: "Cat names", cats: "Your cat's colours", save: "Changes your save", "in-game script": "In-game script",
      code: "Build step (code)", "studio page": "Studio page",
    };
    const MENU = "mod-menu";
    let mods = [], filter = "all", search = "", options = null, settings = null;
    const open = new Set();   // mod cards with "More" open

    const setupBox = el("div");
    const updateBox = el("div");
    const changesBox = el("div");
    const addBox = el("div", { class: "card" });
    const listBox = el("div", { class: "card" });
    const optionsBox = el("div", { class: "card" });
    const repairBox = el("details", { class: "card fold" });
    const makeBox = el("details", { class: "card fold" });

    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Your mods" }),
        el("h1", { text: "Mods" }),
        el("p", { class: "note", text: "Add mods you've downloaded, switch them on or off, then press Play (top right)." })),
      setupBox, updateBox, changesBox, addBox, listBox, optionsBox, repairBox, makeBox);

    const nameOf = id => (mods.find(m => m.id === id) || {}).name || id;

    // ---------- after a game update (wcmods/gamebuild.py) ----------
    let update = null;   // what wcmods found the update changed, once asked (it takes a while the first time)
    let asking = null;   // that question, asked once however often the page redraws
    let drawing = 0;     // the latest redraw: an older one that finishes later draws nothing
    async function renderUpdate() {
      const mine = ++drawing;
      let info;
      try { info = await api.get("/info"); } catch (e) { return; }
      if (mine !== drawing) return;
      clear(updateBox);
      const b = info.game_build || {};
      if (!b.build || b.verified) return;
      const left = mods.filter(m => m.enabled && m.outdated && !m.outdated.allowed);
      const lines = [];
      if (!update) {
        lines.push(el("span", { class: "muted", text: "Checking what the update changed in the values wcmods reads (under a minute, once)…" }));
        asking ||= api.get("/game/update").then(u => { update = u; }, e => { update = { status: "failed", error: e.message }; })
          .finally(() => renderUpdate());
      } else if (update.status === "failed") {
        lines.push(el("span", { text: `Couldn't check what the update changed (${update.error}), so the values wcmods reads stay off until it's updated.` }));
      } else if (update.status === "unknown") {
        lines.push(el("span", { text: "Couldn't find the game's exe to check what the update changed, so the values wcmods reads stay off until it's updated." }));
      } else if (update.status === "adapted") {
        lines.push(el("span", { text: update.moved.length
          ? `wcmods followed the values the update moved (${update.moved.join(", ")}), so its own parts and the mod menu keep working.`
          : "Nothing wcmods reads moved, so its own parts and the mod menu keep working." }));
      } else if (update.status === "partial") {
        lines.push(el("span", { text: `These values couldn't be found again, so what uses them is off until wcmods is updated: ${update.lost.join(", ")}.` }));
      }
      if (left.length) {
        lines.push(el("span", { text: `${left.length} of your mods ${left.length > 1 ? "were" : "was"} made for the older version, so ${left.length > 1 ? "they're" : "it's"} left out until updated: ${left.map(m => m.name).join(", ")}. Each one's card has "Use it anyway…".` }));
      }
      updateBox.append(el("div", { class: "banner" }, el("strong", { text: `The game updated (build ${b.build})` }), ...lines));
    }

    async function allowOutdated(m, on) {
      try {
        await api.post(`/mods/${encodeURIComponent(m.id)}/allow-outdated`, { on });
        toast(on ? `${m.name} will be used on this version of the game. Press Play to put it in.` : `${m.name} is left out again.`);
        await refresh();
        // The card's button changed ("Stop using it" for "Use it anyway"): keep the keyboard's place on it.
        listBox.querySelector(`[data-focus="allow:${CSS.escape(m.id)}"]`)?.focus();
      } catch (e) { toast(e.message, "bad"); }
    }

    // ---------- getting set up (wcmods/onboarding.py): shown until every step is done ----------
    let loaderNote = "";
    async function renderSetup() {
      let s;
      try { s = await api.get("/setup"); } catch (e) { clear(setupBox); return; }
      if (s.save.ok && !s.backup.ok) {
        // A safety copy of the save, the first time there's one.
        try {
          const b = await api.post("/setup/backup");
          if (b.name) toast("Made a safety copy of your save.");
          s = await api.get("/setup");
        } catch (e) { /* the step stays undone */ }
      }
      if (s.inbox && !inboxShown) showInbox();
      clear(setupBox);
      if (s.done) return;
      const step = (ok, title, ...body) => el("li", { class: "step" + (ok ? " done" : "") },
        el("span", { class: "tick", "aria-hidden": "true", text: ok ? "\u2713" : "" }),
        el("div", { class: "step-body" }, el("strong", {}, el("span", { class: "sr-only", text: ok ? "Done: " : "To do: " }), title), ...body));
      const steps = el("ol", { class: "steps" });

      if (s.game.ok) {
        steps.append(step(true, "Found the game", el("span", { class: "muted mono", text: s.game.dir })));
      } else {
        const dir = el("input", { type: "text", id: "setup-game", "aria-label": "The game's folder", spellcheck: "false", placeholder: "D:\\SteamLibrary\\steamapps\\common\\Warrior Cats Clans of the Forest", style: { flex: "1", minWidth: "260px" } });
        steps.append(step(false, "Where's the game?",
          el("span", { class: "muted", text: "Clan Mod Studio couldn't find it in your Steam games. In Steam, right-click Warrior Cats: Clans of the Forest, choose Manage, then Browse local files, and copy the address at the top of that window into here." }),
          el("div", { class: "row" }, dir, el("button", { class: "btn primary", text: "Use this folder", onclick: async () => {
            try { await api.post("/setup/game", { dir: dir.value }); toast("Found the game."); location.reload(); }
            catch (e) { toast(e.message, "bad"); }
          } }))));
      }

      if (!s.save.ok) {
        steps.append(step(false, "Start the game once",
          el("span", { class: "muted", text: "So it makes your save. Press Play (top right), get into the forest, quit the game, and come back here. Clan Mod Studio then makes a safety copy of the save before any mod touches it." })));
      } else {
        steps.append(step(s.backup.ok, s.backup.ok ? "Your save is backed up" : "Back up your save",
          el("span", { class: "muted", text: s.backup.ok ? "If a mod ever spoils it, Backups and repair (at the bottom) puts it back." : "Couldn't make the copy; try Back up now under Backups and repair." })));
      }

      if (s.loader.ok) {
        steps.append(step(true, "The script loader is installed", el("span", { class: "muted", text: "UE4SS: the mod menu and most mods run on it." })));
      } else {
        const blocked = !s.game.ok ? "Find the game first." : s.running ? "Close the game first." : "";
        const input = el("input", { type: "file", accept: ".zip,application/zip", hidden: true });
        const install = async file => {
          loaderNote = file ? `Installing ${file.name}…` : "Downloading UE4SS from GitHub and installing it…";
          renderSetup();
          try {
            const r = file ? await api.upload("/setup/loader", file) : await api.post("/setup/loader");
            toast(`The script loader is installed (${r.result.from}).`);
            loaderNote = "";
            bus.emit("mods-changed", { from: "setup" });
          } catch (e) { loaderNote = ""; toast(e.message, "bad"); }
          renderSetup();
        };
        input.addEventListener("change", () => input.files[0] && install(input.files[0]));
        steps.append(step(false, "Install the script loader",
          el("span", { class: "muted", text: "Most mods need it: the mod menu, colours on your own cat, mouse look and in-game scripts. It's UE4SS, free and open source. Clan Mod Studio downloads it from its GitHub page (about 9 MB) and sets it up for you." }),
          loaderNote ? el("span", { class: "muted", role: "status", text: loaderNote })
            : el("div", { class: "row" },
              el("button", { class: "btn primary", text: "Install it", disabled: !!blocked, onclick: () => install(null) }),
              el("button", { class: "btn small", text: "Use a .zip I downloaded…", disabled: !!blocked, onclick: () => input.click() }),
              blocked ? el("span", { class: "muted", text: blocked }) : null, input),
          el("a", { href: s.loader.page, target: "_blank", rel: "noopener", class: "muted", text: "UE4SS on GitHub" })));
      }

      if (!s.oodle.ok) {
        const path = el("input", { type: "text", id: "setup-oodle", "aria-label": "Where the oo2core file is", spellcheck: "false", placeholder: "C:\\...\\oo2core_9_win64.dll", style: { flex: "1", minWidth: "260px" } });
        steps.append(step(false, "Optional: a file from another game",
          el("span", { class: "muted", text: "Mods that change cat names, game data or eye colours read the game's own files, and that needs a file called oo2core_…_win64.dll. Many other games come with it; Clan Mod Studio looked in your Steam games and didn't find one. Everything else works without it. If you have it, paste where it is:" }),
          el("div", { class: "row" }, path, el("button", { class: "btn", text: "Use it", onclick: async () => {
            try { await api.post("/setup/oodle", { path: path.value }); toast("Got it."); renderSetup(); }
            catch (e) { toast(e.message, "bad"); }
          } }))));
      }

      setupBox.append(el("div", { class: "card setup" },
        el("h2", { text: "Get set up" }),
        el("p", { class: "note", text: "A few things before your first mod; each is done once." }),
        steps,
        el("p", { class: "note", text: "Then add a mod below and press Play." })));
    }

    // ---------- what's not in the game yet ----------
    async function renderChanges() {
      let c;
      try { c = await api.get("/changes"); } catch (e) { clear(changesBox); return; }
      clear(changesBox);
      if (!c.any) {
        if (c.installed) changesBox.append(el("p", { class: "note ok-line", text: "✓ The game has your mods as they are here." }));
        return;
      }
      const parts = [
        ...c.on.map(i => `${c.names[i] || i} on`),
        ...c.off.map(i => `${c.names[i] || i} off`),
        ...c.changed.map(i => `${c.names[i] || i} changed`),
        ...(c.redo || []).map(r => `apply again: ${r}`),
      ];
      changesBox.append(el("div", { class: "banner" },
        el("div", { class: "row spread" },
          el("div", { style: { display: "grid", gap: "2px" } },
            el("strong", { text: c.installed ? "Not in the game yet" : "Nothing is installed yet" }),
            el("span", { class: "muted", text: parts.length > 6 ? `${parts.slice(0, 6).join(" · ")} and ${parts.length - 6} more` : parts.join(" · ") })),
          c.game_running
            ? el("span", { class: "muted", text: "Close the game, then apply." })
            : el("button", { class: "btn primary", text: "Apply to game", onclick: () => bus.emit("apply") }))));
    }

    // ---------- adding a downloaded mod ----------
    function renderAdd() {
      clear(addBox);
      const input = el("input", { type: "file", accept: ".zip,application/zip", hidden: true, id: "mod-file" });
      input.addEventListener("change", () => input.files[0] && look(input.files[0]));
      // Clicking anywhere on it chooses a file too; the keyboard uses its button.
      const zone = el("div", { class: "dropzone" },
        el("strong", { text: "Drop a mod's .zip here" }),
        el("span", { class: "muted", text: "or" }),
        el("button", { class: "btn", type: "button", id: "mod-choose", text: "Choose a file…", "aria-label": "Choose a mod's .zip file", onclick: e => { e.stopPropagation(); input.click(); } }),
        input);
      zone.addEventListener("click", () => input.click());
      zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("over"); });
      zone.addEventListener("dragleave", () => zone.classList.remove("over"));
      zone.addEventListener("drop", e => {
        e.preventDefault();
        zone.classList.remove("over");
        const f = e.dataTransfer.files[0];
        if (f) look(f);
      });
      addBox.append(el("h2", { text: "Add a mod" }), zone,
        el("p", { class: "note", text: "You can also drop a mod's .zip onto Clan Mod Studio, the file you double-click to open this." }),
        el("p", { class: "note" }, "Got a folder instead of a .zip? Put it in your ",
          el("button", { class: "btn link", text: "mods folder", onclick: () => openFolder({ what: "mods" }) }),
          ", then ", el("button", { class: "btn link", text: "look again", onclick: () => refresh() }), "."),
        examplesBox());
    }

    // wcmods comes with only the mod menu. Its example mods (examples/: palettes, mouse look, game
    // tweaks...) are added from here like any other mod, as a copy in your mods folder.
    let examplesOpen = false;
    function examplesBox() {
      const list = el("div", { class: "stack" });
      const box = el("details", { class: "examples" },
        el("summary", {}, el("strong", { text: "Example mods" }),
          el("span", { class: "muted", text: " palettes, mouse look, game tweaks and more, to add in one go" })), list);
      let loaded = false;
      async function load() {
        loaded = true;
        clear(list).append(el("p", { class: "muted", role: "status", text: "Looking…" }));
        let r;
        try { r = await api.get("/examples"); } catch (e) { clear(list).append(el("p", { class: "muted", text: e.message })); return; }
        clear(list);
        if (!r.mods.length) list.append(el("p", { class: "muted", text: "There are no examples in this copy of wcmods." }));
        for (const m of [...r.mods].sort((a, b) => String(a.name).localeCompare(String(b.name)))) {
          const notes = [];
          if (m.code) notes.push(r.code_allowed ? "Runs code: in-game scripts or a build step." : "Runs code, so it stays off until you allow mods that run code (Options, below).");
          if (m.requires.length) notes.push(`Needs ${m.requires.map(nameOf).join(", ")}.`);
          list.append(el("div", { class: "row spread line" },
            el("div", { style: { display: "grid", gap: "2px", minWidth: "0", flex: "1" } },
              el("strong", { text: m.name }),
              m.description ? el("span", { class: "muted", text: m.description }) : null,
              notes.length ? el("span", { class: "muted", text: notes.join(" ") }) : null),
            m.existing
              ? el("span", { class: "muted", text: "In your mods" })
              : el("button", { class: "btn small", "data-focus": `example:${m.id}`, text: "Add", "aria-label": `Add ${m.name}`, onclick: async () => {
                try {
                  const res = await api.post("/examples/add", { ids: [m.id], enable: true });
                  const also = [...new Set(res.added.flatMap(a => a.also_on || []))];
                  toast(`Added ${m.name}.` + (also.length ? ` Also on, because it needs them: ${also.join(", ")}.` : "") + " Press Play to play with it.");
                  await refresh();
                  await load();   // it's in your mods now
                  if (document.activeElement === document.body) box.querySelector("summary").focus();
                } catch (e) { toast(e.message, "bad"); }
              } })));
        }
      }
      box.addEventListener("toggle", () => { examplesOpen = box.open; if (box.open && !loaded) load(); });
      if (examplesOpen) { box.open = true; load(); }
      return box;
    }

    async function look(file) {
      if (!/\.zip$/i.test(file.name)) { toast("That isn't a .zip file. Mods come as .zip files (or folders for the mods folder).", "bad"); return; }
      clear(addBox).append(el("h2", { text: "Add a mod" }), el("p", { class: "muted", role: "status", text: `Looking inside ${file.name}…` }));
      try {
        const r = await api.upload(`/mods/add?step=preview&name=${encodeURIComponent(file.name)}`, file);
        clear(addBox);
        renderPreview(r, file.name,
          (ids, enable) => api.upload(`/mods/add?step=add&enable=${enable ? 1 : 0}&ids=${encodeURIComponent(ids.join(","))}&name=${encodeURIComponent(file.name)}`, file),
          () => renderAdd());
      } catch (e) { toast(e.message, "bad"); renderAdd(); }
    }

    // A mod dropped on the launcher (wcmods studio --add), waiting in the studio's inbox.
    let inboxShown = false;
    async function showInbox() {
      let r;
      try { r = await api.get("/mods/inbox"); } catch (e) { toast(e.message, "bad"); return; }
      if (!r.mods.length) return;
      inboxShown = true;
      clear(addBox);
      renderPreview(r, r.name,
        (ids, enable) => api.post("/mods/inbox/add", { ids, enable }),
        async () => { await api.post("/mods/inbox/clear").catch(() => null); inboxShown = false; renderAdd(); });
      addBox.scrollIntoView({ block: "start" });
    }

    // What's in a .zip (or folder) before adding it; add(ids, enable) and cancel() do the rest.
    function renderPreview(r, name, add, cancel) {
      const picks = new Map();
      addBox.append(el("div", { class: "row spread" }, el("h2", { text: r.mods.length > 1 ? `${r.mods.length} mods in ${name}` : `Add ${r.mods[0].name}?` }),
        el("span", { class: "muted mono", text: name })));
      for (const m of r.mods) {
        const pick = el("input", { type: "checkbox", checked: true, id: `pick-${m.id}`, "aria-label": `Add ${m.name}` });
        picks.set(m.id, pick);
        const notes = [];
        if (m.existing && m.existing.builtin) notes.push(el("li", { class: "warn", text: `Left out: ${m.existing.name} comes with Clan Mod Studio, so this copy doesn't replace it.` }));
        else if (m.existing) notes.push(el("li", { text: `Replaces the ${m.existing.name}${m.existing.version ? " " + m.existing.version : ""} you have${m.version ? " with " + m.version : ""}. The old copy is kept in backups.` }));
        if (m.code) notes.push(el("li", { class: r.code_allowed ? "" : "warn", text: r.code_allowed
          ? "Runs code on your computer and in the game. Only add mods like this from people you trust."
          : "Runs code, so it stays off until you allow mods that run code (Options, below). Only do that for mods from people you trust." }));
        const needs = m.requires.filter(i => !mods.some(x => x.id === i));
        if (m.requires.length) notes.push(el("li", { class: needs.length ? "warn" : "", text: `Needs ${m.requires.map(nameOf).join(", ")}${needs.length ? ", which you don't have: add it too" : " (turned on with it)"}.` }));
        if (m.uses.includes(MENU) || m.requires.includes(MENU)) notes.push(el("li", { text: "Adds a page to the in-game mod menu." }));
        addBox.append(el("div", { class: "mod preview" },
          r.mods.length > 1 ? pick : null,
          el("div", { class: "mod-body" },
            el("label", { for: `pick-${m.id}` }, el("strong", { text: m.name }), m.version ? el("span", { class: "muted", text: ` ${m.version}` }) : null,
              m.author ? el("span", { class: "muted", text: ` · by ${m.author}` }) : null),
            m.description ? el("span", { class: "muted", text: m.description }) : null,
            el("div", { class: "row" }, ...m.kinds.map(k => el("span", { class: "chip", text: KIND[k] || k }))),
            notes.length ? el("ul", { class: "notes" }, ...notes) : null)));
      }
      const on = el("input", { type: "checkbox", id: "add-on", checked: true });
      addBox.append(el("div", { class: "row" },
        el("button", { class: "btn primary", text: r.mods.length > 1 ? "Add these" : "Add to my mods", onclick: async () => {
          const ids = [...picks].filter(([, p]) => p.checked).map(([id]) => id);
          if (!ids.length) { toast("Pick at least one.", "bad"); return; }
          try {
            const res = await add(ids, on.checked);
            const added = res.added.filter(a => !a.skipped), left = res.added.filter(a => a.skipped);
            const also = [...new Set(added.flatMap(a => a.also_on || []))];
            toast(`Added ${added.map(a => a.name).join(", ")}.`
              + (also.length ? ` Also on, because ${added.length > 1 ? "they need" : "it needs"} them: ${also.join(", ")}.` : "")
              + (left.length ? ` Left out ${left.map(a => a.name).join(", ")}: ${left.length > 1 ? "they come" : "it comes"} with Clan Mod Studio.` : "")
              + (on.checked ? " Press Play to play with it." : ""));
            inboxShown = false;
            renderAdd();
            await refresh();
          } catch (e) { toast(e.message, "bad"); }
        } }),
        el("label", { class: "row", for: "add-on" }, on, "Switch it on"),
        el("button", { class: "btn ghost", text: "Cancel", onclick: () => cancel() })));
    }

    // ---------- the list ----------
    async function switchMod(m, on, cascade = false) {
      try {
        const r = await api.post(`/mods/${encodeURIComponent(m.id)}/switch`, { on, cascade });
        if (r.blocked_by.length) { renderList({ blocked: m.id, by: r.blocked_by }); return; }
        const also = r.changed.filter(c => c.id !== m.id).map(c => c.name).join(", ");
        toast(`${m.name} ${on ? "on" : "off"}.` + (also ? (on ? ` Also on, because it needs them: ${also}.` : ` Also off, because they need it: ${also}.`) : ""));
        await refresh();
      } catch (e) { toast(e.message, "bad"); renderList(); }
    }

    function modCard(m, state) {
      const toggle = el("input", { type: "checkbox", role: "switch", class: "switch", id: `mod-on-${m.id}`, checked: m.enabled, "aria-label": m.name });
      toggle.addEventListener("change", () => switchMod(m, toggle.checked));
      const menuMod = mods.find(x => x.id === MENU);
      const flags = [];
      if (m.builtin) flags.push(el("span", { class: "chip", text: "Comes with Clan Mod Studio" }));
      if (m.menu_page && m.id !== MENU) {
        flags.push(el("span", { class: "chip", title: "It has a page in the in-game mod menu (Insert)",
          text: menuMod && menuMod.enabled ? "Page in the mod menu" : "Page in the mod menu (the menu is off)" }));
      }
      for (const k of m.kinds) if (k !== "mod menu") flags.push(el("span", { class: "chip", text: KIND[k] || k }));
      const lines = [];
      if (m.requires.length) lines.push(el("li", { text: `Needs ${m.requires_names.join(", ")}.` }));
      for (const p of m.problems) lines.push(el("li", { class: "bad", text: p.replace(/^needs/, "Needs") + "." }));
      if (m.code && !(settings && settings.allow_code_mods)) lines.push(el("li", { class: "warn", text: "Runs code, so the game won't get it until you allow mods that run code (Options, below)." }));
      if (m.enabled && m.needed_by.length) lines.push(el("li", { class: "muted", text: `${m.needed_by.join(", ")} ${m.needed_by.length > 1 ? "need" : "needs"} it.` }));
      // Made for an older build of the game (gamebuild.py): left out unless the player uses it anyway.
      const old = m.outdated;
      if (old) {
        lines.push(el("li", { class: old.allowed ? "warn" : "bad", text: old.allowed
          ? "Made for an older version of the game, and used anyway: it may not work, or may behave unpredictably."
          : "Made for an older version of the game, so it's left out until it's updated." }));
      }

      const more = open.has(m.id);
      const card = el("div", { class: "mod" + (m.enabled ? "" : " off"), "data-key": `mod:${m.id}` },
        toggle,
        el("div", { class: "mod-body" },
          el("label", { for: `mod-on-${m.id}` }, el("strong", { text: m.name }),
            m.version ? el("span", { class: "muted", text: ` ${m.version}` }) : null,
            m.author ? el("span", { class: "muted", text: ` · by ${m.author}` }) : null),
          m.description ? el("span", { class: "muted", text: m.description }) : null,
          flags.length ? el("div", { class: "row" }, ...flags) : null,
          lines.length ? el("ul", { class: "notes" }, ...lines) : null),
        el("div", { class: "mod-actions" },
          m.id === MENU || m.kinds.includes("mod menu")
            ? el("button", { class: "btn small", "data-focus": `more:${m.id}`, "aria-expanded": String(more), "aria-label": `${m.name} settings`, text: more ? "Close settings" : "Settings", onclick: () => { more ? open.delete(m.id) : open.add(m.id); renderList(); } })
            : el("button", { class: "btn ghost small", "data-focus": `more:${m.id}`, "aria-expanded": String(more), "aria-label": `More about ${m.name}`, text: more ? "Less" : "More", onclick: () => { more ? open.delete(m.id) : open.add(m.id); renderList(); } })));
      if (state && state.blocked === m.id) {
        const them = state.by.length > 1 ? "them" : "it";
        const ask = `${state.by.map(b => b.name).join(", ")} ${state.by.length > 1 ? "need" : "needs"} ${m.name}. ` +
          (state.remove ? `Turn ${them} off and remove ${m.name}?` : `Turn ${them} off too?`);
        announce(ask);
        card.append(el("div", { class: "banner mod-wide", role: "group", "aria-label": `Mods that need ${m.name}` },
          el("span", { text: ask }),
          el("div", { class: "row" },
            state.remove
              ? el("button", { class: "btn danger", text: `Turn ${them} off and remove`, onclick: () => removeMod(m, true) })
              : el("button", { class: "btn", text: `Turn ${state.by.length > 1 ? "all" : "both"} off`, onclick: () => switchMod(m, false, true) }),
            el("button", { class: "btn ghost", text: state.remove ? `Keep ${m.name}` : `Keep ${m.name} on`, onclick: () => renderList() }))));
      }
      if (old && m.enabled) {
        // One focus key for the button that asks and the warning's "Leave it out" (not "Use it anyway",
        // which a second press would confirm), so focus moves between them as the card changes.
        const key = `allow:${m.id}`;
        const warning = `It was made for an older version of the game (build ${old.made_for.join(", ")}). The game has changed since, so it may not work, or may behave unpredictably: a broken page, odd values, a crash. Back up your save first (Backups and repair, below). This only applies to this version of the game; after the next update it's left out again.`;
        if (!old.allowed && state && state.allow === m.id) announce(`Use ${m.name} anyway? ${warning}`);
        card.append(old.allowed
          ? el("div", { class: "row mod-wide" },
            el("button", { class: "btn small", "data-focus": key, text: "Stop using it", "aria-label": `Stop using ${m.name} on this version`, onclick: () => allowOutdated(m, false) }),
            el("span", { class: "muted", text: "It's left out again until it's updated for this version." }))
          : state && state.allow === m.id
            ? el("div", { class: "banner mod-wide", role: "group", "aria-label": `Use ${m.name} anyway?` },
              el("strong", { text: `Use ${m.name} anyway?` }),
              el("span", { text: warning }),
              el("div", { class: "row" },
                el("button", { class: "btn danger", text: "Use it anyway", onclick: () => allowOutdated(m, true) }),
                el("button", { class: "btn ghost", "data-focus": key, text: "Leave it out", onclick: () => renderList() })))
            : el("div", { class: "row mod-wide" },
              el("button", { class: "btn small", "data-focus": key, text: "Use it anyway…", "aria-label": `Use ${m.name} anyway…`, onclick: () => renderList({ allow: m.id }) }),
              el("span", { class: "muted", text: "Or wait for its maker to update it." })));
      }
      if (more) card.append(m.kinds.includes("mod menu") ? menuSettings(m) : details(m));
      return card;
    }

    function details(m) {
      const prio = el("input", { type: "number", id: `mod-prio-${m.id}`, value: m.priority, style: { width: "5.5rem" } });
      prio.addEventListener("change", async () => {
        try { await api.patch(`/mods/${encodeURIComponent(m.id)}`, { priority: Number(prio.value) || 0 }); await refresh(); }
        catch (e) { toast(e.message, "bad"); }
      });
      return el("div", { class: "mod-wide details" },
        el("div", { class: "row" },
          el("label", { for: `mod-prio-${m.id}`, class: "lbl", text: "Priority" }), prio,
          el("span", { class: "muted", text: "When two mods change the same thing, the higher number wins." })),
        el("div", { class: "row" },
          el("span", { class: "muted mono", text: `mods/${m.id}` }),
          el("button", { class: "btn small", text: "Open its folder", onclick: () => openFolder({ what: "mod", id: m.id }) }),
          el("button", { class: "btn small", text: "Save as .zip", onclick: async () => {
            try { toast(`Saved ${await api.download(`/mods/${encodeURIComponent(m.id)}/zip`)}`); } catch (e) { toast(e.message, "bad"); }
          } }),
          m.builtin ? null : confirmButton("Remove", "Press again to remove", () => removeMod(m), "btn small danger")));
    }

    // Removing a mod that mods which are on need asks first, as switching it off does.
    async function removeMod(m, cascade = false) {
      try {
        const r = await api.post(`/mods/${encodeURIComponent(m.id)}/remove`, { cascade });
        if (r.blocked_by.length) { renderList({ blocked: m.id, by: r.blocked_by, remove: true }); return; }
        const off = (r.turned_off || []).join(", ");
        toast(`Removed ${m.name}.` + (off ? ` Also off, because they need it: ${off}.` : "") +
          " It's kept in backups; Put it back under Backups and repair.");
        open.delete(m.id);
        await refresh();
      } catch (e) { toast(e.message, "bad"); }
    }

    // The mod menu's own settings (its menu.json, through /ingame).
    function menuSettings(m) {
      const box = el("div", { class: "mod-wide details" });
      if (!options) { box.append(el("p", { class: "muted", text: "Loading…" })); return box; }
      const o = options;
      const save = async change => {
        try { options = await api.patch("/ingame", change); toast("Saved. Apply to game to use it."); await refresh(); }
        catch (e) { toast(e.message, "bad"); }
      };
      const NAMES = { INS: "Insert", HOME: "Home", END: "End", DEL: "Delete", PAGE_UP: "Page Up", PAGE_DOWN: "Page Down" };
      const key = el("select", { id: "ig-key" }, ...o.menu_keys.map(k => el("option", { value: k, text: NAMES[k] || k, selected: k === o.menu_key })));
      key.addEventListener("change", () => save({ menu_key: key.value }));
      const SIZES = [[0.8, "Small"], [1, "Normal"], [1.25, "Large"], [1.5, "Larger"], [1.8, "Largest"]];
      if (!SIZES.some(([v]) => v === o.menu_scale)) SIZES.push([o.menu_scale, `x${o.menu_scale}`]);
      const size = el("select", { id: "ig-size" }, ...SIZES.map(([v, label]) => el("option", { value: String(v), text: label, selected: v === o.menu_scale })));
      size.addEventListener("change", () => save({ menu_scale: Number(size.value) }));
      const cheats = el("input", { type: "checkbox", id: "ig-cheats", checked: o.cheats });
      cheats.addEventListener("change", () => save({ cheats: cheats.checked }));
      box.append(
        el("div", { class: "row" }, el("label", { for: "ig-key", class: "lbl", text: "Opens with" }), key,
          el("label", { for: "ig-size", class: "lbl", text: "Size" }), size),
        el("label", { class: "row", for: "ig-cheats" }, cheats, el("strong", { text: "Cheats on when the game starts" }),
          el("span", { class: "muted", text: "Its Cheats page switches them on and off while you play." })),
        el("p", { class: "note", text: "In game, A- and A+ in the menu's top bar change its size until the game closes. Other mods add their pages to it; with the menu off they just don't show." }));
      return box;
    }

    function renderList(state = null) {
      const shown = mods.filter(m => (filter === "all" || (filter === "on") === m.enabled)
        && (!search || `${m.name} ${m.id} ${m.description} ${m.author}`.toLowerCase().includes(search)));
      const presets = shown.filter(m => m.preset);
      // String(): a name that isn't text (a mistake in a mod.json) mustn't stop the list from showing.
      const byName = (a, b) => String(a.name).localeCompare(String(b.name));
      const rest = shown.filter(m => !m.preset).sort((a, b) => (b.builtin - a.builtin) || byName(a, b));
      const searchBox = el("input", { type: "search", id: "mod-search", placeholder: "Find a mod", value: search, "aria-label": "Find a mod" });
      searchBox.addEventListener("input", () => { search = searchBox.value.trim().toLowerCase(); renderList(); searchAgain(); });
      const chips = ["all", "on", "off"].map(f => el("button", { class: "chip", id: `mod-show-${f}`, "aria-pressed": String(filter === f), text: { all: "All", on: "On", off: "Off" }[f],
        onclick: () => { filter = f; renderList(); } }));
      clear(listBox).append(
        el("div", { class: "row spread" }, el("h2", { text: `Your mods` }),
          el("span", { class: "muted", text: `${mods.filter(m => m.enabled).length} of ${mods.length} on` })),
        el("div", { class: "row" }, searchBox, el("div", { class: "row", role: "group", "aria-label": "Show" }, ...chips)));
      if (!mods.length) listBox.append(el("p", { class: "empty", text: "No mods yet. Add one above." }));
      else if (!shown.length) listBox.append(el("p", { class: "empty", text: "No mods match." }));
      for (const m of rest) listBox.append(modCard(m, state));
      if (presets.length) {
        listBox.append(el("h3", { class: "group", text: `Colour palettes (${presets.length})` }),
          el("p", { class: "note", text: "Each recolours your cats' coats. The Palettes page shows them side by side and switches between them in one go." }));
        for (const m of presets.sort(byName)) listBox.append(modCard(m, state));
      }
      function searchAgain() {   // keep typing in the box after it's redrawn
        const box = listBox.querySelector('input[type="search"]');
        if (box) { box.focus(); box.setSelectionRange(box.value.length, box.value.length); }
      }
    }

    // ---------- options ----------
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
          try { settings = await api.patch("/settings", { allow_code_mods: on }); toast(on ? "Mods that run code are allowed. Apply to game to use them." : "Mods that run code are off."); await refresh(); location.reload(); }
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
    }

    // ---------- backups and repair ----------
    async function renderRepair() {
      const wasOpen = repairBox.open;
      clear(repairBox).append(el("summary", {}, el("h2", { text: "Backups and repair" })));
      repairBox.open = wasOpen;
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
            try { await api.post("/mods/restore", { name: r.name }); toast(`${r.title} is back (off).`); await refresh(); }
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
            el("span", { class: "muted", text: "Your mods stay here. Control remaps and save edits stay in your save; restore a save backup to undo those." }))));
    }

    // ---------- making your own ----------
    function renderMake() {
      const id = el("input", { type: "text", id: "new-mod-id", placeholder: "e.g. my-tweaks", spellcheck: "false" });
      const name = el("input", { type: "text", id: "new-mod-name", placeholder: "My tweaks" });
      const desc = el("input", { type: "text", id: "new-mod-desc", placeholder: "What it changes" });
      clear(makeBox).append(el("summary", {}, el("h2", { text: "Make your own mod" })),
        el("p", { class: "note", text: "The pages under Make mods (Palettes, Controls, Names, Game data, Save) each save into a mod. Start an empty one here, or from those pages. Save as .zip (under a mod's More) packs one up to share." }),
        el("form", { class: "row", onsubmit: async e => {
          e.preventDefault();
          try {
            await api.post("/mods", { id: id.value.trim(), name: name.value.trim() || undefined, description: desc.value.trim(), enabled: true });
            toast(`Made ${id.value.trim()}`); id.value = name.value = desc.value = "";
            await refresh();
          } catch (err) { toast(err.message, "bad"); }
        } },
          el("div", { class: "field" }, el("label", { for: "new-mod-id", text: "Folder name" }), id),
          el("div", { class: "field" }, el("label", { for: "new-mod-name", text: "Name" }), name),
          el("div", { class: "field", style: { flex: "1" } }, el("label", { for: "new-mod-desc", text: "Description" }), desc),
          el("button", { class: "btn", type: "submit", text: "Make it", style: { alignSelf: "end" } })));
    }

    async function openFolder(what) {
      try { await api.post("/open", what); } catch (e) { toast(e.message, "bad"); }
    }

    // notify: tell the rest of the studio (the top bar's Apply button); not when another page told us.
    async function refresh({ notify = true } = {}) {
      try {
        [mods, options, settings] = await Promise.all([api.get("/mods"), api.get("/ingame").catch(() => null), api.get("/settings")]);
      } catch (e) { toast(e.message, "bad"); }
      renderList();
      renderOptions();
      await Promise.all([renderSetup(), renderUpdate(), renderChanges(), renderRepair()]);
      if (notify) bus.emit("mods-changed", { from: "mods" });
    }

    renderAdd();
    renderMake();
    const off = [
      bus.on("installed", () => { renderChanges(); renderRepair(); }),
      bus.on("mods-changed", d => { if (!d || d.from !== "mods") refresh({ notify: false }); }),
      bus.on("focus", () => renderSetup()),
    ];
    await refresh();
    return { unmount() { off.forEach(f => f()); } };
  },
};
