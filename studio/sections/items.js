// Items: herbs, materials and accessories of the mod's own (items.json): a name, a description, an icon (the
// game's, in other colours, or a picture of your own), what using a herb does, a recipe at the medicine cat's,
// for an accessory its look (a picture) and its shape (a model of your own, OBJ or glTF), and for a herb or a
// material how it lies on the ground for the cat to pick up (a model of your own, with its picture).
// They're real items in the game, everywhere, not only in Sandbox mode. See wcmods/sections/items.py.
import { listEditor, field, itemChoices, itemSelect } from "../lib/story.js";
import { shapeDrawing, asPng, placeMesh } from "../lib/shape.js";

const KIND = { consumable: "Herb", material: "Material", accessory: "Accessory" };
const EDITED = new Set(["id", "kind", "like", "name", "description", "icon", "effect", "rarity", "group", "recipe", "give", "type",
  "texture", "model", "place", "opacity", "glass"]);
const SLOTS = { Neck: "Neck", Body: "Body", Legs: "Paw" };   // accessories that can take new looks; head ones can't
const MODEL_FILES = ".obj,.glb,.gltf";
const PICTURE_FILES = "image/png,image/jpeg,image/webp,image/gif,image/bmp";
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

// "Moon Herb" -> "MoonHerb": an item's id is part of its tag, letters and digits.
function itemId(name, taken) {
  let base = (name || "").normalize("NFKD").replace(/[^A-Za-z0-9 ]+/g, "").split(/\s+/).filter(Boolean)
    .map(w => w[0].toUpperCase() + w.slice(1)).join("").slice(0, 40);
  if (!/^[A-Za-z]/.test(base)) base = "Item" + base;
  let id = base, n = 2;
  while (taken.includes(id)) id = `${base}${n++}`;
  return id;
}

const isPicture = v => typeof v === "string" && (v.startsWith("pictures/") || v.toLowerCase().endsWith(".png"));

export default {
  title: "Items",
  async mount(root, wc) {
    const { el, api, toast, clear } = wc;
    let items = [], extra = {};
    let game;
    try { game = await api.get("/game/items"); }
    catch (e) { root.append(el("div", { class: "error-card" }, el("strong", { text: "Couldn't read the game's items" }), el("span", { text: e.message }))); return {}; }
    const byTag = new Map(game.items.map(i => [i.tag, i]));
    const herbs = game.items.filter(i => i.kind === "consumable");
    const materials = game.items.filter(i => i.kind === "material");
    // Accessories' looks that can take a new look after them: neck, body and paw ones (the game always shows a
    // head accessory's first look). One per accessory: its first look.
    const wearables = game.items.filter(i => i.kind === "accessory" && SLOTS[i.slot] && i.look_number === 1 && i.look);
    // What each effect is: the herbs that have it ("Gameplay.Effect.Consumable.Health.1" -> "like Small Healing Herb").
    const effectName = e => {
      const who = herbs.filter(h => h.effect === e).map(h => h.name);
      return who.length ? `${who.slice(0, 2).join(", ")}'s` : e.replace("Gameplay.Effect.Consumable.", "").replace(/\./g, " ");
    };

    const target = wc.modTarget({
      file: "items.json",
      onLoad: obj => { load(obj); draw(); },
      getValue: () => toJson(),
    });
    const out = wc.codePanel("items.json");
    const editor = listEditor({
      noun: "item", empty: "No items yet. Add one: a herb that heals, a material for quests and recipes, or something to wear.",
      label: it => [el("strong", { text: it.name || it.id }), el("span", { class: "muted", text: ` ${KIND[kindOf(it)] || "item"}` })],
      add: () => {
        const name = "New herb";
        items.push({ id: itemId(name, items.map(x => x.id)), kind: "consumable", like: "MediumHealingHerb", name, description: "", _new: true });
        editor.choose(items.length - 1);
        changed(true);
      },
    });
    root.append(
      el("div", { class: "section-head" },
        el("span", { class: "eyebrow", text: "New items" }),
        el("h1", { text: "Items" }),
        el("p", { class: "note", text: "Herbs, materials and accessories of your own. They're real items: they show in the inventory with their icon, herbs do what you choose when used, accessories are worn in a look and a shape of your own, and the medicine cat can make them. Questlines can ask for them and give them as rewards. They work in story games too, not only in Sandbox mode." })),
      target.element, editor.element, out.element);
    await target.refresh();

    function kindOf(it) {
      if (it.kind) return it.kind;
      const like = byTag.get(fullTag(it.like));
      return like ? like.kind : null;
    }
    function fullTag(short) {
      if (!short) return null;
      if (short.startsWith("Gameplay.Inventory.")) return short;
      if (/^(Head|Neck|Body|Legs)\./.test(short)) return `Gameplay.Inventory.Cosmetic.${short}`;
      if (short.startsWith("Cosmetic.")) return `Gameplay.Inventory.${short}`;
      for (const k of ["Consumable", "Materials"]) if (byTag.has(`Gameplay.Inventory.${k}.${short}`)) return `Gameplay.Inventory.${k}.${short}`;
      return null;
    }
    // Functions, not consts: the first draw happens inside target.refresh(), above.
    function likeOf(it) { return byTag.get(fullTag(it.like)) || null; }
    function tagOf(it) {
      if (kindOf(it) === "accessory") {
        const like = likeOf(it);
        return like ? `Gameplay.Inventory.Cosmetic.${like.slot}.${like.accessory}.(its next look)` : "an accessory: choose which below";
      }
      return `Gameplay.Inventory.${kindOf(it) === "material" ? "Materials" : "Consumable"}.${it.id}`;
    }
    function load(obj) {
      extra = {};
      items = [];
      for (const [k, v] of Object.entries(obj || {})) if (k !== "items" && !k.startsWith("_")) extra[k] = v;
      for (const it of (obj && Array.isArray(obj.items) ? obj.items : [])) if (it && typeof it === "object") items.push({ ...it });
    }
    function toJson() {
      const list = items.map(it => {
        const o = {};
        for (const [k, v] of Object.entries(it)) {
          if (k === "_new" || v === undefined || v === null || v === "") continue;
          if (k === "recipe" && !Object.keys(v).length) continue;
          o[k] = v;
        }
        return o;
      });
      return { _help: "Written by Clan Mod Studio (Items). Herbs, materials and accessories of this mod's own. See docs/SDK.md, New items.", ...extra, items: list };
    }
    function changed(redraw = false) {
      target.markDirty();
      out.set(toJson());
      if (redraw) draw();
    }
    function draw() {
      out.set(toJson());
      editor.render(items, drawItem);
    }
    // The mod has to exist on disk before a file can go in its folder.
    async function modReady() {
      return target.mods.some(m => m.id === target.current) || await target.save();
    }
    function modPath(what, file) { return `/mods/${encodeURIComponent(target.current)}/${what}/${encodeURIComponent(file.split("/").pop())}`; }

    function drawItem(box, it, i) {
      const redraw = () => { clear(box); drawItem(box, it, i); };
      const kind = kindOf(it) || "consumable";
      const accessory = kind === "accessory";
      const like = likeOf(it);
      if (accessory && like && !SLOTS[like.slot]) {
        box.append(el("div", { class: "card" }, el("h3", { text: it.name || it.id }),
          el("p", { class: "note", text: "A new look for a head accessory. The game always shows a head accessory's first look, so it wouldn't show: choose a neck, body or paw accessory instead (Kind, below), or change it in items.json." })));
      }
      const name = el("input", { type: "text", value: it.name || "", maxlength: "40", oninput: () => {
        it.name = name.value;
        if (it._new) it.id = itemId(it.name, items.filter(x => x !== it).map(x => x.id));
        tagNote.textContent = tagOf(it);
        changed();
      }, onchange: () => draw() });
      const desc = el("textarea", { rows: "2", style: { minHeight: "54px", fontFamily: "var(--body)", fontSize: "0.98rem" },
        placeholder: kind === "consumable" ? "Health Recovery (medium). Picked under a full moon." : accessory ? "A collar the colour of moonlight on water." : "A smooth stone from the riverbed." });
      desc.value = it.description || "";
      desc.addEventListener("input", () => { it.description = desc.value; changed(); });
      const tagNote = el("span", { class: "muted mono", text: tagOf(it) });

      const kindSel = el("select", { "aria-label": "Kind", onchange: () => {
        const wasWorn = kindOf(it) === "accessory";
        it.kind = kindSel.value;
        it.like = (kindSel.value === "material" ? materials : kindSel.value === "accessory" ? wearables : herbs)[0]?.short;
        if (it.kind !== "consumable") { delete it.effect; delete it.group; delete it.type; }
        if (it.kind === "material") delete it.recipe;
        // A model and picture are worn on an accessory and lie on the ground for a herb or a material.
        if (wasWorn !== (it.kind === "accessory")) for (const k of ["texture", "model", "place", "opacity", "glass"]) delete it[k];
        if (it.kind === "accessory") { delete it.icon; it.texture = it.texture || { tint: "#a8c4ff" }; }
        changed(true);
      } }, el("option", { value: "consumable", text: "Herb (it can be used)" }), el("option", { value: "material", text: "Material (for quests and recipes)" }),
        el("option", { value: "accessory", text: "Accessory (something to wear)" }));
      kindSel.value = kind;
      const pool = kind === "material" ? materials : accessory ? wearables : herbs;
      const likeSel = el("select", { "aria-label": "Starts from", onchange: () => { it.like = likeSel.value; changed(); redraw(); } });
      if (accessory) {
        for (const [slot, label] of Object.entries(SLOTS)) {
          const list = wearables.filter(w => w.slot === slot);
          if (list.length) likeSel.append(el("optgroup", { label }, ...list.map(w => el("option", { value: w.short, text: w.name }))));
        }
      } else likeSel.append(...pool.map(g => el("option", { value: g.short, text: g.name })));
      likeSel.value = like ? like.short : pool[0]?.short;
      if (like && likeSel.value !== like.short) likeSel.append(el("option", { value: like.short, text: like.name, selected: true }));

      // ---------- the icon ----------
      const icon = el("img", { class: "item-icon", alt: `${it.name || "The item"}'s icon` });
      const iconMode = typeof it.icon === "string" ? (isPicture(it.icon) ? "own" : "item")
        : it.icon && typeof it.icon === "object" ? "tint" : "like";
      const showIcon = async () => {
        let path;
        if (iconMode === "own") path = modPath("picture", it.icon);
        else {
          const from = iconMode === "item" ? fullTag(it.icon) || it.icon : iconMode === "tint" && it.icon.from ? fullTag(it.icon.from) : fullTag(it.like);
          path = `/game/icon?of=${encodeURIComponent(from || "")}${iconMode === "tint" && it.icon.tint ? `&tint=${encodeURIComponent(it.icon.tint)}` : ""}`;
        }
        try { icon.src = await api.image(path); icon.hidden = false; } catch (e) { icon.hidden = true; }
      };
      showIcon();
      const iconPicker = picturePicker(`${it.id}-icon`, r => {
        it.icon = r.path;
        toast(`Added the icon (${r.width} x ${r.height}). ${accessory ? "Accessories' icons are 256 x 256" : "Inventory icons are 512 x 512"} with a see-through background.`);
        changed(); redraw();
      });
      const modeSel = el("select", { "aria-label": "Icon", onchange: () => {
        if (modeSel.value === "like") delete it.icon;
        else if (modeSel.value === "tint") it.icon = { tint: (it.texture && it.texture.tint) || "#a8c4ff" };
        else if (modeSel.value === "item") it.icon = (pool[0] || {}).short;
        else { iconPicker.click(); modeSel.value = iconMode; return; }
        changed(); redraw();
      } },
      el("option", { value: "like", text: "The icon of the item it starts from" }),
      el("option", { value: "tint", text: "That icon in another colour" }),
      el("option", { value: "item", text: "Another item's icon" }),
      el("option", { value: "own", text: "A picture of my own…" }));
      modeSel.value = iconMode;
      const iconExtra = el("div", { class: "row" });
      if (iconMode === "tint") {
        const tint = el("input", { type: "color", value: it.icon.tint || "#a8c4ff", "aria-label": "Colour", onchange: () => { it.icon = { ...it.icon, tint: tint.value }; changed(); showIcon(); } });
        iconExtra.append(el("span", { class: "lbl", text: "Colour" }), tint);
      } else if (iconMode === "item") {
        iconExtra.append(itemSelect(itemChoices({ items: game.items.filter(g => g.kind !== "accessory") }), fullTag(it.icon) || it.icon,
          v => { it.icon = (byTag.get(v) || {}).short || v; changed(); showIcon(); }, "Whose icon"));
      } else if (iconMode === "own") {
        iconExtra.append(el("span", { class: "muted mono", text: it.icon }), el("button", { class: "btn small", text: "Choose another…", onclick: () => iconPicker.click() }));
      }
      iconExtra.append(paintOver(fullTag(iconMode === "item" ? it.icon : iconMode === "tint" && it.icon.from ? it.icon.from : it.like), "icon"));

      const cards = [
        el("div", { class: "card" },
          el("div", { class: "cat-head" },
            el("div", { class: "icon-box" }, icon),
            el("div", { class: "stack", style: { flex: "1", minWidth: "220px" } },
              field("Name", name), field("Description", desc, kind === "consumable" ? "The game's herbs start with what they do: \"Health Recovery (medium).\"" : null), tagNote)),
          el("div", { style: { display: "grid", gap: "10px", alignItems: "start", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" } },
            field("Kind", kindSel), field(accessory ? "A new look of" : "Starts from", likeSel, accessory
              ? "The accessory it's worn as: its place on the cat, its look and shape unless you change them below, and its icon. Head accessories can't take new looks."
              : "Its icon, badge and (for a herb) what it does, unless you change them below."))),
      ];
      if (accessory && like) cards.push(lookCard(it, like, redraw), shapeCard(it, like, redraw));
      if (!accessory) cards.push(groundCard(it, like, redraw));
      cards.push(el("div", { class: "card" }, el("h3", { text: "Icon" }), field("Icon", modeSel), iconExtra, iconPicker));
      if (kind === "consumable") {
        const effect = el("select", { "aria-label": "What using it does", onchange: () => {
          // A herb's type goes with its effect (a stamina herb is a Stamina one): the type of the game's herb that has it.
          it.effect = effect.value || undefined;
          it.type = effect.value ? (herbs.find(h => h.effect === effect.value) || {}).type || undefined : undefined;
          changed();
        } },
          el("option", { value: "", text: "The same as the herb it starts from" }),
          ...game.effects.map(e => el("option", { value: e, text: effectName(e) })));
        effect.value = it.effect || "";
        const group = el("select", { "aria-label": "Badge", onchange: () => { it.group = group.value || undefined; changed(); } },
          el("option", { value: "", text: "The same as the herb it starts from" }), ...game.groups.map(g => el("option", { value: g, text: g })));
        group.value = it.group || "";
        cards.push(el("div", { class: "card" }, el("h3", { text: "Using it" }),
          el("div", { style: { display: "grid", gap: "10px", alignItems: "start", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" } },
            field("What it does", effect, "Named by the game's herbs that do the same."), field("Badge on its icon", group))));
      }
      if (kind !== "material") cards.push(recipeCard(it));
      const give = el("input", { type: "number", min: "0", max: "999", value: it.give || 0, style: { width: "6em" }, "aria-label": "Start with",
        onchange: () => { const n = Math.max(0, Math.min(999, Math.round(Number(give.value) || 0))); if (n) it.give = n; else delete it.give; changed(); } });
      cards.push(el("div", { class: "card" }, el("h3", { text: "Starting with some" }),
        el("div", { class: "row" }, give, el("span", { class: "muted", text: "put in the cat you play now, once, when you Apply (0 for none)" }))));
      const rest = Object.keys(it).filter(k => !EDITED.has(k) && !k.startsWith("_"));
      if (rest.length) cards.push(el("p", { class: "note", text: `Also set in items.json, kept as it is: ${rest.join(", ")}.` }));
      cards.push(el("div", { class: "row" },
        wc.confirmButton(`Remove ${it.name || "this item"}`, "Press again to remove", () => { items.splice(i, 1); changed(true); }, "btn danger")));
      box.append(...cards);
    }

    // A hidden file input for a picture: any the browser opens, sent as a PNG to the mod's pictures/ folder.
    function picturePicker(stem, done) {
      const picker = el("input", { type: "file", accept: PICTURE_FILES, hidden: true, onchange: async () => {
        const f = picker.files[0];
        picker.value = "";
        if (!f) return;
        try {
          if (!await modReady()) return;
          const png = await asPng(f);
          const r = await api.upload(`/mods/${encodeURIComponent(target.current)}/picture?name=${encodeURIComponent(stem)}`, png, "application/octet-stream");
          api.forget(modPath("picture", r.path));
          done(r);
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

    // ---------- an accessory's look: its picture ----------
    function lookCard(it, like, redraw) {
      const tex = it.texture;
      const mode = isPicture(tex) ? "own" : tex && typeof tex === "object" ? "tint" : "like";
      const preview = el("img", { class: "item-icon", alt: `${it.name || "The accessory"}'s look` });
      (async () => {
        const path = mode === "own" ? modPath("picture", tex)
          : `/game/icon?of=${encodeURIComponent(like.look)}${mode === "tint" && tex.tint ? `&tint=${encodeURIComponent(tex.tint)}` : ""}`;
        try { preview.src = await api.image(path); } catch (e) { preview.hidden = true; }
      })();
      const picker = picturePicker(`${it.id}-look`, r => {
        it.texture = r.path;
        toast(`Added the look (${r.width} x ${r.height}). The game's are 2048 x 2048; others are scaled to that.`);
        changed(); redraw();
      });
      const sel = el("select", { "aria-label": "Look", onchange: () => {
        if (sel.value === "tint") it.texture = { tint: "#a8c4ff" };
        else if (sel.value === "like") delete it.texture;
        else { picker.click(); sel.value = mode; return; }
        changed(); redraw();
      } },
      el("option", { value: "tint", text: `${like.name}'s look in another colour` }),
      el("option", { value: "own", text: "A picture of my own…" }),
      it.model || it.place || it.opacity !== undefined || mode === "like" ? el("option", { value: "like", text: `${like.name}'s look as it is` }) : null);
      sel.value = mode;
      const extra = el("div", { class: "row" });
      if (mode === "tint") {
        const tint = el("input", { type: "color", value: tex.tint || "#a8c4ff", "aria-label": "Colour",
          onchange: () => { it.texture = { ...tex, tint: tint.value }; changed(); redraw(); } });
        extra.append(el("span", { class: "lbl", text: "Colour" }), tint);
      } else if (mode === "own") {
        extra.append(el("span", { class: "muted mono", text: tex }), el("button", { class: "btn small", text: "Choose another…", onclick: () => picker.click() }));
      }
      extra.append(paintOver(fullTag(it.like), "look"));
      // Opacity: below 100% it's worn as glass, as the game has no see-through material for cats with a picture.
      const shown = Math.round((it.opacity ?? 1) * 100);
      const glassNote = el("span", { class: "muted", style: { fontSize: "0.85rem" } });
      const glass = el("input", { type: "color", value: it.glass || (tex && tex.tint) || "#ffffff", "aria-label": "Glass colour",
        onchange: () => { it.glass = glass.value; changed(); redraw(); } });
      const glassRow = el("div", { class: "row" }, el("span", { class: "lbl", text: "Glass colour" }), glass, glassNote);
      const opacity = el("input", { type: "range", min: "0", max: "100", step: "5", value: String(shown), "aria-label": "Opacity",
        style: { flex: "1", minWidth: "140px" } });
      const pct = el("span", { class: "mono", text: `${shown}%` });
      const showGlass = () => {
        glassRow.hidden = (it.opacity ?? 1) >= 1;
        glassNote.textContent = "The cat shows through it: it's worn as glass of this colour, without its picture.";
      };
      opacity.addEventListener("input", () => {
        const v = Number(opacity.value) / 100;
        pct.textContent = `${opacity.value}%`;
        if (v >= 1) { delete it.opacity; delete it.glass; } else { it.opacity = v; it.glass = it.glass || glass.value; }
        showGlass();
        changed();
      });
      opacity.addEventListener("change", () => redraw());
      showGlass();
      const see = el("div", { class: "stack" }, el("div", { class: "row" }, el("span", { class: "lbl", text: "Opacity" }), opacity, pct), glassRow,
        el("p", { class: "note", text: "100% shows its look. Below that the cat shows through it, as glass in one colour: the game has no see-through material for cats that shows a picture." }));
      return el("div", { class: "card" }, el("h3", { text: "Look" }),
        el("p", { class: "note", text: "The picture on it, wrapped around its shape. A picture of your own is painted over the game's (save it below): its colours land where the game's do on the shape, or on a model of your own through its UVs. PNG, JPEG or WebP; a see-through background stays see-through only as PNG." }),
        el("div", { class: "cat-head" }, el("div", { class: "icon-box" }, preview),
          el("div", { class: "stack", style: { flex: "1", minWidth: "220px" } }, field("Look", sel), extra)), see, picker);
    }

    // ---------- an accessory's shape: its own, or a model of the mod's; and where it sits ----------
    function shapeCard(it, like, redraw) {
      const drawing = shapeDrawing();
      const facts = el("p", { class: "muted", style: { fontSize: "0.9rem" } });
      let view = null, model = null;
      const paint = () => {
        if (!view) return;
        const base = model || (it.place ? view.accessory : null);
        drawing.draw({ cat: view.cat, accessory: view.accessory, model: base ? placeMesh(base, it.place) : null,
          opacity: it.opacity ?? 1, glass: it.glass });
      };
      const picker = el("input", { type: "file", accept: MODEL_FILES, hidden: true, onchange: async () => {
        const f = picker.files[0];
        picker.value = "";
        if (!f) return;
        try {
          if (!await modReady()) return;
          toast(`Reading ${f.name}…`);
          const r = await api.upload(`/mods/${encodeURIComponent(target.current)}/model?name=${encodeURIComponent(it.id)}&file=${encodeURIComponent(f.name)}`,
            f, "application/octet-stream");
          it.model = r.path;
          toast(`Added ${f.name}: ${r.vertices} vertices, ${r.triangles} triangles, ${r.size_cm.join(" x ")} cm.` +
            (r.farthest_cm > 25 ? " It's far from the cat: models are in metres, around the cat of the start kit (or move it into place below)." : ""),
            r.farthest_cm > 25 ? "bad" : "info");
          changed(); redraw();
        } catch (e) { toast(e.message, "bad"); }
      } });
      const sel = el("select", { "aria-label": "Shape", onchange: () => {
        if (sel.value === "like") {
          delete it.model;
          if (!it.texture && it.opacity === undefined) it.texture = { tint: "#a8c4ff" };   // a new look needs something of its own
          changed(); redraw();
        } else { picker.click(); sel.value = it.model ? "own" : "like"; }
      } },
      el("option", { value: "like", text: `${like.name}'s own shape` }),
      el("option", { value: "own", text: "A model of my own (OBJ or glTF)…" }));
      sel.value = it.model ? "own" : "like";
      const kit = el("button", { class: "btn ghost small", text: "Save a start kit to model on", onclick: async () => {
        kit.disabled = true;
        toast("Making the start kit…");
        try { toast(`Saved ${await api.download(`/game/model-kit?of=${encodeURIComponent(like.short)}`)}: open the .obj files in Blender; README.txt says the rest.`); }
        catch (e) { toast(e.message, "bad"); }
        kit.disabled = false;
      } });
      const row = el("div", { class: "row" });
      if (it.model) row.append(el("span", { class: "muted mono", text: it.model }), el("button", { class: "btn small", text: "Choose another…", onclick: () => picker.click() }));
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
      return el("div", { class: "card" }, el("h3", { text: "Shape and place" }),
        el("p", { class: "note", text: "A model of your own, made in Blender or any 3D program and saved as OBJ or glTF (.glb). Make it around the cat of the start kit, in metres with Y up (the programs' usual settings), or anywhere and move it into place here: wherever it sits, it follows the nearest part of the cat as it moves, and grows and slims with the cat's build. Its look is the picture above, through the model's UVs. The game needs the script loader (UE4SS) for this." }),
        field("Shape", sel), row, drawing.element, facts, placeControls(it, paint), picker);
    }

    // ---------- a herb's or a material's look on the ground, where the cat picks it up ----------
    function groundCard(it, like, redraw) {
      const drawing = shapeDrawing();
      const facts = el("p", { class: "muted", style: { fontSize: "0.9rem" } });
      let cat = null, model = null;
      const paint = () => { if (cat) drawing.draw({ cat, model: model ? placeMesh(model, it.place, true) : null, ground: true }); };
      const modelPicker = el("input", { type: "file", accept: MODEL_FILES, hidden: true, onchange: async () => {
        const f = modelPicker.files[0];
        modelPicker.value = "";
        if (!f) return;
        try {
          if (!await modReady()) return;
          toast(`Reading ${f.name}…`);
          const r = await api.upload(`/mods/${encodeURIComponent(target.current)}/model?name=${encodeURIComponent(`${it.id}-ground`)}&file=${encodeURIComponent(f.name)}&ground=1`,
            f, "application/octet-stream");
          it.model = r.path;
          toast(`Added ${f.name}: ${r.vertices} vertices, ${r.triangles} triangles, ${r.size_cm.join(" x ")} cm.`);
          changed(); redraw();
        } catch (e) { toast(e.message, "bad"); }
      } });
      const picPicker = picturePicker(`${it.id}-ground`, r => {
        it.texture = r.path;
        toast(`Added the picture (${r.width} x ${r.height}). It's scaled to 2048 x 2048 in the game.`);
        changed(); redraw();
      });
      // Without a model, it lies there as the game's pickup of the item it starts from, or as Horsetail.
      const own = like && like.pickup ? `${like.name}, as the game has it` : "Horsetail (the game has no pickup of its own for it)";
      const sel = el("select", { "aria-label": "On the ground", onchange: () => {
        if (sel.value === "game") { delete it.model; delete it.texture; delete it.place; changed(); redraw(); }
        else { modelPicker.click(); sel.value = it.model ? "own" : "game"; }
      } },
      el("option", { value: "game", text: own }),
      el("option", { value: "own", text: "A model of my own (OBJ or glTF)…" }));
      sel.value = it.model ? "own" : "game";
      const cards = [field("On the ground", sel)];
      if (it.model) {
        const preview = el("img", { class: "item-icon", alt: `${it.name || "The item"}'s picture` });
        const previewBox = el("div", { class: "icon-box" }, preview);
        previewBox.hidden = true;            // shown once there's a picture to show (one in the mod's pictures/)
        if (isPicture(it.texture)) (async () => {
          try { preview.src = await api.image(modPath("picture", it.texture)); previewBox.hidden = false; } catch (e) { /* none to show */ }
        })();
        cards.push(el("div", { class: "row" }, el("span", { class: "muted mono", text: it.model }),
          el("button", { class: "btn small", text: "Choose another…", onclick: () => modelPicker.click() })));
        cards.push(el("div", { class: "cat-head" }, previewBox,
          el("div", { class: "stack", style: { flex: "1", minWidth: "220px" } },
            el("div", { class: "row" }, el("span", { class: "lbl", text: "Picture" }),
              el("span", { class: "muted mono", text: isPicture(it.texture) ? it.texture : "none: plain grey" }),
              el("button", { class: "btn small", text: isPicture(it.texture) ? "Choose another…" : "Choose a picture…", onclick: () => picPicker.click() }),
              isPicture(it.texture) ? el("button", { class: "btn ghost small", text: "No picture", onclick: () => { delete it.texture; changed(); redraw(); } }) : null),
            el("p", { class: "note", text: "Painted on the model through its UVs, as in Blender. PNG, JPEG or WebP; it's solid: see-through parts of the picture show as their colour." }))));
        cards.push(drawing.element, facts, placeControls(it, paint, GROUND_MOVES, GROUND_TURNS));
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
      return el("div", { class: "card" }, el("h3", { text: "On the ground" }),
        el("p", { class: "note", text: "How it lies in the forest for your cat to pick up: when a script or a story leaves it there (a quest's reward, say). A model of your own, made in Blender or any 3D program and saved as OBJ or glTF (.glb), in metres with Y up (the programs' usual settings), standing on the ground at its origin; the cat beside it shows its size. The game needs the script loader (UE4SS) for this." }),
        ...cards, modelPicker, picPicker);
    }

    // Sliders (with number boxes) for where it sits: moved, turned, sized and stretched. The drawing above
    // follows them as they move; the game gets it at the next Apply.
    function placeControls(it, paint, moves = MOVES, turns = TURNS) {
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
      const set = (key, value, neutral) => {
        const place = { ...get() };
        if (value === neutral) delete place[key]; else place[key] = value;
        if (Object.keys(place).length) it.place = place; else delete it.place;
        changed();
        paint();
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
          onclick: () => { delete it.place; changed(); paint(); draw(); } })));
      };
      draw();
      return box;
    }

    // ---------- the medicine cat's recipe: materials and how many ----------
    function recipeCard(it) {
      const recipe = el("div", { class: "stack" });
      const drawRecipe = () => {
        clear(recipe);
        for (const [m, n] of Object.entries(it.recipe || {})) {
          const label = (byTag.get(fullTag(m)) || {}).name || m;
          const count = el("input", { type: "number", min: "1", max: "99", value: n, style: { width: "5em" }, "aria-label": `How many ${label}`,
            onchange: () => { it.recipe[m] = Math.max(1, Math.min(99, Math.round(Number(count.value) || 1))); changed(); } });
          recipe.append(el("div", { class: "row" }, count, el("span", { text: label }),
            el("button", { class: "btn ghost small", text: "Remove", "aria-label": `Remove ${label} from the recipe`, onclick: () => { delete it.recipe[m]; changed(); drawRecipe(); } })));
        }
        const add = el("select", { "aria-label": "Add a material to the recipe", onchange: () => {
          if (!add.value) return;
          it.recipe = { ...(it.recipe || {}), [add.value]: (it.recipe || {})[add.value] || 1 };
          changed(); drawRecipe();
        } }, el("option", { value: "", text: "Add a material…" }), ...materials.map(m => el("option", { value: m.short, text: m.name })));
        recipe.append(el("div", { class: "row" }, add));
      };
      drawRecipe();
      return el("div", { class: "card" }, el("h3", { text: "The medicine cat's recipe" }),
        el("p", { class: "note", text: "What the medicine cat asks for to make one, at their bartering. Leave it empty and they don't make it." }), recipe);
    }
    return {};
  },
};
