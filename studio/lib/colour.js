// Colours for Clan Mod Studio's pages: sRGB hex in files, linear floats in the engine. wc.js hands this to pages
// as wc.color; it touches no page, so node:test imports it on its own (and lib/palette.js, the Palettes page's file
// logic, builds on it).
//   normHex   the pickers' check: 3 or 6 hex digits, with or without #, as "#RRGGBB" (else null)
//   parse     a colour every way a mod's file may write it, as wcmods/colors.py reads them (else null)
//   the rest  conversions (sRGB, linear light, HSL), luminance, shade, and the Palettes page's moods

const hexRe = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i;
function normHex(h) {
  const m = hexRe.exec(String(h).trim());
  if (!m) return null;
  let s = m[1];
  if (s.length === 3) s = s.split("").map(c => c + c).join("");
  return "#" + s.toUpperCase();
}
// The colour names a file may use: wcmods/colors.py's NAMED (tests/studio/colour.test.mjs keeps the two the same).
const NAMED = {
  black: "000000", white: "ffffff", red: "ff0000", green: "00ff00", blue: "0000ff", gold: "ffd700", silver: "c0c0c0",
  pink: "ff69b4", purple: "8a2be2", teal: "008080", orange: "ff8c00", cyan: "00ffff", magenta: "ff00ff", lime: "32cd32",
  navy: "000080",
};
// A colour as wcmods/colors.py's parse takes it: "#RGB", "#RRGGBB" or "#RRGGBBAA" (the alpha dropped), with or
// without the #, a name from NAMED, or [r, g, b] from 0 to 255 (clamped; a fourth value is ignored). "#RRGGBB",
// or null for anything else.
function parse(value) {
  if (Array.isArray(value)) {
    if (value.length !== 3 && value.length !== 4) return null;
    const num = v => (typeof v === "number" || typeof v === "boolean" ? Number(v)
      : typeof v === "string" && v.trim() !== "" ? Number(v) : NaN);
    const rgb = value.slice(0, 3).map(num);
    if (rgb.some(v => !Number.isFinite(v))) return null;
    return rgbToHex(rgb.map(v => Math.max(0, Math.min(255, v)) / 255));
  }
  if (value == null || typeof value === "object") return null;
  let s = String(value).trim().toLowerCase();
  s = (NAMED[s] || s).replace(/^#+/, "");
  if (/^[0-9a-f]{3}$/.test(s)) s = s.split("").map(c => c + c).join("");
  if (!/^[0-9a-f]{6}([0-9a-f]{2})?$/.test(s)) return null;
  return "#" + s.slice(0, 6).toUpperCase();
}
const hexToRgb = h => { const s = normHex(h).slice(1); return [0, 2, 4].map(i => parseInt(s.slice(i, i + 2), 16) / 255); };
const rgbToHex = c => "#" + c.map(v => Math.round(Math.max(0, Math.min(1, v)) * 255).toString(16).padStart(2, "0")).join("").toUpperCase();
const s2l = c => c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
const l2s = c => { c = Math.max(0, Math.min(1, c)); return c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055; };
const luminance = p => 0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2];
function rgbToHsl([r, g, b]) {
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
  if (mx === mn) return [0, 0, l];
  const d = mx - mn, s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
  const h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [h * 60, s, l];
}
function hslToRgb([h, s, l]) {
  h = ((h % 360) + 360) % 360 / 360;
  if (s === 0) return [l, l, l];
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
  const f = t => { t = (t + 1) % 1; return t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p; };
  return [f(h + 1 / 3), f(h), f(h - 1 / 3)];
}
const clamp01 = v => Math.max(0, Math.min(1, v));
const toward = (h, t, a) => h + (((t - h + 540) % 360) - 180) * a;
const MOODS = {
  vivid: { name: "Vivid", fn: ([h, s, l]) => [h, clamp01(s * 1.35 + 0.06), l] },
  pastel: { name: "Pastel", fn: ([h, s, l]) => [h, s * 0.55, l + (1 - l) * 0.45] },
  moonlit: { name: "Moonlit", fn: ([h, s, l]) => [toward(h, 212, 0.4), s * 0.7, clamp01(l * 0.9 + 0.08)] },
  ember: { name: "Ember", fn: ([h, s, l]) => [toward(h, 20, 0.45), clamp01(s * 1.2 + 0.05), l * 0.92] },
};
export const color = {
  normHex, parse, NAMED, hexToRgb, rgbToHex, srgbToLinear: s2l, linearToSrgb: l2s, luminance, rgbToHsl, hslToRgb, MOODS,
  hexToLinear: h => hexToRgb(h).map(s2l),
  linearToHex: p => rgbToHex(p.map(l2s)),
  shade: (hex, amt) => { const [h, s, l] = rgbToHsl(hexToRgb(hex)); return rgbToHex(hslToRgb([h, s, clamp01(l * amt)])); },
  mood: (hex, name) => rgbToHex(hslToRgb(MOODS[name].fn(rgbToHsl(hexToRgb(hex))))),
};
