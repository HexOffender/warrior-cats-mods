// The Controls page's model: controls.json as the page holds it, and what each row shows and writes. Pure
// functions over the game's keys as GET /game/keys gives them (wcmods/keymap.py game_keys: keyboard, gamepad,
// aliases, names), importing nothing, so node:test loads it with no page (tests/studio/controls.test.mjs).
//
// The page's state is the file's shape, flattened: { keyboard: {action: key}, gamepad: {action: key},
// keys: {key you press: game key}, menus: {key you press: game key}, notes: {"_help": ...} }. What a row shows
// is read from it; what a row does is written into it. Putting a row back on the game's key deletes its entry
// (so a fresh "Back to the game's keys" writes {}), except when a lower-priority mod sets that entry: then the
// game's key is written, so this mod's "back" wins in the game. Entries a file already has are kept as they
// are until their row is changed, even when they're the game's own key.

// Keys while you play, top to bottom; their labels are the game's names (game.names).
export const PLAY_ROWS = ["Player_Pounce", "Player_Interact", "Player_Run", "Player_Crouch", "Player_Scent_Tracking",
  "Player_Drop", "Player_Friend_Talk", "Player_Den_Place", "Player_ReturnToCamp", "Player_Camera_Reset", "Player_Pause",
  "Player_Show_Inventory", "Player_Show_Quest", "Player_Show_Map", "Player_Growl"];
// Moving and the camera: two keys a row, each its own job, either an axis action (its key is a "keyboard"
// entry) or a key the game has built in (a "keys" pair standing for it). stick: the controller's, which no mod
// can move.
export const MOVE_ROWS = [
  { name: "Move forward / back", keys: [{ raw: "W" }, { action: "Player_Movement_Up" }], stick: "Player_Movement_Up" },
  { name: "Move left / right", keys: [{ action: "Player_Movement_Right" }, { raw: "D" }], stick: "Player_Movement_Right" },
  { name: "Camera up / down", keys: [{ raw: "Up" }, { action: "Player_Camera_Up" }], stick: "Player_Camera_Up" },
  { name: "Camera left / right", keys: [{ action: "Player_Camera_Right" }, { raw: "Right" }], stick: "Player_Camera_Right" },
];
// In menus: the game's key for each, which keeps working; a second key is a "menus" pair standing for it.
export const MENU_ROWS = [{ key: "Enter", command: "Button_Confirm" }, { key: "BackSpace", command: "Button_Back" },
  { key: "One", command: "Button_ShoulderL" }, { key: "Two", command: "Button_ShoulderR" }];
// The mouse's buttons and wheel: keys for an action, never in menus (a click there goes to the button under it).
export const MOUSE_KEYS = ["LeftMouseButton", "RightMouseButton", "MiddleMouseButton", "ThumbMouseButton",
  "ThumbMouseButton2", "MouseScrollUp", "MouseScrollDown"];
// Bindable, but not yet seen working in the game (docs/verified.md).
export const UNTRIED = ["ThumbMouseButton", "ThumbMouseButton2", "MouseScrollUp", "MouseScrollDown"];

const isObj = v => v && typeof v === "object" && !Array.isArray(v);
// A key name as the build reads it: trimmed, one letter in capitals; a controller's short name in full.
export function norm(key, dev = "keyboard", game = null) {
  let k = String(key).trim();
  if (dev === "gamepad" && game) k = game.aliases[k.toLowerCase()] || k;
  return k.length === 1 && /[a-z]/i.test(k) ? k.toUpperCase() : k;
}
const asKey = v => {
  const k = isObj(v) ? v.key : v;
  return typeof k === "string" && k.trim() ? k : null;
};

// A file (or nothing) as the page's state. A null or a list where a key should be is dropped (the build
// refuses it, and saving writes the file without it); {"key": "F"} from older pages is read as "F".
export function normalize(obj, game) {
  const s = { keyboard: {}, gamepad: {}, keys: {}, menus: {}, notes: {} };
  if (!isObj(obj)) return s;
  for (const [k, v] of Object.entries(obj)) if (k.startsWith("_")) s.notes[k] = v;
  for (const dev of ["keyboard", "gamepad"]) {
    for (const [action, v] of Object.entries(isObj(obj[dev]) ? obj[dev] : {})) {
      const k = asKey(v);
      if (!action.startsWith("_") && k) s[dev][action] = norm(k, dev, game);
    }
  }
  const pairs = { keys: obj.keys, menus: isObj(obj.menus) ? obj.menus.keys : null };
  for (const sec of ["keys", "menus"]) {
    for (const [pressed, v] of Object.entries(isObj(pairs[sec]) ? pairs[sec] : {})) {
      const k = asKey(v);
      if (!pressed.startsWith("_") && k) s[sec][norm(pressed)] = norm(k);
    }
  }
  return s;
}

// The state as controls.json: only the sections with something in them.
export function toJson(s) {
  const o = { ...s.notes };
  for (const sec of ["keyboard", "gamepad", "keys"]) if (Object.keys(s[sec]).length) o[sec] = { ...s[sec] };
  if (Object.keys(s.menus).length) o.menus = { keys: { ...s.menus } };
  return o;
}

export const clone = s => JSON.parse(JSON.stringify(s));
export const gameKey = (game, dev, action) => game[dev][action] ?? null;
export const isAxis = (game, action) => game.axes.includes(action);
// The key a row's action is on, with this file's changes.
export const effective = (s, game, dev, action) => s[dev][action] ?? gameKey(game, dev, action);
// Whether the row shows a change: an entry that isn't the game's own key.
export const changed = (s, game, dev, action) => action in s[dev] && s[dev][action] !== gameKey(game, dev, action);
const lowerSets = (lower, sec, name) => (lower || []).some(([a, b]) => a === sec && b === name);

// Put an action on a key. The game's own key deletes the entry (or writes it, over a lower mod's). A
// controller's stick can't be set: false, and nothing changes. True when the state changed.
export function set(s, game, dev, action, key, lower = []) {
  // A stick, or an action the controller has no button for (Inventory): nothing a mod can change.
  if (dev === "gamepad" && (isAxis(game, action) || !gameKey(game, dev, action))) return false;
  const k = norm(key, dev, game);
  const before = s[dev][action];
  if (k === gameKey(game, dev, action) && !lowerSets(lower, dev, action)) delete s[dev][action];
  else s[dev][action] = k;
  return before !== s[dev][action];
}
export const undo = (s, game, dev, action, lower = []) => {
  if (dev === "gamepad" && isAxis(game, action)) return remove(s, dev, action);
  return set(s, game, dev, action, gameKey(game, dev, action), lower);
};
export function remove(s, sec, name) {
  if (!(name in s[sec])) return false;
  delete s[sec][name];
  return true;
}

// The moving keys the game has built in (W, D, Up, Right): the row shows the first pair standing for one; any
// other pair for the same key is an extra, under For mod makers.
export function rowPair(s, raw) {
  return Object.keys(s.keys).find(p => s.keys[p] === raw && p !== raw) || null;
}
export const rawKey = (s, raw) => rowPair(s, raw) || raw;
export function setRaw(s, raw, key) {
  const k = norm(key), was = rowPair(s, raw);
  if (was === k) return false;
  if (was) delete s.keys[was];
  if (k !== raw) s.keys[k] = raw;
  return true;
}

// Second keys: while you play, a "keys" pair standing for the action's game key (it does what that key does
// there, nothing in menus); in menus, a "menus" pair standing for the row's key.
// A controller button standing for a key (file-only for now) is no second key on a row: it's listed under For
// mod makers.
const padSource = p => p.startsWith("Gamepad_");
export const secondKeys = (s, sec, target) => Object.keys(s[sec]).filter(p => s[sec][p] === target && !padSource(p));
export function addSecond(s, sec, target, key) {
  const k = norm(key);
  if (k === target || s[sec][k] === target) return false;
  s[sec][k] = target;
  return true;
}

// "Back to the game's keys" for a column: every change its rows show goes. The keyboard's: the actions while
// you play and their second keys, and the moving keys; the controller's: its buttons (its sticks only change
// through their own Remove).
export function resetDevice(s, game, dev, lower = []) {
  let any = false;
  if (dev === "keyboard") {
    for (const action of [...PLAY_ROWS, ...game.axes]) if (action in s.keyboard) any = undo(s, game, "keyboard", action, lower) || any;
    for (const action of PLAY_ROWS) for (const p of secondKeys(s, "keys", gameKey(game, "keyboard", action))) any = remove(s, "keys", p) || any;
    for (const raw of game.built_in) any = setRaw(s, raw, raw) || any;
  } else {
    for (const action of PLAY_ROWS) if (!isAxis(game, action) && action in s.gamepad) any = undo(s, game, "gamepad", action, lower) || any;
  }
  return any;
}

// A controller preset: each button the map names swaps with its partner, on every row with a button.
export const SWAPS = {
  nintendo: { name: "Nintendo layout", desc: "A and B swap, X and Y swap", map: {
    Gamepad_FaceButton_Bottom: "Gamepad_FaceButton_Right", Gamepad_FaceButton_Right: "Gamepad_FaceButton_Bottom",
    Gamepad_FaceButton_Left: "Gamepad_FaceButton_Top", Gamepad_FaceButton_Top: "Gamepad_FaceButton_Left" } },
  shoulders: { name: "Swap bumpers and triggers", desc: "LB and LT swap, RB and RT swap", map: {
    Gamepad_LeftShoulder: "Gamepad_LeftTrigger", Gamepad_LeftTrigger: "Gamepad_LeftShoulder",
    Gamepad_RightShoulder: "Gamepad_RightTrigger", Gamepad_RightTrigger: "Gamepad_RightShoulder" } },
};
export function swap(s, game, map, lower = []) {
  let any = false;
  for (const action of PLAY_ROWS) {
    if (!gameKey(game, "gamepad", action) || isAxis(game, action)) continue;
    const to = map[effective(s, game, "gamepad", action)];
    if (to) any = set(s, game, "gamepad", action, to, lower) || any;
  }
  return any;
}

// What a file has that no row shows, so it's listed (with a Remove) under For mod makers and kept on save:
// [{ section, name }]. Pairs a row shows (moving keys, second keys) and entries for the rows' actions aren't.
export function unshown(s, game) {
  const out = [];
  const rowActions = new Set([...PLAY_ROWS, ...game.axes]);
  for (const action of Object.keys(s.keyboard)) if (!rowActions.has(action)) out.push({ section: "keyboard", name: action });
  for (const action of Object.keys(s.gamepad)) {
    if (!(PLAY_ROWS.includes(action) && gameKey(game, "gamepad", action)) && !isAxis(game, action)) out.push({ section: "gamepad", name: action });
  }
  const playTargets = new Set(PLAY_ROWS.map(a => gameKey(game, "keyboard", a)));
  const rowPairs = new Set(game.built_in.map(raw => rowPair(s, raw)).filter(Boolean));
  for (const p of Object.keys(s.keys)) {
    if (padSource(p) || (!rowPairs.has(p) && !playTargets.has(s.keys[p]))) out.push({ section: "keys", name: p });
  }
  const menuTargets = new Set(MENU_ROWS.map(r => r.key));
  for (const p of Object.keys(s.menus)) if (padSource(p) || !menuTargets.has(s.menus[p])) out.push({ section: "menus", name: p });
  return out;
}

// Why a key can't (or shouldn't) be chosen: { refuse } for a key wcmods listens on itself (the mod menu's key
// and button, mouse look's key) or the game's fullscreen key, and for a mouse button in menus; { warn } for a
// key a mod listens on (the Emote wheel's, an emote's), which can be switched off; null when it's free.
// inUse: /controls/check's in_use; label: the page's key names.
export function whyNot(key, inUse, where = "play", label = k => k) {
  if (where === "menus" && MOUSE_KEYS.includes(key)) {
    return { refuse: "In menus a click goes to the button under the cursor, so use a key there." };
  }
  const hits = (inUse || []).filter(e => e.key === key && e.taken);
  const refuse = hits.find(e => e.taken === "refuse");
  if (refuse) return { refuse: `${label(key)} ${refuse.does} (${refuse.from}); pick another key.` };
  const warn = hits.find(e => e.taken === "warn");
  if (warn) return { warn: `${label(key)} also ${warn.does} (${warn.from}), and will do both while that mod is on.` };
  return null;
}

// What a key pressed in the capture dialog does. Escape cancels; Tab moves among the dialog's buttons; Enter
// and Space press the button that has focus (and are the key to bind when the dialog itself has focus); any
// other key is the key to bind. keyFromEvent: wc.input's, which names the key as the game does (null: unknown).
export function captureKey(e, onButton, keyFromEvent) {
  if (e.code === "Escape" || e.key === "Escape") return { do: "cancel" };
  if (e.key === "Tab" || e.code === "Tab") return { do: "move", back: !!e.shiftKey };
  if (onButton && ["Enter", "NumpadEnter", "Space"].includes(e.code)) return { do: "press" };
  const key = keyFromEvent(e);
  return key ? { do: "bind", key } : { do: "unknown" };
}

// What /controls/check said about one entry of the file: { key, status, line, notes }, or null.
export const checkRow = (check, section, name) => (check && check.rows && check.rows[section] && check.rows[section][name]) || null;
