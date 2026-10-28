// Parts the Items, Characters and Questlines pages share: a list of things beside the one being edited, a
// box of lines to say, a place in the game (typed, or read from where your cat stands), an item picker, a
// drawing of a cat in its colours, and the strip that says what Sandbox mode can show. See wcmods/story.py
// for npcs.json and quests.json.
import { el, api, clear, toast, bus, openHelp, announce } from "./wc.js";

export const SANDBOX = "sandbox";

// "Mossfoot" -> "mossfoot", unique among `taken`.
export function slug(text, taken = [], fallback = "thing") {
  // NFKD splits an accented letter into the letter and its accent, which then goes ("é" -> "e").
  let base = (text || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "").slice(0, 40) || fallback;
  if (!/^[a-z0-9]/.test(base)) base = fallback;
  let id = base, n = 2;
  while (taken.includes(id)) id = `${base}-${n++}`;
  return id;
}

// A list on the left (pick one to edit, add one), the editor on the right. render() draws both again;
// relabel(i) redraws one list button in place (a name being typed), so nothing loses focus; ready(false)
// holds the Add button back while the page is still reading its file.
export function listEditor({ noun, label, add, empty }) {
  const list = el("div", { class: "pick-list", role: "list", "aria-label": `${noun}s` });
  const editor = el("div", { class: "stack" });
  const addBtn = el("button", { class: "btn", text: `Add ${/^[aeiou]/.test(noun) ? "an" : "a"} ${noun}`, onclick: () => add() });
  const element = el("div", { class: "split" }, el("div", { class: "stack" }, list, addBtn), editor);
  let things = [], chosen = 0, draw = null;
  const buttons = [];
  function render(all, drawEditor) {
    things = all;
    draw = drawEditor || draw;
    chosen = Math.min(chosen, Math.max(0, things.length - 1));
    clear(list);
    buttons.length = 0;
    things.forEach((t, i) => {
      const b = el("button", { class: "pick", "aria-current": i === chosen ? "true" : false, "data-focus": `pick:${i}`,
        onclick: () => { chosen = i; render(things); } }, ...[].concat(label(t, i)));
      buttons.push(b);
      list.append(el("div", { role: "listitem" }, b));
    });
    clear(editor);
    if (!things.length) editor.append(el("div", { class: "empty", text: empty }));
    else draw(editor, things[chosen], chosen);
  }
  function relabel(i) {
    const b = buttons[i];
    if (b && things[i]) b.replaceChildren(...[].concat(label(things[i], i)).filter(x => x != null && x !== false));
  }
  return { element, render, relabel, choose: i => { chosen = i; }, get chosen() { return chosen; },
           ready(on) { addBtn.disabled = !on; } };
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

// A level of the game in words: the forest's, or its own name for one nobody has named yet.
const LEVELS = { L_WorldMap_01_P: "the forest" };
export const levelWords = level => LEVELS[level] || level || "";

// The numbers of a place, with what each one is: across and along the map, and the height.
const AXES = [["X", "across the map"], ["Y", "along the map"], ["Z", "height"]];

// A place in the game: three numbers (cm), read from where your cat stands (the game bridge, so the game
// must be running with your mods applied) or typed. onChange({at, yaw, level}): at is null until all three
// are filled in.
export function wherePicker(spot, onChange) {
  const at = spot.at || ["", "", ""];
  const inputs = AXES.map(([axis, words], i) => el("input", { type: "number", step: "1", value: at[i] ?? "",
    "aria-label": `${axis}, ${words}`, style: { width: "7.5em" }, oninput: () => send() }));
  const where = el("span", { class: "muted", text: spot.level ? `in ${levelWords(spot.level)}` : "" });
  function send(extra = {}) {
    const nums = inputs.map(i => i.value === "" ? null : Math.round(Number(i.value)));
    onChange({ at: nums.every(n => n !== null && Number.isFinite(n)) ? nums : null, ...extra });
  }
  const grab = el("button", { class: "btn small", type: "button", text: "Use where my cat is standing", onclick: async () => {
    grab.disabled = true;
    try {
      const r = await api.post("/game/where");
      r.at.forEach((v, i) => { inputs[i].value = v; });
      where.textContent = r.level ? `in ${levelWords(r.level)}` : "";
      send({ yaw: r.yaw, level: r.level });
      toast(`Got your cat's spot${r.level ? ` in ${levelWords(r.level)}` : ""}.`);
    } catch (e) {
      toast(e.message, "bad");   // the studio says what to press, as a whole sentence
    }
    grab.disabled = false;
  } });
  return el("div", { class: "stack" },
    el("div", { class: "row" }, grab,
      el("span", { class: "muted", style: { fontSize: "0.85rem" }, text: "With the game running: walk your cat there, then press it." })),
    el("div", { class: "row" }, ...AXES.flatMap(([axis, words], i) => [
      el("span", { class: "lbl", title: words, text: `${axis} (${words})` }), inputs[i]]), where));
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

// ---------- what Sandbox mode can show ----------
// What each of Sandbox mode's newer fields is called on the pages, and what happens without it.
const FIELDS = { look: ["fixed looks", "the game makes their look up each time"], slots: ["fixed looks", "the game makes their look up each time"] };

// The words of the strip for the studio's answer about Sandbox mode (GET /story/sandbox: its state, version
// and the fields it's too old for, worked out there) and the fields the page's cats use (["look", "slots"]):
// {kind, title, text, link?, button?, settings?}. kind is "good" when nothing waits.
export function stripWords(s, uses = []) {
  const zip = `sandbox-${s.newest || "0.5"}.zip`;
  const codeStep = s.code_allowed ? "" : " It runs a script, so allow mods that run code on Settings and repair too.";
  if (s.state === "missing") {
    return { kind: "warn", title: "You'll need Sandbox mode",
      text: `Your cats and questlines go in with your mod, but Sandbox mode brings them into the game: download ${zip} from its releases page and drop it on the Mods page.${codeStep}`,
      link: s.releases };
  }
  const tooOld = uses.filter(f => (s.older || []).includes(f) && FIELDS[f]);
  if (tooOld.length) {
    const [what, without] = FIELDS[tooOld[0]];
    return { kind: "warn", title: `Your ${what} need Sandbox mode ${s.newest} or newer; you have ${s.version || "an older one"}`,
      text: `Until then ${without}. Download ${zip} from its releases page and drop it on the Mods page.`, link: s.releases };
  }
  if (s.state === "off") {
    return { kind: "warn", title: "Sandbox mode is off", text: "Your cats and questlines go in, but nothing shows them until it's on.",
      button: "Turn it on" };
  }
  if (s.state === "no-code") {
    return { kind: "warn", title: "Sandbox mode is in, but mods that run code aren't allowed, so it can't run",
      text: "Allow them on Settings and repair, then Apply to game.", settings: true };
  }
  return { kind: "good", title: `Sandbox mode${s.version ? " " + s.version : ""} is on`, text: "It brings your cats and questlines into the game." };
}

// The strip at the top of the Characters and Questlines pages: what Sandbox mode can show (one line, with
// what to press), and under it the whole way to see them in the game, with the guide's page. refresh()
// asks the studio again; update(uses) says which of Sandbox mode's newer fields the page's cats use.
export function sandboxStrip({ help, route }) {
  const line = el("div", { class: "banner", role: "status" });
  const routeLine = el("p", { class: "note" }, el("span", { text: route + " " }),
    el("button", { class: "btn link", type: "button", text: "How this works", onclick: () => openHelp(help) }));
  const element = el("div", { class: "stack sandbox-strip" }, line, routeLine);
  let state = null, uses = [];
  function draw() {
    if (!state) { line.hidden = true; return; }
    const w = stripWords(state, uses);
    line.hidden = false;
    line.className = w.kind === "good" ? "banner info" : "banner";
    // (replaceChildren would write a null out as the word "null": what isn't there is left out first.)
    line.replaceChildren(...[el("strong", { text: w.title }), el("span", { text: w.text }),
      w.link ? el("a", { href: w.link, target: "_blank", rel: "noopener", text: "Sandbox mode's releases page" }) : null,
      w.settings ? el("a", { href: "#settings", text: "Open Settings and repair" }) : null,
      w.button ? el("div", { class: "row" }, el("button", { class: "btn small", type: "button", text: w.button, onclick: turnOn })) : null]
      .filter(Boolean));
  }
  async function turnOn() {
    try {
      const r = await api.post(`/mods/${SANDBOX}/switch`, { on: true });
      const names = (r.changed || []).filter(c => c.on).map(c => c.name);
      toast(names.length ? `Turned on ${names.join(" and ")}. Apply to game to use it.` : "Sandbox mode is on.");
      bus.emit("mods-changed");
      await refresh();
      announce(stripWords(state, uses).title);
    } catch (e) { toast(e.message, "bad"); }
  }
  async function refresh() {
    try { state = await api.get("/story/sandbox"); } catch (e) { state = null; }
    draw();
  }
  return { element, refresh, update(fields) { uses = fields || []; draw(); }, get state() { return state; } };
}

// A drawing of a cat's face in its colours (fur, pattern, markings, nose, eyes). eye null: grey, the
// game's choice.
export function catFace(colours = {}, eye = "#b6c86a") {
  const c = { fur: "#9a8a78", pattern: "#5b4e40", markings: "#e9e1d4", nose: "#c47c7a", ...colours };
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 200 180");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "The cat's colours");
  svg.classList.add("cat-face");
  eye = eye || "#9a9a9a";
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
