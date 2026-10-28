// The game's names for keys, mouse buttons and controller buttons (Unreal's FKey names: "SpaceBar", "F7",
// "Gamepad_DPad_Up"), from a browser's key events, and the labels the studio shows for them. Pure: nothing here
// touches the page, so node:test imports it without a DOM. wc.js re-exports it as `input`, and its captureKey
// (the dialog that asks for a key) is built on it.
const CODE_TO_KEY = {
  Space: "SpaceBar", Enter: "Enter", NumpadEnter: "Enter", Escape: "Escape", Tab: "Tab", Backspace: "BackSpace",
  CapsLock: "CapsLock", ShiftLeft: "LeftShift", ShiftRight: "RightShift", ControlLeft: "LeftControl",
  ControlRight: "RightControl", AltLeft: "LeftAlt", AltRight: "RightAlt", ArrowUp: "Up", ArrowDown: "Down",
  ArrowLeft: "Left", ArrowRight: "Right", Insert: "Insert", Delete: "Delete", Home: "Home", End: "End",
  PageUp: "PageUp", PageDown: "PageDown", Backquote: "Tilde", Minus: "Hyphen", Equal: "Equals",
  BracketLeft: "LeftBracket", BracketRight: "RightBracket", Backslash: "Backslash", Semicolon: "Semicolon",
  Quote: "Apostrophe", Comma: "Comma", Period: "Period", Slash: "Slash", NumpadMultiply: "Multiply",
  NumpadAdd: "Add", NumpadSubtract: "Subtract", NumpadDecimal: "Decimal", NumpadDivide: "Divide",
};
const DIGITS = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"];
// The game's name for the key a keydown event is about, or null for one the game doesn't know.
export function keyFromEvent(e) {
  const c = e.code;
  if (/^Key[A-Z]$/.test(c)) return c.slice(3);
  if (/^Digit\d$/.test(c)) return DIGITS[+c.slice(5)];
  if (/^Numpad\d$/.test(c)) return "NumPad" + DIGITS[+c.slice(6)];
  if (/^F([1-9]|1[0-2])$/.test(c)) return c;   // F13 and above: the game has no key for them
  return CODE_TO_KEY[c] || null;
}
export const MOUSE = ["LeftMouseButton", "MiddleMouseButton", "RightMouseButton", "ThumbMouseButton", "ThumbMouseButton2"];
// Standard Gamepad API layout -> Unreal names.
export const PAD_BUTTONS = ["Gamepad_FaceButton_Bottom", "Gamepad_FaceButton_Right", "Gamepad_FaceButton_Left",
  "Gamepad_FaceButton_Top", "Gamepad_LeftShoulder", "Gamepad_RightShoulder", "Gamepad_LeftTrigger",
  "Gamepad_RightTrigger", "Gamepad_Special_Left", "Gamepad_Special_Right", "Gamepad_LeftThumbstick",
  "Gamepad_RightThumbstick", "Gamepad_DPad_Up", "Gamepad_DPad_Down", "Gamepad_DPad_Left", "Gamepad_DPad_Right"];
export const PAD_AXES = ["Gamepad_LeftX", "Gamepad_LeftY", "Gamepad_RightX", "Gamepad_RightY"];
export const GLYPHS = {
  xbox: { Bottom: "A", Right: "B", Left: "X", Top: "Y", LeftShoulder: "LB", RightShoulder: "RB", LeftTrigger: "LT",
    RightTrigger: "RT", Special_Left: "View", Special_Right: "Menu", LeftThumbstick: "LS click", RightThumbstick: "RS click" },
  playstation: { Bottom: "✕", Right: "○", Left: "□", Top: "△", LeftShoulder: "L1", RightShoulder: "R1", LeftTrigger: "L2",
    RightTrigger: "R2", Special_Left: "Create", Special_Right: "Options", LeftThumbstick: "L3", RightThumbstick: "R3" },
  switch: { Bottom: "B", Right: "A", Left: "Y", Top: "X", LeftShoulder: "L", RightShoulder: "R", LeftTrigger: "ZL",
    RightTrigger: "ZR", Special_Left: "−", Special_Right: "+", LeftThumbstick: "L-stick click", RightThumbstick: "R-stick click" },
};
const KEY_LABELS = {
  SpaceBar: "Space", LeftShift: "Left Shift", RightShift: "Right Shift", LeftControl: "Left Ctrl", RightControl: "Right Ctrl",
  LeftAlt: "Left Alt", RightAlt: "Right Alt", Up: "↑", Down: "↓", Left: "←", Right: "→", BackSpace: "Backspace",
  LeftMouseButton: "Left mouse", RightMouseButton: "Right mouse", MiddleMouseButton: "Middle mouse",
  ThumbMouseButton: "Mouse 4", ThumbMouseButton2: "Mouse 5", MouseScrollUp: "Wheel up", MouseScrollDown: "Wheel down",
  Tilde: "`", Hyphen: "-", Equals: "=", LeftBracket: "[", RightBracket: "]", Semicolon: ";", Apostrophe: "'",
  Comma: ",", Period: ".", Slash: "/", Backslash: "\\",
  Gamepad_LeftX: "Left stick ↔", Gamepad_LeftY: "Left stick ↕", Gamepad_RightX: "Right stick ↔", Gamepad_RightY: "Right stick ↕",
  Gamepad_DPad_Up: "D-pad ↑", Gamepad_DPad_Down: "D-pad ↓", Gamepad_DPad_Left: "D-pad ←", Gamepad_DPad_Right: "D-pad →",
};
// What the studio calls a key: "Space", "Num 5", a controller button by the glyph on `style`'s pad.
export function keyLabel(key, style = "xbox") {
  if (!key) return "—";
  const m = /^Gamepad_(?:FaceButton_)?(.+)$/.exec(key);
  if (m && GLYPHS[style][m[1]]) return GLYPHS[style][m[1]];
  if (KEY_LABELS[key]) return KEY_LABELS[key];
  if (key.startsWith("NumPad")) return "Num " + DIGITS.indexOf(key.slice(6));
  const d = DIGITS.indexOf(key);
  return d >= 0 ? String(d) : key;
}
// What a key pressed in the key dialog (wc.captureKey) does. Escape cancels; Tab moves among the dialog's
// buttons (back with Shift); Enter and Space press the button that has focus (and are the key to bind when the
// dialog itself has focus); any other key is the key to bind, named as the game names it (keyFromEvent), or
// unknown. {do: "cancel" | "move" (back) | "press" | "bind" (key) | "unknown"}.
export function dialogKey(e, onButton, fromEvent = keyFromEvent) {
  if (e.code === "Escape" || e.key === "Escape") return { do: "cancel" };
  if (e.key === "Tab" || e.code === "Tab") return { do: "move", back: !!e.shiftKey };
  if (onButton && ["Enter", "NumpadEnter", "Space"].includes(e.code)) return { do: "press" };
  const key = fromEvent(e);
  return key ? { do: "bind", key } : { do: "unknown" };
}

export const input = { keyFromEvent, MOUSE, PAD_BUTTONS, PAD_AXES, GLYPHS, keyLabel, dialogKey };
