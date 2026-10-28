// Mod packs: a set of mods shared and played together as one experience (wcmods/packs.py). Make one from
// your mods, save it as a .zip that carries them all, and play one on its own (every other mod off, but your
// own tools) or with your own mods.
export default {
  title: "Mod packs",
  async mount(root, wc) {
    const { el, api, clear, toast, bus } = wc;
    const playingBox = el("div");
    const list = el("div", { class: "stack" });
    const form = el("div", { class: "card", "data-key": "pack-form" });
    let editing = null;   // the pack being changed, or null for a new one
    // What's typed and ticked in the form, kept across its redraws (another page changing a mod redraws it).
    let draft = null;

    root.append(
      wc.pageHead({ eyebrow: "Your mods", title: "Mod packs", help: "help:packs",
        lede: "A mod pack is a set of mods that go together as one experience: a story with its cats, quests and items, the colours and names that suit it, new controls. Its .zip carries every mod in it, so whoever adds it on their Mods page gets them all. Play a pack on its own to have just its mods, then go back to yours." }),
      playingBox, list, form);

    async function draw() {
      let data;
      try { data = await api.get("/packs"); }
      catch (e) { clear(list).append(el("div", { class: "error-card", text: e.message })); return; }
      clear(playingBox);
      if (data.playing) {
        // Played on its own, even once removed: Back to my mods brings your own mods back either way.
        playingBox.append(el("div", { class: "banner info" },
          el("strong", { text: data.playing_removed ? `Playing ${data.playing_name}, which was removed` : `Playing ${data.playing_name}` }),
          el("span", { text: "Only its mods are on, with your own tools (Menu pages, Creator palettes, the Emote wheel, if you had them on). Your own mods are remembered." }),
          el("div", { class: "row" }, el("button", { class: "btn", text: "Back to my mods", onclick: () => run("/packs/stop", "Your own mods are back on.") }))));
      }
      clear(list);
      if (!data.packs.length) list.append(el("div", { class: "empty", text: "No mod packs yet. Make one below, or add one someone sent you on the Mods page (drop its .zip there)." }));
      for (const p of data.packs) list.append(card(p));
      drawForm();
    }

    function card(p) {
      const missing = p.mods.filter(m => !m.present);
      const problems = p.problems || [];
      return el("div", { class: "card", "data-key": `pack:${p.id}` },
        el("div", { class: "row spread" },
          el("div", { class: "stack", style: { gap: "2px" } },
            el("h2", { text: p.name }),
            el("span", { class: "muted", text: [p.version && `version ${p.version}`, p.author && `by ${p.author}`].filter(Boolean).join(", ") })),
          p.playing ? el("span", { class: "chip good" }, el("i", { "aria-hidden": "true" }), "Playing")
            : p.enabled ? el("span", { class: "chip good" }, el("i", { "aria-hidden": "true" }), "On") : null),
        p.description ? el("p", { class: "note", text: p.description }) : null,
        el("div", { class: "row" }, ...p.mods.map(m => el("span", { class: `chip ${m.present ? (m.enabled ? "good" : "") : "bad"}`,
          title: m.present ? (m.kinds.join(", ") || "nothing yet") : "not in your mods folder" },
          el("i", { "aria-hidden": "true" }), m.name, m.direct ? null : el("span", { class: "muted", text: " (needed)" })))),
        missing.length ? el("p", { class: "note", style: { color: "var(--bad)" }, text: `Missing: ${missing.map(m => m.name).join(", ")}. Add the pack's .zip again, or the mods on their own.` }) : null,
        // What keeps one of its mods out of the game, said here as on the Mods page's cards.
        problems.length ? el("ul", { class: "notes" }, ...problems.map(t => el("li", { class: "warn", text: `${t}.` }))) : null,
        el("div", { class: "row" },
          el("button", { class: "btn primary", text: "Play only this pack", disabled: !!missing.length || p.playing,
            onclick: () => run(`/packs/${encodeURIComponent(p.id)}/play`, `${p.name}: its mods are on and the rest are off. Press Play (top right) to start.`
              + (problems.length ? ` ${problems.join(". ")}.` : "")) }),
          // Not while it plays on its own: it's on already, and "on with my mods" isn't what's happening.
          p.playing ? null : el("button", { class: "btn", text: p.enabled ? "On with my mods" : "Turn on with my mods", disabled: p.enabled || !!missing.length,
            onclick: async () => {
              try { await api.post(`/mods/${encodeURIComponent(p.id)}/switch`, { on: true }); toast(`${p.name} is on, with your other mods.`); bus.emit("mods-changed"); draw(); }
              catch (e) { toast(e.message, "bad"); }
            } }),
          el("button", { class: "btn", text: "Save as .zip", disabled: !!missing.length, onclick: async () => {
            try { toast(`Saved ${await api.download(`/mods/${encodeURIComponent(p.id)}/zip`)}, with all ${p.mods.length} of its mods. Send it to anyone: they drop it on their Mods page.`); }
            catch (e) { toast(e.message, "bad"); }
          } }),
          el("button", { class: "btn ghost", text: "Change it", onclick: () => { editing = p; draft = null; drawForm(); form.scrollIntoView({ behavior: "smooth" }); } }),
          wc.confirmButton("Remove the pack", "Press again: the pack goes (its mods stay)", async () => {
            try {
              const r = await api.post(`/mods/${encodeURIComponent(p.id)}/remove`, {});
              toast(`Removed ${p.name}. Its mods are still in your mods folder.` + (r.back_to_my_mods ? " Your own mods are back on." : ""));
              bus.emit("mods-changed"); draw();
            }
            catch (e) { toast(e.message, "bad"); }
          }, "btn ghost danger")));
    }

    async function drawForm() {
      let mods = [];
      try { mods = (await api.get("/mods")).filter(m => !m.pack); } catch (e) { /* the list says */ }
      const p = editing;
      // A changed pack starts from its own mods that are here; one that's missing can't go in, and is said so.
      // A new one starts from the mods you have on, but your own tools, which stay on whatever pack plays.
      const dropped = p ? p.mods.filter(m => m.direct && !m.present) : [];
      const chosen = new Set(draft ? draft.chosen
        : p ? p.mods.filter(m => m.direct && m.present).map(m => m.id) : mods.filter(m => m.enabled && !m.tool).map(m => m.id));
      const value = (key, fallback) => draft ? draft[key] : fallback;
      const name = el("input", { type: "text", value: value("name", p ? p.name : ""), placeholder: "The Moonlit Path", "aria-label": "Pack name" });
      const author = el("input", { type: "text", value: value("author", p ? p.author : ""), placeholder: "your name", "aria-label": "Author" });
      const version = el("input", { type: "text", value: value("version", p ? p.version : "1.0"), size: "6", "aria-label": "Version" });
      const desc = el("textarea", { rows: "2", style: { minHeight: "54px", fontFamily: "var(--body)", fontSize: "0.95rem" }, "aria-label": "Description",
        placeholder: "What it's like to play: the story, who you'll meet, what changes." });
      desc.value = value("description", p ? p.description : "");
      // Every change to the form is kept, so a redraw (another page switched a mod) puts it back as it was.
      const keep = () => { draft = { name: name.value, author: author.value, version: version.value, description: desc.value, chosen: [...chosen] }; };
      for (const input of [name, author, version, desc]) input.addEventListener("input", keep);
      const field = (label, input) => el("label", { class: "field" }, el("span", { class: "lbl", text: label }), input);
      const picks = el("div", { class: "stack" }, ...mods.map(m => el("label", { class: "row", style: { flexWrap: "nowrap", alignItems: "start" } },
        el("input", { type: "checkbox", checked: chosen.has(m.id), "aria-label": m.name,
          onchange: e => { if (e.target.checked) chosen.add(m.id); else chosen.delete(m.id); keep(); } }),
        el("span", {}, el("strong", { text: m.name }), el("span", { class: "muted", text: ` ${m.kinds.join(", ") || "nothing in it yet"}${m.requires_names && m.requires_names.length ? ` · needs ${m.requires_names.join(", ")}` : ""}` })))));
      const saveBtn = el("button", { class: "btn primary", text: p ? "Save the pack" : "Make the pack", onclick: async () => {
        if (!name.value.trim()) { toast("Give the pack a name", "bad"); name.focus(); return; }
        try {
          const r = await api.post("/packs", { id: p ? p.id : undefined, name: name.value.trim(), author: author.value, version: version.value,
            description: desc.value, mods: [...chosen] });
          toast(`${p ? "Saved" : "Made"} ${r.name}. Save as .zip shares it.`);
          editing = null;
          draft = null;
          bus.emit("mods-changed");
          draw();
        } catch (e) { toast(e.message, "bad"); }
      } });
      clear(form).append(
        el("h2", { text: p ? `Change ${p.name}` : "Make a mod pack" }),
        el("p", { class: "note", text: "Choose the mods that make the experience. Mods they need (Sandbox mode for characters and questlines, say) go in with them. Menu pages, Creator palettes and the Emote wheel stay on whatever pack plays, so a pack needn't carry them." }),
        el("div", { style: { display: "grid", gap: "10px", alignItems: "start", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" } },
          field("Name", name), field("Author", author), field("Version", version)),
        field("Description", desc),
        el("h3", { text: "Mods in it" }),
        mods.length ? picks : el("div", { class: "empty", text: "No mods yet: make some on the pages under Make mods." }),
        dropped.length ? el("p", { class: "note warn-text", "data-key": "dropped",
          text: `Not in your mods: ${dropped.map(m => m.name).join(", ")}. ${dropped.length > 1 ? "They're" : "It's"} dropped from the pack when you save.` }) : null,
        el("div", { class: "row" }, saveBtn, p ? el("button", { class: "btn ghost", text: "Cancel", onclick: () => { editing = null; draft = null; drawForm(); } }) : null));
    }

    async function run(path, said) {
      try {
        const r = await api.post(path);
        toast(`${said}${r.off && r.off.length ? ` (${r.off.length} turned off)` : ""}`);
        bus.emit("mods-changed");
        draw();
      } catch (e) { toast(e.message, "bad"); }
    }

    bus.on("mods-changed", () => { if (root.isConnected && !root.closest("[hidden]")) draw(); });
    await draw();
    return {};
  },
};
