// Animations: the mod's own (animations.json), made in Blender and saved as glTF, for cats or one kind of animal.
// A cat's can be an emote, played on your cat from a key or the mod menu's Emotes page; scripts play any of
// them on any cat or animal of their kind (Game.anims). One can replace one of the game's own sequences instead
// ("replaces"): every cat, or every animal of its kind, plays it where the game played that one.
// See wcmods/sections/animations.py and wcmods/animations.py.
import { listEditor, field } from "../lib/story.js";

const FILES = ".glb,.gltf";
const EDITED = new Set(["id", "name", "file", "for", "clip", "loop", "speed", "blend", "emote", "key", "claws", "replaces"]);
// What a replacement doesn't take: the game plays it where it played its own, as it played that.
const NOT_WITH_REPLACES = ["loop", "speed", "blend", "emote", "key", "claws"];
const short = path => (path || "").split("/").pop();

// "Tail wave" -> "TailWave": an animation's id is part of its name in the game, letters and digits.
function animId(name, taken) {
  let base = (name || "").normalize("NFKD").replace(/[^A-Za-z0-9 ]+/g, "").split(/\s+/).filter(Boolean)
    .map(w => w[0].toUpperCase() + w.slice(1)).join("").slice(0, 40);
  if (!/^[A-Za-z]/.test(base)) base = "Anim" + base;
  let id = base, n = 2;
  while (taken.includes(id)) id = `${base}${n++}`;
  return id;
}

export default {
  title: "Animations",
  async mount(root, wc) {
    const { el, api, toast, clear, input } = wc;
    let anims = [], extra = {};
    let kinds;
    const sequences = {};   // the game's sequences by kind, read once each: [{name, paths}]
    const sequencesOf = kind => (sequences[kind] = sequences[kind] || api.get(`/game/anim-sequences?for=${encodeURIComponent(kind)}`)
      .then(r => r.sequences).catch(e => { delete sequences[kind]; throw e; }));
    try { kinds = (await api.get("/game/anim-kinds")).kinds; }
    catch (e) { root.append(el("div", { class: "error-card" }, el("strong", { text: "Couldn't read the game's animals" }), el("span", { text: e.message }))); return {}; }
    const kindLabel = k => (kinds.find(x => x.id === k) || {}).label || k;

    const target = wc.modTarget({
      file: "animations.json",
      onLoad: obj => { load(obj); draw(); },
      getValue: () => toJson(),
    });
    const out = wc.codePanel("animations.json");
    const editor = listEditor({
      noun: "animation", empty: "No animations yet. Add one: an emote for your cat, or something for a script to play on a cat or an animal.",
      label: a => [el("strong", { text: a.name || a.id }), el("span", { class: "muted", text: ` ${a.replaces ? `replaces ${short(a.replaces)}` : a.emote ? "emote" : kindLabel(a.for || "cat").toLowerCase()}` })],
      add: () => {
        const name = "New emote";
        anims.push({ id: animId(name, anims.map(x => x.id)), name, for: "cat", emote: true, _new: true });
        editor.choose(anims.length - 1);
        changed(true);
      },
    });
    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "Animations" }),
        el("h1", { text: "Animations" }),
        el("p", { class: "note", text: "Animations of your own, made in Blender and saved as glTF: emotes for your cat, played from a key or the mod menu's Emotes page, or for a script to play on any cat or animal. They play over what the cat is doing, where it stands; they don't move it. Start from a start kit: the cat (or an animal) rigged to the game's own skeleton." })),
      target.element, editor.element, out.element);
    await target.refresh();

    function load(obj) {
      extra = {};
      anims = [];
      for (const [k, v] of Object.entries(obj || {})) if (k !== "animations" && !k.startsWith("_")) extra[k] = v;
      for (const a of (obj && Array.isArray(obj.animations) ? obj.animations : [])) if (a && typeof a === "object") anims.push({ ...a });
    }
    function toJson() {
      const list = anims.map(a => {
        const o = {};
        for (const [k, v] of Object.entries(a)) {
          if (k === "_new" || k === "_info" || v === undefined || v === null || v === "" || v === false) continue;
          if (k === "for" && v === "cat") continue;
          o[k] = v;
        }
        return o;
      });
      return { _help: "Written by Clan Mod Studio (Animations). Animations of this mod's own. See docs/SDK.md, Animations.", ...extra, animations: list };
    }
    function changed(redraw = false) {
      target.markDirty();
      out.set(toJson());
      if (redraw) draw();
    }
    function draw() {
      out.set(toJson());
      editor.render(anims, drawAnim);
    }
    async function modReady() {
      return target.mods.some(m => m.id === target.current) || await target.save();
    }

    function drawAnim(box, a) {
      const redraw = () => { clear(box); drawAnim(box, a); };
      const kind = a.for || "cat";
      const cat = kind === "cat";
      const name = el("input", { type: "text", value: a.name || "", maxlength: "40", oninput: () => {
        a.name = name.value;
        if (a._new) a.id = animId(a.name, anims.filter(x => x !== a).map(x => x.id));
        idNote.textContent = idOf(a);
        changed();
      }, onchange: () => draw() });
      const idOf = x => x.replaces ? `Plays where the game played ${short(x.replaces)}; scripts don't play it by name.`
        : `In scripts: Game.anims.play(cat, "${target.current || "this-mod"}/${x.id}")`;
      const idNote = el("span", { class: "muted mono", text: idOf(a) });
      const forSel = el("select", { "aria-label": "For", onchange: () => {
        a.for = forSel.value;
        if (a.for !== "cat") { delete a.emote; delete a.key; delete a.claws; }
        delete a.file; delete a.clip; delete a._info; delete a.replaces;
        changed(true);
      } }, ...kinds.map(k => el("option", { value: k.id, text: k.label })));
      forSel.value = kind;

      // ---------- in place of one of the game's ----------
      const listId = `anim-sequences-${kind}`;
      const seqList = el("datalist", { id: listId });
      const seqFacts = el("p", { class: "note" });
      const seqInput = el("input", { type: "text", list: listId, value: a.replaces || "", spellcheck: "false", placeholder: "None: a new animation",
        "aria-label": "The game's sequence it replaces", style: { minWidth: "22em" }, onchange: async () => {
          const v = seqInput.value.trim(), path = v.split(".")[0];   // a path may come with its object's name
          if (!v) { delete a.replaces; changed(true); return; }
          const refuse = text => { toast(text, "bad"); seqInput.value = a.replaces || ""; };
          try {
            const known = await sequencesOf(kind);
            const hit = known.find(s => s.name === v || s.paths.includes(path)) || known.find(s => s.name.toLowerCase() === v.toLowerCase());
            if (!hit) return refuse(`The game has no sequence ${v} for ${kindLabel(kind).toLowerCase()}.`);
            if (hit.additive) return refuse(`${hit.name} is an additive animation (its keys are added to another pose); replacing those isn't supported.`);
            if (hit.paths.length > 1 && !hit.paths.includes(path)) return refuse(`There are ${hit.paths.length} called ${hit.name}: choose one by its path.`);
            const chosen = hit.paths.length > 1 ? path : hit.name;
            await api.get(`/game/anim-sequence?for=${encodeURIComponent(kind)}&name=${encodeURIComponent(chosen)}`);   // one wcmods can read
            a.replaces = chosen;
            for (const k of NOT_WITH_REPLACES) delete a[k];
            changed(true);
          } catch (e) { refuse(e.message); }
        } });
      sequencesOf(kind).then(list => seqList.append(...list.filter(s => !s.additive).flatMap(s => s.paths.length > 1
        ? s.paths.map(p => el("option", { value: p })) : [el("option", { value: s.name })]))).catch(() => {});
      if (a.replaces) {
        const who = kind === "cat" ? "Every cat (yours and the clans')" : `Every one of the ${kindLabel(kind).toLowerCase()}`;
        seqFacts.textContent = `${who} plays this where the game played ${short(a.replaces)}.`;
        api.get(`/game/anim-sequence?for=${encodeURIComponent(kind)}&name=${encodeURIComponent(a.replaces)}`)
          .then(s => { seqFacts.textContent = `${who} plays this where the game played ${short(a.replaces)}, fitted to its ${s.seconds.toFixed(2)} s (${s.keys} keys at the game's rate): make yours that long to see it at the speed you made it. Its footsteps and other cues stay where they were.`
            + (s.root_motion ? " The game's has root motion: where the game uses it (attacks, jumps), its root bone's movement moves the animal itself, so keep your root's path close to the game's." : ""); })
          .catch(e => { seqFacts.textContent = e.message; });
      } else {
        seqFacts.textContent = "Leave it empty for a new animation (an emote, or one for scripts). Choose one of the game's, like A_CatMaster_Trot_1, and this plays in its place instead, everywhere the game plays it. The start kit has some of them to start from.";
      }

      // ---------- the file ----------
      const facts = el("p", { class: "note" });
      const clipSel = el("select", { "aria-label": "Which animation in the file", onchange: () => { a.clip = clipSel.value || undefined; changed(); } });
      const showInfo = info => {
        clear(clipSel);
        clipSel.append(el("option", { value: "", text: info && info.clips.length ? `The first: ${info.clips[0].name}` : "The first in the file" }),
          ...(info ? info.clips : []).map(c => el("option", { value: c.name, text: `${c.name} (${c.seconds.toFixed(2)} s)` })));
        clipSel.value = a.clip || "";
        if (a.clip && clipSel.value !== a.clip) clipSel.append(el("option", { value: a.clip, text: `${a.clip} (not in the file)`, selected: true }));
        if (!info) { facts.textContent = "A glTF file (.glb) with the animal's armature animated: start from the start kit."; return; }
        const missing = info.missing.length ? ` It leaves ${info.missing.length} of the game's bones where they rest${info.missing.length <= 6 ? ` (${info.missing.join(", ")})` : ""}.` : "";
        const extraBones = info.extra.length ? ` ${info.extra.length} of its bones aren't the game's and are left out${info.extra.length <= 6 ? ` (${info.extra.join(", ")})` : ""}.` : "";
        facts.textContent = `${info.clips.length} animation${info.clips.length === 1 ? "" : "s"} in it; it has ${info.matched.length} of the game's bones.${missing}${extraBones}`;
      };
      showInfo(a._info);
      if (a.file && !a._info) {
        api.get(`/mods/${encodeURIComponent(target.current)}/animation-info?path=${encodeURIComponent(a.file)}&for=${encodeURIComponent(kind)}`)
          .then(info => { a._info = info; showInfo(info); })
          .catch(e => { facts.textContent = `Couldn't read ${a.file}: ${e.message}`; });
      }
      const picker = el("input", { type: "file", accept: FILES, hidden: true, onchange: async () => {
        const f = picker.files[0];
        picker.value = "";
        if (!f) return;
        try {
          const id = a.id;
          if (!await modReady()) return;
          toast(`Reading ${f.name}…`);
          const r = await api.upload(`/mods/${encodeURIComponent(target.current)}/animation?name=${encodeURIComponent(id)}&file=${encodeURIComponent(f.name)}&for=${encodeURIComponent(kind)}`,
            f, "application/octet-stream");
          // Saving a new mod first reads its file again, so the animation is looked up again.
          const live = anims.find(x => x.id === id) || a;
          live.file = r.path;
          live._info = r;
          if (live.clip && !r.clips.some(c => c.name === live.clip)) delete live.clip;
          toast(`Added ${f.name}: ${r.clips.map(c => `${c.name} (${c.seconds.toFixed(1)} s)`).join(", ")}.`);
          changed(true);
        } catch (e) { toast(e.message, "bad"); }
      } });
      const kit = el("button", { class: "btn ghost small", text: `Save a start kit to animate (${kindLabel(kind).toLowerCase()})`, onclick: async () => {
        kit.disabled = true;
        toast("Making the start kit…");
        try { toast(`Saved ${await api.download(`/game/anim-kit?for=${encodeURIComponent(kind)}`)}: import the .glb into Blender; README.txt says the rest.`); }
        catch (e) { toast(e.message, "bad"); }
        kit.disabled = false;
      } });
      const fileRow = el("div", { class: "row" },
        a.file ? el("span", { class: "muted mono", text: a.file }) : null,
        el("button", { class: "btn small", text: a.file ? "Choose another…" : "Choose a glTF file…", onclick: () => picker.click() }), kit);

      // ---------- how it plays ----------
      const loop = el("input", { type: "checkbox", checked: !!a.loop, onchange: () => { a.loop = loop.checked || undefined; changed(); } });
      const speed = el("input", { type: "number", min: "0.1", max: "10", step: "0.05", value: a.speed ?? 1, style: { width: "6em" }, "aria-label": "Speed",
        onchange: () => { const v = Math.max(0.1, Math.min(10, Number(speed.value) || 1)); a.speed = v === 1 ? undefined : v; speed.value = v; changed(); } });
      const blend = el("input", { type: "number", min: "0", max: "2", step: "0.05", value: a.blend ?? 0.25, style: { width: "6em" }, "aria-label": "Blend",
        onchange: () => { const v = Math.max(0, Math.min(2, Number(blend.value))); a.blend = Number.isFinite(v) && v !== 0.25 ? v : undefined; blend.value = a.blend ?? 0.25; changed(); } });
      const cards = [
        el("div", { class: "card" },
          field("Name", name, cat ? "What the Emotes page calls it." : null), idNote,
          el("div", { style: { display: "grid", gap: "10px", alignItems: "start", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" } },
            field("For", forSel, "Every cat shares one skeleton; each kind of animal has its own, and plays only its own animations."))),
        el("div", { class: "card" }, el("h3", { text: "Replaces one of the game's" }),
          field("The game's sequence", el("div", { class: "row" }, seqInput, seqList)), seqFacts),
        el("div", { class: "card" }, el("h3", { text: "The animation" }),
          el("p", { class: "note", text: "Animate the start kit's armature in Blender, keeping its bones' names, then File > Export > glTF 2.0 as glTF Binary (.glb) with Animation on. Units are metres with Y up, Blender's own settings. Bones you don't move hold their place; moving the root moves the body, not the cat." }),
          fileRow, picker, field("Which animation in the file", clipSel), facts),
      ];
      if (!a.replaces) cards.push(
        el("div", { class: "card" }, el("h3", { text: "How it plays" }),
          el("label", { class: "row" }, loop, el("span", { text: "Loop until it's stopped (a script stops it, or for an emote, its key again or walking off)" })),
          el("div", { class: "row" }, el("span", { class: "lbl", text: "Speed" }), speed, el("span", { class: "muted", text: "1 is as made" }),
            el("span", { class: "lbl", text: "Blend" }), blend, el("span", { class: "muted", text: "seconds from what it was doing, and back" }))));
      if (cat && !a.replaces) {
        const emote = el("input", { type: "checkbox", checked: !!a.emote, onchange: () => { a.emote = emote.checked || undefined; if (!a.emote) delete a.key; changed(true); } });
        const claws = el("input", { type: "checkbox", checked: !!a.claws, onchange: () => { a.claws = claws.checked || undefined; changed(); } });
        const keyLabel = el("span", { class: "mono", text: a.key || "no key" });
        const pickKey = el("button", { class: "btn small", text: "Press a key…", disabled: !a.emote, onclick: () => {
          pickKey.textContent = "Press a key (Escape for none)…";
          const onKey = e => {
            e.preventDefault(); e.stopPropagation();
            window.removeEventListener("keydown", onKey, true);
            if (e.code === "Escape") delete a.key;
            else {
              const k = input.keyFromEvent(e);
              if (!k) { toast(`That key (${e.code}) isn't one the game understands.`, "bad"); pickKey.textContent = "Press a key…"; return; }
              a.key = k;
            }
            changed(); redraw();
          };
          window.addEventListener("keydown", onKey, true);
        } });
        cards.push(el("div", { class: "card" }, el("h3", { text: "Your cat" }),
          el("label", { class: "row" }, emote, el("span", { text: "An emote: on the mod menu's Emotes page (Insert), for your cat" })),
          el("div", { class: "row" }, el("span", { class: "lbl", text: "Key" }), keyLabel, pickKey,
            el("span", { class: "muted", text: "pressed in the game, it plays (or stops) the emote. Pick one the game doesn't use, like F5 to F8." })),
          el("label", { class: "row" }, claws, el("span", { text: "Claws out while it plays (the game's animations keep them in)" }))));
      }
      const rest = Object.keys(a).filter(k => !EDITED.has(k) && !k.startsWith("_"));
      if (rest.length) cards.push(el("p", { class: "note", text: `Also set in animations.json, kept as it is: ${rest.join(", ")}.` }));
      cards.push(el("div", { class: "row" },
        wc.confirmButton(`Remove ${a.name || "this animation"}`, "Press again to remove", () => { anims.splice(anims.indexOf(a), 1); changed(true); }, "btn danger")));
      box.append(...cards);
    }
    return {};
  },
};
