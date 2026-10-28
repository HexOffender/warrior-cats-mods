// Cats' looks: colours only that cat wears (coat, paws, ears, nose, whiskers), which of the game's colours it uses
// (new pattern and marking colours from palettes included), its scars and its shape (body, ears, tail, pattern...),
// for your cat and for any cat in your save (cats.json's "cats", by name or place). Writes cats.json (see
// wcmods/catcolours.py); reading and writing it is lib/catlook.js, and the drawn cat lib/cat.js (the Palettes page's).
//
// "Your cat" is the cat in the game being played when you Apply ("player", the default, and what a shared mod wants),
// or your cat in one game of your save, chosen in Which game ("4/player" under "cats": that game's cat only). The
// other cats are every game's, each listed under its game (lib/games.js says the games the same way on every page).
import * as C from "../lib/catlook.js";
import * as G from "../lib/games.js";
import { catSvg, paintCat } from "../lib/cat.js";
import { eyeRamp, eyeWord, plainRow } from "../lib/palette.js";

const PARTS = [
  { id: "fur", name: "Coat", note: "Replaces the coat colour, whichever of the game's coats it has." },
  { id: "paws", name: "Paw pads" }, { id: "ears", name: "Inner ears" }, { id: "nose", name: "Nose" },
  { id: "whiskers", name: "Whiskers" },
];
// Scar places, in the order the card shows them (the build's names: catcolours.SCARS).
const SCAR_PARTS = [
  { id: "ear", name: "Ears" }, { id: "eye", name: "Eye" }, { id: "back", name: "Back" }, { id: "chest", name: "Chest" },
];
const SLOT_PARTS = [
  { id: "fur", name: "Coat colour", table: "FurColors" },
  { id: "pattern", name: "Pattern colour", table: "PatternMaskColors" },
  { id: "marking", name: "Marking colour", table: "MarkingMaskColors" },
  { id: "eye_left", name: "Left eye colour", table: "IrisColors" },
  { id: "eye_right", name: "Right eye colour", table: "IrisColors" },
];
// The shape (catcolours.LOOK): the game's options for each part, counted from 0.
const LOOK_PARTS = [
  { id: "body", name: "Body", note: "the fur's shape follows it, as in the cat maker" }, { id: "fur", name: "Fur shape" },
  { id: "tail", name: "Tail" }, { id: "ears", name: "Ears" }, { id: "eyes", name: "Eyes" },
  { id: "whiskers", name: "Whiskers" }, { id: "face", name: "Face" }, { id: "pattern", name: "Pattern" },
  { id: "marking", name: "Markings" },
];
// A cat's entry in a few words (lib/catlook.js's describe), in this page's words.
const WORDS = {
  colours: Object.fromEntries(PARTS.map(p => [p.id, p.name.toLowerCase()])),
  slots: { ...Object.fromEntries(SLOT_PARTS.map(s => [s.id, s.name.toLowerCase()])), eyes: "eye colour" },
  look: Object.fromEntries(LOOK_PARTS.map(p => [p.id, p.name.toLowerCase()])),
};

export default {
  title: "Your cat",
  async mount(root, wc) {
    const { el, api, clear, toast, color } = wc;
    // clear() hands back the bare element, whose own append writes a null as the text "null": this leaves them out.
    const put = (node, ...kids) => { clear(node).append(...kids.filter(k => k != null && k !== false)); return node; };
    // looks: each cat's choices, "player" for yours and the others by their cats.json key (lib/catlook.js says
    // what each holds); fileExtra: the file's other keys, kept as they are.
    let looks = { player: C.blank() }, fileExtra = {}, who = "player";
    // The title, and a line while the page waits: the first GET /cat on a real save takes a couple of seconds (it
    // reads the whole save), and until it answers there'd be nothing on the page at all.
    const head = wc.pageHead({ eyebrow: "Your cat", title: "Your cat",
      lede: "Your cat's look, or any other cat's in your save: colours only that cat wears, which of the game's colours it uses, its scars and its shape. Save to a mod, then Apply to game.",
      help: "help:cat" });
    const reading = el("p", { class: "muted reading", role: "status", text: "Reading your save…" });
    root.append(head, reading);
    // GET /cat, the game's colour tables and eye colours (either may not be readable yet), the studio's status (the
    // script loader, the last Apply) and the mods (which one the in-game Colours page saves into).
    const [firstInfo, tablesRes, eyesRes, firstStatus, firstMods] = await Promise.all([api.get("/cat"),
      api.get("/game/tables").catch(() => ({ tables: null })), api.get("/game/eyes").catch(() => null), api.get("/info").catch(() => null),
      api.get("/mods").catch(() => [])]);
    reading.remove();
    let info = firstInfo, status = firstStatus, mods = firstMods;
    const TABLES = tablesRes.tables || {};
    const EYE_LIN = eyesRes ? eyesRes.rows.map(r => r.map(h => color.hexToLinear("#" + h))) : null;
    const known = () => C.knownFrom(info);
    const others = () => info.cats || [];
    // An eye colour as the game draws it: atlas row slot + 1 (row 0 is the eye white), with an enabled palette's
    // colour on it. Without the game's files, the cat maker's button colour (IrisColors) on a plain strip.
    const eyeOf = row => (info.eyes || {})[String(row)] || null;
    function eyeStrip(slot) {
      if (EYE_LIN && EYE_LIN[slot + 1]) return eyeRamp(EYE_LIN[slot + 1], eyeOf(slot + 1));
      const hex = (TABLES.IrisColors || [])[slot];
      return hex ? eyeRamp(plainRow(64), { mode: "single", colors: [hex] }) : plainRow(64);
    }
    const rimOf = ramp => color.linearToHex(ramp[ramp.length - 1]);
    // In the Palettes page's words: "Extra eye 1" for the game's "Dlc1", else the game's name.
    const eyeName = slot => (eyesRes ? eyeWord(eyesRes.labels, slot + 1) : null);

    const target = wc.modTarget({
      file: "cats.json",
      onLoad: obj => { ({ looks, fileExtra } = C.load(obj, known())); if (!looks[who] && !mine()) who = "player"; render(); },
      getValue: () => json(),
      // Saved: the page reads what it wrote as it reads any file (a save doesn't read the file back), on the same
      // cat. Not when something changed while it saved: that stays on the page, still to be saved.
      onSaved: (saved, { changed }) => { if (changed) return; ({ looks, fileExtra } = C.load(saved, known())); render(); },
    });
    const saveLine = el("div", { class: "banner", role: "status", hidden: true });
    const whoCard = el("div", { class: "card" }), lookCard = el("div", { class: "card" }),
      coloursCard = el("div", { class: "card" }), slotsCard = el("div", { class: "card" }), scarsCard = el("div", { class: "card" });
    // types: each place's scars as [name, label], scar n being the n-th (catcolours.SCAR_TYPES).
    const scars = () => info.scars || { current: {}, types: {} };
    const scarTypes = part => scars().types[part] || [];
    const out = wc.codePanel("cats.json");
    // The drawn cat, as the choices on this page would make it, and what the save holds now.
    const stage = el("div", { class: "cat-stage" });
    stage.innerHTML = catSvg("cat", "The drawn cat, with its look as chosen on this page");
    const svg = stage.querySelector("svg");
    const nowCard = el("div", { class: "card" });
    root.append(
      el("div", { class: "banner info" }, el("strong", { text: "Two ways to colour a cat" }),
        el("span", { text: "Colours of its own go onto the cat while you play (they need the script loader), so any colour works, even for paws, ears and nose. The game's colours, scars and shape pick from the game's own, plus new pattern and marking colours your palettes add; they go into your save on Apply, after a backup." })),
      saveLine, target.element, whoCard,
      el("div", { class: "cat-top" },
        el("div", { class: "card" }, stage,
          el("p", { class: "note", text: "The drawing shows colours and head scars; the body shape, the back and chest scars and the paws aren't in it." })),
        nowCard),
      lookCard, coloursCard, slotsCard, scarsCard,
      el("details", { class: "card fold" },
        el("summary", {}, el("h3", { text: "For people who edit the file by hand" }), el("span", { class: "muted", text: "this page's cats.json, as Save writes it" })),
        out.element));

    function changed() {
      target.markDirty();
      out.set(json());
      drawCat();
      // A cat's entry kept as written ("player": "none") says beside it once a look set here takes its place.
      if (Object.keys(fileExtra).some(k => k === "player" || (k.startsWith("cats.") && !k.startsWith("cats._")))) renderWho();
    }

    // What the page can't change, under the card it belongs to: each kept as written until its Remove.
    function cantChange(entries) {
      if (!entries.length) return null;
      return el("div", { class: "stack" },
        el("strong", { text: "Things this page can't change" }),
        el("p", { class: "note", text: "They're in the file as written, and Save says whether they keep it out of the game. Remove takes one out." }),
        el("ul", { class: "notes" }, ...entries.map(e => el("li", { class: "row" },
          el("span", { class: "mono", text: `${e.where}: ${JSON.stringify(e.value)}` }),
          // A cat's entry that isn't a look ("player": "none"): the look set here takes its place at Save.
          C.lookFor(looks, e.where, known()) ? el("span", { class: "muted", text: "the look set on this page takes its place when you save" }) : null,
          el("button", { class: "btn ghost small", text: "Remove", "aria-label": `Remove ${e.where}`, onclick: () => { e.remove(); changed(); render(); } })))));
    }
    const rawOf = key => C.cantChange(look()).filter(e => e.where.startsWith(key + "."));

    // ---------- whose look ----------
    const look = () => (looks[who] = looks[who] || C.blank());
    // Your cat: in the game being played at Apply ("player"), or in one game ("4/player": yourGame() is "4").
    const mine = () => C.isYours(who);
    const yourGame = () => C.yourGame(who);
    const games = () => info.games || [];
    const gameNow = () => G.gameOf(games(), info.current_slot ?? "0");   // the game played last
    let lastMine = "player";   // the game Your cat was last on, for coming back to it from another cat
    // The cats a key means, as the build finds them, with the game being played's slot first or without it.
    const slot = () => info.current_slot ?? null;
    const hitsOf = k => C.catsFor(k, others(), slot());
    const bare = k => String(k).trim().replace(/^\d+\//, "");
    const byPlace = k => bare(k).includes("/");
    // The cats being changed: the one whose target the key is, else every one the key means (the build's way).
    const whoCats = () => { if (mine()) return []; const own = others().find(c => c.target === who); return own ? [own] : hitsOf(who); };
    const fileKeys = () => Object.keys(looks).filter(t => t !== "player");
    const changedLook = t => looks[t] && Object.keys(C.oneJson(looks[t], known())).length > 0;
    // The cat in a sentence: a place that means cats in several clans is "each of these cats".
    const whoName = () => {
      if (yourGame() !== null) return `your cat in ${G.gameWords(yourGame())}`;
      if (mine()) return "your cat";
      const cs = whoCats();
      return cs.length === 1 ? cs[0].name : cs.length > 1 && !byPlace(who) ? cs[0].name : cs.length > 1 ? "each of these cats" : `"${who}"`;
    };
    const whose = () => (mine() ? "your cat's" : whoName() === "each of these cats" ? "each one's" : `${whoName()}'s`);
    const capital = t => t[0].toUpperCase() + t.slice(1);
    // The file as Save writes it: a cat's own entry after the other keys that reach it, so the page's choices win.
    const lastKeys = () => {
      const last = C.ownLast(looks, others(), slot());
      if (!mine() && whoCats().length === 1 && who in looks && !last.includes(who)) last.push(who);
      return last;
    };
    const json = () => C.toJson(looks, fileExtra, known(), lastKeys());
    // What the save has now for the cat chosen: null for a cat cats.json names that isn't in the game being played,
    // for your cat while that game has none yet, and for a save that can't be read now. For a key that means several
    // cats, what they all have the same, `differs` naming the rest (lib/catlook.js's common).
    const saveRead = () => !info.save_problem;
    const now = () => {
      if (!saveRead()) return null;
      if (yourGame() !== null) return games().find(g => g.slot === yourGame())?.look_now || null;
      if (mine()) return Object.keys(info.current || {}).length ? { slots: info.current, scars: scars().current, look: (info.look || {}).current || {} } : null;
      const cs = whoCats();
      return cs.length === 1 ? cs[0].current || null : cs.length ? C.common(cs.map(c => c.current)) : null;
    };
    const differs = (key, part) => ((now() || {}).differs?.[key] || []).includes(part);
    const itWord = () => (mine() ? "my cat" : whoCats().length > 1 ? "each" : "it");

    function renderSaveLine() {
      saveLine.hidden = saveRead();
      clear(saveLine);
      if (!saveRead()) saveLine.append(el("strong", { text: "What your cat wears now isn't shown" }), el("span", { text: `${info.save_problem}. Colours of its own work all the same.` }));
    }

    // The cats to choose from, by game (the one played last first) and clan (yours first), each by its name and role,
    // with the file's keys that mean no single cat (a name two cats share, a cat not in the save) after them. The
    // filter box narrows the list.
    let filter = "";
    const GROUP_WORDS = { NarrativeRoles: "Story roles" };
    const gameOfCat = c => String(c.slot ?? slot());
    function whoOptions() {
      const cats = others(), keys = fileKeys(), f = filter.trim().toLowerCase(), chosen = whoValue();
      // The chosen cat stays in the list whatever the filter says, so the box never shows another one.
      const shown = c => !f || `cat:${c.target}` === chosen || [c.name, c.where, C.roleWords(c.role)].some(s => s.toLowerCase().includes(f));
      // Changed by any key that reaches it (a shared name too); "in the file as" the keys that mean it alone.
      const optionFor = c => {
        const on = C.keysOn(c, keys, cats, slot()), alone = on.filter(k => k !== c.target && hitsOf(k).length === 1);
        const label = [c.name, C.roleWords(c.role)].filter(Boolean).join(", ")
          + (on.some(changedLook) ? ", changed" : "") + (alone.length ? ` (in the file as ${alone.map(k => `"${k}"`).join(" and ")})` : "");
        return el("option", { value: `cat:${c.target}`, text: label, title: c.where });
      };
      // Each game's cats under it, the game being played first (GET /cat lists it first); a save with one game, by
      // clan alone.
      const slots = [...new Set(cats.map(gameOfCat))];
      const groups = slots.flatMap(at => {
        const inGame = cats.filter(c => gameOfCat(c) === at);
        const clans = [...new Set(inGame.map(c => c.clan || ""))]
          .sort((a, b) => (b === info.your_clan) - (a === info.your_clan) || (b.endsWith("Clan") - a.endsWith("Clan")) || a.localeCompare(b));
        return clans.map(clan => {
          const inIt = inGame.filter(c => (c.clan || "") === clan && shown(c));
          const name = GROUP_WORDS[clan] || clan || "Other cats";
          return inIt.length ? el("optgroup", { label: slots.length > 1 ? `${name}, ${G.gameWords(at)}` : name }, ...inIt.map(optionFor)) : null;
        });
      });
      // Keys that mean two or more cats, or none the page lists (your cat's are in Which game, not here).
      const anyNames = cats.some(c => (c.aliases?.names || []).length);
      const elsewhere = k => !/^\d+\//.test(String(k).trim()) && cats.some(c => gameOfCat(c) !== String(slot()) && C.catsFor(`${gameOfCat(c)}/${k}`, [c], slot()).length);
      const loose = keys.filter(k => !C.isYours(k) && hitsOf(k).length !== 1).map(k => {
        const hits = hitsOf(k);
        const why = hits.length > 1 ? (byPlace(k) ? `changes ${hits.length} cats: ${hits.map(c => c.where).join(", ")}`
            : `changes ${hits.length} cats called ${hits[0].name}`)
          : !saveRead() ? "your save can't be read now"
          : elsewhere(k) ? "not in the game you're playing: choose the cat in its game above"
          : !byPlace(k) && !anyNames ? "found by its name once the game's files can be read"
          : "not in your save";
        return el("option", { value: `key:${k}`, text: `"${k}" (${why})` });
      });
      return [el("option", { value: "player", text: "Your cat" }), ...groups,
        loose.length ? el("optgroup", { label: "In the file" }, ...loose) : null];
    }
    // The option that stands for `who`: your cat (in whichever game), the cat a key that means it alone stands for,
    // else the key itself.
    function whoValue() {
      if (mine()) return "player";
      const cs = whoCats();
      return cs.length === 1 ? `cat:${cs[0].target}` : `key:${who}`;
    }
    // Which game for your cat: the game being played at Apply ("player"), or one game of the save ("4/player"); a
    // game the file names that isn't in the save is listed too, so its entry can be seen and removed.
    function gameOptions() {
      const keyed = fileKeys().map(C.yourGame).filter(s => s !== null);
      const slots = [...new Set([...games().map(g => g.slot), ...keyed])].sort((a, b) => Number(a) - Number(b));
      return [el("option", { value: "player", text: `The cat in the game you're playing (whichever it is when you Apply)${changedLook("player") ? ", changed" : ""}` }),
        ...slots.map(at => {
          const g = games().find(x => x.slot === at);
          const facts = g ? [g.name || "Your cat", G.gameWords(at), g.sandbox ? "Sandbox mode" : null, g.current ? "played last" : null]
            : [`"${at}/player"`, G.gameWords(at), "not in your save"];
          return el("option", { value: `${at}/player`, text: facts.filter(Boolean).join(", ") + (changedLook(`${at}/player`) ? ", changed" : "") });
        })];
    }
    // The header: whose look, and in which game.
    function whoTitle() {
      if (yourGame() !== null) return G.catInGame(G.gameOf(games(), yourGame())).replace(/^y/, "Y");
      if (mine()) return "Your cat, in the game you're playing";
      const cs = whoCats();
      return cs.length === 1 && games().length > 1 ? `${cs[0].name}, in ${G.gameWords(gameOfCat(cs[0]))}` : "Whose look";
    }
    // What choosing your cat's game means, in words.
    function yourNote() {
      const playing = gameNow(), at = yourGame();
      if (at === null) {
        return `Your cat in the game you're playing when you Apply${games().length ? ` (now ${G.gameTitle(playing).replace(/^Y/, "y")}, the game you played last)` : ""}. It's what a mod to share wants: it changes the cat of whoever adds it. Choose a game to change only that game's cat, or another cat below to change its look the same way: it's found by its name (or its place, when two share a name), and only it changes.`;
      }
      const g = G.gameOf(games(), at), twins = G.sameName(games(), g);
      return `Only your cat in ${G.gameWords(at)} changes, whichever game you're playing: its scars, its shape and the game's colours it wears go into that game in your save at Apply. Its colours of its own go on by its name while you play${twins.length ? `, so your cat in ${G.andList(twins.map(t => G.gameWords(t.slot)))}, which has the same name, gets them too` : ""}; a rank-up changes its name, so apply again after one. For someone you share the mod with, it's the cat in their ${G.ordinal(G.numberOf(at))} game.`;
    }
    function renderWho() {
      const sel = el("select", { "aria-label": "Whose look" }, ...whoOptions());
      sel.value = whoValue();
      sel.addEventListener("change", () => {
        const v = sel.value;
        const cat = v.startsWith("cat:") && others().find(c => c.target === v.slice(4));
        who = v === "player" ? lastMine : cat ? C.keyFor(cat, fileKeys(), others(), slot()) : v.slice(4);
        render();
      });
      const pick = el("select", { "aria-label": "Which game", id: "cat-game" }, ...gameOptions());
      pick.value = who;
      pick.addEventListener("change", () => { who = lastMine = pick.value; render(); });
      const find = el("input", { type: "search", value: filter, placeholder: "Find a cat", "aria-label": "Find a cat by name, place or role" });
      find.addEventListener("input", () => {
        filter = find.value;
        const keep = sel.value;
        clear(sel).append(...whoOptions().filter(Boolean));
        sel.value = keep;
      });
      const hits = whoCats(), places = hits.map(c => c.where).join(", ");
      const note = mine() ? yourNote()
        : hits.length > 1 && byPlace(who) ? `"${who}" changes ${hits.length} cats: ${places}. A place without its clan means that place in every clan. Choose one of them above to change just it.`
        : hits.length > 1 ? `"${who}" changes ${hits.length} cats called ${hits[0].name} (${places}). Choose one of them above to change just it.`
        : hits.length === 1 && gameOfCat(hits[0]) !== String(slot()) ? `${whoName()} is in ${G.gameWords(gameOfCat(hits[0]))}, not the one you played last: its scars, its shape and the game's colours it wears go into that game at Apply, but its colours of its own go on only while its game is the one you're playing when you Apply.`
        : `${whoName()} is changed by ${byPlace(who) ? "its place" : "its name"} (${who}). Its colours go on by its name, so a cat with the same name gets them too; a rank-up changes a cat's name: apply again after one to keep its colours on it.`;
      // Other keys of the file that reach this cat too: the build applies them as well. Save writes this cat's own
      // entry after them (lastKeys), so where both choose a part, this page's choice wins.
      const also = hits.length === 1 ? C.keysOn(hits[0], fileKeys(), others(), slot()).filter(k => k !== who && changedLook(k)) : [];
      put(whoCard, el("h2", { id: "cat-who-title", text: whoTitle() }),
        el("div", { class: "row" }, find, sel),
        mine() ? el("div", { class: "row" }, el("label", { for: "cat-game", class: "lbl", text: "Which game" }), pick) : null,
        el("p", { class: "note", id: "cat-who-note", text: note }),
        also.length ? el("div", { class: "stack cat-also" },
          el("strong", { text: "Other entries in the file for this cat" }),
          el("p", { class: "note", text: "The build applies them too. Where this page chooses the same thing, this page's choice wins: Save writes it after them. Remove takes one out of the file." }),
          el("ul", { class: "notes" }, ...also.map(k => {
            const n = hitsOf(k).length;
            return el("li", { class: "row" },
              el("span", { text: `also changed by "${k}"${n > 1 ? ` (it changes ${n} cats)` : ""}: ${C.describe(looks[k], known(), WORDS)}` }),
              el("button", { class: "btn ghost small", text: "Remove", "aria-label": `Remove "${k}"`,
                onclick: () => { delete looks[k]; changed(); render(); } }));
          }))) : null);
      // Yours (in the game being played) lists the file's own keys too; another cat's, its own entry when the file
      // has it as something else.
      const theirs = who !== "player" && `cats.${who}` in fileExtra ? { [`cats.${who}`]: fileExtra[`cats.${who}`] } : null;
      const raw = [...C.cantChange(look(), who === "player" ? fileExtra : null), ...(theirs ? C.cantChange(C.blank(), theirs) : [])]
        .filter(e => !/^(colours|slots|scars|look)\./.test(e.where))
        .map(e => (theirs && e.where in theirs ? { ...e, remove: () => { delete fileExtra[e.where]; } } : e));
      const block = cantChange(raw);
      if (block) whoCard.append(block);
    }

    // The colour a slot shows with the enabled palettes: a palette's colour, else the game's; an eye, its rim.
    const slotHex = (part, i) => (part.startsWith("eye") ? (EYE_LIN || TABLES.IrisColors ? rimOf(eyeStrip(i)) : null)
      : (info.palette[part] || {})[i] || (TABLES[SLOT_PARTS.find(s => s.id === part).table] || [])[i] || null);

    function render() {
      renderSaveLine(); renderWho(); renderNow(); renderLook(); renderColours(); renderSlots(); renderScars(); drawCat();
      out.set(json());
    }

    // ---------- the drawn cat, and what the save holds now ----------
    // The page's choice for a part, else what the save has now.
    const wears = (key, part) => { const l = look(), cur = (now() || {})[key] || {}; return part in l[key] ? l[key][part] : cur[part]; };
    function drawCat() {
      const l = look(), slot = part => wears("slots", part);
      paintCat(svg, {
        coat: l.colours.fur || slotHex("fur", slot("fur")) || "#9A8F84",
        pattern: slotHex("pattern", slot("pattern")) || undefined, marking: slotHex("marking", slot("marking")) || undefined,
        eyeWhite: EYE_LIN ? rimOf(eyeRamp(EYE_LIN[0], eyeOf(0))) : undefined,
        rightEye: eyeStrip(slot("eye_right") ?? 0), leftEye: eyeStrip(slot("eye_left") ?? 0),
        nose: l.colours.nose, ears: l.colours.ears, whiskers: l.colours.whiskers,
        scars: { ear: wears("scars", "ear"), eye: wears("scars", "eye") },
      });
    }
    function renderNow() {
      const cur = now(), name = whoName(), cats = whoCats();
      const built = status && status.installed && status.installed.built;
      const when = built ? new Date(built).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : null;
      const line = (label, text) => el("li", {}, el("strong", { text: `${label}: ` }), text);
      const eye = slot => (eyeName(slot) ? `${eyeName(slot)} (${slot})` : String(slot));
      // One cat's save values, as a list.
      const list = c => {
        const s = c.slots || {}, l = c.look || {};
        const scarText = Object.entries(c.scars || {}).filter(([, n]) => n > 0)
          .map(([part, n]) => `${SCAR_PARTS.find(p => p.id === part)?.name.toLowerCase() || part}: ${scarLabel(part, n).toLowerCase()}`);
        const shape = LOOK_PARTS.filter(p => p.id in l).map(p => `${p.name.toLowerCase()} ${l[p.id]}`);
        return el("ul", { class: "notes" },
          line("Colours", `coat ${s.fur}, pattern ${s.pattern}, markings ${s.marking}`),
          line("Eyes", `left ${eye(s.eye_left)}, right ${eye(s.eye_right)}`),
          line("Scars", scarText.length ? scarText.join("; ") : "none"),
          line("Shape", shape.join(", ") + (l.size != null ? `, size ${l.size}` : "")));
      };
      // Which game it's read from: the game played last for "player", the chosen game, or the cat's own.
      const fromGame = yourGame() ?? (mine() ? String(slot() ?? "") : cats.length === 1 ? gameOfCat(cats[0]) : null);
      const gameSaid = !saveRead() || !fromGame || (!games().length && !yourGame()) ? ""
        : `: ${G.gameWords(fromGame)}${who === "player" ? ", the game you played last" : ""}`;
      put(nowCard, el("h2", { id: "cat-now-title", text: `In your save now${gameSaid}` }),
        !saveRead() ? el("p", { class: "note", text: `Unknown: ${info.save_problem}.` })
          : yourGame() !== null && !cur ? el("p", { class: "note", text: `Your save has no cat of yours in ${G.gameWords(yourGame())}: the build changes nothing until it has one. Choose another game above, or the game you're playing.` })
          : mine() && !cur ? el("p", { class: "note", text: "There's no cat of yours in the game being played yet: start one in the game, then come back here." })
          : cats.length > 1 ? el("div", { class: "stack" },
            el("p", { class: "note", text: `"${who}" changes ${cats.length} cats, each with its own:` }),
            ...cats.map(c => el("div", {}, el("strong", { text: `${c.name}${c.name !== c.where ? `, ${c.where}` : ""}` }), list(c.current || {}))))
          : !cur ? el("p", { class: "note", text: `${name[0].toUpperCase()}${name.slice(1)} isn't in your save, so it has nothing for it.` })
          : list(cur),
        el("p", { class: "note", text: `${when ? `Last applied ${when}. ` : ""}It's read again after every Apply. Switching the mod off doesn't undo the game's colours, the shape or the scars: they stay in your save. To put them back, choose the old ones here and apply again, or put back the copy of your save the studio made (Backups and repair, on the Settings and repair page).` }));
    }

    function renderLook() {
      const l = look(), cur = (now() || {}).look || {}, parts = (info.look || {}).parts || {};
      const rows = LOOK_PARTS.filter(p => p.id in parts).map(p => {
        const sel = el("select", { "aria-label": p.name },
          el("option", { value: "", text: `Keep what ${itWord()} has now${p.id in cur ? ` (${cur[p.id]})` : differs("look", p.id) ? " (not the same for each)" : saveRead() ? "" : " (unknown now)"}` }),
          ...[...Array(parts[p.id] + 1).keys()].map(n => el("option", { value: String(n), text: String(n) })));
        sel.value = p.id in l.look ? String(l.look[p.id]) : "";
        sel.addEventListener("change", () => { if (sel.value === "") delete l.look[p.id]; else l.look[p.id] = Number(sel.value); changed(); });
        return el("div", { class: "row" }, el("strong", { text: p.name, style: { minWidth: "150px" } }), sel,
          el("span", { class: "muted", text: p.note || "" }));
      });
      const [lo, hi] = (info.look || {}).size || [0.05, 1.5];
      const on = "size" in l.look;
      const clampSize = v => Math.max(lo, Math.min(hi, Number(v) || 0.8));
      // A size as the file has it (0.873, not rounded to the slider's steps), with two decimals at least.
      const sizeText = v => { const n = Math.round(Number(v) * 1000) / 1000; return n.toFixed(/\.\d{3}$/.test(String(n)) ? 3 : 2); };
      // A slider with the game's sizes marked (a kit, an apprentice, a warrior, a leader), and the number beside it.
      const marks = el("datalist", { id: "cat-size-marks" }, ...[[0.1, "kit"], [0.45, "apprentice"], [0.75, "warrior"], [1, "leader"]]
        .map(([v, label]) => el("option", { value: String(v), label })));
      const start = clampSize(l.look.size ?? cur.size);
      const size = el("input", { type: "range", min: String(lo), max: String(hi), step: "0.01", list: "cat-size-marks",
        value: String(start), "aria-label": "Size", disabled: !on, style: { width: "min(260px, 60vw)" } });
      const shown = el("output", { class: "mono", text: sizeText(start) });   // the slider itself snaps to 0.01
      const box = el("input", { type: "checkbox", checked: on, "aria-label": "Change the size" });
      let exact = start;   // what the number says: the file's or the save's size until the slider moves
      size.addEventListener("input", () => { exact = Number(size.value); shown.textContent = sizeText(exact); });
      size.addEventListener("change", () => { const v = clampSize(size.value); exact = l.look.size = v; size.value = v; changed(); });
      box.addEventListener("change", () => { if (box.checked) l.look.size = clampSize(exact); else delete l.look.size; size.disabled = !box.checked; changed(); });
      put(lookCard, el("h2", { text: "Shape" }),
        el("p", { class: "note", text: `${capital(whose())} body, fur, tail, ears, eyes, whiskers and face, each one of the game's 10 (the cat maker shows a clan's 7 of them), and its pattern and markings (21 each). They go into your save on Apply, after a backup.${mine() ? " Body, ears and face chose your cat's traits when it was made; the traits stay as they are." : ""}` }),
        ...rows,
        el("div", { class: "row" }, el("label", { class: "row", style: { minWidth: "150px" } }, box, el("strong", { text: "Size" })), size, shown, marks,
          el("span", { class: "muted", text: `${cur.size != null ? `now ${cur.size}; ` : differs("look", "size") ? "each has its own size now; " : ""}a kit is about 0.1, an apprentice 0.45, a warrior 0.75, a leader 1.0${mine() ? ". The game sets your cat's size again when it ranks up" : ""}` })));
      const block = cantChange(rawOf("look"));
      if (block) lookCard.append(block);
    }

    function renderColours() {
      const l = look();
      // The parts the build knows (catcolours.PARTS), labelled here; a part with no label shows its id.
      const parts = Object.keys(info.parts || {}).map(id => PARTS.find(p => p.id === id) || { id, name: id });
      const rows = parts.map(p => {
        const on = p.id in l.colours;
        const inp = el("input", { type: "color", value: (l.colours[p.id] || "#a0a0a0").toLowerCase(), "aria-label": `${p.name} colour`, disabled: !on });
        const box = el("input", { type: "checkbox", checked: on, "aria-label": `Use its own ${p.name.toLowerCase()} colour` });
        inp.addEventListener("input", () => { l.colours[p.id] = color.normHex(inp.value); changed(); });
        box.addEventListener("change", () => {
          if (box.checked) l.colours[p.id] = color.normHex(inp.value); else delete l.colours[p.id];
          inp.disabled = !box.checked; changed();
        });
        return el("div", { class: "row" }, el("label", { class: "row", style: { minWidth: "150px", flexWrap: "nowrap" } }, box, el("strong", { text: p.name })),
          inp, el("span", { class: "muted", text: p.note || "" }));
      });
      const noLoader = status && status.game_dir && !status.ue4ss;
      // The in-game Colours page changes your cat's colours only, and its Save writes them into the mod that's on with
      // a cats.json, the last of them in the Mods list (sections/cats.py): name it, as it may not be this one.
      const top = mods.filter(m => m.enabled && (m.kinds.includes("cats") || m.id === target.current)).pop();
      const saves = !top ? "the last mod in the Mods list with your cat's look in it (this one, once it's saved and on)"
        : top.id === target.current ? `${top.name}, this mod (the last in the Mods list with a cat's look)`
        : `${top.name}, the one later in the Mods list, not in this mod`;
      put(coloursCard, el("h2", { text: "Colours of its own" }),
        el("p", { class: "note", text: `Tick a part to give ${whoName()} its own colour; unticked parts keep the game's. They show while you play, in menus and portraits, and go away if you turn the mod off.` }),
        who === "player" ? el("p", { class: "note cat-insert", text: `In the game, Insert opens the mod menu: its Colours page changes your cat's colours while you play, and its Save keeps them in ${saves}.` }) : null,
        noLoader ? el("p", { class: "note heads-up", text: "They need the script loader, which isn't installed yet: Get set up, on the Mods page, installs it." }) : null,
        ...rows);
      const block = cantChange(rawOf("colours"));
      if (block) coloursCard.append(block);
    }

    function renderSlots() {
      const l = look(), current = (now() || {}).slots || {};
      const shown = saveRead();
      const blocks = SLOT_PARTS.map(s => {
        const base = (TABLES[s.table] || []).length || info.game_slots;
        const extraSlots = Object.keys(info.palette[s.id] || {}).map(Number).filter(i => i >= base).sort((a, b) => a - b);
        const slots = [...Array(base).keys(), ...extraSlots];
        const cur = current[s.id], chosen = l.slots[s.id];
        const swatch = i => {
          const hex = slotHex(s.id, i) || "#888888";
          const feral = s.id === "fur" && info.feral_slots.includes(i);
          const picked = chosen === i, isNow = cur === i && chosen === undefined;
          // Picked shows as a ring and a tick, the cat's now as a thinner ring; screen readers hear both. The
          // number is black on a light colour and white on a dark one.
          const ink = color.luminance(color.hexToLinear(hex)) > 0.18 ? ["#000", "#fff"] : ["#fff", "#000"];
          const mark = { position: "absolute", fontWeight: "700", color: ink[0], textShadow: `0 0 2px ${ink[1]}` };
          return el("button", { class: "btn swatch", type: "button", "data-focus": `slot:${s.id}:${i}`,
            title: `${s.name} ${i}${s.id.startsWith("eye") && eyeName(i) ? ` (${eyeName(i)})` : ""}${i >= base ? " (new)" : ""}${feral ? " (Feral Edition)" : ""}${cur === i ? ", now" : ""}`,
            "aria-pressed": String(picked), "aria-label": `${s.name} ${i}${i >= base ? ", new" : ""}${cur === i ? ", now" : ""}`,
            style: { width: "38px", height: "38px", padding: "0", background: hex, position: "relative",
              boxShadow: picked ? "0 0 0 3px var(--accent)" : isNow ? "0 0 0 2px var(--ink)" : "",
              border: i >= base ? "2px dashed var(--field)" : "" },
            onclick: () => { if (l.slots[s.id] === i) delete l.slots[s.id]; else l.slots[s.id] = i; changed(); renderSlots(); } },
            picked ? el("span", { "aria-hidden": "true", style: { ...mark, top: "1px", left: "4px", fontSize: "0.85rem" }, text: "✓" }) : null,
            el("span", { "aria-hidden": "true", style: { ...mark, bottom: "1px", right: "3px", fontSize: "0.75rem" }, text: String(i) }));
        };
        const nowText = !shown ? "unknown" : differs("slots", s.id) ? "not the same for each" : cur ?? "?";
        const state = chosen === undefined ? `now: ${nowText} (kept)` : `${chosen}${cur !== undefined ? ` (now ${cur})` : ""}`;
        return el("div", { style: { display: "grid", gap: "6px" } },
          el("div", { class: "row spread" }, el("h3", { text: s.name }), el("span", { class: "muted", text: state })),
          el("div", { class: "row", style: { flexWrap: "wrap", gap: "6px" } }, ...slots.map(swatch)),
          (s.id === "pattern" || s.id === "marking") && !extraSlots.length ? el("p", { class: "note", text: "Palettes can add new colours here (Palettes page, New colours)." }) : null);
      });
      const tablesMissing = !Object.keys(TABLES).length;
      const feral = info.feral_slots.includes(wears("slots", "fur"));
      put(slotsCard, el("h2", { text: "Colours from the game's picker" }),
        el("p", { class: "note", text: `Pick one of the game's colours for ${whoName()} to wear, by its number; click it again to keep the one in your save. Dashed ones are new colours your palettes add, which only the cats set to them wear.` }),
        feral ? el("p", { class: "note heads-up", text: `Coat ${wears("slots", "fur")} is one of the Feral Edition's (coats 20-24): a game without it gives this cat another coat.` }) : null,
        tablesMissing ? el("p", { class: "note", text: "The game's colours show here once the game has run with the script loader (press Play once after an Apply); until then they're grey squares with their numbers." }) : null,
        ...blocks);
      const block = cantChange(rawOf("slots"));
      if (block) slotsCard.append(block);
    }
    // What a scar number looks like, from the build's list; a number past it (a save the game wrote)
    // as its number.
    function scarLabel(part, n) {
      if (n === 0) return "No scar";
      return (scarTypes(part)[n - 1] || [null, `Scar ${n}`])[1];
    }

    function renderScars() {
      const l = look(), current = (now() || {}).scars || {};
      // A place's entry the page can't show (written by hand) goes when the page chooses for that place.
      const dropRaw = id => { for (const k of Object.keys(l.raw.scars)) if ((k === "body" ? "back" : k) === id) delete l.raw.scars[k]; };
      const rows = SCAR_PARTS.map(s => {
        const top = scarTypes(s.id).length;
        const isNow = !saveRead() ? "unknown now" : differs("scars", s.id) ? "not the same for each"
          : s.id in current ? scarLabel(s.id, current[s.id]).toLowerCase() : "not in your save";
        const sel = el("select", { "aria-label": `${s.name} scar` },
          el("option", { value: "", text: `Keep what ${itWord()} has now (${isNow})` }),
          ...[...Array(top + 1).keys()].map(n => el("option", { value: String(n), text: scarLabel(s.id, n) })));
        sel.value = s.id in l.scars ? String(l.scars[s.id]) : "";
        sel.addEventListener("change", () => {
          const had = rawOf("scars").length;
          dropRaw(s.id);
          if (sel.value === "") delete l.scars[s.id]; else l.scars[s.id] = Number(sel.value);
          changed();
          if (rawOf("scars").length !== had) renderScars();   // its entry left the list of things the page can't change
        });
        return el("div", { class: "row" }, el("strong", { text: s.name, style: { minWidth: "150px" } }), sel);
      });
      const none = el("button", { class: "btn", type: "button", text: "No scars at all", "data-focus": "scars:none",
        onclick: () => { for (const s of SCAR_PARTS) l.scars[s.id] = 0; l.raw.scars = {}; changed(); renderScars(); } });
      const keep = el("button", { class: "btn", type: "button", text: "Keep the scars it has now", "data-focus": "scars:keep",
        onclick: () => { l.scars = {}; l.raw.scars = {}; changed(); renderScars(); } });
      put(scarsCard, el("h2", { text: "Scars" }),
        el("p", { class: "note", text: `Choose ${whose()} scars, or none. An eye scar shuts that eye; right and left are the cat's own. They go into your save on Apply, after a backup. A boss fight can still give new ones.` }),
        el("p", { class: "note heads-up" }, "Scars show only with the game's Injury system on: ",
          el("a", { href: "#save", text: "the Save page" }), " has the switch, under the game's settings."),
        ...rows, el("div", { class: "row" }, none, keep));
      const block = cantChange(rawOf("scars"));
      if (block) scarsCard.append(block);
    }

    // What your cat wears now is read again after an Apply or Play (it wrote the save), after another page saved a
    // mod (a palette's new colour), and on coming back to the window (the game may have changed the save): the
    // page's own choices stay, unsaved ones too. The file itself is read again after an Apply only while nothing
    // here is unsaved (installedEvent); coming back re-reads it when it changed (the bar does that).
    async function readCat() {
      try {
        [info, status, mods] = await Promise.all([api.get("/cat"), api.get("/info").catch(() => status), api.get("/mods").catch(() => mods)]);
      } catch (e) { return; }
      render();
    }
    const offs = [
      wc.installedEvent(target, () => target.refresh()),
      ...["installed", "mods-changed", "focus"].map(evt => wc.bus.on(evt, readCat)),
    ];
    await target.refresh();   // last: loading renders, which needs everything above
    return { unmount() { for (const off of offs) off(); } };
  },
};
