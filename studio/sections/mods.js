// Mods: get set up (the first time), add mods you've downloaded, switch them on and off, and apply them
// to the game. Mods say in mod.json what they need ("requires") or work with ("uses"). Options (the mod
// menu's key among them), backups and repairs are on the Settings and repair page.
export default {
  title: "Mods",
  async mount(root, wc) {
    const { el, api, clear, toast, bus, confirmButton, announce } = wc;
    const KIND = {
      files: "Replaces game files", "cooked content": "New models or textures",
      palette: "Colours", controls: "Controls", "mouse look": "Mouse look", data: "Game rules and numbers",
      names: "Cat names", cats: "Your cat's colours", animations: "Animations", save: "Changes your save", "in-game script": "In-game script",
      "C++ mod": "C++ mod", "C++ source": "C++ source", code: "Build step (code)", "studio page": "Studio page",
    };
    let mods = [], filter = "all", search = "", settings = null;
    const open = new Set();   // mod cards with "More" open

    const setupBox = el("div");
    const updateBox = el("div");
    const changesBox = el("div");
    const addBox = el("div", { class: "card" });
    const listBox = el("div", { class: "card" });

    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Your mods" }),
        el("h1", { text: "Mods" }),
        el("p", { class: "note", text: "Add mods you've downloaded, switch them on or off, then press Play (top right)." })),
      setupBox, updateBox, changesBox, addBox, listBox);

    const nameOf = id => (mods.find(m => m.id === id) || {}).name || id;

    // ---------- after a game update (wcmods/exe/gamebuild.py) ----------
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
    let loaderNote = "", pagesNote = "";
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
          el("span", { class: "muted", text: s.backup.ok ? "If a mod ever spoils it, Backups and repair (on the Settings and repair page) puts it back." : "Couldn't make the copy; try Back up now under Settings and repair." })));
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

      // The menu's pages about the game: a mod of their own (wcmods/menupages.py), from its GitHub releases.
      if (s.pages.ok) {
        steps.append(step(true, s.pages.installed ? "The menu's pages are in your mods" : "The menu's pages: skipped",
          s.pages.installed
            ? el("span", { class: "muted", text: `Menu pages ${s.pages.version || ""}: your cat, the world, quests, fights and cheats in the in-game menu.` })
            : el("span", { class: "muted" }, "Skipped for now. To add it later, download its .zip from ",
              el("a", { href: s.pages.page, target: "_blank", rel: "noopener", text: "its GitHub page" }),
              " and drop it on this page, or run python wcmods.py menu-pages.")));
      } else {
        const input = el("input", { type: "file", accept: ".zip,application/zip", hidden: true });
        const addPages = async (file, skip = false) => {
          pagesNote = skip ? "" : file ? `Adding ${file.name}…` : "Downloading Menu pages from GitHub…";
          renderSetup();
          try {
            const r = file ? await api.upload("/setup/pages", file) : await api.post("/setup/pages", skip ? { skip: true } : {});
            if (!skip) toast(`Menu pages ${r.result.version || ""} is in your mods.` + (settings && settings.allow_code_mods ? " Press Play to put it in the game."
              : " It runs code, so allow mods that run code (Options, on the Settings and repair page) for the game to get it."));
            pagesNote = "";
            await refresh();
          } catch (e) { pagesNote = ""; toast(e.message, "bad"); renderSetup(); }
        };
        input.addEventListener("change", () => input.files[0] && addPages(input.files[0]));
        steps.append(step(false, "Add the menu's pages",
          el("span", { class: "muted", text: "The in-game menu (Insert) lists your mods and their pages. Its pages about your cat, the world, travel, quests, fights and cheats are a mod of their own, Menu pages. It's a script, so it needs mods that run code allowed (Options, on the Settings and repair page). Clan Mod Studio downloads it from its GitHub page (under 100 KB)." }),
          pagesNote ? el("span", { class: "muted", role: "status", text: pagesNote })
            : el("div", { class: "row" },
              el("button", { class: "btn primary", text: "Add it", onclick: () => addPages(null) }),
              el("button", { class: "btn small", text: "Use a .zip I downloaded…", onclick: () => input.click() }),
              el("button", { class: "btn ghost small", text: "Not now", onclick: () => addPages(null, true) }), input),
          el("a", { href: s.pages.page, target: "_blank", rel: "noopener", class: "muted", text: "Menu pages on GitHub" })));
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
        el("p", { class: "note" }, "Looking for mods to try? Themed palettes, mouse look, game tweaks and more are in ",
          el("a", { href: "https://github.com/HexOffender/wcmods-examples", target: "_blank", rel: "noopener", text: "wcmods-examples" }),
          ": download it (Code, then Download ZIP) and drop the .zip here to pick the ones you want."));
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
      const pack = r.mods.find(m => m.kinds.includes("mod pack"));
      addBox.append(el("div", { class: "row spread" }, el("h2", { text: pack ? `Add the mod pack ${pack.name}?` : r.mods.length > 1 ? `${r.mods.length} mods in ${name}` : `Add ${r.mods[0].name}?` }),
        el("span", { class: "muted mono", text: name })),
        pack ? el("p", { class: "note", text: "A mod pack: its mods go together. Mods you already have aren't ticked, so yours stay as they are; tick one to use the pack's copy instead." })
          : r.mods.length > 1 ? el("p", { class: "note", text: "Tick the ones you want. With palettes, pick one theme at a time." }) : null);
      for (const m of r.mods) {
        // One mod is simply added; out of several (a collection like wcmods-examples) the player picks. A mod
        // pack's are ticked, except mods the player has already.
        const pick = el("input", { type: "checkbox", checked: r.mods.length === 1 || (!!pack && !m.existing), id: `pick-${m.id}`, "aria-label": `Add ${m.name}` });
        picks.set(m.id, pick);
        const notes = [];
        if (m.existing) notes.push(el("li", { text: `Replaces the ${m.existing.name}${m.existing.version ? " " + m.existing.version : ""} you have${m.version ? " with " + m.version : ""}. The old copy is kept in backups.` }));
        if (m.code) notes.push(el("li", { class: r.code_allowed ? "" : "warn", text: r.code_allowed
          ? "Runs code on your computer and in the game. Only add mods like this from people you trust."
          : "Runs code, so it stays off until you allow mods that run code (Options, on the Settings and repair page). Only do that for mods from people you trust." }));
        const needs = m.requires.filter(i => !mods.some(x => x.id === i));
        if (m.requires.length) notes.push(el("li", { class: needs.length ? "warn" : "", text: `Needs ${m.requires.map(nameOf).join(", ")}${needs.length ? ", which you don't have: add it too" : " (turned on with it)"}.` }));
        if (m.menu_page) notes.push(el("li", { text: "Adds a page to the in-game mod menu." }));
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
            const added = res.added;
            const also = [...new Set(added.flatMap(a => a.also_on || []))];
            toast(`Added ${added.map(a => a.name).join(", ")}.`
              + (also.length ? ` Also on, because ${added.length > 1 ? "they need" : "it needs"} them: ${also.join(", ")}.` : "")
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
      const flags = [];
      if (m.menu_page) flags.push(el("span", { class: "chip", title: "It has a page in the in-game mod menu (Insert)", text: "Page in the mod menu" }));
      for (const k of m.kinds) flags.push(el("span", { class: "chip", text: KIND[k] || k }));
      const lines = [];
      if (m.requires.length) lines.push(el("li", { text: `Needs ${m.requires_names.join(", ")}.` }));
      for (const p of m.problems) lines.push(el("li", { class: "bad", text: p.replace(/^needs/, "Needs") + "." }));
      if (m.code && !(settings && settings.allow_code_mods)) lines.push(el("li", { class: "warn", text: "Runs code, so the game won't get it until you allow mods that run code (Options, on the Settings and repair page)." }));
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
          el("button", { class: "btn ghost small", "data-focus": `more:${m.id}`, "aria-expanded": String(more), "aria-label": `More about ${m.name}`, text: more ? "Less" : "More", onclick: () => { more ? open.delete(m.id) : open.add(m.id); renderList(); } })));
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
        const warning = `It was made for an older version of the game (build ${old.made_for.join(", ")}). The game has changed since, so it may not work, or may behave unpredictably: a broken page, odd values, a crash. Back up your save first (Backups and repair, on the Settings and repair page). This only applies to this version of the game; after the next update it's left out again.`;
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
      if (more) card.append(details(m));
      return card;
    }

    // Build a mod's C++ (python wcmods.py cpp build <id>) from its card: the studio builds in the background
    // and this polls until it's done, then says how it went.
    async function buildCpp(m) {
      try {
        await api.post(`/cpp/build/${encodeURIComponent(m.id)}`, {});
      } catch (e) { toast(e.message, "bad"); return; }
      toast(`Building ${m.name}... (the first build compiles UE4SS too: a few minutes)`);
      for (;;) {
        await new Promise(r => setTimeout(r, 1500));
        let st;
        try { st = await api.get("/cpp"); } catch (e) { toast(e.message, "bad"); return; }
        if (!st.building) {
          if (st.result) toast(st.result.message, st.result.ok ? undefined : "bad");
          await refresh();
          return;
        }
      }
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
          m.kinds.includes("C++ source") ? el("button", { class: "btn small", text: "Build C++", onclick: () => buildCpp(m) }) : null,
          m.menu_pages ? el("button", { class: "btn small", text: "Get the latest", onclick: async () => {
            toast("Looking for a newer Menu pages on GitHub…");
            try {
              const r = await api.post("/setup/pages", {});
              toast(r.result.unchanged ? `Menu pages ${r.result.version} is the latest already.`
                : `Menu pages ${r.result.version || ""} is in your mods, with your settings kept. Apply to game to use it.`);
              await refresh();
            } catch (e) { toast(e.message, "bad"); }
          } }) : null,
          confirmButton("Remove", "Press again to remove", () => removeMod(m), "btn small danger")));
    }

    // Removing a mod that mods which are on need asks first, as switching it off does.
    async function removeMod(m, cascade = false) {
      try {
        const r = await api.post(`/mods/${encodeURIComponent(m.id)}/remove`, { cascade });
        if (r.blocked_by.length) { renderList({ blocked: m.id, by: r.blocked_by, remove: true }); return; }
        const off = (r.turned_off || []).join(", ");
        toast(`Removed ${m.name}.` + (off ? ` Also off, because they need it: ${off}.` : "") +
          " It's kept in backups; Put it back under Settings and repair.");
        open.delete(m.id);
        await refresh();
      } catch (e) { toast(e.message, "bad"); }
    }

    function renderList(state = null) {
      const shown = mods.filter(m => (filter === "all" || (filter === "on") === m.enabled)
        && (!search || `${m.name} ${m.id} ${m.description} ${m.author}`.toLowerCase().includes(search)));
      const presets = shown.filter(m => m.preset);
      // String(): a name that isn't text (a mistake in a mod.json) mustn't stop the list from showing.
      const byName = (a, b) => String(a.name).localeCompare(String(b.name));
      const rest = shown.filter(m => !m.preset).sort(byName);
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
    async function openFolder(what) {
      try { await api.post("/open", what); } catch (e) { toast(e.message, "bad"); }
    }

    // notify: tell the rest of the studio (the top bar's Apply button); not when another page told us.
    async function refresh({ notify = true } = {}) {
      try {
        [mods, settings] = await Promise.all([api.get("/mods"), api.get("/settings")]);
      } catch (e) { toast(e.message, "bad"); }
      renderList();
      await Promise.all([renderSetup(), renderUpdate(), renderChanges()]);
      if (notify) bus.emit("mods-changed", { from: "mods" });
    }

    renderAdd();
    const off = [
      bus.on("installed", () => renderChanges()),
      bus.on("mods-changed", d => { if (!d || d.from !== "mods") refresh({ notify: false }); }),
      bus.on("focus", () => renderSetup()),
    ];
    await refresh();
    return { unmount() { off.forEach(f => f()); } };
  },
};
