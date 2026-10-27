// Parts the Items, Characters and Questlines pages share: a list of things beside the one being edited, a
// box of lines to say, a place in the game (typed, or read from where your cat stands), an item picker, and
// a drawing of a cat in its colours. See wcmods/story.py for npcs.json and quests.json.
import { el, api, clear, toast } from "./wc.js";

export const SANDBOX = "sandbox";
export const SANDBOX_URL = "https://github.com/HexOffender/wcmods-sandbox/releases";

// "Mossfoot" -> "mossfoot", unique among `taken`.
export function slug(text, taken = [], fallback = "thing") {
  let base = (text || "").toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || fallback;
  if (!/^[a-z0-9]/.test(base)) base = fallback;
  let id = base, n = 2;
  while (taken.includes(id)) id = `${base}-${n++}`;
  return id;
}

// A list on the left (pick one to edit, add one), the editor on the right. render() draws both again.
export function listEditor({ noun, label, add, empty }) {
  const list = el("div", { class: "pick-list", role: "list", "aria-label": `${noun}s` });
  const editor = el("div", { class: "stack" });
  const addBtn = el("button", { class: "btn", text: `Add ${/^[aeiou]/.test(noun) ? "an" : "a"} ${noun}`, onclick: add });
  const element = el("div", { class: "split" }, el("div", { class: "stack" }, list, addBtn), editor);
  let things = [], chosen = 0, draw = null;
  function render(all, drawEditor) {
    things = all;
    draw = drawEditor || draw;
    chosen = Math.min(chosen, Math.max(0, things.length - 1));
    clear(list);
    things.forEach((t, i) => list.append(el("div", { role: "listitem" },
      el("button", { class: "pick", "aria-current": i === chosen ? "true" : false, "data-focus": `pick:${i}`,
        onclick: () => { chosen = i; render(things); } }, ...[].concat(label(t, i))))));
    clear(editor);
    if (!things.length) editor.append(el("div", { class: "empty", text: empty }));
    else draw(editor, things[chosen], chosen);
  }
  return { element, render, choose: i => { chosen = i; }, get chosen() { return chosen; } };
}

// A labelled field.
export function field(label, input, hint) {
  return el("label", { class: "field" }, el("span", { class: "lbl", text: label }), input,
    hint ? el("span", { class: "muted", style: { fontSize: "0.85rem" }, text: hint }) : null);
}

// Lines to say: a box with one line of talk per line of text.
export function linesBox(lines, onChange, placeholder) {
  const box = el("textarea", { rows: String(Math.max(3, lines.length + 1)), placeholder,
    style: { fontFamily: "var(--body)", fontSize: "0.98rem", minHeight: "84px" } });
  box.value = lines.join("\n");
  box.addEventListener("input", () => onChange(box.value.split("\n").map(s => s.trim()).filter(Boolean)));
  return box;
}

// A place in the game: x, y, z (cm), filled in by hand or from where your cat stands (the game bridge,
// so the game must be running with mods that run code allowed). onChange({at, yaw, level}).
export function wherePicker(spot, onChange) {
  const at = spot.at || ["", "", ""];
  const inputs = [0, 1, 2].map(i => el("input", { type: "number", step: "1", value: at[i] ?? "", "aria-label": "XYZ"[i],
    style: { width: "7.5em" }, oninput: () => send() }));
  const where = el("span", { class: "muted", text: spot.level ? `in ${spot.level}` : "" });
  function send(extra = {}) {
    const nums = inputs.map(i => i.value === "" ? null : Math.round(Number(i.value)));
    onChange({ at: nums.every(n => n !== null && Number.isFinite(n)) ? nums : null, ...extra });
  }
  const grab = el("button", { class: "btn small", text: "Use where my cat is standing", onclick: async () => {
    grab.disabled = true;
    try {
      const r = await api.post("/game/where");
      r.at.forEach((v, i) => { inputs[i].value = v; });
      where.textContent = r.level ? `in ${r.level}` : "";
      send({ yaw: r.yaw, level: r.level });
      toast(`Got your cat's spot: ${r.at.join(", ")}`);
    } catch (e) {
      toast(`${e.message}. Start the game (Play) and stand where you want it, then press this again.`, "bad");
    }
    grab.disabled = false;
  } });
  return el("div", { class: "stack" },
    el("div", { class: "row" }, el("span", { class: "lbl", text: "X" }), inputs[0], el("span", { class: "lbl", text: "Y" }), inputs[1],
      el("span", { class: "lbl", text: "Z" }), inputs[2], where),
    el("div", { class: "row" }, grab,
      el("span", { class: "muted", style: { fontSize: "0.85rem" }, text: "With the game running: walk your cat there, then press it." })));
}

// The items a quest can name: the game's herbs and materials, and the mod's own (items.json).
export function itemChoices(game, own = []) {
  const groups = [
    ["Your items", own.map(i => ({ tag: i.tag, name: i.name }))],
    ["Herbs", game.items.filter(i => i.kind === "consumable")],
    ["Materials", game.items.filter(i => i.kind === "material")],
    ["Accessories", game.items.filter(i => i.kind === "accessory")],
  ].filter(([, list]) => list.length);
  const names = new Map();
  for (const [, list] of groups) for (const i of list) names.set(i.tag, i.name);
  return { groups, name: tag => names.get(tag) || (tag || "").split(".").pop() };
}

export function itemSelect(choices, value, onChange, label = "Item") {
  const s = el("select", { "aria-label": label, onchange: () => onChange(s.value) },
    el("option", { value: "", text: "Choose an item…" }),
    ...choices.groups.map(([g, list]) => el("optgroup", { label: g }, ...list.map(i => el("option", { value: i.tag, text: i.name })))));
  if (value && ![...s.options].some(o => o.value === value)) s.append(el("option", { value, text: choices.name(value) }));
  s.value = value || "";
  return s;
}

// An item's own items from items.json, as the tags the game gives them.
export function ownItems(itemsJson) {
  const kinds = { consumable: "Consumable", material: "Materials" };
  return ((itemsJson && itemsJson.items) || []).filter(i => i && i.id && (kinds[i.kind] || i.like))
    .map(i => {
      const k = kinds[i.kind] || (/Materials/.test(i.like || "") ? "Materials" : "Consumable");
      return { tag: `Gameplay.Inventory.${k}.${i.id}`, name: i.name || i.id };
    });
}

// Whether the Sandbox mode mod is in the mods folder; a note to get it when it isn't.
export async function sandboxNote() {
  let mods = [];
  try { mods = await api.get("/mods"); } catch (e) { /* the target says */ }
  const s = mods.find(m => m.id === SANDBOX);
  if (s && s.enabled) return null;
  return el("div", { class: "banner" },
    el("strong", { text: s ? "Sandbox mode is off" : "You'll need the Sandbox mode mod" }),
    el("span", {}, s
      ? "Characters and questlines show up in Sandbox mode. Saving here turns it on with your mod."
      : "Characters and questlines show up in Sandbox mode, a mod of its own: download sandbox.zip from ",
      s ? null : el("a", { href: SANDBOX_URL, target: "_blank", rel: "noopener", text: "its releases" }),
      s ? null : " and drop it on the Mods page. It runs a script, so it needs mods that run code allowed (Settings and repair)."));
}

// A drawing of a cat's face in its colours (fur, pattern, markings, nose, eyes).
export function catFace(colours = {}, eye = "#b6c86a") {
  const c = { fur: "#9a8a78", pattern: "#5b4e40", markings: "#e9e1d4", nose: "#c47c7a", ...colours };
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 200 180");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "The cat's colours");
  svg.classList.add("cat-face");
  svg.innerHTML = `
    <path d="M38 78 L48 14 L92 52 Z" fill="${c.fur}" stroke="#0004" stroke-width="2"/>
    <path d="M162 78 L152 14 L108 52 Z" fill="${c.fur}" stroke="#0004" stroke-width="2"/>
    <path d="M52 62 L56 30 L80 52 Z" fill="${c.ears || "#e4a9a2"}" opacity=".85"/>
    <path d="M148 62 L144 30 L120 52 Z" fill="${c.ears || "#e4a9a2"}" opacity=".85"/>
    <ellipse cx="100" cy="104" rx="78" ry="66" fill="${c.fur}" stroke="#0004" stroke-width="2"/>
    <g stroke="${c.pattern}" stroke-width="7" stroke-linecap="round" fill="none">
      <path d="M100 42 L100 66"/><path d="M84 46 Q88 58 90 68"/><path d="M116 46 Q112 58 110 68"/>
      <path d="M24 100 Q42 98 56 104"/><path d="M26 118 Q44 114 58 120"/>
      <path d="M176 100 Q158 98 144 104"/><path d="M174 118 Q156 114 142 120"/>
    </g>
    <ellipse cx="100" cy="138" rx="40" ry="28" fill="${c.markings}"/>
    <path d="M100 74 C94 92 92 106 94 118 L106 118 C108 106 106 92 100 74 Z" fill="${c.markings}"/>
    <g><ellipse cx="70" cy="98" rx="15" ry="11" fill="#f6f1e4"/><circle cx="70" cy="98" r="10" fill="${eye}"/>
      <ellipse cx="70" cy="98" rx="3" ry="9" fill="#111"/></g>
    <g><ellipse cx="130" cy="98" rx="15" ry="11" fill="#f6f1e4"/><circle cx="130" cy="98" r="10" fill="${eye}"/>
      <ellipse cx="130" cy="98" rx="3" ry="9" fill="#111"/></g>
    <path d="M92 122 L108 122 Q110 124 106 128 L101 132 Q100 133 99 132 L94 128 Q90 124 92 122 Z" fill="${c.nose}"/>
    <g stroke="${c.whiskers || "#f4f0e8"}" stroke-width="1.4" opacity=".8" stroke-linecap="round">
      <path d="M78 130 L30 122 M78 134 L28 138"/><path d="M122 130 L170 122 M122 134 L172 138"/></g>`;
  return svg;
}
