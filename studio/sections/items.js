// Items: herbs, materials and accessories of the mod's own (items.json): a name, a description, an icon (the
// game's, in other colours, or a picture of your own), what using a herb does, a recipe at the medicine cat's,
// for an accessory its look (a colour or a picture), and behind the Advanced fold its shape (a model of your
// own, OBJ or glTF) or, for a herb or a material, how it lies on the ground for the cat to pick up.
// They're real items in the game, everywhere, not only in Sandbox mode. See wcmods/sections/items.py; the
// page's pure parts are in lib/items-model.js.
import { listEditor, field, itemChoices, itemSelect, lastApply } from "../lib/story.js";
import { shapeDrawing, asPng, placeMesh } from "../lib/shape.js";
import { KIND, SLOTS, START_HERB, itemId, isPicture, toJson, fullTag, kindOf, giveOwn, switchKind, effectName,
  chooseEffect, whoAndWhen, badgeWords, NEW_LOOK } from "../lib/items-model.js";

// The keys the page has controls for; others an item has are listed as kept as they are (rarity among them:
// what it changes in the game hasn't been seen, so there's no control for it). target, combat, exploring and
// fight_only come with the effect chosen under Using it.
const EDITED = new Set(["id", "kind", "like", "name", "description", "icon", "effect", "type", "target", "combat",
  "exploring", "fight_only", "group", "recipe", "give", "texture", "model", "place", "opacity", "glass"]);
const MODEL_FILES = ".obj,.glb,.gltf";
const PICTURE_FILES = "image/png,image/jpeg,image/webp,image/gif,image/bmp";
const OWN_AGAIN = "A new look needs something of its own, so it's back to a colour";
// Where an accessory sits ("place"): moves in cm, turns in degrees, sizes as a factor. The sliders' ranges;
// the number boxes beside them take more, as far as items.json does.
const MOVES = [["forward", "Forward / back", "cm toward the head (- toward the tail)"], ["up", "Up / down", "cm"],
  ["left", "Left / right", "cm toward the cat's left"]];
const TURNS = [["yaw", "Turn", "degrees, its front toward the cat's left"], ["pitch", "Tip", "degrees, its front up"],
  ["roll", "Tilt", "degrees, its left side down"]];
const STRETCH = [["forward", "Length"], ["up", "Height"], ["left", "Width"]];
// The same for a model on the ground, which has no cat to be relative to: its origin is the pickup's spot.
const GROUND_MOVES = [["forward", "Forward / back", "cm"], ["up", "Up / down", "cm above the ground"], ["left", "Left / right", "cm"]];
const GROUND_TURNS = [["yaw", "Turn", "degrees around"], ["pitch", "Tip", "degrees, its front up"], ["roll", "Tilt", "degrees, its left side down"]];
const EXAMPLES = {
  consumable: { name: "Moon Herb", description: "Heals a cat under the full moon." },
  material: { name: "Moonstone", description: "A pale stone that glows at night." },
  accessory: { name: "Moonlit Collar", description: "A collar the colour of moonlight on water." },
};

export default {
  title: "Items",
  async mount(root, wc) {
    const { el, api, toast, clear } = wc;
    let items = [], extra = {};
    const stash = new WeakMap();     // what a Kind change put aside, by item (items-model.switchKind)
    const opened = new WeakSet();    // items whose Advanced fold was opened by hand
    let lastResult = null;           // the last Apply's result, for what it said about this mod's items
    const head = wc.pageHead({ eyebrow: "New items", title: "Items", help: "help:items",
      lede: "Herbs, materials and accessories of your own. They're real items: they show in the inventory with their icon, herbs do what you choose when used, accessories are worn in a look of your own, and the medicine cat can make them. Questlines can ask for them and give them as rewards. They work in story games too, not only in Sandbox mode." });
    let game;
    try { game = await api.get("/game/items"); }
    catch (e) {
      root.append(head, el("div", { class: "error-card" }, el("strong", { text: "Couldn't read the game's items" }), el("span", { text: e.message }),
        el("span", { class: "note", text: "This page starts every item from one of the game's own, so it needs the game's files." })));
      return {};
    }
    const byTag = new Map(game.items.map(i => [i.tag, i]));
    const herbs = game.items.filter(i => i.kind === "consumable");
    const materials = game.items.filter(i => i.kind === "material");
    // Every look of the neck, body and paw accessories can take a new look after it (the game always shows a
    // head accessory's first look).
    const wearables = game.items.filter(i => i.kind === "accessory" && SLOTS[i.slot] && i.look);
    const gameIds = kind => (kind === "material" ? materials : kind === "consumable" ? herbs : []).map(i => i.short);
    const start = kind => kind === "material" ? materials[0]?.short : kind === "accessory" ? wearables[0]?.short
      : (herbs.some(h => h.short === START_HERB) ? START_HERB : herbs[0]?.short);
    const missing = it => !(it.name || "").trim() ? "a name" : !(it.description || "").trim() ? "a description" : null;

    const target = wc.modTarget({
      file: "items.json",
      onLoad: obj => { load(obj); draw(); },
      getValue: () => toJson(items, extra),
    });
    const out = wc.codePanel("items.json");
    const lastBox = el("div", { class: "banner", role: "status", hidden: true });
    const editor = listEditor({
      noun: "item", empty: "No items yet. Add one: a herb that heals, a material for quests and recipes, or something to wear.",
      label: it => [el("strong", { text: it.name || it.id }), el("span", { class: "muted", text: ` ${KIND[kindOf(it, byTag)] || "item"}` }),
        missing(it) ? el("span", { class: "field-problem", text: ` needs ${missing(it)}` }) : null],
      add: () => {
        const name = "New herb";
        items.push({ id: itemId(name, items.map(x => x.id), gameIds("consumable")), kind: "consumable", like: start("consumable"),
          name, description: "", _new: true });
        editor.choose(items.length - 1);
        changed(true);
      },
    });
    root.append(head, target.element, lastBox, editor.element, out.element);
    // After an Apply, what the build said about this mod's items (wc.installedEvent: not over unsaved changes).
    wc.installedEvent(target, result => { lastResult = result; showLast(); });
    await target.refresh();

    function likeOf(it) { return byTag.get(fullTag(it.like, byTag)) || null; }
    function tagOf(it) {
      const kind = kindOf(it, byTag);
      if (kind === "accessory") {
        const like = likeOf(it);
        return like ? `Gameplay.Inventory.Cosmetic.${like.slot}.${like.accessory}.(its next look)` : "an accessory: choose which look it's a new one of";
      }
      return `Gameplay.Inventory.${kind === "material" ? "Materials" : "Consumable"}.${it.id}`;
    }
    function load(obj) {
      extra = {};
      items = [];
      for (const [k, v] of Object.entries(obj || {})) if (k !== "items" && !k.startsWith("_")) extra[k] = v;
      for (const it of (obj && Array.isArray(obj.items) ? obj.items : [])) if (it && typeof it === "object") items.push({ ...it });
    }
    function changed(redraw = false) {
      target.markDirty();
      out.set(toJson(items, extra));
      if (redraw) draw();
    }
    function draw() {
      out.set(toJson(items, extra));
      editor.render(items, drawItem);
      showLast();
    }
    function showLast() {
      const notes = lastApply(lastResult, "items", target.current);
      clear(lastBox);
      lastBox.hidden = !notes;
      if (!notes) return;
      const nameOf = id => (items.find(x => x.id === id) || {}).name || id;
      if (!notes.on) lastBox.append(el("strong", { text: "Last Apply: " }), "this mod wasn't in it. It's off, or it couldn't be made ready (the log says why).");
      else if (!notes.said.length) lastBox.append(el("strong", { text: "Last Apply: " }), "the items saved here went in the game.");
      else lastBox.append(el("strong", { text: "Last Apply, about these items: " }),
        notes.said.map(n => `${n.id ? `${nameOf(n.id)}: ` : ""}${n.why}.`).join(" "));
    }
    // The mod has to exist on disk before a file can go in its folder. Saving a new mod reads its file again,
    // so the item a picker was opened for is found again by its id afterwards (live).
    async function modReady() {
      return target.mods.some(m => m.id === target.current) || await target.save();
    }
    const live = (id, it) => items.find(x => x.id === id) || it;
    function picturePath(file) {
      return file.startsWith("pictures/") && !file.slice(9).includes("/")
        ? `/mods/${encodeURIComponent(target.current)}/picture/${encodeURIComponent(file.slice(9))}`
        : `/mods/${encodeURIComponent(target.current)}/picture?path=${encodeURIComponent(file)}`;
    }
    const others = it => items.filter(x => x !== it).map(x => x.id);

    function drawItem(box, it, i) {
      const redraw = () => changed(true);
      const kind = kindOf(it, byTag) || "consumable";
      const accessory = kind === "accessory";
      const like = likeOf(it);
      if (accessory && like && !SLOTS[like.slot]) {
        box.append(el("div", { class: "card" }, el("h3", { text: it.name || it.id }),
          el("p", { class: "note", text: "A new look for a head accessory. The game always shows a head accessory's first look, so it wouldn't show: choose a neck, body or paw accessory instead (Kind, below), or change it in items.json." })));
      }

      // ---------- what it is ----------
      const techNote = el("span", { class: "muted mono", text: tagOf(it) });
      const example = EXAMPLES[kind] || EXAMPLES.consumable;
      const nameProblem = el("span", { class: "field-problem", text: "Needed: it goes back to its technical name if you leave it empty.", hidden: true });
      const name = el("input", { type: "text", value: it.name || "", maxlength: "40", "aria-label": "Name", placeholder: `For example: ${example.name}`,
        oninput: () => {
          it.name = name.value;
          if (it._new && it.name.trim()) it.id = itemId(it.name, others(it), gameIds(kind));
          techNote.textContent = tagOf(it);
          nameProblem.hidden = !!it.name.trim();
          editor.relabel(i);
          changed();
        } });
      // A name left empty goes back to the item's id, so it's never nameless.
      name.addEventListener("blur", () => {
        if (name.value.trim()) return;
        name.value = it.name = it.id;
        nameProblem.hidden = true;
        editor.relabel(i);
        changed();
      });
      const descProblem = el("span", { class: "field-problem", text: "Needed: without a description it's left out of the game.",
        hidden: !!(it.description || "").trim() });
      const desc = el("textarea", { rows: "2", "aria-label": "Description", placeholder: `For example: ${example.description}`,
        style: { minHeight: "54px", fontFamily: "var(--body)", fontSize: "0.98rem" } });
      desc.value = it.description || "";
      desc.addEventListener("input", () => {
        it.description = desc.value;
        descProblem.hidden = !!desc.value.trim();
        editor.relabel(i);
        changed();
      });

      const kindSel = el("select", { "aria-label": "Kind", onchange: () => {
        switchKind(it, kindSel.value, stash, start, kind);
        if (it._new) it.id = itemId(it.name, others(it), gameIds(it.kind));
        changed(true);
      } }, el("option", { value: "consumable", text: "Herb (it can be used)" }), el("option", { value: "material", text: "Material (for quests and recipes)" }),
        el("option", { value: "accessory", text: "Accessory (something to wear)" }));
      kindSel.value = kind;
      const pool = kind === "material" ? materials : accessory ? wearables : herbs;
      const likeSel = el("select", { "aria-label": accessory ? "A new look of" : "Starts from", onchange: () => { it.like = likeSel.value; changed(true); } });
      if (accessory) {
        for (const [slot, label] of Object.entries(SLOTS)) {
          const list = wearables.filter(w => w.slot === slot);
          if (list.length) likeSel.append(el("optgroup", { label }, ...list.map(w => el("option", { value: w.short, text: w.name }))));
        }
      } else likeSel.append(...pool.map(g => el("option", { value: g.short, text: g.name })));
      likeSel.value = like ? like.short : pool[0]?.short;
      if (like && likeSel.value !== like.short) likeSel.append(el("option", { value: like.short, text: like.name, selected: true }));

      const icon = el("img", { class: "item-icon", alt: `${it.name || "The item"}'s icon` });
      const whatItIs = el("div", { class: "card" }, el("h3", { text: "What it is" }),
        el("div", { class: "cat-head" },
          el("div", { class: "icon-box" }, icon),
          el("div", { class: "stack", style: { flex: "1", minWidth: "220px" } },
            field("Name", name, null, { required: true }), nameProblem,
            field("Description", desc, kind === "consumable" ? "The game's herbs often start with what they do: \"Health Recovery (medium).\"" : null, { required: true }),
            descProblem)),
        el("div", { style: { display: "grid", gap: "10px", alignItems: "start", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" } },
          field("Kind", kindSel, "Changing the kind puts its look, model and recipe aside; they come back if you change it back before you leave the page."),
          field(accessory ? "A new look of" : "Starts from", likeSel, accessory
            ? "The accessory it's worn as: its place on the cat, its shape unless you give it a model, and its icon. Head accessories can't take new looks."
            : "Its icon, badge and what it does, unless you change them below.")),
        kind === "consumable" ? el("p", { class: "muted", text: whoAndWhen(it, like || {}) }) : null,
        el("details", { class: "fold", "data-key": "items:tag" },
          el("summary", {}, el("span", { text: "Technical name" })),
          el("p", { class: "note", text: "What the game calls it. You don't need it, unless a script or another mod names this item." }), techNote));

      // ---------- the icon ----------
      const iconMode = typeof it.icon === "string" ? (isPicture(it.icon) ? "own" : "item")
        : it.icon && typeof it.icon === "object" ? "tint" : "like";
      const gamePath = src => !src ? null : src.startsWith("/Game/") ? src : fullTag(src, byTag);
      const showIcon = async () => {
        let path;
        if (iconMode === "own") path = picturePath(it.icon);
        else {
          const from = iconMode === "item" ? gamePath(it.icon) || it.icon : iconMode === "tint" && it.icon.from ? gamePath(it.icon.from) : fullTag(it.like, byTag);
          path = `/game/icon?of=${encodeURIComponent(from || "")}${iconMode === "tint" && it.icon.tint ? `&tint=${encodeURIComponent(it.icon.tint)}` : ""}`;
        }
        try { icon.src = await api.image(path); icon.hidden = false; } catch (e) { icon.hidden = true; }
      };
      showIcon();
      const iconPicker = picturePicker(it, "icon", "-icon", (item, r) => {
        item.icon = r.path;
        toast(`Added the icon (${r.width} x ${r.height}). ${accessory ? "Accessories' icons are 256 x 256" : "Inventory icons are 512 x 512"} with a see-through background.`);
      });
      const modeSel = el("select", { "aria-label": "Icon", onchange: () => {
        if (modeSel.value === "like") delete it.icon;
        else if (modeSel.value === "tint") it.icon = { tint: (it.texture && it.texture.tint) || NEW_LOOK };
        else if (modeSel.value === "item") it.icon = (pool[0] || {}).short;
        else { iconPicker.click(); modeSel.value = iconMode; return; }
        redraw();
      } },
      el("option", { value: "like", text: "The icon of the item it starts from" }),
      el("option", { value: "tint", text: "That icon in another colour" }),
      el("option", { value: "item", text: "Another item's icon" }),
      el("option", { value: "own", text: "A picture of my own…" }));
      modeSel.value = iconMode;
      const iconExtra = el("div", { class: "row" });
      if (iconMode === "tint") {
        const tint = el("input", { type: "color", value: it.icon.tint || NEW_LOOK, "aria-label": "Colour", onchange: () => { it.icon = { ...it.icon, tint: tint.value }; changed(); showIcon(); } });
        iconExtra.append(el("span", { class: "lbl", text: "Colour" }), tint);
      } else if (iconMode === "item") {
        iconExtra.append(itemSelect(itemChoices({ items: game.items.filter(g => g.kind !== "accessory") }), gamePath(it.icon) || it.icon,
          v => { if (v) it.icon = (byTag.get(v) || {}).short || v; else delete it.icon; redraw(); }, "Whose icon"));
      } else if (iconMode === "own") {
        iconExtra.append(el("span", { class: "muted mono", text: it.icon }), el("button", { class: "btn small", text: "Choose another…", "aria-label": "Choose another picture for the icon", onclick: () => iconPicker.click() }));
      }
      const paint = paintOver(fullTag(iconMode === "item" ? it.icon : iconMode === "tint" && it.icon.from ? it.icon.from : it.like, byTag), "icon");
      const iconCard = el("div", { class: "card" }, el("h3", { text: "Icon" }), field("Icon", modeSel), iconExtra, iconPicker,
        paint ? el("div", { class: "stack" }, el("div", { class: "row" }, paint),
          el("ol", { class: "note", style: { margin: "0", paddingLeft: "1.3em" } },
            el("li", { text: "Save the game's icon to paint over, with the button above." }),
            el("li", { text: "Paint over it in any drawing program, keeping its size and its see-through background." }),
            el("li", { text: "Choose it here with \"A picture of my own…\"." }))) : null);

      const cards = [whatItIs, iconCard];
      // ---------- using it ----------
      if (kind === "consumable") {
        const effect = el("select", { "aria-label": "What it does", onchange: () => { chooseEffect(it, effect.value, herbs); redraw(); } },
          el("option", { value: "", text: `The same as ${like ? like.name : "the herb it starts from"}${like && like.words ? `: ${like.words}` : ""}` }),
          ...game.effects.map(e => el("option", { value: e, text: effectName(e, herbs) })));
        effect.value = it.effect || "";
        const group = el("select", { "aria-label": "Badge on its icon", onchange: () => { it.group = group.value || undefined; changed(); } },
          el("option", { value: "", text: `The same as ${like ? `${like.name}'s${like.group && like.group !== "None" ? `: ${like.group}` : ""}` : "the herb it starts from"}` }),
          ...game.groups.map(g => el("option", { value: g, text: badgeWords(g, herbs) })));
        group.value = it.group || "";
        cards.push(el("div", { class: "card" }, el("h3", { text: "Using it" }),
          el("div", { style: { display: "grid", gap: "10px", alignItems: "start", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" } },
            field("What it does", effect, "It does what that herb of the game's does, for whoever that herb is for, when that herb can be used."),
            field("Badge on its icon", group, "The small picture on its icon in the inventory."))));
      }
      if (kind !== "material") cards.push(recipeCard(it));
      const give = el("input", { type: "number", min: "0", max: "999", value: it.give || 0, style: { width: "6em" }, "aria-label": "Start with",
        onchange: () => { const n = Math.max(0, Math.min(999, Math.round(Number(give.value) || 0))); if (n) it.give = n; else delete it.give; changed(); } });
      cards.push(el("div", { class: "card" }, el("h3", { text: "Starting with some" }),
        el("div", { class: "row" }, give, el("span", { class: "muted", text: "of them, 0 for none" })),
        el("p", { class: "note", text: "Given once, to the cat you're playing, when you Apply. It needs a save to put them in: start the game once first." })));
      if (accessory && like) cards.push(lookCard(it, like, kind));

      // ---------- advanced: a 3D model of your own ----------
      if (!accessory || like) {
        const adv = el("details", { class: "card fold", "data-key": "items:advanced", open: !!(it.model || it.place) || opened.has(it) },
          el("summary", {}, el("h3", { text: "Advanced: a 3D model of your own (needs Blender)" }),
            el("span", { class: "muted", text: "In the game it needs the script loader, which Get set up installs" })));
        let filled = false;
        const fill = () => {
          if (filled) return;
          filled = true;
          adv.append(...(accessory ? shapeParts(it, like, kind) : groundParts(it, like)));
        };
        adv.addEventListener("toggle", () => {
          if (adv.open) { opened.add(it); fill(); } else opened.delete(it);
        });
        if (adv.open) fill();
        cards.push(adv);
      }
      const rest = Object.keys(it).filter(k => !EDITED.has(k) && !k.startsWith("_"));
      if (rest.length) cards.push(el("p", { class: "note", text: `Also set in items.json, kept as it is: ${rest.join(", ")}.` }));
      cards.push(el("div", { class: "row" },
        wc.confirmButton(`Remove ${it.name || "this item"}`, "Press again to remove", () => { items.splice(i, 1); changed(true); }, "btn danger")));
      box.append(...cards);
    }

    // A hidden file input for one of an item's pictures (`key`: "icon" or "texture"): any picture the browser
    // opens, sent as a PNG to the mod's pictures/ folder, named after the item (its id and `suffix`). It
    // never lands on another item's file: the route takes a free name unless it's this item's own (current).
    function picturePicker(it, key, suffix, done) {
      const picker = el("input", { type: "file", accept: PICTURE_FILES, hidden: true, onchange: async () => {
        const f = picker.files[0];
        picker.value = "";
        if (!f) return;
        const id = it.id;
        try {
          if (!await modReady()) return;
          const item = live(id, it);
          const current = isPicture(item[key]) ? item[key] : "";
          const png = await asPng(f);
          const r = await api.upload(`/mods/${encodeURIComponent(target.current)}/picture?name=${encodeURIComponent(item.id + suffix)}&current=${encodeURIComponent(current)}`,
            png, "application/octet-stream");
          api.forget(picturePath(r.path));
          done(item, r);
          changed(true);
        } catch (e) { toast(e.message, "bad"); }
      } });
      return picker;
    }
    // A model the same way, in the mod's models/ folder.
    function modelPicker(it, suffix, ground) {
      const picker = el("input", { type: "file", accept: MODEL_FILES, hidden: true, onchange: async () => {
        const f = picker.files[0];
        picker.value = "";
        if (!f) return;
        const id = it.id;
        try {
          if (!await modReady()) return;
          const item = live(id, it);
          toast(`Reading ${f.name}…`);
          const r = await api.upload(`/mods/${encodeURIComponent(target.current)}/model?name=${encodeURIComponent(item.id + suffix)}&file=${encodeURIComponent(f.name)}` +
            `&current=${encodeURIComponent(item.model || "")}${ground ? "&ground=1" : ""}`, f, "application/octet-stream");
          item.model = r.path;
          const far = !ground && r.farthest_cm > 25;
          toast(`Added ${f.name}: ${r.vertices} vertices, ${r.triangles} triangles, ${r.size_cm.join(" x ")} cm.` +
            (far ? " It's far from the cat: models are in metres, around the cat of the start kit (or move it into place below)." : ""), far ? "bad" : "info");
          changed(true);
        } catch (e) { toast(e.message, "bad"); }
      } });
      return picker;
    }

    // "Save the game's picture to paint over": an item's icon or an accessory's look, full size, as a PNG.
    function paintOver(of, what) {
      if (!of) return null;
      const btn = el("button", { class: "btn ghost small", text: `Save the game's ${what} to paint over`, onclick: async () => {
        btn.disabled = true;
        toast(`Making the ${what} as a picture…`);
        const which = what === "look" ? "look" : "icon";
        try { toast(`Saved ${await api.download(`/game/texture?of=${encodeURIComponent(of)}&what=${which}`)}: paint over it, keep the size, and choose it here.`); }
        catch (e) { toast(e.message, "bad"); }
        btn.disabled = false;
      } });
      return btn;
    }

    // ---------- an accessory's look: a colour, a picture, or the look as it is; and opacity ----------
    function lookCard(it, like, kind) {
      const tex = it.texture;
      const mode = isPicture(tex) ? "own" : tex && typeof tex === "object" ? "tint" : "like";
      const preview = el("img", { class: "item-icon", alt: `${it.name || "The accessory"}'s look` });
      (async () => {
        const path = mode === "own" ? picturePath(tex)
          : `/game/icon?of=${encodeURIComponent(like.look)}${mode === "tint" && tex.tint ? `&tint=${encodeURIComponent(tex.tint)}` : ""}`;
        try { preview.src = await api.image(path); } catch (e) { preview.hidden = true; }
      })();
      const picker = picturePicker(it, "texture", "-look", (item, r) => {
        item.texture = r.path;
        toast(`Added the look (${r.width} x ${r.height}). The game's are 2048 x 2048; others are scaled to that.`);
      });
      const sel = el("select", { "aria-label": "Look", onchange: () => {
        if (sel.value === "tint") it.texture = { tint: NEW_LOOK };
        else if (sel.value === "like") delete it.texture;
        else { picker.click(); sel.value = mode; return; }
        changed(true);
      } },
      el("option", { value: "tint", text: `${like.name}'s look in another colour` }),
      el("option", { value: "own", text: "A picture of my own…" }),
      it.model || it.place || it.opacity !== undefined || mode === "like" ? el("option", { value: "like", text: `${like.name}'s look as it is` }) : null);
      sel.value = mode;
      const extra = el("div", { class: "row" });
      if (mode === "tint") {
        const tint = el("input", { type: "color", value: tex.tint || NEW_LOOK, "aria-label": "Colour",
          onchange: () => { it.texture = { ...tex, tint: tint.value }; changed(true); } });
        extra.append(el("span", { class: "lbl", text: "Colour" }), tint);
      } else if (mode === "own") {
        extra.append(el("span", { class: "muted mono", text: tex }), el("button", { class: "btn small", text: "Choose another…", "aria-label": "Choose another picture for the look", onclick: () => picker.click() }));
      }
      extra.append(paintOver(fullTag(it.like, byTag), "look"));
      // Opacity: below 100% it's worn as glass, as the game has no see-through material for cats with a picture.
      const shown = Math.round((it.opacity ?? 1) * 100);
      const glassNote = el("span", { class: "muted", style: { fontSize: "0.85rem" } });
      const glass = el("input", { type: "color", value: it.glass || (tex && tex.tint) || "#ffffff", "aria-label": "Glass colour",
        onchange: () => { it.glass = glass.value; changed(true); } });
      const glassRow = el("div", { class: "row" }, el("span", { class: "lbl", text: "Glass colour" }), glass, glassNote);
      const opacity = el("input", { type: "range", min: "0", max: "100", step: "5", value: String(shown), "aria-label": "Opacity",
        style: { flex: "1", minWidth: "140px" } });
      const pct = el("span", { class: "mono", text: `${shown}%` });
      const showGlass = () => {
        glassRow.hidden = (it.opacity ?? 1) >= 1;
        glassNote.textContent = "The cat shows through it: it's worn as glass of this colour, without its picture.";
      };
      let ownAgain = false;
      opacity.addEventListener("input", () => {
        const v = Number(opacity.value) / 100;
        pct.textContent = `${opacity.value}%`;
        if (v >= 1) { delete it.opacity; delete it.glass; } else { it.opacity = v; it.glass = it.glass || glass.value; }
        if (giveOwn(it, kind)) ownAgain = true;
        showGlass();
        changed();
      });
      opacity.addEventListener("change", () => { if (ownAgain) toast(OWN_AGAIN); changed(true); });
      showGlass();
      const see = el("div", { class: "stack" }, el("div", { class: "row" }, el("span", { class: "lbl", text: "Opacity" }), opacity, pct), glassRow,
        el("p", { class: "note", text: "100% shows its look. Below that the cat shows through it, as glass in one colour: the game has no see-through material for cats that shows a picture. Like a model, it needs the script loader in the game." }));
      return el("div", { class: "card" }, el("h3", { text: "Look" }),
        el("p", { class: "note", text: "The picture on it, wrapped around its shape. A picture of your own is painted over the game's (save it below): its colours land where the game's do on the shape, or on a model of your own through its UVs. PNG, JPEG or WebP; a see-through background stays see-through only as PNG." }),
        el("div", { class: "cat-head" }, el("div", { class: "icon-box" }, preview),
          el("div", { class: "stack", style: { flex: "1", minWidth: "220px" } }, field("Look", sel), extra)), see, picker);
    }

    // ---------- an accessory's shape: its own, or a model of the mod's; and where it sits ----------
    function shapeParts(it, like, kind) {
      const drawing = shapeDrawing();
      const facts = el("p", { class: "muted", style: { fontSize: "0.9rem" } });
      let view = null, model = null;
      const paint = () => {
        if (!view) return;
        const base = model || (it.place ? view.accessory : null);
        drawing.draw({ cat: view.cat, accessory: view.accessory, model: base ? placeMesh(base, it.place) : null,
          opacity: it.opacity ?? 1, glass: it.glass });
      };
      const picker = modelPicker(it, "", false);
      const sel = el("select", { "aria-label": "Shape", onchange: () => {
        if (sel.value === "like") {
          delete it.model;
          if (giveOwn(it, kind)) toast(OWN_AGAIN);
          changed(true);
        } else { picker.click(); sel.value = it.model ? "own" : "like"; }
      } },
      el("option", { value: "like", text: `${like.name}'s own shape` }),
      el("option", { value: "own", text: "A model of my own (OBJ or glTF)…" }));
      sel.value = it.model ? "own" : "like";
      const kit = el("button", { class: "btn ghost small", text: "Save a start kit to model on", onclick: async () => {
        kit.disabled = true;
        toast("Making the start kit…");
        try { toast(`Saved ${await api.download(`/game/model-kit?of=${encodeURIComponent(like.short)}`)}: unzip it, then open the .obj files in Blender; README.txt says the rest.`); }
        catch (e) { toast(e.message, "bad"); }
        kit.disabled = false;
      } });
      const row = el("div", { class: "row" });
      if (it.model) row.append(el("span", { class: "muted mono", text: it.model }), el("button", { class: "btn small", text: "Choose another…", "aria-label": "Choose another model", onclick: () => picker.click() }));
      row.append(kit);
      (async () => {
        try {
          view = await api.get(`/game/accessory?of=${encodeURIComponent(like.short)}`);
          if (it.model) {
            try {
              model = await api.get(`/mods/${encodeURIComponent(target.current)}/model-view?path=${encodeURIComponent(it.model)}`);
              facts.textContent = `${model.vertices} vertices, ${model.triangles} triangles, ${model.size_cm.join(" x ")} cm; ` +
                (model.farthest_cm > 25 ? `part of it is ${model.farthest_cm} cm from the cat as it's made: move it into place below, or check it's in metres.`
                  : `at most ${model.farthest_cm} cm from the cat as it's made.`);
            } catch (e) { facts.textContent = `Couldn't read ${it.model}: ${e.message}`; }
          } else facts.textContent = `${like.name} as the game has it. A model of your own takes its place for this look only.`;
          paint();
        } catch (e) { facts.textContent = `Couldn't draw it: ${e.message}`; }
      })();
      return [el("h4", { text: "Shape and place", style: { margin: "0" } }),
        el("p", { class: "note", text: "A model of your own, made in Blender or any 3D program and saved as OBJ or glTF (.glb). Make it around the cat of the start kit, in metres with Y up (the programs' usual settings), or anywhere and move it into place here: wherever it sits, it follows the nearest part of the cat as it moves, and grows and slims with the cat's build. Its look is the picture under Look, through the model's UVs." }),
        field("Shape", sel), row, drawing.element, facts, placeControls(it, paint, kind), picker];
    }

    // ---------- a herb's or a material's look on the ground, where the cat picks it up ----------
    function groundParts(it, like) {
      const drawing = shapeDrawing();
      const facts = el("p", { class: "muted", style: { fontSize: "0.9rem" } });
      let cat = null, model = null;
      const paint = () => { if (cat) drawing.draw({ cat, model: model ? placeMesh(model, it.place, true) : null, ground: true }); };
      const picker = modelPicker(it, "-ground", true);
      const picPicker = picturePicker(it, "texture", "-ground", (item, r) => {
        item.texture = r.path;
        toast(`Added the picture (${r.width} x ${r.height}). It's scaled to 2048 x 2048 in the game.`);
      });
      // Without a model, it lies there as the game's pickup of the item it starts from, or as Horsetail.
      const own = like && like.pickup ? `${like.name}, as the game has it` : "Horsetail (the game has no pickup of its own for it)";
      const sel = el("select", { "aria-label": "On the ground", onchange: () => {
        if (sel.value === "game") { delete it.model; delete it.texture; delete it.place; changed(true); }
        else { picker.click(); sel.value = it.model ? "own" : "game"; }
      } },
      el("option", { value: "game", text: own }),
      el("option", { value: "own", text: "A model of my own (OBJ or glTF)…" }));
      sel.value = it.model ? "own" : "game";
      const parts = [field("On the ground", sel)];
      if (it.model) {
        const preview = el("img", { class: "item-icon", alt: `${it.name || "The item"}'s picture` });
        const previewBox = el("div", { class: "icon-box" }, preview);
        previewBox.hidden = true;            // shown once there's a picture to show
        if (isPicture(it.texture)) (async () => {
          try { preview.src = await api.image(picturePath(it.texture)); previewBox.hidden = false; } catch (e) { /* none to show */ }
        })();
        parts.push(el("div", { class: "row" }, el("span", { class: "muted mono", text: it.model }),
          el("button", { class: "btn small", text: "Choose another…", "aria-label": "Choose another model", onclick: () => picker.click() })));
        parts.push(el("div", { class: "cat-head" }, previewBox,
          el("div", { class: "stack", style: { flex: "1", minWidth: "220px" } },
            el("div", { class: "row" }, el("span", { class: "lbl", text: "Picture" }),
              el("span", { class: "muted mono", text: isPicture(it.texture) ? it.texture : "none: plain grey" }),
              el("button", { class: "btn small", text: isPicture(it.texture) ? "Choose another…" : "Choose a picture…", "aria-label": "Choose a picture for the model", onclick: () => picPicker.click() }),
              isPicture(it.texture) ? el("button", { class: "btn ghost small", text: "No picture", onclick: () => { delete it.texture; changed(true); } }) : null),
            el("p", { class: "note", text: "Painted on the model through its UVs, as in Blender. PNG, JPEG or WebP; it's solid: see-through parts of the picture show as their colour." }))));
        parts.push(drawing.element, facts, placeControls(it, paint, "ground", GROUND_MOVES, GROUND_TURNS));
        (async () => {
          try {
            cat = (await api.get("/game/cat-shape")).cat;
            try {
              model = await api.get(`/mods/${encodeURIComponent(target.current)}/model-view?path=${encodeURIComponent(it.model)}&ground=1`);
              let low = Infinity;
              for (let k = 2; k < model.p.length; k += 3) low = Math.min(low, model.p[k]);
              facts.textContent = `${model.vertices} vertices, ${model.triangles} triangles, ${model.size_cm.join(" x ")} cm; ` +
                (Math.abs(low) > 2 ? `its bottom is ${Math.round(low)} cm ${low > 0 ? "above" : "below"} the ground as it's made (Up / down below moves it).`
                  : "it stands on the ground as it's made.");
            } catch (e) { facts.textContent = `Couldn't read ${it.model}: ${e.message}`; }
            paint();
          } catch (e) { facts.textContent = `Couldn't draw it: ${e.message}`; }
        })();
      }
      return [el("h4", { text: "On the ground", style: { margin: "0" } }),
        el("p", { class: "note", text: "How it lies in the forest for your cat to pick up: when a script or a story leaves it there (a quest's reward, say). A model of your own, made in Blender or any 3D program and saved as OBJ or glTF (.glb), in metres with Y up (the programs' usual settings), standing on the ground at its origin; the cat beside it shows its size." }),
        ...parts, picker, picPicker];
    }

    // Sliders (with number boxes) for where it sits: moved, turned, sized and stretched. The drawing above
    // follows them as they move; the game gets it at the next Apply. An accessory left with nothing of its own
    // (its place back to neutral, no look, model or opacity) gets a colour again (items-model.giveOwn).
    function placeControls(it, paint, kind, moves = MOVES, turns = TURNS) {
      const box = el("div", { class: "stack" });
      const get = () => it.place || {};
      // The size sliders' own values: one size for all of it, and a stretch each way. items.json keeps a
      // number when nothing's stretched, else each way's size (the size times its stretch).
      let size = 1, stretch = { forward: 1, up: 1, left: 1 };
      const readScale = () => {
        const s = get().scale;
        size = typeof s === "number" ? s : 1;
        stretch = Object.fromEntries(STRETCH.map(([a]) => [a, typeof s === "object" && s ? s[a] ?? 1 : 1]));
      };
      const own = () => { if (giveOwn(it, kind)) { toast(OWN_AGAIN); changed(true); return true; } return false; };
      const set = (key, value, neutral) => {
        const place = { ...get() };
        if (value === neutral) delete place[key]; else place[key] = value;
        if (Object.keys(place).length) it.place = place; else delete it.place;
        changed();
        if (!own()) paint();
      };
      const setScale = (axis, v) => {
        if (axis === "size") size = v; else stretch[axis] = v;
        const round = x => Math.round(x * 1000) / 1000;
        const stretched = STRETCH.some(([a]) => round(stretch[a]) !== 1);
        const each = a => Math.min(20, Math.max(0.01, round(size * stretch[a])));
        set("scale", stretched ? Object.fromEntries(STRETCH.map(([a]) => [a, each(a)])) : round(size), 1);
      };
      // min/max are the slider's; lo/hi what items.json takes, which the number box keeps to.
      function slider(label, hint, value, min, max, step, onInput, aria, lo = min, hi = max) {
        const range = el("input", { type: "range", min: String(min), max: String(max), step: String(step), value: String(value),
          "aria-label": aria || label, style: { width: "100%" } });
        const num = el("input", { type: "number", step: String(step), value: String(value), "aria-label": `${aria || label} (number)`, style: { width: "100%" } });
        range.addEventListener("input", () => { num.value = range.value; onInput(Number(range.value)); });
        num.addEventListener("change", () => {
          let v = Number(num.value);
          if (!Number.isFinite(v)) v = value;
          v = Math.min(hi, Math.max(lo, v));
          num.value = String(v); range.value = String(v); onInput(v);
        });
        return el("div", { style: { display: "grid", gridTemplateColumns: "8.5em minmax(100px, 1fr) 5.5em minmax(0, 16em)", gap: "4px 10px", alignItems: "center" } },
          el("span", { class: "lbl", text: label }), range, num, el("span", { class: "muted", style: { fontSize: "0.85rem" }, text: hint || "" }));
      }
      const draw = () => {
        clear(box);
        const place = get();
        readScale();
        box.append(el("h4", { text: moves === MOVES ? "Where it sits" : "Where it lies", style: { margin: "6px 0 0" } }));
        for (const [key, label, hint] of moves) box.append(slider(label, hint, place[key] ?? 0, -25, 25, 0.1, v => set(key, Math.round(v * 100) / 100, 0), null, -100, 100));
        for (const [key, label, hint] of turns) box.append(slider(label, hint, place[key] ?? 0, -180, 180, 1, v => set(key, Math.round(v * 10) / 10, 0), null, -360, 360));
        // Each way's size (size times stretch) must stay within 0.01 to 20.
        box.append(slider("Size", "times as big", size, 0.2, 4, 0.01, v => setScale("size", v), null, 0.05, 20));
        for (const [axis, label] of STRETCH) {
          box.append(slider(`Stretch: ${label.toLowerCase()}`, null, stretch[axis], 0.2, 4, 0.01, v => setScale(axis, v), `Stretch ${label}`, 0.05, 20));
        }
        box.append(el("div", { class: "row" }, el("button", { class: "btn ghost small", text: "Put it back where it was made",
          onclick: () => { delete it.place; changed(); if (!own()) { paint(); draw(); } } })));
      };
      draw();
      return box;
    }

    // ---------- the medicine cat's recipe: materials and how many ----------
    function recipeCard(it) {
      const recipe = el("div", { class: "stack" });
      // This mod's own materials can be asked for too, by their id: the build makes materials first.
      const mine = () => items.filter(x => x !== it && kindOf(x, byTag) === "material" && x.id);
      const labelOf = m => (byTag.get(fullTag(m, byTag)) || {}).name || (items.find(x => x.id === m) || {}).name || m;
      const drawRecipe = () => {
        clear(recipe);
        for (const [m, n] of Object.entries(it.recipe || {})) {
          const label = labelOf(m);
          const count = el("input", { type: "number", min: "1", max: "99", value: n, style: { width: "5em" }, "aria-label": `How many ${label}`,
            onchange: () => { it.recipe[m] = Math.max(1, Math.min(99, Math.round(Number(count.value) || 1))); changed(); } });
          recipe.append(el("div", { class: "row" }, count, el("span", { text: label }),
            el("button", { class: "btn ghost small", text: "Remove", "aria-label": `Remove ${label} from the recipe`, onclick: () => { delete it.recipe[m]; changed(); drawRecipe(); } })));
        }
        const own = mine();
        const add = el("select", { "aria-label": "Add a material to the recipe", onchange: () => {
          if (!add.value) return;
          it.recipe = { ...(it.recipe || {}), [add.value]: (it.recipe || {})[add.value] || 1 };
          changed(); drawRecipe();
        } }, el("option", { value: "", text: "Add a material…" }),
          el("optgroup", { label: "The game's materials" }, ...materials.map(m => el("option", { value: m.short, text: m.name }))),
          own.length ? el("optgroup", { label: "Your materials" }, ...own.map(m => el("option", { value: m.id, text: m.name || m.id }))) : null);
        recipe.append(el("div", { class: "row" }, add));
      };
      drawRecipe();
      return el("div", { class: "card" }, el("h3", { text: "The medicine cat's recipe" }),
        el("p", { class: "note", text: "What the medicine cat asks for to make one, at their bartering. Leave it empty and they don't make it." }), recipe);
    }
    return {};
  },
};
