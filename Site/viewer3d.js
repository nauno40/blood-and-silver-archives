// Visualiseur 3D (three.js) : window.Viewer3D.show(container, url, onInfo, {mode}) -> { dispose(), play(clip), setMode(mode), clips }
// Modes de rendu :
//   jeu      : ombrage « toon » en 3 paliers + contour sombre (coque inversée) + liseré de lumière, comme le shader du jeu
//              (_OutlineWidth / _OutlineColor / _Rim* des matériaux des personnages)
//   lumineux : éclairage doux + texture en partie auto-éclairée (cartes, décors)
//   plat     : texture sans éclairage
//   realiste : PBR mat (ancien rendu)
import * as THREE from "three";
import { GLTFLoader } from "./lib/three/GLTFLoader.js";
import { OrbitControls } from "./lib/three/OrbitControls.js";

const MODES = [["jeu", "Jeu (toon)"], ["lumineux", "Lumineux"], ["plat", "Plat"], ["realiste", "Réaliste"]];
let GRAD = null;
function toonGradient() {
  if (GRAD) return GRAD;
  GRAD = new THREE.DataTexture(new Uint8Array([168, 160, 178, 255, 222, 216, 226, 255, 255, 255, 255, 255]), 3, 1);
  GRAD.minFilter = GRAD.magFilter = THREE.NearestFilter; GRAD.needsUpdate = true; return GRAD;
}
function rimify(mat, strength) {  // liseré de lumière sur les bords (fresnel), ajouté à l'émission
  mat.onBeforeCompile = sh => {
    sh.fragmentShader = sh.fragmentShader.replace("#include <emissivemap_fragment>",
      "#include <emissivemap_fragment>\n float rimF = pow(1.0 - clamp(dot(normal, normalize(vViewPosition)), 0.0, 1.0), 3.0);\n" +
      " totalEmissiveRadiance += diffuseColor.rgb * rimF * " + strength.toFixed(2) + ";");
  };
  mat.customProgramCacheKey = () => "rim" + strength;
  return mat;
}
function outlineMaterial(width, src) {  // coque inversée : sommets poussés le long de la normale, faces arrière en gris sombre
  // si la pièce est découpée (alphaTest), le contour reprend la transparence de sa texture : pas de trous remplis de noir
  const cut = src && src.map && src.alphaTest > 0;
  const m = new THREE.MeshBasicMaterial({ color: 0x262626, side: THREE.BackSide, map: cut ? src.map : null, alphaTest: cut ? src.alphaTest : 0 });
  m.onBeforeCompile = sh => {
    sh.vertexShader = sh.vertexShader.replace("#include <begin_vertex>",
      "#include <begin_vertex>\n transformed += normalize(normal) * " + width.toExponential(4) + ";");
    if (cut) sh.fragmentShader = sh.fragmentShader.replace("#include <map_fragment>",
      "#include <map_fragment>\n diffuseColor.rgb = vec3(0.149);");
  };
  m.customProgramCacheKey = () => "outline" + width.toExponential(3) + (cut ? "c" : "");
  return m;
}
function applyMode(root, mode, size) {
  root.traverse(o => {
    if (o.userData.isOutline) { o.visible = mode === "jeu"; return; }
    if (!o.isMesh) return;
    const m0 = o.userData.orig || (o.userData.orig = o.material);
    const base = { map: m0.map || null, transparent: m0.transparent, alphaTest: m0.alphaTest, side: THREE.DoubleSide,
                   color: m0.color ? m0.color.clone() : new THREE.Color(1, 1, 1) };
    if (m0.map) m0.map.colorSpace = THREE.SRGBColorSpace;
    let m;
    if (mode === "jeu") m = rimify(new THREE.MeshToonMaterial({ ...base, gradientMap: toonGradient() }), 0.35);
    else if (mode === "lumineux") m = rimify(new THREE.MeshStandardMaterial({ ...base, roughness: 0.75, metalness: 0, emissive: 0xffffff,
                                                                               emissiveMap: base.map, emissiveIntensity: base.map ? 0.38 : 0.1 }), 0.15);
    else if (mode === "plat") m = new THREE.MeshBasicMaterial(base);
    else m = new THREE.MeshStandardMaterial({ ...base, roughness: 0.85, metalness: 0 });
    if (o.material !== m0) o.material.dispose();
    o.material = m;
  });
  // contours : créés une seule fois, visibles en mode « jeu »
  if (mode === "jeu" && !root.userData.outlined) {
    root.userData.outlined = true;
    const width = Math.max(size, 1e-3) * 0.0022, om = outlineMaterial(width), cache = new Map(), list = [];
    root.traverse(o => { if (o.isMesh && !o.userData.isOutline) list.push(o); });
    for (const o of list) {
      const m0 = o.userData.orig;
      if (m0 && m0.transparent && !m0.alphaTest) continue;  // pas de contour sur les pièces translucides
      let ol, mat = om;
      if (m0 && m0.map && m0.alphaTest > 0) { if (!cache.has(m0)) cache.set(m0, outlineMaterial(width, m0)); mat = cache.get(m0); }
      if (o.isSkinnedMesh) {
        ol = new THREE.SkinnedMesh(o.geometry, mat); ol.bind(o.skeleton, o.bindMatrix);
        ol.position.copy(o.position); ol.quaternion.copy(o.quaternion); ol.scale.copy(o.scale); o.parent.add(ol);
      } else { ol = new THREE.Mesh(o.geometry, mat); o.add(ol); }
      ol.userData.isOutline = true; ol.frustumCulled = false;
    }
  }
}
// Boîte de cadrage robuste : pièce principale (le plus de sommets) + pièces qui la touchent ;
// ignore les accessoires « rangés » loin du corps (ex. arme cachée à 400 unités dans certaines poses)
function robustBox(root) {
  root.updateMatrixWorld(true);
  const parts = [];
  root.traverse(o => {
    if (!o.isMesh || o.userData.isOutline) return;
    let b;
    if (o.isSkinnedMesh) { o.skeleton.update(); o.computeBoundingBox(); b = o.boundingBox.clone().applyMatrix4(o.matrixWorld); }
    else b = new THREE.Box3().setFromObject(o);
    if (!b.isEmpty()) parts.push({ b, n: o.geometry.attributes.position.count });
  });
  if (!parts.length) return new THREE.Box3().setFromObject(root);
  parts.sort((a, b) => b.n - a.n);
  const box = parts[0].b.clone();
  for (let pass = 0; pass < 2; pass++)
    for (const p of parts) {
      const grow = box.clone().expandByScalar(box.getSize(new THREE.Vector3()).length() * 0.04);
      if (grow.intersectsBox(p.b)) box.union(p.b);
    }
  return box;
}
// distance de caméra pour que la boîte tienne dans le cadre (fov vertical, rapport largeur/hauteur)
function fitDistance(size, fov, aspect, margin = 1.12) {
  const t = Math.tan(THREE.MathUtils.degToRad(fov) / 2);
  return Math.max(size.y / 2 / t, Math.max(size.x, size.z) / 2 / (t * aspect)) * margin + Math.max(size.x, size.z) / 2;
}
function setupLights(scene) {
  scene.add(new THREE.HemisphereLight(0xfff8f0, 0x5a4a66, 1.3));
  const key = new THREE.DirectionalLight(0xfff2e6, 2.0); key.position.set(2, 3.5, 4); scene.add(key);
  const fill = new THREE.DirectionalLight(0xc8d8ff, 0.9); fill.position.set(-3, 1.5, 2); scene.add(fill);
  const back = new THREE.DirectionalLight(0xffe0ea, 1.1); back.position.set(-1, 3, -4); scene.add(back);
}
function groundShadow(size, center, minY) {  // ombre douce au sol (dégradé radial)
  const c = document.createElement("canvas"); c.width = c.height = 128; const x = c.getContext("2d");
  const g = x.createRadialGradient(64, 64, 4, 64, 64, 64); g.addColorStop(0, "rgba(0,0,0,0.55)"); g.addColorStop(1, "rgba(0,0,0,0)");
  x.fillStyle = g; x.fillRect(0, 0, 128, 128);
  const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false }));
  m.rotation.x = -Math.PI / 2; m.scale.set(size.x * 1.6 + size.z * 0.4, size.z * 1.6 + size.x * 0.4, 1);
  m.position.set(center.x, minY + size.y * 0.002, center.z);
  return m;
}

function show(container, url, onInfo, opts = {}) {
  const w = container.clientWidth, h = container.clientHeight;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(w, h);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(0x000000, 0);
  container.innerHTML = ""; container.appendChild(renderer.domElement);
  container.classList.add("v3d");
  const scene = new THREE.Scene();
  setupLights(scene);
  const camera = new THREE.PerspectiveCamera(35, w / h, 0.01, 5000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  let raf, disposed = false, auto = true, mixer = null, current = null, root = null, R = 1, mode = opts.mode || "jeu";
  const clock = new THREE.Clock();
  controls.addEventListener("start", () => { auto = false; });
  const api = { clips: [], dispose, play, setMode };

  function play(name) {
    if (!mixer) return;
    const clip = api.clips.find(c => c.name === name);
    if (!clip) return;
    if (current) current.fadeOut(0.15);
    current = mixer.clipAction(clip).reset().fadeIn(0.15).play();
  }
  function setMode(m) { mode = m; if (root) applyMode(root, mode, R); }

  new GLTFLoader().load(url, gltf => {
    if (disposed) return;
    root = gltf.scene;
    let tris = 0;
    root.traverse(o => {
      if (o.isMesh) {
        tris += (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3;
        if (o.isSkinnedMesh) o.frustumCulled = false;  // les os animés sortent de la boîte de repos
      }
    });
    scene.add(root);
    // cadrage automatique sur la pose de repos
    const box = robustBox(root), size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
    R = Math.max(size.x, size.y, size.z) || 1;
    applyMode(root, mode, R);
    if (opts.shadow !== false) scene.add(groundShadow(size, center, box.min.y));
    controls.target.copy(center);
    camera.position.copy(center).add(new THREE.Vector3(0, size.y * 0.08, fitDistance(size, 35, w / h)));
    camera.near = R / 500; camera.far = R * 50; camera.updateProjectionMatrix();
    controls.update();
    if (gltf.animations.length) {
      mixer = new THREE.AnimationMixer(root);
      api.clips = gltf.animations;
    }
    onInfo && onInfo({ meshes: root.children.length, tris: Math.round(tris), size: size.toArray().map(v => +v.toFixed(2)),
                       clips: gltf.animations.map(a => ({ name: a.name, duration: +a.duration.toFixed(2) })) });
  }, undefined, err => { onInfo && onInfo({ error: String(err && err.message || err) }); });

  const tick = () => {
    if (disposed) return;
    const dt = clock.getDelta();
    if (mixer) mixer.update(dt);
    if (auto) { // rotation lente jusqu'à la première interaction
      const t = controls.target, p = camera.position.clone().sub(t);
      p.applyAxisAngle(new THREE.Vector3(0, 1, 0), 0.004); camera.position.copy(t).add(p);
    }
    controls.update(); renderer.render(scene, camera); raf = requestAnimationFrame(tick);
  };
  tick();
  const ro = new ResizeObserver(() => {
    const W = container.clientWidth, H = container.clientHeight; if (!W || !H) return;
    renderer.setSize(W, H); camera.aspect = W / H; camera.updateProjectionMatrix();
  });
  ro.observe(container);
  function dispose() { disposed = true; cancelAnimationFrame(raf); ro.disconnect(); controls.dispose(); if (mixer) mixer.stopAllAction(); renderer.dispose(); container.innerHTML = ""; }
  return api;
}
// Aperçu d'une texture plaquée sur une forme 3D (boule, cube, beignet) qui tourne : Viewer3D.shape(container, url, forme)
const SHAPES = {
  boule: () => new THREE.SphereGeometry(1, 96, 64),
  cube: () => new THREE.BoxGeometry(1.4, 1.4, 1.4),
  beignet: () => new THREE.TorusGeometry(0.85, 0.38, 64, 128),
};
function shape(container, url, kind = "boule") {
  const w = container.clientWidth, h = container.clientHeight;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(w, h);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.innerHTML = ""; container.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x2a2030, 1.5));
  const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(3, 3, 4); scene.add(key);
  const camera = new THREE.PerspectiveCamera(35, w / h, 0.1, 100); camera.position.set(0, 0.3, 4.2);
  const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true;
  controls.autoRotate = true; controls.autoRotateSpeed = 2.5;
  const tex = new THREE.TextureLoader().load(url, t => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = renderer.capabilities.getMaxAnisotropy(); t.needsUpdate = true; });
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  const mat = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.6, metalness: 0, transparent: true, alphaTest: 0.02, side: THREE.FrontSide });
  // noyau uni légèrement plus petit : la forme reste visible sous les zones transparentes de la texture
  const core = new THREE.MeshStandardMaterial({ color: 0x4a3d52, roughness: 0.8, metalness: 0 });
  const build = k => { const gm = SHAPES[k](), gr = new THREE.Group(); gr.add(new THREE.Mesh(gm, core));
    const top = new THREE.Mesh(gm, mat); top.scale.setScalar(1.004); gr.add(top); return gr; };
  let mesh = build(kind); scene.add(mesh);
  let raf, disposed = false;
  const tick = () => { if (disposed) return; controls.update(); renderer.render(scene, camera); raf = requestAnimationFrame(tick); };
  tick();
  return {
    setShape(k) { scene.remove(mesh); mesh.children[0].geometry.dispose(); mesh = build(k); scene.add(mesh); },
    dispose() { disposed = true; cancelAnimationFrame(raf); controls.dispose(); mesh.children[0].geometry.dispose(); mat.dispose(); core.dispose(); tex.dispose(); renderer.dispose(); container.innerHTML = ""; },
  };
}
// Ciel 360° depuis une image « croix » 4x3 (cubemap extraite) : on est au centre et on regarde autour
function sky(container, url) {
  const w = container.clientWidth, h = container.clientHeight;
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(w, h);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.innerHTML = ""; container.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(75, w / h, 0.1, 10); camera.position.set(0, 0, 0.01);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableZoom = false; controls.enablePan = false; controls.rotateSpeed = -0.4;
  controls.autoRotate = true; controls.autoRotateSpeed = 0.6;
  let raf, disposed = false, cube = null;
  const img = new Image(); img.crossOrigin = "anonymous";
  img.onload = () => {
    if (disposed) return;
    const f = img.width / 4;
    // croix : +Y (1,0) ; -X (0,1) +Z (1,1) +X (2,1) -Z (3,1) ; -Y (1,2) — repère Unity (main gauche) -> three
    const cut = (cx, cy) => { const c = document.createElement("canvas"); c.width = c.height = f; c.getContext("2d").drawImage(img, cx * f, cy * f, f, f, 0, 0, f, f); return c; };
    cube = new THREE.CubeTexture([cut(0, 1), cut(2, 1), cut(1, 0), cut(1, 2), cut(1, 1), cut(3, 1)]);
    cube.colorSpace = THREE.SRGBColorSpace; cube.needsUpdate = true;
    scene.background = cube;
  };
  img.src = url;
  const tick = () => { if (disposed) return; controls.update(); renderer.render(scene, camera); raf = requestAnimationFrame(tick); };
  tick();
  return { setShape() {}, dispose() { disposed = true; cancelAnimationFrame(raf); controls.dispose(); cube?.dispose(); renderer.dispose(); container.innerHTML = ""; } };
}
window.Viewer3D = { show, shape, sky, MODES, applyMode, setupLights, robustBox, fitDistance };
window.dispatchEvent(new Event("viewer3d-ready"));
