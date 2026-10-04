// Rend un squelette Spine 4.1 : chaque animation en WebP animé transparent (qualité 95), plus une
// image fixe (_image_fixe.png = idle immobile, haute résolution).
// Usage : node render.mjs <dossier_squelette> <dossier_sortie> [--max 1024] [--fps 20] [--only anim1,anim2]
//         [--base idle|none] [--nostill]
// Diagnostic : [--preview] [--previewonly] [--sheet] [--frame x0,y0,x1,y1] [--slots regex] [--nolayers] [--printframe]
import fs from "node:fs";
import path from "node:path";
import { createCanvas, loadImage } from "@napi-rs/canvas";
import os from "node:os";
import { spawnSync } from "node:child_process";

const FFMPEG = "C:/Users/Nauno/.bns_tools/venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe";
const SS = 2; // facteur de sur-échantillonnage
import * as spine from "@esotericsoftware/spine-core";

const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : def; };
const SRC = args[0], OUT = args[1];
const MAX = +opt("--max", 1024), STILLMAX = +opt("--stillmax", 2048), FPS = +opt("--fps", 20), MAXDUR = +opt("--maxdur", 12);
const ONLY_SLOTS = opt("--slots") ? new RegExp(opt("--slots")) : null; // diagnostic : ne dessiner que ces slots
const BG = opt("--bg", "#1c1c22"); // fond par défaut de render() (les sorties sont transparentes)
const ONLY =opt("--only", "") ? opt("--only").split(",") : null;

class CanvasTexture extends spine.Texture {
  setFilters() {} setWraps() {} dispose() {}
}

const files = fs.readdirSync(SRC);
const atlasFile = files.find(f => f.endsWith(".atlas"));
const skelFile = files.find(f => f.endsWith(".skel")) || files.find(f => f.endsWith(".json"));
const atlas = new spine.TextureAtlas(fs.readFileSync(path.join(SRC, atlasFile), "utf8"));
for (const page of atlas.pages) page.setTexture(new CanvasTexture(await loadImage(path.join(SRC, page.name))));
// Correctif d'un bug de spine-core 4.1 (JS) : pour les régions « rotate:270 », u2/v2 sont calculés
// sans inverser largeur/hauteur (seul le cas 90° l'est). La pièce affiche alors une mauvaise zone de
// texture (= pièces au mauvais endroit). Le runtime Unity du jeu gère correctement ce cas.
for (const r of atlas.regions) if (r.degrees === 270) {
  r.u2 = (r.x + r.height) / r.page.width;
  r.v2 = (r.y + r.width) / r.page.height;
}
const loader = new spine.AtlasAttachmentLoader(atlas);
let data;
if (skelFile.endsWith(".skel")) data = new spine.SkeletonBinary(loader).readSkeletonData(new Uint8Array(fs.readFileSync(path.join(SRC, skelFile))));
else data = new spine.SkeletonJson(loader).readSkeletonData(fs.readFileSync(path.join(SRC, skelFile), "utf8"));

const skeleton = new spine.Skeleton(data);
// skin : défaut + première variante de chaque groupe ("Core/green_1" -> groupe "Core").
// Les skins sans groupe ne servent que si la skin par défaut est vide.
const hasAtt = s => s && s.attachments.some(a => a && Object.keys(a).length);
const groups = new Map();
for (const s of data.skins) {
  if (s === data.defaultSkin) continue;
  const g = s.name.includes("/") ? s.name.split("/")[0] : "";
  if (!groups.has(g)) groups.set(g, s);
}
const combo = new spine.Skin("combo");
if (data.defaultSkin) combo.addSkin(data.defaultSkin);
for (const [g, s] of groups) if (g || !hasAtt(data.defaultSkin)) combo.addSkin(s);
skeleton.setSkin(combo);
skeleton.setToSetupPose();
const state = new spine.AnimationState(new spine.AnimationStateData(data));
const clipper = new spine.SkeletonClipping();

const BLEND = { 0: "source-over", 1: "lighter", 2: "multiply", 3: "screen" };
const QUAD = [0, 1, 2, 2, 3, 0];
const tmp = new Float32Array(4096 * 2);

// Sous-image d'une région de l'atlas, teintée si besoin (couleur RGB du slot, comme dans le jeu).
// Cache par région + couleur quantifiée.
// La zone lue est celle que couvrent réellement les UV de la pièce (comme le GPU du jeu), et non
// le rectangle déclaré dans l'atlas : certains maillages lisent un peu au-delà, et les couper
// faisait disparaître des morceaux (ex. mollet de Joan).
const tintCache = new Map(), uvBoxCache = new WeakMap();
function uvBox(att, page) {
  let box = uvBoxCache.get(att);
  if (!box) {
    const uvs = att.uvs, PW = page.width, PH = page.height;
    let u0 = Infinity, v0 = Infinity, u1 = -Infinity, v1 = -Infinity;
    for (let k = 0; k < uvs.length; k += 2) {
      u0 = Math.min(u0, uvs[k]); u1 = Math.max(u1, uvs[k]); v0 = Math.min(v0, uvs[k + 1]); v1 = Math.max(v1, uvs[k + 1]);
    }
    const sx = Math.max(0, Math.floor(u0 * PW) - 1), sy = Math.max(0, Math.floor(v0 * PH) - 1);
    box = { sx, sy, sw: Math.max(1, Math.min(PW, Math.ceil(u1 * PW) + 1) - sx), sh: Math.max(1, Math.min(PH, Math.ceil(v1 * PH) + 1) - sy) };
    uvBoxCache.set(att, box);
  }
  return box;
}
function regionSource(att, region, r, g, b) {
  const page = region.page.texture.getImage(), PW = page.width, PH = page.height;
  const { sx, sy, sw, sh } = uvBox(att, page);
  const q = v => Math.round(Math.min(1, Math.max(0, v)) * 63);
  const qr = q(r), qg = q(g), qb = q(b);
  if (qr === 63 && qg === 63 && qb === 63) return { img: page, sx, sy, sw, sh, ox: 0, oy: 0, PW, PH };
  const key = `${region.page.name}|${sx},${sy},${sw},${sh}|${qr},${qg},${qb}`;
  let c = tintCache.get(key);
  if (!c) {
    if (tintCache.size > 600) tintCache.clear();
    c = createCanvas(sw, sh);
    const x = c.getContext("2d");
    x.drawImage(page, sx, sy, sw, sh, 0, 0, sw, sh);
    // multiplication exacte des canaux RGB (l'alpha ne change pas)
    const id = x.getImageData(0, 0, sw, sh), d = id.data, tr = qr / 63, tg = qg / 63, tb = qb / 63;
    for (let k = 0; k < d.length; k += 4) { d[k] *= tr; d[k + 1] *= tg; d[k + 2] *= tb; }
    x.putImageData(id, 0, 0);
    tintCache.set(key, c);
  }
  return { img: c, sx: 0, sy: 0, sw, sh, ox: sx, oy: sy, PW, PH };
}

function drawTriangles(ctx, src, verts, uvs, tris, alpha, blend) {
  const W = src.PW, H = src.PH;
  ctx.globalAlpha = alpha;
  ctx.globalCompositeOperation = blend;
  for (let t = 0; t < tris.length; t += 3) {
    const i0 = tris[t] * 2, i1 = tris[t + 1] * 2, i2 = tris[t + 2] * 2;
    const x0 = verts[i0], y0 = verts[i0 + 1], x1 = verts[i1], y1 = verts[i1 + 1], x2 = verts[i2], y2 = verts[i2 + 1];
    // coordonnées texture dans la sous-image (src.ox/oy = position de la sous-image dans la page)
    const u0 = uvs[i0] * W - src.ox, v0 = uvs[i0 + 1] * H - src.oy, u1 = uvs[i1] * W - src.ox, v1 = uvs[i1 + 1] * H - src.oy,
      u2 = uvs[i2] * W - src.ox, v2 = uvs[i2 + 1] * H - src.oy;
    // léger agrandissement du triangle pour masquer les jointures
    const cx = (x0 + x1 + x2) / 3, cy = (y0 + y1 + y2) / 3, g = 0.6;
    const e = (x, y) => { const dx = x - cx, dy = y - cy, l = Math.hypot(dx, dy) || 1; return [x + dx / l * g, y + dy / l * g]; };
    const [a0, b0] = e(x0, y0), [a1, b1] = e(x1, y1), [a2, b2] = e(x2, y2);
    ctx.save();
    ctx.beginPath(); ctx.moveTo(a0, b0); ctx.lineTo(a1, b1); ctx.lineTo(a2, b2); ctx.closePath(); ctx.clip();
    // transformation affine UV -> écran
    const det = (u1 - u0) * (v2 - v0) - (u2 - u0) * (v1 - v0);
    if (Math.abs(det) < 1e-9) { ctx.restore(); continue; }
    const a = ((x1 - x0) * (v2 - v0) - (x2 - x0) * (v1 - v0)) / det;
    const b = ((y1 - y0) * (v2 - v0) - (y2 - y0) * (v1 - v0)) / det;
    const c = ((x2 - x0) * (u1 - u0) - (x1 - x0) * (u2 - u0)) / det;
    const d = ((y2 - y0) * (u1 - u0) - (y1 - y0) * (u2 - u0)) / det;
    const ex = x0 - a * u0 - c * v0, fy = y0 - b * u0 - d * v0;
    ctx.setTransform(a, b, c, d, ex, fy);
    // on ne dessine que la région (évite de déborder sur les pièces voisines de l'atlas)
    ctx.drawImage(src.img, src.sx, src.sy, src.sw, src.sh, src.sx, src.sy, src.sw, src.sh);
    ctx.restore();
  }
}

// boîte englobante grossière : tous les éléments visibles
function visibleBounds(b) {
  for (const slot of skeleton.drawOrder) {
    const att = slot.getAttachment();
    if (!slot.bone.active || !att || !att.region) continue;
    if (skeleton.color.a * slot.color.a * att.color.a <= 0.02) continue;
    let n;
    if (att instanceof spine.RegionAttachment) { att.computeWorldVertices(slot, tmp, 0, 2); n = 8; }
    else if (att instanceof spine.MeshAttachment) { n = att.worldVerticesLength; att.computeWorldVertices(slot, 0, n, tmp, 0, 2); }
    else continue;
    for (let k = 0; k < n; k += 2) {
      b.x0 = Math.min(b.x0, tmp[k]); b.x1 = Math.max(b.x1, tmp[k]);
      b.y0 = Math.min(b.y0, tmp[k + 1]); b.y1 = Math.max(b.y1, tmp[k + 1]);
    }
  }
}

// framing = true : passe de cadrage, on ne dessine que le personnage
// (ni effets additifs, ni pièces de décor de fond, cf. BG_SLOTS)
function render(ctx, view, bg = BG, framing = false) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  if (bg) { ctx.fillStyle = bg; ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height); }
  const { s, ox, oy } = view;
  for (const slot of skeleton.drawOrder) {
    const att = slot.getAttachment();
    if (!slot.bone.active) { clipper.clipEndWithSlot(slot); continue; }
    if (framing && !(att instanceof spine.ClippingAttachment) && (slot.data.blendMode !== 0 || BG_SLOTS.has(slot.data.index))) {
      clipper.clipEndWithSlot(slot); continue;
    }
    if (ONLY_SLOTS && !(att instanceof spine.ClippingAttachment) && !ONLY_SLOTS.test(slot.data.name)) { clipper.clipEndWithSlot(slot); continue; }
    if (att instanceof spine.ClippingAttachment) { clipper.clipStart(slot, att); continue; }
    let verts, uvs, tris, region;
    if (att instanceof spine.RegionAttachment) {
      att.computeWorldVertices(slot, tmp, 0, 2); verts = tmp.subarray(0, 8); uvs = att.uvs; tris = QUAD; region = att.region;
    } else if (att instanceof spine.MeshAttachment) {
      const n = att.worldVerticesLength;
      att.computeWorldVertices(slot, 0, n, tmp, 0, 2); verts = tmp.subarray(0, n); uvs = att.uvs; tris = att.triangles; region = att.region;
    } else { clipper.clipEndWithSlot(slot); continue; }
    const alpha = skeleton.color.a * slot.color.a * att.color.a;
    if (alpha <= 0.003 || !region) { clipper.clipEndWithSlot(slot); continue; }
    const sc = skeleton.color, kc = slot.color, ac = att.color;
    const src = regionSource(att, region,sc.r * kc.r * ac.r, sc.g * kc.g * ac.g, sc.b * kc.b * ac.b);
    if (clipper.isClipping()) {
      // découpe : on reconstruit sommets / uvs / triangles
      const vv = [], uu = [], tt = [];
      clipper.clipTriangles(verts, verts.length, tris, tris.length, uvs,new spine.Color(1, 1, 1, 1), new spine.Color(0, 0, 0, 0), false);
      const cv = clipper.clippedVertices, ct = clipper.clippedTriangles; // stride 8 : x y r g b a u v
      for (let k = 0; k < cv.length; k += 8) { vv.push(cv[k], cv[k + 1]); uu.push(cv[k + 6], cv[k + 7]); }
      for (let k = 0; k < ct.length; k++) tt.push(ct[k]);
      verts = vv; uvs = uu; tris = tt;
    }
    const sv = new Float32Array(verts.length);
    for (let k = 0; k < verts.length; k += 2) { sv[k] = (verts[k] - ox) * s; sv[k + 1] = (oy - verts[k + 1]) * s; }
    drawTriangles(ctx, src, sv,uvs, tris, alpha, BLEND[slot.data.blendMode] || "source-over");
    clipper.clipEndWithSlot(slot);
  }
  clipper.clipEnd();
}

function frames(anim) {
  const dur = Math.min(anim.duration || 1 / FPS, MAXDUR);
  return Math.max(1, Math.round(dur * FPS));
}

// ---- Composition des pistes, comme dans le jeu -------------------------------------
// - animations de « corps » (idle, touch, chuchang...) : pilotent une bonne partie du squelette ;
// - « couches » (clothing_*, shoe_*, sock_*, slime_*... des Lounge) : quelques os seulement,
//   jouées en parallèle sur d'autres pistes.
// Piste 0 = idle de base, puis l'animation de corps, puis l'état par défaut de chaque couche,
// puis la couche demandée. Sans ça, tout ce qu'une animation ne pilote pas reste dans la pose
// de montage (= pièces mal placées).
const keyedBones = a => { const s = new Set(); for (const tl of a.timelines) if (tl.boneIndex !== undefined) s.add(tl.boneIndex); return s.size; };
const bodyLike = a => keyedBones(a) >= data.bones.length * 0.15;
const hasBody = data.animations.some(bodyLike);
const isLayer = a => hasBody && !bodyLike(a) && a.name.includes("_");
const findIdle = () => data.findAnimation(opt("--base", "idle")) || data.findAnimation("idle_01") || data.findAnimation("Idle")
  || data.animations.find(a => /idle/i.test(a.name) && !isLayer(a)) || data.animations.find(a => !isLayer(a)) || data.animations[0];
const BASE = opt("--base", "") === "none" ? null : findIdle();
const layerGroups = new Map();
for (const a of data.animations) if (isLayer(a)) {
  const g = a.name.split("_")[0];
  if (!layerGroups.has(g)) layerGroups.set(g, []);
  layerGroups.get(g).push(a);
}
const layerDefaults = new Map();
if (!args.includes("--nolayers")) for (const [g, list] of layerGroups) {
  const pick = list.find(a => a.name === `${g}_idle`) || list.find(a => a.name === `${g}_01_idle`)
    || list.find(a => a.name === `${g}_idle_01`) || list.find(a => /idle/.test(a.name))
    // couche d'état sans variante « idle » (ex. bg_01 / bg_02 = éclairage de la pièce) : son état n°1.
    // Jamais pour les interactions (touch_*).
    || (g !== "touch" ? list.find(a => /_01$/.test(a.name)) : undefined);
  if (pick) layerDefaults.set(g, pick);
}

function pose(anim, t) {
  skeleton.setToSetupPose();
  state.clearTracks();
  let track = 0;
  const layer = isLayer(anim), group = layer ? anim.name.split("_")[0] : null;
  if (BASE) state.setAnimationWith(track++, BASE, true);
  if (!layer && anim !== BASE) state.setAnimationWith(track++, anim, true);
  for (const [g, d] of layerDefaults) if (g !== group) state.setAnimationWith(track++, d, true);
  if (layer) state.setAnimationWith(track++, anim, true);
  state.update(t); state.apply(skeleton);
  skeleton.updateWorldTransform();
}

// ---- Pièces de décor de fond ---------------------------------------------------------
// Les versions « Final » ont un fond géant (bg, bgh, brumes) tout en bas de l'ordre de dessin.
// Dans le jeu la caméra cadre le personnage et le fond déborde : on l'exclut donc du cadrage
// (il reste dessiné et remplit l'image).
const BG_SLOTS = new Set();
{
  pose(BASE || data.animations[0], 0.5);
  const items = [];
  skeleton.drawOrder.forEach((slot, i) => {
    const att = slot.getAttachment();
    if (!slot.bone.active || !att || !att.region || slot.data.blendMode !== 0) return;
    let n;
    if (att instanceof spine.RegionAttachment) { att.computeWorldVertices(slot, tmp, 0, 2); n = 8; }
    else if (att instanceof spine.MeshAttachment) { n = att.worldVerticesLength; att.computeWorldVertices(slot, 0, n, tmp, 0, 2); }
    else return;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let k = 0; k < n; k += 2) { x0 = Math.min(x0, tmp[k]); x1 = Math.max(x1, tmp[k]); y0 = Math.min(y0, tmp[k + 1]); y1 = Math.max(y1, tmp[k + 1]); }
    items.push({ i, idx: slot.data.index, x0, y0, x1, y1, area: (x1 - x0) * (y1 - y0) });
  });
  const lowCut = Math.max(3, Math.round(skeleton.drawOrder.length * 0.1));
  const body = items.filter(it => it.i >= lowCut);
  if (body.length) {
    const bx0 = Math.min(...body.map(it => it.x0)), bx1 = Math.max(...body.map(it => it.x1));
    const by0 = Math.min(...body.map(it => it.y0)), by1 = Math.max(...body.map(it => it.y1));
    const bodyArea = (bx1 - bx0) * (by1 - by0);
    for (const it of items) if (it.i < lowCut && it.area >= 0.4 * bodyArea) BG_SLOTS.add(it.idx);
  }
}

// Cadre (coordonnées monde) d'une animation : boîte des pixels opaques du personnage seul
function computeFrame(anim, n) {
  if (opt("--frame")) { // cadre imposé (diagnostic) : x0,y0,x1,y1 en coordonnées monde
    const [x0, y0, x1, y1] = opt("--frame").split(",").map(Number);
    return { x0, y0, x1, y1 };
  }
  const b ={ x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
  for (let f = 0; f < n; f++) { pose(anim, f / FPS); visibleBounds(b); }
  if (!isFinite(b.x0)) return null;
  // cadrage fin : rendu basse résolution sur fond transparent, puis boîte des pixels
  // bien opaques (alpha > 60 %) -> les halos et lueurs diffuses sont ignorés
  {
    const ps = 256 / Math.max(b.x1 - b.x0, b.y1 - b.y0);
    const pw = Math.ceil((b.x1 - b.x0) * ps) + 1, ph = Math.ceil((b.y1 - b.y0) * ps) + 1;
    const pc = createCanvas(pw, ph), px = pc.getContext("2d");
    // histogrammes colonnes / lignes des pixels opaques, puis on retire 1 % de chaque côté :
    // les traits fins (graduations, rayons) qui s'étirent loin ne dictent plus le cadre
    const colH = new Float64Array(pw), rowH = new Float64Array(ph);
    for (let f = 0; f < n; f += Math.max(1, Math.floor(n / 12))) {
      pose(anim, f / FPS);
      render(px, { s: ps, ox: b.x0, oy: b.y1 }, null, true);
      const d = px.getImageData(0, 0, pw, ph).data;
      for (let yy = 0; yy < ph; yy++) for (let xx = 0; xx < pw; xx++) {
        if (d[(yy * pw + xx) * 4 + 3] > 153) { colH[xx]++; rowH[yy]++; }
      }
    }
    const trim = (h) => {
      const tot = h.reduce((p, v) => p + v, 0); if (!tot) return [0, -1];
      let lo = 0, hi = h.length - 1, acc = 0;
      while (lo < hi && acc + h[lo] <= tot * 0.01) acc += h[lo++];
      acc = 0; while (hi > lo && acc + h[hi] <= tot * 0.01) acc += h[hi--];
      return [lo, hi];
    };
    const [a0, a1] = trim(colH), [c0, c1] = trim(rowH);
    if (a1 >= 0) {
      const nx0 = b.x0 + a0 / ps, nx1 = b.x0 + (a1 + 1) / ps;
      const ny1 = b.y1 - c0 / ps, ny0 = b.y1 - (c1 + 1) / ps;
      b.x0 = nx0; b.x1 = nx1; b.y0 = ny0; b.y1 = ny1;
    }
  }
  // marge de 6 %
  const m = 0.06 * Math.max(b.x1 - b.x0, b.y1 - b.y0);
  return { x0: b.x0 - m, y0: b.y0 - m, x1: b.x1 + m, y1: b.y1 + m };
}

// Prépare les canvas de rendu pour un cadre et une taille max donnés
function makeView(fr, maxPx) {
  // --fixedscale : échelle imposée (composition de fonds d'écran : 1 unité = N pixels)
  const s = opt("--fixedscale") ? +opt("--fixedscale") : Math.min(1, maxPx / Math.max(fr.x1 - fr.x0, fr.y1 - fr.y0));
  const W = Math.max(2, Math.round((fr.x1 - fr.x0) * s)), H = Math.max(2, Math.round((fr.y1 - fr.y0) * s));
  // rendu sur-échantillonné (SS x) puis réduction lissée -> contours propres
  const big = createCanvas(W * SS, H * SS), bctx = big.getContext("2d");
  bctx.imageSmoothingEnabled = true; bctx.imageSmoothingQuality = "high";
  const canvas = createCanvas(W, H), ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = "high";
  const view = { s: s * SS, ox: fr.x0, oy: fr.y1 };
  const frame = () => {
    render(bctx, view, null);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.drawImage(big, 0, 0, W * SS, H * SS, 0, 0, W, H);
    return canvas.toBuffer("image/png");
  };
  return { W, H, frame };
}

const safeName = s => s.replace(/[<>:"/\\|?*]/g, "_");
fs.mkdirSync(OUT, { recursive: true });
const PREVIEW_ONLY = args.includes("--previewonly"); // test rapide : une image par animation, pas d'encodage

// ---- Image fixe (animation désactivée dans le jeu) : idle immobile, haute résolution --------
if (BASE && !args.includes("--nostill")) {
  const fr = computeFrame(BASE, frames(BASE));
  if (fr) {
    const v = makeView(fr, STILLMAX);
    if (args.includes("--printframe")) console.error("cadre image fixe :", JSON.stringify(fr), v.W, v.H);
    // On garde le début de l'idle (t=0), sauf s'il est presque vide (effets/décors qui apparaissent
    // en fondu) : on prend alors l'instant où l'élément est le plus visible.
    const n = frames(BASE), probe = makeView(fr, 128);
    const coverage = t => {
      pose(BASE, t);
      const img = probe.frame(), c = createCanvas(probe.W, probe.H), x = c.getContext("2d");
      return new Promise(res => loadImage(img).then(im => {
        x.drawImage(im, 0, 0);
        const d = x.getImageData(0, 0, probe.W, probe.H).data;
        let k = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 128) k++;
        res(k / (probe.W * probe.H));
      }));
    };
    let bestT = 0, c0 = await coverage(0), best = c0;
    for (let k = 1; k < 16; k++) {
      const t = Math.floor(k * n / 16) / FPS, c = await coverage(t);
      if (c > best) { best = c; bestT = t; }
    }
    // seulement si t=0 est quasi vide (< 2 % de pixels opaques) : sinon on garde le début de l'idle
    pose(BASE, c0 >= 0.02 || args.includes("--t0") ? 0 : bestT);
    fs.writeFileSync(path.join(OUT, "_image_fixe.png"), v.frame());
  }
}

// ---- Animations ----------------------------------------------------------------------
const anims = data.animations.filter(a => !ONLY || ONLY.includes(a.name));
let done = 0;
for (const anim of anims) {
  const n = frames(anim);
  const fr = computeFrame(anim, n);
  if (!fr) continue;
  const { W, H, frame } = makeView(fr, MAX);
  const name = safeName(anim.name);
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "bns_"));
  try {
    const f0 = PREVIEW_ONLY ? Math.floor(n / 2) : 0, f1 = PREVIEW_ONLY ? f0 + 1 : n;
    if (args.includes("--sheet")) { // diagnostic : 8 images réparties sur l'animation, pas d'encodage
      for (let k = 0; k < 8; k++) {
        const f = Math.floor(k * n / 8);
        pose(anim, f / FPS);
        fs.writeFileSync(path.join(OUT, `${name}_t${String(k).padStart(2, "0")}.png`), frame());
      }
      done++; continue;
    }
    for (let f = f0; f < f1; f++) {
      pose(anim, f / FPS);
      const png = frame();
      fs.writeFileSync(path.join(tmpDir, String(f).padStart(5, "0") + ".png"), png);
      if (args.includes("--preview") && f === Math.floor(n / 2)) fs.writeFileSync(path.join(OUT, name + "_preview.png"), png);
    }
    if (PREVIEW_ONLY) { done++; continue; }
    // WebP animé transparent, qualité 95 (visuellement identique au sans-perte, 2,3x plus léger)
    const r = spawnSync(FFMPEG, ["-v", "error", "-y", "-framerate", String(FPS), "-i", path.join(tmpDir, "%05d.png"),
      "-c:v", "libwebp_anim", "-lossless", "0", "-quality", "95", "-compression_level", "5", "-loop", "0",
      path.join(OUT, name + ".webp")], { encoding: "utf8" });
    if (r.status !== 0) throw new Error("ffmpeg webp: " + r.stderr);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
  done++;
}
console.log(JSON.stringify({
  src: SRC, base: BASE && BASE.name, layers: Object.fromEntries([...layerDefaults].map(([g, a]) => [g, a.name])),
  bgSlots: [...BG_SLOTS].map(i => data.slots[i].name), animations: data.animations.map(a => a.name), rendered: done,
}));
