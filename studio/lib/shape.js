// A drawing of an accessory's shape on the cat, from the side and from the front, for the Items page: the
// cat's skin in grey, the game's accessory faint, and a model of the mod's own in colour, all in the game's
// space (cm, Z up, the cat facing +Y). Meshes come from the API as flat lists: {p: [x, y, z, ...], t: [a, b, c, ...]}.
import { el } from "./wc.js";

const VIEWS = [
  { title: "Side", x: p => p[1], y: p => p[2], depth: p => -p[0], light: [-1, 0.2, 0.6] },
  { title: "Front", x: p => -p[0], y: p => p[2], depth: p => p[1], light: [0.2, 1, 0.6] },
];

function point(m, i) { return [m.p[3 * i], m.p[3 * i + 1], m.p[3 * i + 2]]; }

// A mesh moved, turned and scaled as items.json's "place" says, the same way models.place does at install:
// scaled and turned about the middle of its bounds (roll, then pitch, then yaw), then moved. X is the cat's
// left, Y its front, Z up.
export function placeMesh(mesh, place) {
  if (!mesh || !place) return mesh;
  const s = place.scale, deg = Math.PI / 180;
  const k = typeof s === "object" && s ? [s.left ?? 1, s.forward ?? 1, s.up ?? 1] : [s ?? 1, s ?? 1, s ?? 1];
  const [roll, pitch, yaw] = ["roll", "pitch", "yaw"].map(n => (place[n] || 0) * deg);
  const move = [place.left || 0, place.forward || 0, place.up || 0];
  const [lo, hi] = bounds([mesh]);
  const c = [0, 1, 2].map(i => (lo[i] + hi[i]) / 2);
  const p = new Array(mesh.p.length);
  for (let i = 0; i < mesh.p.length; i += 3) {
    let x = (mesh.p[i] - c[0]) * k[0], y = (mesh.p[i + 1] - c[1]) * k[1], z = (mesh.p[i + 2] - c[2]) * k[2];
    [x, z] = [x * Math.cos(roll) + z * Math.sin(roll), -x * Math.sin(roll) + z * Math.cos(roll)];
    [y, z] = [y * Math.cos(pitch) - z * Math.sin(pitch), y * Math.sin(pitch) + z * Math.cos(pitch)];
    [x, y] = [x * Math.cos(yaw) + y * Math.sin(yaw), -x * Math.sin(yaw) + y * Math.cos(yaw)];
    p[i] = x + c[0] + move[0]; p[i + 1] = y + c[1] + move[1]; p[i + 2] = z + c[2] + move[2];
  }
  return { p, t: mesh.t };
}

function rgbOf(hex) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || "");
  return m ? [1, 2, 3].map(i => parseInt(m[i], 16)) : null;
}

function bounds(meshes) {
  const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
  for (const m of meshes) for (let i = 0; i < m.p.length; i += 3) for (let k = 0; k < 3; k++) {
    lo[k] = Math.min(lo[k], m.p[i + k]); hi[k] = Math.max(hi[k], m.p[i + k]);
  }
  return [lo, hi];
}

function unit(v) { const n = Math.hypot(v[0], v[1], v[2]) || 1; return [v[0] / n, v[1] / n, v[2] / n]; }

// Every triangle of the meshes, as [depth, screen points, colour] in the order to paint them.
function triangles(view, layers, toScreen) {
  const out = [];
  const light = unit(view.light);
  for (const { mesh, rgb, alpha } of layers) {
    for (let k = 0; k < mesh.t.length; k += 3) {
      const a = point(mesh, mesh.t[k]), b = point(mesh, mesh.t[k + 1]), c = point(mesh, mesh.t[k + 2]);
      const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      // The game's triangles turn clockwise, so the face's outside is v x u.
      const n = unit([v[1] * u[2] - v[2] * u[1], v[2] * u[0] - v[0] * u[2], v[0] * u[1] - v[1] * u[0]]);
      const lit = 0.45 + 0.55 * Math.abs(n[0] * light[0] + n[1] * light[1] + n[2] * light[2]);
      const shade = rgb.map(x => Math.round(x * lit));
      out.push([(view.depth(a) + view.depth(b) + view.depth(c)) / 3, [toScreen(a), toScreen(b), toScreen(c)],
        `rgba(${shade[0]},${shade[1]},${shade[2]},${alpha})`]);
    }
  }
  return out.sort((p, q) => p[0] - q[0]);
}

// draw({cat, accessory, model, glass, opacity}): a model (or the accessory placed elsewhere) replaces the
// accessory, which then shows as an outline; below opacity 1 it's drawn as see-through glass of that colour.
export function shapeDrawing() {
  const canvases = VIEWS.map(v => el("canvas", { width: "300", height: "250", "aria-label": `${v.title} view`,
    style: { width: "100%", maxWidth: "300px", borderRadius: "10px", background: "var(--stage)" } }));
  const element = el("div", { style: { display: "grid", gap: "10px", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" } },
    ...VIEWS.map((v, i) => el("figure", { style: { margin: "0" } }, canvases[i],
      el("figcaption", { class: "muted", style: { fontSize: "0.85rem" }, text: v.title }))));
  function draw({ cat, accessory, model, glass, opacity = 1 }) {
    const worn = opacity < 1 ? { rgb: rgbOf(glass) || [235, 245, 255], alpha: Math.max(0.2, opacity) } : null;
    const focus = [model, accessory].filter(Boolean);
    const [lo, hi] = bounds(focus.length ? focus : [cat]);
    VIEWS.forEach((view, i) => {
      const canvas = canvases[i];
      const g = canvas.getContext("2d");
      g.clearRect(0, 0, canvas.width, canvas.height);
      // Around what's being worn, with room to see where on the cat it sits.
      const corners = [];
      for (const x of [lo[0], hi[0]]) for (const y of [lo[1], hi[1]]) for (const z of [lo[2], hi[2]]) corners.push([x, y, z]);
      const xs = corners.map(view.x), ys = corners.map(view.y);
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
      const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 4) * 2.2;
      const scale = Math.min(canvas.width, canvas.height) / span;
      const toScreen = p => [canvas.width / 2 + (view.x(p) - cx) * scale, canvas.height / 2 - (view.y(p) - cy) * scale];
      const layers = [{ mesh: cat, rgb: [205, 198, 190], alpha: 1 }];
      if (model) layers.push({ mesh: model, rgb: worn ? worn.rgb : [236, 150, 70], alpha: worn ? worn.alpha : 1 });
      else if (accessory) layers.push({ mesh: accessory, rgb: worn ? worn.rgb : [120, 170, 235], alpha: worn ? worn.alpha : 1 });
      for (const [, pts, fill] of triangles(view, layers, toScreen)) {
        g.beginPath();
        g.moveTo(pts[0][0], pts[0][1]); g.lineTo(pts[1][0], pts[1][1]); g.lineTo(pts[2][0], pts[2][1]);
        g.closePath();
        g.fillStyle = fill;
        g.strokeStyle = fill;
        g.lineWidth = 0.5;
        g.fill();
        g.stroke();
      }
      if (model && accessory) {             // where the game's own one sits, as an outline
        g.strokeStyle = "rgba(90,150,235,0.35)";
        g.lineWidth = 0.6;
        for (let k = 0; k < accessory.t.length; k += 3) {
          const a = toScreen(point(accessory, accessory.t[k])), b = toScreen(point(accessory, accessory.t[k + 1])),
            c = toScreen(point(accessory, accessory.t[k + 2]));
          g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.lineTo(c[0], c[1]); g.closePath(); g.stroke();
        }
      }
    });
  }
  return { element, draw };
}

// A picture file from the computer as a PNG the API takes: PNGs as they are, other pictures the browser can
// open (JPEG, WebP, GIF, BMP) drawn onto a canvas and saved as PNG, no bigger than `max` pixels each way.
export async function asPng(file, max = 4096) {
  if (file.type === "image/png") return file;
  let bmp;
  try { bmp = await createImageBitmap(file); }
  catch (e) { throw new Error(`${file.name} isn't a picture this browser can open (PNG, JPEG, WebP, GIF or BMP)`); }
  const k = Math.min(1, max / Math.max(bmp.width, bmp.height));
  const canvas = el("canvas", { width: String(Math.round(bmp.width * k)), height: String(Math.round(bmp.height * k)) });
  canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
  return await new Promise((ok, bad) => canvas.toBlob(b => b ? ok(b) : bad(new Error("couldn't make a PNG of it")), "image/png"));
}
