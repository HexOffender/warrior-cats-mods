// The cat drawing the Palettes and Your cat pages share: a cat's face with a coat, pattern and marking colour,
// eye strips from the game's eye atlas, nose, ear and whisker colours, and its head scars. It's a sketch: the
// game's real pattern shapes, the body, the paws and the back and chest scars aren't in it, and each page's caption
// says so. (studio/lib/shape.js is something else: the Items page's model view.)
//
//   stage.innerHTML = catSvg("pal");            // ids inside it start with the prefix: two drawings on one page
//   paintCat(stage.querySelector("svg"), { coat: "#9A8F84", pattern, marking, eyeWhite, rightEye: ramp, leftEye: ramp,
//     nose, ears, whiskers, scars: { ear: 4, eye: 1 } });
//
// A ramp is an eye row as linear [r, g, b] per pixel, pupil to rim (lib/palette.js's eyeRamp makes one). Right and
// left are the cat's own, as in the save (EyeRightColorIdx): its right eye is on the drawing's left. Leave a colour
// out for the drawing's own; scars count as catcolours.SCAR_TYPES does (ear 1 torn, right; eye 1, right).
import { color } from "./colour.js";

export function catSvg(prefix = "cat", label = "Preview cat with the chosen colours") {
  const id = name => `${prefix}-${name}`;
  return `
<svg viewBox="0 0 360 330" role="img" aria-label="${label}">
  <defs>
    <radialGradient id="${id("irisL")}" cx="50%" cy="50%" r="50%"></radialGradient>
    <radialGradient id="${id("irisR")}" cx="50%" cy="50%" r="50%"></radialGradient>
    <clipPath id="${id("almondL")}"><path d="M88 184 Q124 146 162 180 Q124 214 88 184 Z"/></clipPath>
    <clipPath id="${id("almondR")}"><path d="M272 184 Q236 146 198 180 Q236 214 272 184 Z"/></clipPath>
    <clipPath id="${id("headClip")}"><path d="M180 80 C252 80 318 120 322 196 C326 262 262 306 180 306 C98 306 34 262 38 196 C42 120 108 80 180 80 Z"/></clipPath>
    <mask id="${id("earCuts")}" maskUnits="userSpaceOnUse" x="0" y="0" width="360" height="330">
      <rect x="0" y="0" width="360" height="330" fill="white"/><g data-part="ear-scars"></g>
    </mask>
  </defs>
  <g data-part="outline" stroke-width="3" stroke-linejoin="round" mask="url(#${id("earCuts")})">
    <path data-part="coat" d="M70 152 L90 36 Q96 26 106 33 L172 100 Z"/>
    <path data-part="coat" d="M290 152 L270 36 Q264 26 254 33 L188 100 Z"/>
    <path data-part="coat" d="M180 80 C252 80 318 120 322 196 C326 262 262 306 180 306 C98 306 34 262 38 196 C42 120 108 80 180 80 Z"/>
  </g>
  <g mask="url(#${id("earCuts")})">
    <path data-part="ear" d="M92 128 L103 58 L150 106 Z" opacity="0.85"/>
    <path data-part="ear" d="M268 128 L257 58 L210 106 Z" opacity="0.85"/>
  </g>
  <g clip-path="url(#${id("headClip")})">
    <g data-part="pattern" fill="none" stroke-width="9" stroke-linecap="round">
      <path d="M180 92 L180 134"/><path d="M158 98 Q163 118 168 136"/><path d="M202 98 Q197 118 192 136"/>
      <path d="M136 108 Q147 124 154 142"/><path d="M224 108 Q213 124 206 142"/>
      <path d="M36 190 Q72 184 102 196"/><path d="M38 216 Q74 208 104 220"/><path d="M46 244 Q78 236 108 244"/>
      <path d="M324 190 Q288 184 258 196"/><path d="M322 216 Q286 208 256 220"/><path d="M314 244 Q282 236 252 244"/>
    </g>
    <g data-part="marking">
      <path d="M180 144 C170 172 166 198 168 218 L192 218 C194 198 190 172 180 144 Z"/>
      <ellipse cx="180" cy="258" rx="66" ry="50"/><ellipse cx="180" cy="318" rx="90" ry="40"/>
    </g>
  </g>
  <g data-part="eye" data-side="right">
    <g data-part="open">
      <path data-part="sclera" d="M88 184 Q124 146 162 180 Q124 214 88 184 Z"/>
      <circle clip-path="url(#${id("almondL")})" cx="125" cy="181" r="27" fill="url(#${id("irisL")})"/>
      <ellipse cx="125" cy="181" rx="5.5" ry="18" fill="#0b0b0c"/><circle cx="133" cy="171" r="4" fill="#ffffff" opacity="0.85"/>
      <path data-part="lid" d="M88 184 Q124 146 162 180 Q124 214 88 184 Z" fill="none" stroke-width="3"/>
    </g>
    <path data-part="shut" d="M88 182 Q124 200 162 180" fill="none" stroke-width="4" stroke-linecap="round" display="none"/>
  </g>
  <g data-part="eye" data-side="left">
    <g data-part="open">
      <path data-part="sclera" d="M272 184 Q236 146 198 180 Q236 214 272 184 Z"/>
      <circle clip-path="url(#${id("almondR")})" cx="235" cy="181" r="27" fill="url(#${id("irisR")})"/>
      <ellipse cx="235" cy="181" rx="5.5" ry="18" fill="#0b0b0c"/><circle cx="243" cy="171" r="4" fill="#ffffff" opacity="0.85"/>
      <path data-part="lid" d="M272 184 Q236 146 198 180 Q236 214 272 184 Z" fill="none" stroke-width="3"/>
    </g>
    <path data-part="shut" d="M272 182 Q236 200 198 180" fill="none" stroke-width="4" stroke-linecap="round" display="none"/>
  </g>
  <path data-part="nose" d="M168 236 L192 236 Q195 238 190 245 L183 252 Q180 255 177 252 L170 245 Q165 238 168 236 Z"/>
  <path data-part="mouth" d="M180 254 L180 262 M180 262 Q170 272 160 266 M180 262 Q190 272 200 266" fill="none" stroke-width="2.5" stroke-linecap="round"/>
  <g data-part="whiskers" stroke-width="1.6" stroke-linecap="round" opacity="0.75">
    <path d="M148 252 L62 238 M148 259 L58 262 M150 266 L66 286"/><path d="M212 252 L298 238 M212 259 L302 262 M210 266 L294 286"/>
  </g>
</svg>`;
}

// The ear scars, by the cat's own side (its right is the drawing's left): a torn ear loses its tip, a notched one
// has a bite out of its outer edge. They're cut out of the ears (a mask), so the clearing shows through.
const EAR_CUTS = {
  right: { torn: "M80 20 L118 20 L110 50 L100 44 L96 62 L86 54 Z", notch: "M64 82 L99 96 L68 122 Z" },
  left: { torn: "M280 20 L242 20 L250 50 L260 44 L264 62 L274 54 Z", notch: "M296 82 L261 96 L292 122 Z" },
};
// catcolours.SCAR_TYPES: ear 1-6 torn right, left, both, notched right, left, both; an eye scar shuts the eye,
// odd numbers the cat's right, even its left.
export function scarShapes(scars = {}) {
  const ear = scars.ear || 0, eye = scars.eye || 0;
  const kind = ear >= 1 && ear <= 3 ? "torn" : ear >= 4 && ear <= 6 ? "notch" : null;
  const side = (ear - 1) % 3;   // 0 right, 1 left, 2 both
  return {
    ears: kind ? (side === 2 ? ["right", "left"] : [side === 0 ? "right" : "left"]).map(s => ({ side: s, kind, d: EAR_CUTS[s][kind] })) : [],
    shut: eye > 0 ? (eye % 2 === 1 ? "right" : "left") : null,
  };
}

function setIris(svg, gradient, ramp) {
  const g = svg.querySelector(`[id$="-${gradient}"]`);
  if (!g) return;
  g.textContent = "";
  for (let k = 0; k <= 8; k++) {
    const st = document.createElementNS("http://www.w3.org/2000/svg", "stop");
    st.setAttribute("offset", `${18 + k * 10.25}%`);
    st.setAttribute("stop-color", color.linearToHex(ramp[Math.round(k * (ramp.length - 1) / 8)]));
    g.append(st);
  }
}

export function paintCat(svg, { coat = "#9A8F84", pattern, marking, eyeWhite = "#E8E4DA", rightEye, leftEye, nose, ears, whiskers, scars } = {}) {
  const outline = color.shade(coat, 0.55);
  svg.querySelectorAll('[data-part="coat"]').forEach(n => { n.setAttribute("fill", coat); n.setAttribute("stroke", outline); });
  svg.querySelector('[data-part="pattern"]').setAttribute("stroke", pattern || coat);
  svg.querySelector('[data-part="marking"]').setAttribute("fill", marking || coat);
  svg.querySelectorAll('[data-part="sclera"]').forEach(n => n.setAttribute("fill", eyeWhite));
  svg.querySelectorAll('[data-part="lid"], [data-part="mouth"], [data-part="shut"]').forEach(n => n.setAttribute("stroke", outline));
  // Whiskers in a light tone of the coat (the game takes them from the coat too), unless a colour is given.
  svg.querySelector('[data-part="whiskers"]').setAttribute("stroke", whiskers || color.shade(coat, 1.6));
  svg.querySelector('[data-part="nose"]').setAttribute("fill", nose || "var(--nose)");
  svg.querySelectorAll('[data-part="ear"]').forEach(n => n.setAttribute("fill", ears || "var(--ear)"));
  if (rightEye) setIris(svg, "irisL", rightEye);   // the gradients are named by the drawing's side
  if (leftEye) setIris(svg, "irisR", leftEye);
  const drawn = scarShapes(scars);
  const cuts = svg.querySelector('[data-part="ear-scars"]');
  cuts.textContent = "";
  for (const cut of drawn.ears) {
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", cut.d);
    p.setAttribute("fill", "black");
    p.setAttribute("data-scar", `${cut.kind}-${cut.side}`);
    cuts.append(p);
  }
  svg.querySelectorAll('[data-part="eye"]').forEach(eye => {
    const shut = drawn.shut === eye.getAttribute("data-side");
    eye.querySelector('[data-part="open"]').setAttribute("display", shut ? "none" : "inline");
    eye.querySelector('[data-part="shut"]').setAttribute("display", shut ? "inline" : "none");
  });
}
