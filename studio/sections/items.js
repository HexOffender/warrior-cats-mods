// Items: herbs and materials of the mod's own (items.json): a name, a description, an icon (the game's, in
// other colours, or a picture of your own), what using a herb does, and a recipe at the medicine cat's.
// They're real items in the game, everywhere, not only in Sandbox mode. See wcmods/sections/items.py.
import { listEditor, field, itemChoices, itemSelect } from "../lib/story.js";

const KIND = { consumable: "Herb", material: "Material" };
const EDITED = new Set(["id", "kind", "like", "name", "description", "icon", "effect", "rarity", "group", "recipe", "give", "type"]);

// "Moon Herb" -> "MoonHerb": an item's id is part of its tag, letters and digits.
function itemId(name, taken) {
  let base = (name || "").normalize("NFKD").replace(/[^A-Za-z0-9 ]+/g, "").split(/\s+/).filter(Boolean)
    .map(w => w[0].toUpperCase() + w.slice(1)).join("").slice(0, 40);
  if (!/^[A-Za-z]/.test(base)) base = "Item" + base;
  let id = base, n = 2;
  while (taken.includes(id)) id = `${base}${n++}`;
  return id;
}

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
      noun: "item", empty: "No items yet. Add one: a herb that heals, or a material for quests and recipes.",
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
        el("p", { class: "note", text: "Herbs and materials of your own. They're real items: they show in the inventory with their icon, herbs do what you choose when used, and the medicine cat can make them. Questlines can ask for them and give them as rewards. They work in story games too, not only in Sandbox mode." })),
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
      for (const k of ["Consumable", "Materials"]) if (byTag.has(`Gameplay.Inventory.${k}.${short}`)) return `Gameplay.Inventory.${k}.${short}`;
      return null;
    }
    const tagOf = it => `Gameplay.Inventory.${kindOf(it) === "material" ? "Materials" : "Consumable"}.${it.id}`;
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
      return { _help: "Written by Clan Mod Studio (Items). Herbs and materials of this mod's own. See docs/SDK.md, New items.", ...extra, items: list };
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

    function drawItem(box, it, i) {
      const redraw = () => { clear(box); drawItem(box, it, i); };
      // Accessories (new looks) are made by hand in items.json; the page leaves them as they are.
      if (kindOf(it) === "accessory" || it.texture) {
        box.append(el("div", { class: "card" }, el("h3", { text: it.name || it.id }),
          el("p", { class: "note", text: "A new look for an accessory. The Items page doesn't edit those yet: change it in items.json (docs/SDK.md, New items). It's kept as it is." })));
        return;
      }
      const kind = kindOf(it) || "consumable";
      const name = el("input", { type: "text", value: it.name || "", maxlength: "40", oninput: () => {
        it.name = name.value;
        if (it._new) it.id = itemId(it.name, items.filter(x => x !== it).map(x => x.id));
        tagNote.textContent = tagOf(it);
        changed();
      }, onchange: () => draw() });
      const desc = el("textarea", { rows: "2", style: { minHeight: "54px", fontFamily: "var(--body)", fontSize: "0.98rem" },
        placeholder: kind === "consumable" ? "Health Recovery (medium). Picked under a full moon." : "A smooth stone from the riverbed." });
      desc.value = it.description || "";
      desc.addEventListener("input", () => { it.description = desc.value; changed(); });
      const tagNote = el("span", { class: "muted mono", text: tagOf(it) });

      const kindSel = el("select", { "aria-label": "Kind", onchange: () => {
        it.kind = kindSel.value;
        it.like = (kindSel.value === "material" ? materials : herbs)[0]?.short;
        if (it.kind === "material") { delete it.effect; delete it.recipe; delete it.group; }
        changed(true);
      } }, el("option", { value: "consumable", text: "Herb (it can be used)" }), el("option", { value: "material", text: "Material (for quests and recipes)" }));
      kindSel.value = kind;
      const pool = kind === "material" ? materials : herbs;
      const like = el("select", { "aria-label": "Starts from", onchange: () => { it.like = like.value; changed(); redraw(); } },
        ...pool.map(g => el("option", { value: g.short, text: g.name })));
      like.value = (byTag.get(fullTag(it.like)) || {}).short || pool[0]?.short;

      // ---------- the icon ----------
      const icon = el("img", { class: "item-icon", alt: `${it.name || "The item"}'s icon` });
      const iconMode = typeof it.icon === "string" ? (it.icon.startsWith("pictures/") || it.icon.endsWith(".png") ? "own" : "item")
        : it.icon && typeof it.icon === "object" ? "tint" : "like";
      const showIcon = async () => {
        let path;
        if (iconMode === "own") path = `/mods/${encodeURIComponent(target.current)}/picture/${encodeURIComponent(it.icon.split("/").pop())}`;
        else {
          const from = iconMode === "item" ? fullTag(it.icon) || it.icon : iconMode === "tint" && it.icon.from ? fullTag(it.icon.from) : fullTag(it.like);
          path = `/game/icon?of=${encodeURIComponent(from || "")}${iconMode === "tint" && it.icon.tint ? `&tint=${encodeURIComponent(it.icon.tint)}` : ""}`;
        }
        try { icon.src = await api.image(path); icon.hidden = false; } catch (e) { icon.hidden = true; }
      };
      showIcon();
      const modeSel = el("select", { "aria-label": "Icon", onchange: () => {
        if (modeSel.value === "like") delete it.icon;
        else if (modeSel.value === "tint") it.icon = { tint: "#a8c4ff" };
        else if (modeSel.value === "item") it.icon = (pool[0] || {}).short;
        else { picker.click(); modeSel.value = iconMode; return; }
        changed(); redraw();
      } },
      el("option", { value: "like", text: "The icon of the item it starts from" }),
      el("option", { value: "tint", text: "That icon in another colour" }),
      el("option", { value: "item", text: "Another item's icon" }),
      el("option", { value: "own", text: "A picture of my own (PNG)…" }));
      modeSel.value = iconMode;
      const picker = el("input", { type: "file", accept: ".png,image/png", hidden: true, onchange: async () => {
        const f = picker.files[0];
        picker.value = "";
        if (!f) return;
        try {
          if (!target.mods.some(m => m.id === target.current) && !await target.save()) return;   // the mod has to exist first
          const r = await api.upload(`/mods/${encodeURIComponent(target.current)}/picture?name=${encodeURIComponent(it.id)}`, f, "application/octet-stream");
          api.forget(`/mods/${encodeURIComponent(target.current)}/picture/${encodeURIComponent(r.path.split("/").pop())}`);
          it.icon = r.path;
          toast(`Added ${f.name} (${r.width} x ${r.height}). Inventory icons are 512 x 512 with a see-through background.`);
          changed(); redraw();
        } catch (e) { toast(e.message, "bad"); }
      } });
      const iconExtra = el("div", { class: "row" });
      if (iconMode === "tint") {
        const tint = el("input", { type: "color", value: it.icon.tint || "#a8c4ff", "aria-label": "Colour", onchange: () => { it.icon = { ...it.icon, tint: tint.value }; changed(); showIcon(); } });
        iconExtra.append(el("span", { class: "lbl", text: "Colour" }), tint);
      } else if (iconMode === "item") {
        iconExtra.append(itemSelect(itemChoices({ items: game.items.filter(g => g.kind !== "accessory") }), fullTag(it.icon) || it.icon,
          v => { it.icon = (byTag.get(v) || {}).short || v; changed(); showIcon(); }, "Whose icon"));
      } else if (iconMode === "own") {
        iconExtra.append(el("span", { class: "muted mono", text: it.icon }), el("button", { class: "btn small", text: "Choose another…", onclick: () => picker.click() }));
      }

      const cards = [
        el("div", { class: "card" },
          el("div", { class: "cat-head" },
            el("div", { class: "icon-box" }, icon),
            el("div", { class: "stack", style: { flex: "1", minWidth: "220px" } },
              field("Name", name), field("Description", desc, kind === "consumable" ? "The game's herbs start with what they do: \"Health Recovery (medium).\"" : null), tagNote)),
          el("div", { style: { display: "grid", gap: "10px", alignItems: "start", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" } },
            field("Kind", kindSel), field("Starts from", like, "Its icon, badge and (for a herb) what it does, unless you change them below."))),
        el("div", { class: "card" }, el("h3", { text: "Icon" }), field("Icon", modeSel), iconExtra, picker),
      ];
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
        // The medicine cat's recipe: materials and how many.
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
        cards.push(el("div", { class: "card" }, el("h3", { text: "The medicine cat's recipe" }),
          el("p", { class: "note", text: "What the medicine cat asks for to make one, at their bartering. Leave it empty and they don't make it." }), recipe));
      }
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
    return {};
  },
};
