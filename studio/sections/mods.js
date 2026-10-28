// Mods: get set up (the first time), the mods that go with Clan Mod Studio, add mods you've downloaded, switch
// them on and off, and apply them to the game. Mods say in mod.json what they need ("requires") or work with
// ("uses"). Options (the mod menu's key among them), backups and repairs are on the Settings and repair page.
// What the page says and chooses without the page (search, requirements, the add-ons' states, toasts) is in
// ../lib/modlist.js.
import { ADDON_NAMES, addAllToast, addedToast, addonState, addonToast, allSet, changeParts, checkTrouble, matches,
  needs, needsLine, recheckHeading, recheckSentence, recheckSorted, sentence, worksWith } from "../lib/modlist.js";

export default {
  title: "Mods",
  async mount(root, wc) {
    const { el, api, clear, toast, bus, confirmButton, announce } = wc;
    const KIND = {
      files: "Replaces game files", "cooked content": "New models or textures",
      palette: "Colours", controls: "Controls", "mouse look": "Mouse look", data: "Game rules and numbers",
      items: "New items", animations: "Animations", characters: "New characters", questlines: "Questlines",
      names: "Cat names", cats: "Your cat's colours", save: "Changes your save", "in-game script": "In-game script",
      "C++ mod": "C++ mod", "C++ source": "C++ source", code: "Build step (code)", "studio page": "Studio page",
      "mod pack": "Mod pack",
    };
    let mods = [], filter = "all", search = "", settings = null, addons = [];
    const open = new Set();   // mod cards with "More" open

    const setupBox = el("div");
    const changesBox = el("div");
    const addonsBox = el("div", { class: "card addons", "data-key": "addons" });
    const addBox = el("div", { class: "card" });
    const updateBox = el("div");
    const listBox = el("div", { class: "card" });

    root.append(
      wc.pageHead({ eyebrow: "Your mods", title: "Mods", help: "help:mods",
        lede: "Add mods you've downloaded, switch them on or off, then press Play (top right)." }),
      setupBox, changesBox, addonsBox, addBox, updateBox, listBox);

    // ---------- after a game update (wcmods/exe/gamebuild.py) ----------
    let update = null;   // what wcmods found the update changed, once asked (it takes a while the first time)
    let asking = null;   // that question, asked once however often the page redraws
    let drawing = 0;     // the latest redraw: an older one that finishes later draws nothing
    // The re-check: the held-back data mods built on the new version (POST /mods/recheck), started once per
    // visit to the page when GET /changes says it has something to do.
    let rechecking = false, recheckTried = false;
    async function maybeRecheck(c) {
      if (!c || !c.recheck_due || rechecking || recheckTried) return;
      recheckTried = true;
      rechecking = true;
      if (lastInfo) drawUpdate(lastInfo);   // said before it starts, however quick the check is
      const b = (lastInfo && lastInfo.game_build) || {};
      bus.emit("working", `Checking your mods on ${b.build && !b.verified ? "the new version" : "this version of the game"}…`);
      try { await api.post("/mods/recheck"); } catch (e) { toast(sentence(e.message), "bad"); }
      bus.emit("working", null);
      rechecking = false;
      await refresh();
    }

    let lastInfo = null;   // the last GET /info, for drawing the banner again without asking
    async function renderUpdate() {
      const mine = ++drawing;
      let info;
      try { info = await api.get("/info"); } catch (e) { return; }
      if (mine !== drawing) return;
      lastInfo = info;
      drawUpdate(info);
    }
    function drawUpdate(info) {
      clear(updateBox);
      const b = info.game_build || {};
      const updated = b.build && !b.verified;
      const sorted = recheckSorted(mods);
      // Shown whenever a mod is left out for the game's version, or was just checked on it: on the build wcmods
      // was checked on too.
      if (!updated && !rechecking && !Object.values(sorted).some(list => list.length)) return;
      const lines = [];
      const where = updated ? "the new version" : "this version of the game";
      if (rechecking) lines.push(el("span", { class: "muted", role: "status", text: `Checking your mods on ${where}…` }));
      const said = recheckSentence(sorted, !!updated);
      if (said) lines.push(el("span", { text: said }));
      if (sorted.failed.length) {
        lines.push(el("ul", { class: "notes" }, ...sorted.failed.map(m => el("li", { class: "row" },
          el("span", { text: `${m.name}: ${m.rechecked}` }),
          m.enabled ? el("button", { class: "btn small", type: "button", "aria-label": `Turn ${m.name} off`, text: "Turn it off", onclick: () => switchMod(m, false) }) : null))));
      }
      // Couldn't be checked: the game's files unreadable (tried again next time), or a file whose edits can't be
      // told apart (checked again when the mod changes).
      const unreadable = sorted.couldnt.filter(m => /the game's files can't be read/.test(m.rechecked));
      const other = sorted.couldnt.filter(m => !unreadable.includes(m));
      if (unreadable.length) {
        lines.push(el("span", { text: `${unreadable.map(m => m.name).join(", ")} couldn't be checked on ${where}: the game's files can't be read right now (is Steam updating it?). They're left out, and checked again the next time this page opens.` }));
      }
      for (const m of other) {
        lines.push(el("span", { text: `${m.name} couldn't be checked on ${where} (${m.rechecked.replace(/^couldn't check: /, "")}), so it's left out; it's checked again when it changes.` }));
      }
      if (sorted.maker.length) {
        lines.push(el("span", { text: `${sorted.maker.map(m => m.name).join(", ")} ${sorted.maker.length > 1 ? "were" : "was"} made for the older version and can't be checked here (code, or the game's own kind of files): ${sorted.maker.length > 1 ? "their makers have" : "its maker has"} to update ${sorted.maker.length > 1 ? "them" : "it"}. Each card has "Use it anyway…".` }));
      }
      if (sorted.unchecked.length && !rechecking) {
        lines.push(el("span", { text: `${sorted.unchecked.map(m => m.name).join(", ")} ${sorted.unchecked.length > 1 ? "are" : "is"} left out until checked on the new version.` }));
      }
      if (!updated) {
        updateBox.append(el("div", { class: "banner" }, el("strong", { text: rechecking ? "Checking your mods on this version of the game" : recheckHeading(sorted) }), ...lines));
        return;
      }
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

    // ---------- getting set up (wcmods/onboarding.py): every step, then one line once they're all done ----------
    let loaderNote = "", showSetup = false, asked = false, adding = null;
    const step = (ok, title, ...body) => el("li", { class: "step" + (ok ? " done" : "") },
      el("span", { class: "tick", "aria-hidden": "true", text: ok ? "\u2713" : "" }),
      el("div", { class: "step-body" }, el("strong", {}, el("span", { class: "sr-only", text: ok ? "Done: " : "To do: " }), title), ...body));

    async function allowCode() {
      try {
        settings = await api.patch("/settings", { allow_code_mods: true });
        const info = await api.get("/info").catch(() => ({}));
        toast(info.installed ? "Allowed. Press Apply to game (top right) to put them in." : "Allowed. Play puts them in the game with your mods.");
        asked = false;
        // The side bar's pages change (the Console, mods' own pages): the shell redraws it without a reload.
        bus.emit("sections-changed");
        await refresh();
      } catch (e) { toast(e.message, "bad"); }
    }

    // Add all four, one after the other, each row on the add-ons card saying "Adding …" while it goes. The
    // step counts as done once something went in, or only "no release yet" kept them out (addAllToast).
    async function addAll() {
      const todo = addons.filter(a => !a.installed);
      const went = [], unreleased = [], failed = [];
      adding = todo.length ? todo[0].id : null;
      renderSetup();
      for (const a of todo) {
        adding = a.id;
        renderAddons();
        try {
          const r = await api.post(`/addons/${encodeURIComponent(a.id)}`, {});
          went.push(`${r.result.name} ${r.result.version || ""}`.trim());
        } catch (e) {
          if (e.data?.no_release || /no release yet/.test(e.message)) unreleased.push(a.name);
          else failed.push({ message: e.message, offline: !!e.data?.offline });
        }
      }
      adding = null;
      const said = addAllToast(went, unreleased, failed, settings && settings.allow_code_mods);
      if (said.done) {
        try { await api.post("/setup/addons", { choice: "added" }); } catch (e) { toast(e.message, "bad"); }
      }
      toast(said.text, said.kind);
      await refresh();
    }

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
      // Steam starts another copy of the game than the one mods go into: shown whether or not setup is done.
      if (s.game.steam) {
        setupBox.append(el("div", { class: "banner" }, el("strong", { text: "Your mods go into another copy of the game" }),
          el("span", { text: `${s.game.steam_text}.` }),
          el("div", { class: "row" }, el("button", { class: "btn primary", text: "Use Steam's copy", onclick: async () => {
            try { await api.post("/setup/game", { dir: s.game.steam }); toast("Using Steam's copy of the game. Play or Apply to game puts your mods in it."); location.reload(); }
            catch (e) { toast(e.message, "bad"); }
          } }))));
      }
      if (s.done && !showSetup) {
        setupBox.append(el("div", { class: "card setup folded" }, el("div", { class: "row spread" },
          el("strong", {}, "Set up ", el("span", { class: "ok-line", text: "\u2713" })),
          el("button", { class: "btn link", type: "button", "aria-expanded": "false", text: "Show the steps",
            onclick: () => { showSetup = true; renderSetup(); } }))));
        return;
      }
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
        steps.append(step(true, "The script loader is installed", el("span", { class: "muted", text: "The mod menu and most mods run on it." })));
      } else {
        const blocked = !s.game.ok ? "Find the game first." : s.running ? "Close the game first." : "";
        const input = el("input", { type: "file", accept: ".zip,application/zip", hidden: true });
        const install = async file => {
          loaderNote = file ? `Installing ${file.name}…` : "Downloading the script loader from GitHub and installing it…";
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
          el("a", { href: s.loader.page, target: "_blank", rel: "noopener", class: "muted", text: "The script loader on GitHub" })));
      }

      // Mods that run their own scripts: the same switch as Options on Settings and repair, asked once here.
      const scripts = `${ADDON_NAMES} are small programs that run inside the game. Only add mods like these from people you trust; the four that come with Clan Mod Studio are fine.`;
      if (s.code.allowed) {
        steps.append(step(true, "Mods can run their own scripts", el("span", { class: "muted", text: "Options, on the Settings and repair page, can turn it off again." })));
      } else if (s.code.ok && !asked) {
        steps.append(step(true, "Mods' own scripts: not now",
          el("span", { class: "muted", text: `${ADDON_NAMES} stay out of the game until you allow it.` }),
          el("div", { class: "row" }, el("button", { class: "btn small", text: "Allow…", onclick: () => { asked = true; renderSetup(); } }))));
      } else {
        // Your mods that run code, by name and author; one of the four says what it's for.
        const warning = asked ? wc.codeWarning(mods.map(m => ({ ...m, about: (addons.find(a => a.id === m.id) || {}).about }))) : null;
        steps.append(step(false, "Let mods run their own scripts",
          el("span", { class: "muted", text: scripts }),
          warning,
          asked
            ? el("div", { class: "row", role: "group", "aria-label": "Allow mods that run code?" },
              el("button", { class: "btn danger", text: "Allow mods that run code", onclick: () => allowCode() }),
              el("button", { class: "btn ghost", text: "Cancel", onclick: () => { asked = false; renderSetup(); } }))
            : el("div", { class: "row" },
              el("button", { class: "btn primary", text: "Allow", onclick: () => {
                asked = true;
                renderSetup().then(() => announce(`Only for mods from people you trust. ${wc.CODE_WARNING}`));
              } }),
              el("button", { class: "btn ghost small", text: "Not now", onclick: async () => {
                try { await api.post("/setup/code", { skip: true }); } catch (e) { toast(e.message, "bad"); }
                renderSetup();
              } }))));
      }

      // The mods that go with Clan Mod Studio: listed on their card below, not a second time here.
      if (s.addons.ok) {
        steps.append(step(true, s.addons.choice === "not now" ? "The mods that go with Clan Mod Studio: not now" : "The mods that go with Clan Mod Studio",
          el("span", { class: "muted", text: s.addons.missing.length ? "Their card below adds any of them, one at a time." : "All four are in your mods." })));
      } else {
        steps.append(step(false, "Get the mods that go with Clan Mod Studio",
          el("span", { class: "muted", text: "They bring what you make on the Make pages into the game: their card below says what each one does. Clan Mod Studio downloads them from GitHub." }),
          adding ? el("span", { class: "muted", role: "status", text: "Adding them…" })
            : el("div", { class: "row" },
              el("button", { class: "btn primary", text: "Add all four", onclick: () => addAll() }),
              el("button", { class: "btn ghost small", text: "Not now", onclick: async () => {
                try { await api.post("/setup/addons", { choice: "not now" }); } catch (e) { toast(e.message, "bad"); }
                renderSetup();
              } }))));
      }

      setupBox.append(el("div", { class: "card setup" },
        el("div", { class: "row spread" }, el("h2", { text: "Get set up" }),
          s.done ? el("button", { class: "btn link", type: "button", "aria-expanded": "true", text: "Fold it away", onclick: () => { showSetup = false; renderSetup(); } }) : null),
        el("p", { class: "note", text: "A few things before your first mod; each is done once." }),
        steps,
        el("p", { class: "note", text: "Then add a mod below and press Play." })));
    }

    // ---------- the mods that go with Clan Mod Studio (wcmods/addons.py) ----------
    let showAddons = false, checking = false;
    async function addonAction(a, action) {
      try {
        if (action === "on") {
          await api.post(`/mods/${encodeURIComponent(a.id)}/switch`, { on: true });
          toast(`${a.name} on. Press Play to put it in the game.`);
        } else {
          adding = a.id;
          renderAddons();
          const r = await api.post(`/addons/${encodeURIComponent(a.id)}`, {});
          toast(addonToast(r.result, settings && settings.allow_code_mods));
        }
      } catch (e) { toast(e.data?.offline ? "No internet connection; try again when you're online." : sentence(e.message), "bad"); }
      adding = null;
      await refresh();
    }

    async function renderAddons(latest = false) {
      if (latest) { checking = true; drawAddons(); }
      try {
        const r = await api.get(latest ? "/addons?latest=1" : "/addons");
        addons = r.addons;
        // GitHub had no answer: said at once, and on the card until it answers.
        const trouble = latest ? checkTrouble(addons) : null;
        if (trouble) toast(trouble.all || "GitHub didn't answer for some of them; their rows say why.", "bad");
      } catch (e) { if (latest) toast(sentence(e.message), "bad"); }
      checking = false;
      drawAddons();
    }
    function drawAddons() {
      clear(addonsBox);
      if (!addons.length) return;
      const head = el("div", { class: "row spread" }, el("h2", { text: "Mods that go with Clan Mod Studio" }),
        el("button", { class: "btn link", type: "button", text: "What they do", onclick: () => wc.openHelp("companion-mods") }));
      const trouble = checkTrouble(addons);
      if (allSet(addons) && !showAddons) {
        addonsBox.append(head, el("div", { class: "row spread" },
          el("span", { class: "ok-line", text: "\u2713 All four are in, on and up to date as far as the studio knows." }),
          el("button", { class: "btn link", type: "button", "aria-expanded": "false", text: "Show them", onclick: () => { showAddons = true; drawAddons(); } })));
        if (trouble) addonsBox.append(el("p", { class: "warn-text", text: trouble.all || "GitHub didn't answer for some of them: Show them says why." }));
        return;
      }
      addonsBox.append(head, el("p", { class: "note", text: "Four mods of their own that bring what you make on the Make pages into the game. Each one runs its own scripts." }));
      for (const a of addons) {
        const st = addonState(a);
        const busy = adding === a.id;
        const label = { add: "Add", on: "Switch on", latest: "Get the latest" }[st.action];
        addonsBox.append(el("div", { class: "addon", "data-key": `addon:${a.id}` },
          el("div", { class: "addon-body" },
            el("strong", { text: a.name }),
            el("span", { class: "muted", text: a.about }),
            a.no_release && !a.installed ? el("span", { class: "muted" }, "The owner of that mod has to publish a release before Clan Mod Studio can add it (",
              el("a", { href: a.page, target: "_blank", rel: "noopener", text: "its releases" }), ").") : null,
            trouble && trouble.each[a.id] ? el("span", { class: "warn-text", text: `Couldn't check for a newer version: ${trouble.each[a.id]}` }) : null,
            a.too_new ? el("span", { class: "warn-text", text: sentence(a.too_new) }) : null),
          el("span", { class: `chip ${st.kind}` }, el("i"), busy ? `Adding ${a.name}…` : st.chip),
          label && !busy ? el("button", { class: "btn small", type: "button", "aria-label": `${label}: ${a.name}`, text: label,
            disabled: !!adding, onclick: () => addonAction(a, st.action) }) : el("span")));
      }
      if (trouble && trouble.all) addonsBox.append(el("p", { class: "warn-text", role: "status", text: trouble.all }));
      addonsBox.append(el("div", { class: "row" },
        el("button", { class: "btn small ghost", type: "button", text: checking ? "Asking GitHub…" : "Check for newer versions", disabled: checking,
          onclick: () => renderAddons(true) }),
        allSet(addons) ? el("button", { class: "btn link", type: "button", text: "Fold it away", onclick: () => { showAddons = false; drawAddons(); } }) : null));
    }

    // ---------- what's not in the game yet ----------
    async function renderChanges() {
      let c;
      try { c = await api.get("/changes"); } catch (e) { clear(changesBox); return null; }
      clear(changesBox);
      if (!c.any) {
        if (c.installed) changesBox.append(el("p", { class: "note ok-line", text: "\u2713 The game has your mods as they are here." }));
        return c;
      }
      const parts = changeParts(c);
      changesBox.append(el("div", { class: "banner" },
        el("div", { class: "row spread" },
          el("div", { style: { display: "grid", gap: "2px" } },
            el("strong", { text: c.installed ? "Not in the game yet" : "Nothing is installed yet" }),
            el("span", { class: "muted", text: parts.length > 6 ? `${parts.slice(0, 6).join(" · ")} and ${parts.length - 6} more` : parts.join(" · ") })),
          c.game_running
            ? el("span", { class: "muted", text: "Close the game, then apply." })
            : el("button", { class: "btn primary", text: "Apply to game", onclick: () => bus.emit("apply") }))));
      return c;
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

    // The preview names the mods that go with Clan Mod Studio and offers their Add: their list first, if the
    // page hasn't got it yet.
    async function knowAddons() {
      if (addons.length) return;
      try { addons = (await api.get("/addons")).addons; } catch (e) { /* named by their ids */ }
    }

    async function look(file) {
      if (!/\.zip$/i.test(file.name)) { toast("That isn't a .zip file. Mods come as .zip files (or folders for the mods folder).", "bad"); return; }
      clear(addBox).append(el("h2", { text: "Add a mod" }), el("p", { class: "muted", role: "status", text: `Looking inside ${file.name}…` }));
      await knowAddons();
      try {
        const r = await api.upload(`/mods/add?step=preview&name=${encodeURIComponent(file.name)}`, file);
        clear(addBox);
        renderPreview(r, file.name,
          // on: the ticked mods that go in switched on. With none, "on=" is an empty value the server can't tell
          // from no value at all, so enable=0 says it: every one goes in off.
          (ids, on) => api.upload(`/mods/add?step=add&ids=${encodeURIComponent(ids.join(","))}&on=${encodeURIComponent(on.join(","))}&enable=0&name=${encodeURIComponent(file.name)}`, file),
          () => renderAdd());
      } catch (e) { toast(e.message, "bad"); renderAdd(); }
    }

    // A mod dropped on the launcher (wcmods studio --add), waiting in the studio's inbox.
    let inboxShown = false;
    async function showInbox() {
      let r;
      try { r = await api.get("/mods/inbox"); } catch (e) { toast(e.message, "bad"); return; }
      if (!r.mods.length) return;
      await knowAddons();
      inboxShown = true;
      clear(addBox);
      renderPreview(r, r.name,
        (ids, on) => api.post("/mods/inbox/add", { ids, on }),
        async () => { await api.post("/mods/inbox/clear").catch(() => null); inboxShown = false; renderAdd(); });
      addBox.scrollIntoView({ block: "start" });
    }

    // What's in a .zip (or folder) before adding it; add(ids, on) adds the ticked ones (`on`: those that go in
    // switched on) and cancel() goes back.
    function renderPreview(r, name, add, cancel) {
      const picks = new Map(), ons = new Map();
      const many = r.mods.length > 1;
      const pack = r.mods.find(m => m.kinds.includes("mod pack"));
      addBox.append(el("div", { class: "row spread" }, el("h2", { text: pack ? `Add the mod pack ${pack.name}?` : many ? `${r.mods.length} mods in ${name}` : `Add ${r.mods[0].name}?` }),
        el("span", { class: "muted mono", text: name })),
        pack ? el("p", { class: "note", text: "A mod pack: its mods go together. Mods you already have aren't ticked, so yours stay as they are; tick one to use the pack's copy instead." })
          : many ? el("p", { class: "note", text: "Tick the ones you want, and whether each goes in switched on. With palettes, pick one theme at a time." }) : null);
      for (const m of r.mods) {
        // One mod is simply added; out of several (a collection like wcmods-examples) the player picks. A mod
        // pack's are ticked, except mods the player has already. Each goes in on or off as it ships, unless changed.
        // In a pack, a mod you have already is ticked only when the pack's copy is different and newer (or neither
        // says a version), and never when it's an older copy of one of the mods that go with Clan Mod Studio.
        // An older copy of one of the mods that go with Clan Mod Studio than yours is never ticked, a .zip of it
        // alone included: its box shows, unticked, for one who means to go back to it.
        const keepYours = !!(m.existing && m.existing.keep);
        const pick = el("input", { type: "checkbox", checked: !keepYours && (!many || (!!pack && (!m.existing || !!m.existing.take))), id: `pick-${m.id}`, "aria-label": `Add ${m.name}` });
        const on = el("input", { type: "checkbox", checked: m.enabled !== false, id: `on-${m.id}`, "aria-label": `${m.name} switched on` });
        picks.set(m.id, pick);
        ons.set(m.id, on);
        const notes = [];
        const had = m.existing;
        if (had && had.keep) notes.push(el("li", { text: `${had.keep}. Tick it to put this older copy in instead (yours is kept in backups).` }));
        else if (had && pack && !had.different) notes.push(el("li", { class: "muted", text: "You have this one already, the same." }));
        else if (had && pack) notes.push(el("li", { text: "You have a different mod with this name; tick it to use the pack's copy (yours is kept in backups)." }));
        else if (had) notes.push(el("li", { text: `Replaces the ${had.name}${had.version ? " " + had.version : ""} you have${m.version ? " with " + m.version : ""}. The old copy is kept in backups.` }));
        if (m.too_new) notes.push(el("li", { class: "warn", text: `${sentence(m.too_new)} Until then it's left out of the game.` }));
        if (m.code) notes.push(el("li", { class: r.code_allowed ? "" : "warn", text: r.code_allowed
          ? "Runs code on your computer and in the game. Only add mods like this from people you trust."
          : "Runs code, so it stays out of the game until you allow mods that run code (Get set up, or Options on the Settings and repair page). Only do that for mods from people you trust." }));
        const need = needs(m, r.mods, mods, addons);
        const line = needsLine(need);
        if (line) {
          notes.push(el("li", { class: line[1] }, line[0],
            ...need.filter(n => n.where === "missing" && n.addon).map(n => [" ", wc.addonButton(n.id, { label: `Add ${n.name}`, name: n.name })])));
        }
        for (const a of worksWith(m, r.mods, mods, addons)) {
          notes.push(el("li", {}, `Works with ${a.name}, which you don't have. `, wc.addonButton(a.id, { label: `Add ${a.name}`, name: a.name })));
        }
        if (m.menu_page) notes.push(el("li", { text: "Adds a page to the in-game mod menu." }));
        addBox.append(el("div", { class: "mod preview" },
          many || keepYours ? pick : null,
          el("div", { class: "mod-body" },
            el("label", { for: `pick-${m.id}` }, el("strong", { text: m.name }), m.version ? el("span", { class: "muted", text: ` ${m.version}` }) : null,
              m.author ? el("span", { class: "muted", text: ` · by ${m.author}` }) : null),
            m.description ? el("span", { class: "muted", text: m.description }) : null,
            el("div", { class: "row" }, ...m.kinds.map(k => el("span", { class: "chip", text: KIND[k] || k }))),
            notes.length ? el("ul", { class: "notes" }, ...notes) : null,
            many ? el("label", { class: "row small-on", for: `on-${m.id}` }, on, "Switched on") : null)));
      }
      const single = !many ? ons.get(r.mods[0].id) : null;
      if (single) single.id = "add-on";
      addBox.append(el("div", { class: "row" },
        el("button", { class: "btn primary", text: many ? "Add these" : "Add to my mods", onclick: async () => {
          const ids = [...picks].filter(([, p]) => p.checked).map(([id]) => id);
          if (!ids.length) { toast(many ? "Pick at least one." : "Nothing to add: you're keeping yours. Tick it to put this copy in instead.", "bad"); return; }
          try {
            const res = await add(ids, ids.filter(id => ons.get(id).checked));
            toast(addedToast(res.added, addons));
            inboxShown = false;
            renderAdd();
            await refresh();
          } catch (e) { toast(e.message, "bad"); }
        } }),
        single ? el("label", { class: "row", for: "add-on" }, single, "Switch it on") : null,
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
      // A mod whose mod.json can't be read is listed, off, with what's wrong; it can't be switched on until that's fixed.
      // The switch carries the mod's name for screen readers; the name itself is text, so clicking it changes nothing.
      const toggle = el("input", { type: "checkbox", role: "switch", class: "switch", id: `mod-on-${m.id}`, checked: m.enabled, "aria-label": m.name, disabled: !!m.problem });
      toggle.addEventListener("change", () => switchMod(m, toggle.checked));
      const flags = [];
      if (m.menu_page) flags.push(el("span", { class: "chip", title: "It has a page in the in-game mod menu (Insert)", text: "Page in the mod menu" }));
      for (const k of m.kinds) flags.push(el("span", { class: "chip", text: KIND[k] || k }));
      const lines = [];
      if (m.requires.length) lines.push(el("li", { text: `Needs ${m.requires_names.join(", ")}.` }));
      for (const p of m.problems) lines.push(el("li", { class: "bad", text: sentence(p) }));
      if (m.code && !(settings && settings.allow_code_mods)) lines.push(el("li", { class: "warn", text: "Runs code, so the game won't get it until you allow mods that run code (Get set up, or Options on the Settings and repair page)." }));
      if (m.enabled && m.needed_by.length) lines.push(el("li", { class: "muted", text: `${m.needed_by.join(", ")} ${m.needed_by.length > 1 ? "need" : "needs"} it.` }));
      for (const w of m.warnings || []) lines.push(el("li", { class: "warn", text: sentence(w) }));
      // Made for an older build of the game (gamebuild.py): left out unless the player uses it anyway. A data
      // mod is checked on the new version first (the re-check): one that didn't build says why.
      const old = m.outdated;
      const failedCheck = old && !old.allowed && m.checkable && m.rechecked && m.rechecked !== "ok" && !m.rechecked.startsWith("couldn't check");
      if (old) {
        lines.push(el("li", { class: old.allowed ? "warn" : "bad", text: old.allowed
          ? "Made for an older version of the game, and used anyway: it may not work, or may behave unpredictably."
          : failedCheck ? `Made for an older version of the game, and checked on this one: ${m.rechecked}. It's left out until its maker updates it.`
            : "Made for an older version of the game, so it's left out until it's updated." }));
      }
      if (m.rechecked === "ok" && m.rechecked_since_apply) lines.push(el("li", { class: "muted", text: "Checked after the game update: it builds on this version." }));

      const more = open.has(m.id);
      const card = el("div", { class: "mod" + (m.enabled ? "" : " off"), "data-key": `mod:${m.id}` },
        toggle,
        el("div", { class: "mod-body" },
          el("div", { class: "mod-name" }, el("strong", { text: m.name }),
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
      if (failedCheck && m.enabled && !(state && state.allow === m.id)) {
        // The build has shown it fails on this version: Turn it off first; it's checked again once it changes,
        // and "Use it anyway…" stays for a creator who knows better (the Apply then stops at what failed).
        card.append(el("div", { class: "row mod-wide" },
          el("button", { class: "btn small", "aria-label": `Turn ${m.name} off`, text: "Turn it off", onclick: () => switchMod(m, false) }),
          el("span", { class: "muted", text: "Its maker has to update it for this version. It's checked again when the mod changes." })));
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
              el("span", { class: "muted", text: failedCheck ? "Using it anyway puts in what the check said fails: Apply stops at it until you choose Apply the rest anyway."
                : m.checkable ? "Or wait for its maker to update it." : "It can't be checked here (code, or the game's own kind of files): its maker has to update it." })));
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
      toast(`Building ${m.name}... (the first build compiles the script loader too: a few minutes)`);
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
          // One of the mods that go with Clan Mod Studio: its latest release from GitHub, your settings kept.
          m.addon ? el("button", { class: "btn small", text: "Get the latest", onclick: async () => {
            toast(`Looking for a newer ${m.name} on GitHub…`);
            try {
              const r = await api.post(`/addons/${encodeURIComponent(m.id)}`, {});
              toast(addonToast(r.result, settings && settings.allow_code_mods));
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

    // The list's head (its count, Find a mod and the All, On, Off chips) is made once, so the search box keeps
    // what's typed, the caret and the focus while the cards under it are drawn again.
    const count = el("span", { class: "muted" });
    const searchBox = el("input", { type: "search", id: "mod-search", placeholder: "Find a mod", "aria-label": "Find a mod" });
    searchBox.addEventListener("input", () => { search = searchBox.value; renderList(); });
    const chips = ["all", "on", "off"].map(f => el("button", { class: "chip", id: `mod-show-${f}`, "aria-pressed": String(filter === f), text: { all: "All", on: "On", off: "Off" }[f],
      onclick: () => { filter = f; renderList(); } }));
    const cards = el("div", { class: "mod-cards", "aria-live": "off" });
    listBox.append(
      el("div", { class: "row spread" }, el("h2", { text: "Your mods" }), count),
      el("div", { class: "row" }, searchBox, el("div", { class: "row", role: "group", "aria-label": "Show" }, ...chips)),
      cards);

    function renderList(state = null) {
      const shown = mods.filter(m => (filter === "all" || (filter === "on") === m.enabled) && matches(m, search));
      const presets = shown.filter(m => m.preset);
      // String(): a name that isn't text (a mistake in a mod.json) mustn't stop the list from showing.
      const byName = (a, b) => String(a.name).localeCompare(String(b.name));
      const rest = shown.filter(m => !m.preset).sort(byName);
      count.textContent = `${mods.filter(m => m.enabled).length} of ${mods.length} on`;
      for (const c of chips) c.setAttribute("aria-pressed", String(c.id === `mod-show-${filter}`));
      clear(cards);
      if (!mods.length) cards.append(el("p", { class: "empty", text: "No mods yet. Add one above." }));
      else if (!shown.length) cards.append(el("p", { class: "empty", text: "No mods match." }));
      for (const m of rest) cards.append(modCard(m, state));
      if (presets.length) {
        cards.append(el("h3", { class: "group", text: `Colour palettes (${presets.length})` }),
          el("p", { class: "note", text: "Each recolours your cats' coats. The Palettes page shows them side by side and switches between them in one go." }));
        for (const m of presets.sort(byName)) cards.append(modCard(m, state));
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
      const [, , , changes] = await Promise.all([renderSetup(), renderAddons(), renderUpdate(), renderChanges()]);
      if (notify) bus.emit("mods-changed", { from: "mods" });
      maybeRecheck(changes);
    }

    renderAdd();
    const off = [
      bus.on("installed", () => renderChanges()),
      bus.on("mods-changed", d => { if (!d || d.from !== "mods") refresh({ notify: false }); }),
      // Coming back to the window: the steps and the add-ons as they are now (GitHub isn't asked).
      bus.on("focus", () => { renderSetup(); renderAddons(); }),
    ];
    await refresh();
    return { unmount() { off.forEach(f => f()); } };
  },
};
