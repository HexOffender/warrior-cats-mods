// The games in a save, in the words every page says them in: GET /save's and GET /cat's "games" (wcmods/games.py),
// one for each cat started, numbered as the game's cat choice numbers them (its first is slot 0, "your 1st game").
// A game: { slot: "4", n: 5, name: "Sharppaw" | null, clan, rank, level, sandbox, current (the game played last) }.
// The Save page and Your cat pick a game with these; the Names page heads its games with them.
// tests/studio/unit/games.test.mjs runs these in node.

// 1st, 2nd, 3rd, 4th, 11th, 21st.
export function ordinal(n) {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}
// Things in a sentence: "A", "A and B", "A, B and C".
export const andList = words => (words.length < 2 ? words.join("") : `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`);
// A slot's number as the game shows it ("4" is 5), or null for a key that isn't a slot.
export const numberOf = slot => (/^\d+$/.test(String(slot)) ? Number(slot) + 1 : null);
// "your 5th game", as wcmods/names.py's game_words says it.
export function gameWords(slot) {
  const n = numberOf(slot);
  return `your ${n === null ? String(slot) : ordinal(n)} game`;
}
const cap = t => t.charAt(0).toUpperCase() + t.slice(1);
// A game's heading: "Your 5th game: Sharppaw", or "Your 5th game" while its cat's name isn't known.
export function gameTitle(game) {
  return `${cap(gameWords(game.slot))}${game.name ? `: ${game.name}` : ""}`;
}
// "your cat in your 5th game: Sharppaw", for a header that names the cat and its game.
export function catInGame(game) {
  return `your cat in ${gameWords(game.slot)}${game.name ? `: ${game.name}` : ""}`;
}
// What a game is, after its number: "Sharppaw, ThunderClan, level 1, Sandbox mode, played last". The level when
// the save has it, else the rank.
export function gameFacts(game) {
  const rank = game.rank ? String(game.rank).replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase() : null;
  return [game.name, game.clan, game.level != null ? `level ${game.level}` : rank,
    game.sandbox ? "Sandbox mode" : null, game.current ? "played last" : null].filter(Boolean).join(", ");
}
// A game picker's line: "5th game: Sharppaw, ThunderClan, level 1, Sandbox mode, played last".
export function gameLabel(game) {
  const n = numberOf(game.slot), facts = gameFacts(game);
  return `${n === null ? String(game.slot) : ordinal(n)} game${facts ? `: ${facts}` : ""}`;
}
// The games another game's cat shares a name with ([] when its name is its own, or not known): two games with a
// Sharppaw are told apart by their numbers, never by the name.
export function sameName(games, game) {
  if (!game?.name) return [];
  return games.filter(g => g.slot !== game.slot && g.name && g.name.toLowerCase() === game.name.toLowerCase());
}

// The game a save path is in ("4" for "4/GameplayProgression/Level"), or null for one every game shares
// ("Shared/SettingsData/MasterVolume").
export function slotOfPath(path) {
  const m = /^(\d+)\//.exec(String(path));
  return m ? m[1] : null;
}
// The game a list of games has for a slot; one the list hasn't (no cat of yours in it, or not in the save) by its
// number alone.
export function gameOf(games, slot) {
  return (games || []).find(g => g.slot === String(slot))
    || { slot: String(slot), n: numberOf(slot), name: null, clan: null, rank: null, level: null, sandbox: false, current: false };
}
// The games a picker lists: the save's, and the game played last even when it has no cat of yours yet (the page
// still opens on it), in the game's order.
export function pickable(games, current) {
  const list = [...(games || [])];
  if (current != null && !list.some(g => g.slot === String(current))) list.push({ ...gameOf([], current), current: true });
  return list.sort((a, b) => Number(a.slot) - Number(b.slot));
}
// The game a picker starts on: the one kept from before (this tab's last choice, `kept`: { slot, last }) while the
// save still has it and the game played last is the same as when it was chosen; else the game played last.
export function startSlot(games, current, kept) {
  if (kept && kept.slot != null && String(kept.last) === String(current) && (games || []).some(g => g.slot === String(kept.slot))) {
    return String(kept.slot);
  }
  return current == null ? null : String(current);
}
// A list of things by their games, in the game's order ([[slot or null, [things]]]), the ones every game shares
// (slot null) last: for the Save page's lists of changes.
export function byGame(items, pathOf = x => x.path) {
  const groups = new Map();
  for (const x of items) {
    const slot = slotOfPath(pathOf(x));
    if (!groups.has(slot)) groups.set(slot, []);
    groups.get(slot).push(x);
  }
  return [...groups.entries()].sort(([a], [b]) => (a === null) - (b === null) || Number(a) - Number(b));
}
