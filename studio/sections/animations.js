// Animations: the mod's own (animations.json), for cats or one kind of animal. Each comes from one of the game's
// own animations (no Blender needed) or a glTF file made in Blender, and does one of three things: an emote on
// your cat (a key, and the mod menu's Emotes page), plays where the game plays one of its own ("replaces":
// every cat, or every animal of its kind, plays it there), or waits for scripts and stories (Game.anims).
// See wcmods/sections/animations.py and wcmods/animations.py; the page's pure parts are in lib/animations-model.js.
import { listEditor, field, lastApply } from "../lib/story.js";
import { EDITED, ROLE_KEYS, SOURCE_KEYS, KIND_KEYS, NEW_NAME, animId, toJson, sourceOf, roleOf, switchChoice,
  sequenceGroups, sequenceOptions, findSequence, plainName, emoteReserved } from "../lib/animations-model.js";

const FILES = ".glb,.gltf";

export default {
  title: "Animations",
  async mount(root, wc) {
    const { el, api, toast, clear, input } = wc;
    let anims = [], extra = {};
    const stash = new WeakMap();     // what a switch put aside, by animation (animations-model.switchChoice)
    const chosen = new WeakMap();    // where an animation with nothing picked yet comes from, as chosen here
    const chosenRole = new WeakMap(); // what one that's to replace a game animation, not picked yet, does
    let lastResult = null;
    const head = wc.pageHead({ eyebrow: "Animations", title: "Animations", help: "help:animations",
      lede: "Animations for your cat and the animals. Use one of the game's own (a yawn, a stretch, a photo pose) as an emote on a key, or play one where the game plays another, every cat trotting with the run, say: no Blender needed. Or make your own in Blender from a start kit. They play over what the cat is doing, where it stands." });
    let kinds;
    try { kinds = (await api.get("/game/anim-kinds")).kinds; }
    catch (e) { root.append(head, el("div", { class: "error-card" }, el("strong", { text: "Couldn't read the game's animals" }), el("span", { text: e.message }))); return {}; }
    const kindLabel = k => (kinds.find(x => x.id === k) || {}).label || k;
    // The mod menu's key, for the emote hint (the Settings page changes it).
    const ingame = await api.get("/ingame").catch(() => null);
    const menuKey = ingame ? ((ingame.keys || []).find(k => k[0] === ingame.key) || [null, ingame.key])[1] : "Insert";
    // The game's sequences by kind, read once each when a list first needs them (about 3 s for cats).
    const sequences = {}, known = {};
    const sequencesOf = kind => (sequences[kind] ||= api.get(`/game/anim-sequences?for=${encodeURIComponent(kind)}`)
      .then(r => { known[kind] = r.sequences; return r.sequences; })
      .catch(e => { delete sequences[kind]; throw e; }));
    const plain = (kind, value) => plainName(known[kind], value);

    const target = wc.modTarget({
      file: "animations.json",
      onLoad: obj => { load(obj); draw(); },
      getValue: () => toJson(anims, extra),
      onSaved: saved => wc.settleNew(anims, saved.animations),   // saved animations keep their ids from now on
    });
    const out = wc.codePanel("animations.json");
    const lastBox = el("div", { class: "banner", role: "status", hidden: true });
    const does = a => {
      const kind = a.for || "cat";
      if (roleOf(a, chosenRole) === "replaces") return `in place of ${a.replaces && known[kind] ? plain(kind, a.replaces) : "one of the game's"}`;
      if (a.emote) return `emote${a.key ? ` (${input.keyLabel(a.key)})` : ""}`;
      return `for scripts (${kindLabel(kind).toLowerCase()})`;
    };
    const editor = listEditor({
      noun: "animation", empty: "No animations yet. Add one: one of the game's as an emote for your cat, the game's own in another's place, or your own from Blender.",
      label: a => [el("strong", { text: a.name || a.id }), el("span", { class: "muted", text: ` ${does(a)}` }),
        !a.file && !a.game ? el("span", { class: "field-problem", text: " needs an animation" }) : null],
      add: () => {
        const a = { id: animId(NEW_NAME, anims.map(x => x.id)), name: NEW_NAME, for: "cat", emote: true, _new: true };
        chosen.set(a, "game");
        anims.push(a);
        editor.choose(anims.length - 1);
        changed(true);
      },
    });
    root.append(head, target.element, lastBox, editor.element, out.element);
    wc.installedEvent(target, result => { if (!wc.onlyChecked(result)) { lastResult = result; showLast(); } });
    await target.refresh();

    function load(obj) {
      extra = {};
      anims = [];
      for (const [k, v] of Object.entries(obj || {})) if (k !== "animations" && !k.startsWith("_")) extra[k] = v;
      for (const a of (obj && Array.isArray(obj.animations) ? obj.animations : [])) if (a && typeof a === "object") anims.push({ ...a });
      // The plain names of the game's sequences these name, for the list.
      for (const kind of new Set(anims.filter(a => a.game || a.replaces).map(a => a.for || "cat"))) {
        sequencesOf(kind).then(() => anims.forEach((_, i) => editor.relabel(i))).catch(() => {});
      }
    }
    function changed(redraw = false) {
      target.markDirty();
      out.set(toJson(anims, extra));
      if (redraw) draw();
    }
    function draw() {
      out.set(toJson(anims, extra));
      editor.render(anims, drawAnim);
      showLast();
    }
    function showLast() {
      const notes = lastApply(lastResult, "animations", target.current);
      clear(lastBox);
      lastBox.hidden = !notes;
      if (!notes) return;
      const nameOf = id => (anims.find(x => x.id === id) || {}).name || id;
      if (!notes.on) lastBox.append(el("strong", { text: "Last Apply: " }), "this mod wasn't in it. It's off, or it couldn't be made ready (the log says why).");
      else if (!notes.said.length) lastBox.append(el("strong", { text: "Last Apply: " }), "the animations saved here went in the game.");
      else lastBox.append(el("strong", { text: "Last Apply, about these animations: " }),
        notes.said.map(n => `${n.id ? `${nameOf(n.id)}: ` : ""}${n.why}.`).join(" "));
    }
    async function modReady() {
      return target.mods.some(m => m.id === target.current) || await target.save();
    }
    const others = a => anims.filter(x => x !== a).map(x => x.id);

    // A list of the game's sequences for `kind` (Everyday, Photo poses, All of them), read when it's first
    // shown. value: the chosen one's name or path; onPick(value, its sequence) when another is chosen.
    function sequencePicker(kind, value, label, onPick) {
      const sel = el("select", { "aria-label": label, disabled: true },
        el("option", { value: value || "", text: value ? plain(kind, value) : "Reading the game's animations…" }));
      const status = el("p", { class: "muted", style: { fontSize: "0.9rem" }, text: "Reading the game's animations…" });
      sequencesOf(kind).then(list => {
        clear(sel);
        sel.append(el("option", { value: "", text: "Choose one…" }));
        for (const [group, members] of sequenceGroups(list)) {
          sel.append(el("optgroup", { label: group }, ...members.flatMap(s => sequenceOptions(s).map(o => el("option", { value: o.value, text: o.text })))));
        }
        if (value && ![...sel.options].some(o => o.value === value)) sel.append(el("option", { value, text: `${value} (set by hand)` }));
        sel.value = value || "";
        sel.disabled = false;
        status.textContent = "";
        status.hidden = true;
      }).catch(e => { status.textContent = `Couldn't read the game's animations: ${e.message}`; });
      sel.addEventListener("change", () => {
        const s = findSequence(known[kind] || [], sel.value);
        onPick(sel.value || undefined, s);
      });
      return { element: el("div", { class: "stack" }, sel, status), select: sel };
    }
    // One of the game's sequences' facts: how long it plays, its keys, and whether it moves the animal; once the
    // list is in too, so it's said by its plain name.
    async function sequenceFacts(kind, value) {
      const [facts] = await Promise.all([api.get(`/game/anim-sequence?for=${encodeURIComponent(kind)}&name=${encodeURIComponent(value)}`),
        sequencesOf(kind).catch(() => null)]);
      return facts;
    }

    function drawAnim(box, a, i) {
      const kind = a.for || "cat";
      const cat = kind === "cat";
      const source = sourceOf(a, chosen);
      const role = roleOf(a, chosenRole);
      // ---------- what it is ----------
      const idNote = el("span", { class: "muted mono" });
      const scriptId = () => `Game.anims.play(cat, "${target.current || "this-mod"}/${a.id}")`;
      const name = el("input", { type: "text", value: a.name || "", maxlength: "40", "aria-label": "Name", placeholder: "For example: Yawn",
        oninput: () => {
          a.name = name.value;
          if (a._new && a.name.trim()) a.id = animId(a.name, others(a));
          idNote.textContent = scriptId();
          editor.relabel(i);
          changed();
        } });
      // A name left empty goes back to the animation's id, so it's never nameless.
      name.addEventListener("blur", () => {
        if (name.value.trim()) return;
        name.value = a.name = a.id;
        editor.relabel(i);
        changed();
      });
      const forSel = el("select", { "aria-label": "For", onchange: () => {
        const to = forSel.value;
        chosen.set(a, source);     // where it comes from stays chosen, without its file or sequence
        switchChoice(a, stash, "kind", kind, to, KIND_KEYS);
        a.for = to;
        if (to !== "cat") { delete a.emote; delete a.key; delete a.claws; }
        changed(true);
      } }, ...kinds.map(k => el("option", { value: k.id, text: k.label })));
      forSel.value = kind;
      const cards = [el("div", { class: "card" }, el("h3", { text: "What it is" }),
        el("div", { style: { display: "grid", gap: "10px", alignItems: "start", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" } },
          field("Name", name, cat ? "What the Emotes page calls it." : null, { required: true }),
          field("For", forSel, "Every cat shares one skeleton; each kind of animal has its own, and plays only its own animations. Changing it puts this one's animation aside until you change it back.")))];

      // ---------- the animation: where it comes from ----------
      const sourceBox = el("div", { class: "stack" });
      const pickSource = to => {
        if (to === source) return;
        switchChoice(a, stash, "source", source, to, SOURCE_KEYS);
        chosen.set(a, to);
        changed(true);
      };
      const radio = (group, value, text, on, pick, disabled = false) => el("label", { class: "row" },
        el("input", { type: "radio", name: `${group}-${i}`, value, checked: on, disabled, "aria-label": text, onchange: () => pick(value) }),
        el("span", { text }));
      if (source === "game") {
        const facts = el("p", { class: "note" });
        const tryBtn = cat ? el("button", { class: "btn small", text: "Try it on my cat", disabled: !a.game, onclick: () => tryIt(a.game, tryBtn) }) : null;
        const picker = sequencePicker(kind, a.game, "The game's animation", (v, s) => {
          if (v) a.game = v; else delete a.game;
          if (a.replaces && v && findSequence(known[kind] || [], a.replaces) === s) {
            toast("An animation can't take its own place: choose another for where it plays", "bad");
          }
          changed(true);
        });
        if (a.game) {
          sequenceFacts(kind, a.game).then(f => {
            facts.textContent = `${plain(kind, a.game)}: ${f.seconds.toFixed(2)} s.` +
              (f.root_motion ? " The game moves the animal with it where it uses it (root motion); here it plays where the animal stands." : "");
          }).catch(e => { facts.textContent = e.message; });
        } else facts.textContent = "Choose one: the everyday ones first, then the photo poses, then all of them by the game's own names.";
        sourceBox.append(field("The game's animation", picker.element), facts,
          tryBtn ? el("div", { class: "row" }, tryBtn, el("span", { class: "muted", text: "With the game running and your cat in the forest (it needs mods that run code allowed)." })) : null);
      } else {
        sourceBox.append(...fileParts(a, kind));
      }
      cards.push(el("div", { class: "card" }, el("h3", { text: "The animation" }),
        el("div", { role: "radiogroup", "aria-label": "Where it comes from", class: "stack" },
          el("span", { class: "lbl", text: "Where it comes from" }),
          radio("source", "game", "One of the game's animations", source === "game", pickSource),
          radio("source", "file", "A file I made in Blender", source === "file", pickSource)),
        sourceBox));

      // ---------- what it does ----------
      const pickRole = to => {
        if (to === role) return;
        switchChoice(a, stash, "role", role, to, ROLE_KEYS);
        if (to === "emote") a.emote = true;
        else delete a.emote;
        chosenRole.set(a, to);
        changed(true);
      };
      const roleBox = el("div", { class: "stack" });
      if (role === "emote") roleBox.append(...emoteParts(a).filter(Boolean));
      else if (role === "replaces") roleBox.append(...replaceParts(a, kind, source));
      else {
        idNote.textContent = scriptId();
        roleBox.append(el("p", { class: "note", text: "Scripts and stories play it on a cat or an animal of its kind, by its name in the game:" }), idNote);
      }
      cards.push(el("div", { class: "card" }, el("h3", { text: "What it does" }),
        el("div", { role: "radiogroup", "aria-label": "What it does", class: "stack" },
          cat ? radio("role", "emote", "An emote on my cat", role === "emote", pickRole) : null,
          radio("role", "replaces", "Plays where the game plays one of its own", role === "replaces", pickRole),
          radio("role", "scripts", "Only for scripts and stories", role === "scripts", pickRole)),
        roleBox));

      // ---------- how it plays ----------
      if (role !== "replaces") {
        const loop = el("input", { type: "checkbox", checked: !!a.loop, "aria-label": "Loop", onchange: () => { a.loop = loop.checked || undefined; changed(); } });
        const speed = el("input", { type: "number", min: "0.1", max: "10", step: "0.05", value: a.speed ?? 1, style: { width: "6em" }, "aria-label": "Speed",
          onchange: () => { const v = Math.max(0.1, Math.min(10, Number(speed.value) || 1)); a.speed = v === 1 ? undefined : v; speed.value = v; changed(); } });
        const blend = el("input", { type: "number", min: "0", max: "2", step: "0.05", value: a.blend ?? 0.25, style: { width: "6em" }, "aria-label": "Blend",
          onchange: () => { const v = Math.max(0, Math.min(2, Number(blend.value))); a.blend = Number.isFinite(v) && v !== 0.25 ? v : undefined; blend.value = a.blend ?? 0.25; changed(); } });
        cards.push(el("div", { class: "card" }, el("h3", { text: "How it plays" }),
          el("label", { class: "row" }, loop, el("span", { text: "Loop until it's stopped (a script stops it, or for an emote, its key again or walking off)" })),
          el("div", { class: "row" }, el("span", { class: "lbl", text: "Speed" }), speed, el("span", { class: "muted", text: "1 is as made" }),
            el("span", { class: "lbl", text: "Blend" }), blend, el("span", { class: "muted", text: "seconds from what it was doing, and back" }))));
      }
      const rest = Object.keys(a).filter(k => !EDITED.has(k) && !k.startsWith("_"));
      if (rest.length) cards.push(el("div", { class: "row" },
        el("p", { class: "note", text: `The game won't take these, so the animation is left out while they're here: ${rest.join(", ")}.` }),
        el("button", { class: "btn small", text: "Remove them", onclick: () => { for (const k of rest) delete a[k]; changed(true); } })));
      cards.push(el("div", { class: "row" },
        wc.confirmButton(`Remove ${a.name || "this animation"}`, "Press again to remove", () => { anims.splice(anims.indexOf(a), 1); changed(true); }, "btn danger")));
      box.append(...cards);
    }

    // ---------- an emote: its key, and the claws ----------
    function emoteParts(a) {
      const reserved = emoteReserved(anims, a, k => input.keyLabel(k));
      const keyText = el("span", { class: "chip", text: a.key ? input.keyLabel(a.key) : "No key" });
      const ask = async pad => {
        const k = await wc.captureKey({ title: `The ${pad ? "controller button" : "key"} for ${a.name || a.id}`, pad, reserved,
          message: pad ? "Press a button on your controller, or pick one below. Escape cancels."
            : "Press the key that plays it in the game. Escape cancels. F7 and F8 are free; F6 turns mouse look on and off, unless you changed its key." });
        if (k) { a.key = k; changed(true); }
      };
      const claws = el("input", { type: "checkbox", checked: !!a.claws, "aria-label": "Claws out", onchange: () => { a.claws = claws.checked || undefined; changed(); } });
      return [
        el("p", { class: "note", text: `A button on the mod menu's Emotes page (${menuKey} opens the mod menu), for your cat. Its key, pressed in the game, plays it or stops it.` }),
        el("div", { class: "row" }, el("span", { class: "lbl", text: "Key" }), keyText,
          el("button", { class: "btn small", text: "Press a key…", "aria-label": `Choose a key for ${a.name || a.id}`, onclick: () => ask(false) }),
          el("button", { class: "btn small", text: "Press a controller button…", "aria-label": `Choose a controller button for ${a.name || a.id}`, onclick: () => ask(true) }),
          a.key ? el("button", { class: "btn ghost small", text: "No key", "aria-label": `No key for ${a.name || a.id}`, onclick: () => { delete a.key; changed(true); } }) : null),
        a.key && reserved[a.key] ? el("p", { class: "field-problem", text: `${reserved[a.key]}.` }) : null,
        el("label", { class: "row" }, claws, el("span", { text: "Claws out while it plays (the game's animations keep them in)" })),
      ];
    }

    // ---------- in place of one of the game's ----------
    function replaceParts(a, kind, source) {
      const facts = el("p", { class: "note" });
      const who = kind === "cat" ? "Every cat (yours and the clans')" : `Every one of the ${kindLabel(kind).toLowerCase()}`;
      const picker = sequencePicker(kind, a.replaces, "The game's animation it plays in place of", (v, s) => {
        if (v && source === "game" && a.game && findSequence(known[kind] || [], a.game) === s) {
          toast("An animation can't take its own place: choose another", "bad");
          picker.select.value = a.replaces || "";
          return;
        }
        if (v) a.replaces = v; else delete a.replaces;
        changed(true);
      });
      if (a.replaces) {
        facts.textContent = known[kind] ? `${who} plays this where the game played ${plain(kind, a.replaces)}.` : "Reading the game's animations…";
        sequenceFacts(kind, a.replaces).then(f => {
          const what = source === "game" && a.game ? plain(kind, a.game) : "this";
          facts.textContent = `${who} plays ${what} where the game played ${plain(kind, a.replaces)} (${f.seconds.toFixed(2)} s; fitted to its ${f.keys} frames).` +
            (source === "file" ? " Make yours that long to see it at the speed you made it." : "") + " Its footsteps and other cues stay where they were." +
            (f.root_motion ? " The game moves the animal with it in some places (attacks, jumps), so keep the root's path close to the game's." : "");
        }).catch(e => { facts.textContent = e.message; });
      } else {
        facts.textContent = "Choose which of the game's it plays in place of: everywhere the game plays that one, this plays instead.";
      }
      return [field("In place of", picker.element), facts];
    }

    // ---------- a file made in Blender ----------
    function fileParts(a, kind) {
      const facts = el("p", { class: "note" });
      const clipSel = el("select", { "aria-label": "Which animation in the file", onchange: () => { a.clip = clipSel.value || undefined; changed(); } });
      const showInfo = info => {
        clear(clipSel);
        const clips = info ? info.clips : [];
        const first = clips.find(c => !c.too_long);
        clipSel.append(el("option", { value: "", text: first ? `The first: ${first.name}` : "The first in the file" }),
          ...clips.map(c => el("option", { value: c.name, disabled: !!c.too_long,
            text: `${c.name} (${c.seconds.toFixed(2)} s${c.too_long ? ": too long" : ""})` })));
        clipSel.value = a.clip || "";
        if (!info) { facts.textContent = "A glTF file (.glb) with the animal's armature animated: start from the start kit. Up to 60 s."; return; }
        const missing = info.missing.length ? ` It leaves ${info.missing.length} of the game's bones where they rest${info.missing.length <= 6 ? ` (${info.missing.join(", ")})` : ""}.` : "";
        const extraBones = info.extra.length ? ` ${info.extra.length} of its bones aren't the game's and are left out${info.extra.length <= 6 ? ` (${info.extra.join(", ")})` : ""}.` : "";
        const long = clips.filter(c => c.too_long).length;
        facts.textContent = `${clips.length} animation${clips.length === 1 ? "" : "s"} in it; it has ${info.matched.length} of the game's bones.${missing}${extraBones}` +
          (long ? ` ${long === 1 ? "One is" : `${long} are`} over ${info.max_seconds} s, which the game can't take.` : "");
      };
      showInfo(a._info);
      if (a.file && !a._info) {
        api.get(`/mods/${encodeURIComponent(target.current)}/animation-info?path=${encodeURIComponent(a.file)}&for=${encodeURIComponent(kind)}`)
          .then(info => { a._info = info; showInfo(info); })
          .catch(e => { facts.textContent = `Couldn't read ${a.file}: ${e.message}`; });
      }
      let uploading = false;
      const chooseBtn = el("button", { class: "btn small", text: a.file ? "Choose another…" : "Choose a glTF file…",
        "aria-label": a.file ? "Choose another file" : "Choose a glTF file", onclick: () => picker.click() });
      const picker = el("input", { type: "file", accept: FILES, hidden: true, onchange: async () => {
        const f = picker.files[0];
        picker.value = "";
        if (!f || uploading) return;
        uploading = true;
        chooseBtn.disabled = true;
        const id = a.id;
        try {
          if (!await modReady()) return;
          // Found again by its id, in case the page's animations were read again while the mod was saved.
          const live = anims.find(x => x.id === id) || a;
          toast(`Reading ${f.name}…`);
          const r = await api.upload(`/mods/${encodeURIComponent(target.current)}/animation?name=${encodeURIComponent(live.id)}` +
            `&file=${encodeURIComponent(f.name)}&for=${encodeURIComponent(kind)}&current=${encodeURIComponent(live.file || "")}`,
            f, "application/octet-stream");
          live.file = r.path;
          live._info = r;
          const fits = r.clips.filter(c => !c.too_long);
          if (live.clip && !fits.some(c => c.name === live.clip)) {
            toast(`${f.name} has no animation called ${live.clip} the game can take, so it plays ${fits[0].name}.`);
            delete live.clip;
          }
          if (!live.clip && r.clips[0] && r.clips[0].too_long) live.clip = fits[0].name;   // the first is too long
          toast(`Added ${f.name}: ${r.clips.map(c => `${c.name} (${c.seconds.toFixed(1)} s${c.too_long ? ", too long" : ""})`).join(", ")}.`);
          changed(true);
        } catch (e) { toast(e.message, "bad"); }
        finally { uploading = false; chooseBtn.disabled = false; }
      } });
      const kit = el("button", { class: "btn ghost small", text: `Save a start kit to animate (${kindLabel(kind).toLowerCase()})`, onclick: async () => {
        kit.disabled = true;
        toast("Making the start kit…");
        try { toast(`Saved ${await api.download(`/game/anim-kit?for=${encodeURIComponent(kind)}`)}: unzip it, then import the .glb into Blender; README.txt says the rest.`); }
        catch (e) { toast(e.message, "bad"); }
        kit.disabled = false;
      } });
      return [
        el("p", { class: "note", text: "Animate the start kit's armature in Blender, keeping its bones' names, then File > Export > glTF 2.0 as glTF Binary (.glb) with Animation on. Units are metres with Y up, Blender's own settings. Bones you don't move hold their place; moving the root moves the body, not the cat. Up to 60 seconds." }),
        el("div", { class: "row" }, a.file ? el("span", { class: "muted mono", text: a.file }) : null, chooseBtn, kit), picker,
        field("Which animation in the file", clipSel), facts];
    }

    // Play one of the game's on your cat in the running game, to see it before choosing it.
    async function tryIt(value, btn) {
      const s = findSequence(known.cat || [], value);
      const path = s ? (s.paths.length > 1 && value.startsWith("/Game/") ? value.split(".")[0] : s.paths[0]) : value;
      if (!path || !path.startsWith("/Game/")) { toast("Wait for the list of the game's animations, then try again.", "bad"); return; }
      btn.disabled = true;
      try { await api.post("/game/try-anim", { path }); toast(`Your cat plays ${plain("cat", value)} in the game.`); }
      catch (e) { toast(e.message, "bad"); }
      btn.disabled = false;
    }
    return {};
  },
};
