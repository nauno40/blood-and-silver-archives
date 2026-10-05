/* Blood and Silver — Archives : navigation par hash, rendu des rubriques, lightbox, lecteur audio. */
"use strict";
const D = window.DATA || {};
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const view = $("#view");
const PAGE = 240;

// Chargement à la demande des gros fichiers de données (textures, tables)
const lazy = {};
function need(name) {
  if (D[name]) return Promise.resolve(D[name]);
  if (!lazy[name]) lazy[name] = new Promise((res, rej) => {
    const s = document.createElement("script"); s.src = `data/${name}.js`;
    s.onload = () => res(window.DATA[name]); s.onerror = rej; document.head.appendChild(s);
  });
  return lazy[name];
}

const ROUTES = [
  ["", "Accueil", home],
  ["personnages", "Personnages", characters],
  ["spine", "Spine", spinePage],
  ["portraits", "Portraits", portraitsPage],
  ["fonds-principal", "Écran principal", () => imageGallery("mainbg", "Fonds de l'écran principal", "Les 28 fonds sélectionnables de l'écran d'accueil, recomposés comme en jeu (2880×1440).", true)],
  ["fonds", "Fonds", () => imageGallery("backgrounds", "Fonds d'écran", "Décors d'histoire, illustrations d'événements, écrans de chargement et fonds d'interface.", true)],
  ["textures", "Textures", texturesPage],
  ["modeles", "Modèles 3D", modelsPage],
  ["shaders", "Shaders", shadersPage],
  ["pixel", "Pixel art", pixelPage],
  ["polices", "Polices", fontsPage],
  ["videos", "Vidéos", videosPage],
  ["audio", "Audio", audioPage],
  ["textes", "Données", textsPage],
];

// Libellés lisibles
const ANIM_LABELS = { idle: "Repos", idle2: "Repos 2", touch: "Toucher", chuchang: "Entrée", chuchang2: "Entrée (courte)", xp: "Gain d'XP", shadow: "Ombre" };
function animLabel(a) {
  if (ANIM_LABELS[a]) return ANIM_LABELS[a];
  return a.replace(/^idle_?/i, "Repos ").replace(/^touch_?/i, "Toucher ").replace(/_/g, " ").replace(/\s+/g, " ").trim();
}
function pretty(s) {
  return String(s).replace(/^(Form_|ui_panel_|ui_lounge_|ui_)/i, "").replace(/_(base|final)$/i, "").replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2").replace(/\s+/g, " ").trim().replace(/^./, c => c.toUpperCase());
}
const skinOrder = c => (/^base$/i.test(c.skin) ? 0 : 1);

function nav() {
  const cur = (location.hash.slice(2).split("/")[0]) || "";
  $("#nav").innerHTML = ROUTES.slice(1).map(([k, t]) => `<a href="#/${k}" class="${k === cur ? "on" : ""}">${t}</a>`).join("");
}
function route() {
  nav();
  const [key, ...rest] = location.hash.slice(2).split("/").map(decodeURIComponent);
  const r = ROUTES.find(([k]) => k === (key || "")) || ROUTES[0];
  if (key !== "shaders" && typeof shaderPrev !== "undefined" && shaderPrev) { shaderPrev.dispose(); shaderPrev = null; }
  view.innerHTML = ""; window.scrollTo(0, 0);
  r[2](...rest);
}
window.addEventListener("hashchange", route);
let searchTimer;
$("#search").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => window.onSearch && window.onSearch(), 180); });
const q = () => $("#search").value.trim().toLowerCase();

// ---------------------------------------------------------------- composants
function card({ img, title, sub, onClick, href }) {
  const el = document.createElement(href ? "a" : "div");
  el.className = "card"; if (href) { el.href = href; el.style.textDecoration = "none"; el.style.color = "inherit"; }
  el.innerHTML = `<div class="img"><img loading="lazy" src="${esc(img)}" alt=""></div><div class="cap"><b>${esc(title)}</b>${sub ? `<span>${esc(sub)}</span>` : ""}</div>`;
  if (onClick) el.addEventListener("click", onClick);
  return el;
}
// Liste paginée en défilement infini : les éléments suivants arrivent automatiquement en bas de page
// (sentinelle observée), avec un compteur et un bouton « Tout afficher ».
function paged(container, items, render, cls = "grid") {
  if (!items.length) { container.insertAdjacentHTML("beforeend", `<p class="empty">Aucun résultat.</p>`); return; }
  const grid = document.createElement("div"); grid.className = cls; container.appendChild(grid);
  const foot = document.createElement("div"); foot.className = "pager"; container.appendChild(foot);
  let n = 0, io = null;
  const add = count => {
    const frag = document.createDocumentFragment();
    items.slice(n, n + count).forEach((it, i) => frag.appendChild(render(it, n + i)));
    n = Math.min(items.length, n + count); grid.appendChild(frag);
    if (n >= items.length) { foot.innerHTML = items.length > PAGE ? `<span class="count">${items.length} affichés</span>` : ""; io && io.disconnect(); return; }
    foot.innerHTML = `<span class="count">${n} / ${items.length} affichés — la suite se charge en descendant</span>` +
      (items.length <= 2000 ? `<button class="btn ghost">Tout afficher</button>` : "");
    const b = foot.querySelector("button"); if (b) b.onclick = () => add(items.length);
  };
  add(PAGE);
  if (n < items.length && "IntersectionObserver" in window) {
    io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting) && document.body.contains(foot)) add(PAGE); }, { rootMargin: "1200px" });
    io.observe(foot);
  }
}
function header(title, sub) {
  view.insertAdjacentHTML("beforeend", `<h1>${esc(title)}</h1>${sub ? `<p class="sub">${sub}</p>` : ""}`);
}
function chips(options, current, onPick) {
  const bar = document.createElement("div"); bar.className = "toolbar";
  options.forEach(([val, label]) => {
    const b = document.createElement("button"); b.className = "chip" + (val === current ? " on" : ""); b.textContent = label;
    b.onclick = () => onPick(val); bar.appendChild(b);
  });
  return bar;
}

// ---------------------------------------------------------------- lightbox
const LB = { list: [], i: 0 };
function lightbox(list, i) {
  LB.list = list; LB.i = i; $("#lightbox").hidden = false; showLB();
}
// mode d'affichage des textures : image à plat, ou plaquée sur une forme 3D qui tourne (mémorisé)
const LB_MODES = [["image", "Image à plat"], ["boule", "Boule 3D"], ["cube", "Cube 3D"], ["beignet", "Beignet 3D"]];
let lbMode = "image", lb3d = null;
try { lbMode = localStorage.getItem("lbMode") || "image"; } catch (e) {}
function closeLB() { $("#lightbox").hidden = true; if (lb3d) { lb3d.dispose(); lb3d = null; } }
function showLB() {
  const it = LB.list[LB.i]; const lb = $("#lightbox");
  const isSky = /\/Cubemaps\//.test(it.file);  // ciel 360° (cubemap dépliée en croix)
  const opts = isSky ? [["image", "Image à plat"], ["ciel", "Ciel 360°"]] : LB_MODES;
  const mode = isSky ? (lbMode === "image" ? "image" : "ciel") : it.tex3d ? (lbMode === "ciel" ? "boule" : lbMode) : "image";
  const box = $("#lb3d"), modes = $(".lb-modes", lb);
  modes.hidden = !it.tex3d;
  modes.innerHTML = opts.map(([k, l]) => `<a data-m="${k}" class="${k === mode ? "on" : ""}">${l}</a>`).join("");
  modes.querySelectorAll("a").forEach(a => a.onclick = () => {
    lbMode = a.dataset.m; try { localStorage.setItem("lbMode", lbMode); } catch (e) {}
    if (lb3d && lbMode !== "image" && lbMode !== "ciel" && !isSky) { lb3d.setShape(lbMode); modes.querySelectorAll("a").forEach(b => b.classList.toggle("on", b === a)); }
    else showLB();
  });
  $("img", lb).hidden = mode !== "image"; box.hidden = mode === "image";
  if (lb3d) { lb3d.dispose(); lb3d = null; }
  if (mode !== "image") {
    const start = () => { if (!$("#lightbox").hidden && LB.list[LB.i] === it) lb3d = mode === "ciel" ? window.Viewer3D.sky(box, it.file) : window.Viewer3D.shape(box, it.file, mode); };
    window.Viewer3D ? start() : window.addEventListener("viewer3d-ready", start, { once: true });
  } else $("img", lb).src = it.file;
  $("figcaption", lb).innerHTML = `${esc(it.name)} <span>(${LB.i + 1}/${LB.list.length})</span><a href="${esc(it.file)}" target="_blank">taille réelle</a>` +
    (it.png ? `<a href="${esc(it.png)}" download>PNG original</a>` : "");
}
$("#lightbox .lb-close").onclick = closeLB;
$("#lightbox .lb-prev").onclick = () => { LB.i = (LB.i - 1 + LB.list.length) % LB.list.length; showLB(); };
$("#lightbox .lb-next").onclick = () => { LB.i = (LB.i + 1) % LB.list.length; showLB(); };
$("#lightbox").addEventListener("click", e => { if (e.target.id === "lightbox") closeLB(); });
document.addEventListener("keydown", e => {
  if ($("#lightbox").hidden) return;
  if (e.key === "Escape") closeLB();
  if (e.key === "ArrowLeft") $("#lightbox .lb-prev").click();
  if (e.key === "ArrowRight") $("#lightbox .lb-next").click();
});

// ---------------------------------------------------------------- accueil
function home() {
  window.onSearch = null;
  const S = D.stats || {}, H = D.heroes || [], C = D.characters || [];
  const fmt = n => (n || 0).toLocaleString("fr");
  const rnd = a => a.length ? a[Math.floor(Math.random() * a.length)] : null;
  const shuffle = a => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const banner = rnd(D.mainbg || []) || {};
  // héros à la une : tenues animées au hasard (une par héros)
  const featured = shuffle(H.map(h => ({ h, c: h.skins.map(spineOfSkin).find(Boolean) })).filter(x => x.c)).slice(0, 14);
  const stillOf = name => (C.find(c => c.bundle.toLowerCase().includes(name)) || {}).thumb;
  const sections = [
    ["Personnages", [
      ["personnages", "Héros", `${fmt(S.heroes)} héros · ${fmt(S.skins)} tenues`, (rnd(featured) || {}).c?.thumb, ""],
      ["spine", "Spine interactif", `${fmt(S.spine)} squelettes · ${fmt(S.spineAnims)} animations`, stillOf("agares") || (featured[1] || {}).c?.thumb, ""],
      ["portraits", "Portraits", `${fmt(S.portraits)} expressions et illustrations`, (H.flatMap(h => h.skins).filter(s => s.illusThumb)[7] || {}).illusThumb, ""],
      ["pixel", "Pixel art", `${fmt(S.pixel)} sprites · ${fmt(S.pixelAnims)} animations`, null, "pix"],
    ]],
    ["Univers", [
      ["fonds-principal", "Écran principal", `${fmt((D.mainbg || []).length)} fonds recomposés`, (rnd(D.mainbg || []) || {}).thumb, ""],
      ["fonds", "Fonds d'écran", `${fmt((D.backgrounds || []).length)} illustrations`, (rnd((D.backgrounds || []).slice(0, 200)) || {}).thumb, ""],
      ["modeles", "Modèles 3D", `${fmt(S.models)} modèles · ${fmt(S.modelsAnimated)} animés`, rnd(S.modelSamples || []), ""],
      ["modeles", "Cartes 3D", `${fmt((S.modelCats || {}).cartes)} cartes et zones`, rnd(S.mapSamples || []), "", "cartes"],
      ["videos", "Vidéos", `${fmt((D.videos || []).length)} cinématiques`, (rnd(D.videos || []) || {}).poster, ""],
      ["audio", "Audio", `${fmt((D.audio || []).length)} musiques, voix et sons`, (rnd((D.backgrounds || []).slice(100, 300)) || {}).thumb, ""],
    ]],
    ["Ressources", [
      ["textures", "Textures", `${fmt(S.textures)} images du jeu`, (rnd((D.backgrounds || []).slice(300)) || {}).thumb, ""],
      ["shaders", "Shaders", `${fmt(S.shaders)} shaders · aperçu en direct`, rnd(S.modelSamples || []), ""],
      ["polices", "Polices", "6 polices du jeu", null, "font"],
      ["textes", "Données du jeu", `textes en 9 langues · ${fmt(S.tables)} tables`, null, "data"],
    ]],
  ];
  view.innerHTML = `
    <section class="hero-banner" style="background-image:url('${esc(banner.file || banner.thumb || "")}')">
      <div class="hb-inner">
        <p class="hb-kicker">Archives du jeu</p>
        <h1 class="hb-title">Blood and Silver</h1>
        <p class="hb-sub">Tout le contenu extrait du jeu, consultable hors ligne : héros animés, modèles 3D, cartes, illustrations, musiques, voix et cinématiques.</p>
        <div class="hb-search"><input id="homeFind" placeholder="Chercher un héros, un modèle, une vidéo…" autocomplete="off"><div id="homeRes" class="hb-res" hidden></div></div>
      </div>
    </section>
    <div class="stats-bar">
      ${[[S.heroes, "héros"], [S.spineAnims, "animations 2D"], [S.models, "modèles 3D"], [S.textures, "images"], [(D.audio || []).length, "sons"], [(D.videos || []).length, "vidéos"]]
        .map(([n, l]) => `<div><b>${fmt(n)}</b><span>${l}</span></div>`).join("")}
    </div>
    <div class="home-sec-title"><h2>Héros à la une</h2><a href="#/personnages">Tous les héros →</a></div>
    <div class="feat-strip">${featured.map(({ h, c }) => `<a class="feat" href="#/personnages/${encodeURIComponent(c.bundle)}/${encodeURIComponent(c.skel)}">
      <img loading="lazy" src="${esc(c.thumb)}" alt=""><span>${esc(h.label)}</span></a>`).join("")}</div>
    ${sections.map(([title, cards]) => `
      <div class="home-sec-title"><h2>${title}</h2></div>
      <div class="home-cards" style="--n:${cards.length > 4 ? 3 : cards.length}">${cards.map(([route, t, sub, img, kind, cat]) => `
        <a class="hcard ${kind ? "hc-" + kind : ""}" href="#/${route}" ${cat ? `data-cat="${cat}"` : ""}>
          <div class="hc-img">${img ? `<img loading="lazy" src="${esc(img)}" alt="">` : kind === "font" ? `<span class="hc-font">Aa 血 銀</span>` : kind === "data" ? `<span class="hc-glyph">{ }</span>` : ""}</div>
          <div class="hc-cap"><b>${esc(t)}</b><small>${esc(sub)}</small></div></a>`).join("")}</div>`).join("")}`;
  // cartes : ouvrir la page Modèles 3D directement sur la catégorie « Cartes »
  view.querySelectorAll(".hcard[data-cat]").forEach(a => a.addEventListener("click", () => { modelCat = a.dataset.cat; }));
  // image pixel art et police réelle du jeu dans leurs cartes
  need("pixel").then(P => { const x = rnd(P.filter(p => p.kind === "heros")); const box = $(".hc-pix .hc-img"); if (x && box) box.innerHTML = `<img src="${esc(x.thumb)}" alt="">`; });
  need("fonts").then(F => { const f = F.find(x => /Full/.test(x.name)) || F[0]; const el = $(".hc-font"); if (!f || !el) return;
    document.head.insertAdjacentHTML("beforeend", `<style>@font-face{font-family:"bns_home";src:url("${f.file}")}</style>`); el.style.fontFamily = "bns_home"; });
  // recherche globale : héros, pixel art, vidéos, modèles 3D
  const box = $("#homeRes"), inp = $("#homeFind");
  const search = async () => {
    const s = inp.value.trim().toLowerCase(); if (s.length < 2) { box.hidden = true; return; }
    const [M, P] = await Promise.all([need("models"), need("pixel")]);
    if (inp.value.trim().toLowerCase() !== s) return;
    const res = [
      ...H.filter(h => `${h.label} ${h.name}`.toLowerCase().includes(s)).slice(0, 6).map(h => ["Héros", h.label, heroHref(h), heroThumb(h)]),
      ...M.filter(m => m.name.toLowerCase().includes(s)).slice(0, 6).map(m => ["Modèle 3D", m.name.replace(/^[CMTGHE]_/, "").replace(/_/g, " "), `#/modeles/${m.cat}/${encodeURIComponent(m.name)}`, m.thumb]),
      ...P.filter(p => `${p.label} ${p.name}`.toLowerCase().includes(s)).slice(0, 4).map(p => ["Pixel art", p.label, `#/pixel/${encodeURIComponent(p.name)}`, p.thumb]),
      ...(D.videos || []).filter(v => (v.title || v.name || "").toLowerCase().includes(s)).slice(0, 4).map(v => ["Vidéo", v.title || v.name, `#/videos/${encodeURIComponent(v.name)}`, v.poster]),
    ];
    box.hidden = false;
    box.innerHTML = res.length ? res.map(([k, t, href, img]) => `<a href="${href}"><img src="${esc(img || "")}" alt=""><span><b>${esc(t)}</b><small>${k}</small></span></a>`).join("")
      : `<p class="kv" style="padding:10px 14px">Aucun résultat — la recherche en haut à droite filtre aussi chaque rubrique.</p>`;
  };
  let tmo; inp.oninput = () => { clearTimeout(tmo); tmo = setTimeout(search, 160); };
  inp.onkeydown = e => { if (e.key === "Enter") { const a = box.querySelector("a"); if (a) location.hash = a.getAttribute("href"); } if (e.key === "Escape") { inp.value = ""; box.hidden = true; } };
}

// ---------------------------------------------------------------- personnages
let charKind = "personnage";
// Noms explicites pour les scènes et éléments qui ne sont pas des tenues
const NAMES = {
  "activity103_hall/glass_ui": "Événement 103 — salle aux vitraux", "activity105_hourglass/m_activity5_hourglass": "Sablier (événement 105)",
  "activity108_spider/Spider": "Araignée (mini-jeu 108)", "Astel_Base_Lounge/20740_Astel": "Astel — Lounge",
  "dialog_bg/bg": "Dialogue — décor du fiacre", "dialog_fireman_talk/fireman_talk": "Dialogue — le pompier",
  "dialog_nanzhu_talk/nanzhu_talk": "Dialogue — le protagoniste", "Empusae_SP_lounge/Empusae_SP_lounge": "Empusae — Lounge",
  "fanu_base_bite/20320_Fanny_bite": "Fanny — Lounge (morsure)", "fanu_base_key/20320_Fanny_key": "Fanny — Lounge (clé)",
  "fanu_base_lounge/20320_Fanny": "Fanny — Lounge", "Form_Activity101Lamia_ShardPersonalityComplete/village_girl": "Villageoise (événement Lamia)",
  "Form_EquipmentCopyMainChoose2/dungeon_bg_spine": "Donjon — ambiance (pluie, chauves-souris)", "Form_GachaTouchNew/qiao": "Invocation — effet de toucher",
  "Form_Hall/hangup_starglobe": "Globe céleste (hall)", "Form_LegacyActivityMain/legacystage_bg": "Héritage — décor animé",
  "Form_MainExploreRemenber/mainloststoryexchange": "Histoire perdue — livre", "jacinta_cat/jacinta_cat": "Chat de Jacinta",
  "jeffrey_wofl_base/wolf": "Loup de Jeffrey", "Joan_Final_Lounge/Joan_Final_Lounge": "Joan — Lounge",
  "Typhoeus_Base_Lounge_Mecanim/20730_Typhoeus": "Typhoeus — Lounge", "Typhoeus_Base_Perfume/20730_Typhoeus_perfume": "Flacon de parfum (Typhoeus)",
  "ui_lounge_aisiti/bite_ffx": "Lounge — effet de morsure", "ui_panel_bgmain/role_blackgril": "Écran principal — la fille en noir",
  "ui_panel_bgmain/role_canglin": "Écran principal — la dame en blanc", "ui_panel_bgmain/role_Empusae": "Écran principal — Empusae",
  "ui_panel_bgmain/role_gai": "Écran principal — le majordome", "ui_panel_bgmain/role_nemont": "Écran principal — Noah au fauteuil",
  "ui_panel_bgmain/role_wolf": "Écran principal — la femme-loup", "ui_panel_bgmain/scene_chair": "Écran principal — fauteuil",
  "ui_panel_bgmain/scene_sofa": "Écran principal — canapé", "ui_panel_bgmain/scene_table": "Écran principal — table",
};
function displayName(c) { return c.kind === "personnage" ? c.name : (NAMES[c.id] || pretty(c.bundle === c.skel ? c.bundle : `${c.bundle} ${c.skel}`)); }
const heroOf = id => (D.heroes || []).find(h => h.id === id);
// tenue jouable -> fiche Spine animée si présente sur le téléphone
const spineOfSkin = s => (D.characters || []).find(c => c.skinId === s.skinId && c.kind === "personnage") ||
                         (D.characters || []).find(c => c.bundle.toLowerCase() === s.bundle.toLowerCase());
const heroThumb = h => { const sk = h.skins.map(spineOfSkin).find(Boolean); return sk ? sk.thumb : (h.skins[0] || {}).illusThumb; };
const heroHref = h => { const sk = h.skins.map(spineOfSkin).find(Boolean);
  return sk ? `#/personnages/${encodeURIComponent(sk.bundle)}/${encodeURIComponent(sk.skel)}` : `#/personnages/heros/${h.id}`; };
function characters(bundle, skel, extra) {
  if (bundle === "heros") return heroIllus(+skel, extra);
  if (bundle) return characterDetail(`${bundle}/${skel}`);
  header("Personnages", "Les héros du jeu (table officielle CharacterInfo) avec toutes leurs tenues : image fixe, animations, illustrations et portraits.");
  const body = document.createElement("div"); view.appendChild(body);
  const all = D.characters || [], heroes = D.heroes || [];
  const draw = () => {
    body.innerHTML = "";
    body.appendChild(chips([["personnage", `Héros (${heroes.length})`], ["lounge", `Scènes Lounge (${all.filter(c => c.kind === "lounge").length})`],
      ["autre", `Dialogues & interface (${all.filter(c => c.kind === "autre").length})`]], charKind, v => { charKind = v; draw(); }));
    const s = q();
    if (charKind === "personnage") {
      const items = heroes.filter(h => !s || `${h.label} ${h.name} ${h.skins.map(x => x.label + " " + x.bundle).join(" ")}`.toLowerCase().includes(s));
      const nAnim = heroes.filter(h => h.skins.some(spineOfSkin)).length;
      body.firstChild.insertAdjacentHTML("beforeend", `<span class="count">${items.length} héros · ${nAnim} animés · ${heroes.reduce((n, h) => n + h.skins.length, 0)} tenues</span>`);
      paged(body, items, h => {
        const anim = h.skins.filter(spineOfSkin).length;
        return card({ img: heroThumb(h), title: h.label,
          sub: `${h.skins.length} tenue${h.skins.length > 1 ? "s" : ""}${anim ? "" : " · illustration seule"}${h.skins.length > 1 ? " · " + h.skins.map(x => x.label).join(", ") : ""}`,
          href: heroHref(h) });
      });
    } else {
      const match = c => !s || `${c.name} ${c.skin} ${c.bundle} ${c.skel}`.toLowerCase().includes(s);
      const items = all.filter(c => c.kind === charKind && match(c)).sort((a, b) => displayName(a).localeCompare(displayName(b)));
      body.firstChild.insertAdjacentHTML("beforeend", `<span class="count">${items.length} éléments</span>`);
      paged(body, items, c => card({ img: c.thumb, title: displayName(c), sub: `${c.anims.length} animations`,
        href: `#/personnages/${encodeURIComponent(c.bundle)}/${encodeURIComponent(c.skel)}` }));
    }
  };
  window.onSearch = draw; draw();
}
// bandeau des tenues d'un héros (animées ou illustration seule) + portraits regroupés
function skinStrip(h, currentSkinId) {
  return h.skins.map(sk => {
    const c = spineOfSkin(sk);
    const href = c ? `#/personnages/${encodeURIComponent(c.bundle)}/${encodeURIComponent(c.skel)}` : `#/personnages/heros/${h.id}/${sk.skinId}`;
    return `<a class="skin${sk.skinId === currentSkinId ? " on" : ""}${c ? "" : " noanim"}" href="${href}"><img loading="lazy" src="${esc(c ? c.thumb : sk.illusThumb)}" alt=""><span>${esc(sk.label)}${c ? "" : '<span class="badge">illustration</span>'}</span></a>`;
  }).join("");
}
function heroPixel(hid, el) {
  need("pixel").then(P => { const L = P.filter(x => x.hero === hid); if (!L.length || !document.body.contains(el)) return;
    el.insertAdjacentHTML("afterbegin", `<p>${L.map(x => `<a class="btn ghost" href="#/pixel/${encodeURIComponent(x.name)}">Version pixel art${L.length > 1 ? " · " + esc(x.label) : ""}</a>`).join(" ")}</p>`); });
}
function heroPortraits(hid, el) {
  heroPixel(hid, el);
  const ports = (D.portraits || []).filter(p => p.hero === hid);
  if (!ports.length) return;
  el.insertAdjacentHTML("beforeend", `<h2>Portraits & expressions <span class="badge">${ports.length}</span></h2><div class="grid small" id="ports"></div>`);
  ports.forEach((p, i) => $("#ports").appendChild(card({ img: p.thumb, title: p.atlas === "Atlas_Roleskin" ? "Illustration de tenue" : p.name.replace(/^.*?\d{3}_?/, "") || p.name,
    sub: p.atlas.replace(/^Atlas_/, ""), onClick: () => lightbox(ports, i) })));
}
function heroIllus(hid, skinId) {
  window.onSearch = null;
  const h = heroOf(hid);
  if (!h) { view.innerHTML = `<p class="empty">Introuvable.</p>`; return; }
  const sk = h.skins.find(x => x.skinId === skinId) || h.skins[0];
  view.innerHTML = `<p><a href="#/personnages">← Personnages</a></p>
    <h1>${esc(h.label)} <span style="color:var(--muted)">· ${esc(sk.label)}</span></h1>
    <p class="kv">Héros n° <b>${h.id}</b> · tenue n° <b>${esc(sk.skinId)}</b> · animation <b>non présente sur le téléphone</b> (tenue jamais téléchargée) : illustration seule.</p>
    ${h.skins.length > 1 ? `<div class="skins">${skinStrip(h, sk.skinId)}</div>` : ""}
    <div class="detail"><div><div class="stage"><img src="${esc(sk.illus)}" alt=""></div></div><div id="side"></div></div>`;
  heroPortraits(h.id, $("#side"));
}
function characterDetail(id) {
  window.onSearch = null;
  const c = (D.characters || []).find(x => x.id === id);
  if (!c) { view.innerHTML = `<p class="empty">Introuvable.</p>`; return; }
  const hero = c.heroId ? heroOf(c.heroId) : null;
  const curSkin = hero ? hero.skins.find(x => x.skinId === c.skinId) : null;
  const skins = [c];  // le bandeau des tenues vient du héros
  const ports = [];
  view.innerHTML = `
    <p><a href="#/personnages">← Personnages</a></p>
    <h1>${esc(hero ? hero.label : displayName(c))} ${curSkin || c.skin ? `<span style="color:var(--muted)">· ${esc(curSkin ? curSkin.label : c.skin)}</span>` : ""}</h1>
    <p class="kv">Fichier <b>${esc(c.bundle)}</b> · squelette <b>${esc(c.skel)}</b>${c.skinId ? ` · tenue n° <b>${esc(c.skinId)}</b>` : ""}</p>
    ${hero && hero.skins.length > 1 ? `<div class="skins">${skinStrip(hero, c.skinId)}</div>` : ""}
    <div class="detail">
      <div><div class="stage" id="stage"><img id="stageImg" src="${esc(c.still)}" alt=""><video id="stageVid" autoplay loop muted playsinline hidden></video></div></div>
      <div>
        <h2 style="margin-top:0">Affichage</h2>
        <div class="anims" id="anims"></div>
        <p class="kv" id="animName"></p>
        <p><a class="btn ghost" id="dl" href="${esc(c.still)}" download>Télécharger</a> <a class="btn ghost" id="dl2" download hidden>WebP animé</a>
           <a class="btn ghost" id="full" href="${esc(c.still)}" target="_blank">Plein écran</a>
           ${c.spine ? `<a class="btn" href="#/spine/${encodeURIComponent(c.bundle)}/${encodeURIComponent(c.skel)}">Lecteur Spine</a>` : ""}</p>
        <div id="side"></div>
      </div>
    </div>`;
  // Animations : WebM VP9 transparent (lecteur vidéo) avec repli automatique sur le WebP animé
  const webmOf = a => `anim/${encodeURIComponent(c.bundle)}/${encodeURIComponent(c.skel)}/${encodeURIComponent(a)}.webm`;
  const webpOf = a => `${c.dir}/${encodeURIComponent(a)}.webp`;
  let useWebm = true;
  const set = key => {
    const img = $("#stageImg"), vid = $("#stageVid");
    [...$("#anims").children].forEach(b => b.classList.toggle("on", b.dataset.k === key));
    if (!key) {
      vid.pause(); vid.hidden = true; vid.removeAttribute("src"); img.hidden = false; img.src = c.still;
      $("#full").href = c.still; $("#dl").href = c.stillPng || c.still; $("#dl2").hidden = true;
      $("#animName").textContent = c.webp === false ? "Image fixe (WebP transparent haute résolution)" : "Image fixe — affichage WebP, téléchargement en PNG transparent haute résolution";
      return;
    }
    $("#dl").href = webmOf(key); $("#dl").textContent = "Télécharger (WebM)";
    $("#dl2").hidden = c.webp === false; $("#dl2").href = webpOf(key); $("#full").href = useWebm ? webmOf(key) : webpOf(key);
    if (useWebm) {
      img.hidden = true; vid.hidden = false; vid.src = webmOf(key);
      vid.onerror = () => { if (c.webp === false) return; useWebm = false; set(key); };
      vid.play().catch(() => {});
      $("#animName").textContent = `Animation « ${key} » — WebM VP9 transparent` + (c.webp === false ? "" : " (aussi disponible en WebP animé)");
    } else {
      vid.hidden = true; img.hidden = false; img.src = webpOf(key);
      $("#animName").textContent = `Animation « ${key} » — WebP animé transparent`;
    }
  };
  const btn = (key, label) => { const b = document.createElement("button"); b.className = "chip"; b.dataset.k = key; b.textContent = label; b.onclick = () => { if (!key) $("#dl").textContent = "Télécharger"; set(key); }; $("#anims").appendChild(b); };
  btn("", "Image fixe");
  const order = a => (/^idle/i.test(a) ? 0 : /^touch/i.test(a) ? 1 : /^chuchang/i.test(a) ? 2 : 3);
  [...c.anims].sort((a, b) => order(a) - order(b) || a.localeCompare(b)).forEach(a => btn(a, animLabel(a)));
  set("");
  if (hero) heroPortraits(hero.id, $("#side"));
}

// ---------------------------------------------------------------- Spine interactif
let spinePlayer = null;
function spinePage(...parts) {
  window.onSearch = null;
  const id = parts.filter(Boolean).join("/");
  const list = (D.characters || []).filter(c => c.spine);
  const c = list.find(x => x.id === id) || list.find(x => x.heroId) || list[0];
  if (!c) { view.innerHTML = `<p class="empty">Aucun squelette Spine.</p>`; return; }
  const hero = c.heroId ? heroOf(c.heroId) : null;
  const skinLabel = x => { const h = x.heroId ? heroOf(x.heroId) : null; const s = h && h.skins.find(k => k.skinId === x.skinId); return s ? s.label : x.skin; };
  const title = x => (x.heroId && heroOf(x.heroId) ? heroOf(x.heroId).label : displayName(x));
  view.innerHTML = `
    <div class="sp-layout">
      <aside class="sp-side">
        <input id="spFind" placeholder="Chercher un personnage…" autocomplete="off">
        <div class="sp-tabs" id="spTabs"></div>
        <div class="sp-list" id="spList"></div>
      </aside>
      <section class="sp-main">
        <div class="sp-head">
          <div><h1 style="margin:0">${esc(title(c))} <span style="color:var(--muted)">${skinLabel(c) ? "· " + esc(skinLabel(c)) : ""}</span></h1>
            <p class="kv" id="spInfo">Chargement…</p></div>
          <div class="sp-links">${hero ? `<a class="btn ghost" href="${heroHref(hero)}">Fiche du héros</a>` : `<a class="btn ghost" href="#/personnages/${encodeURIComponent(c.bundle)}/${encodeURIComponent(c.skel)}">Fiche</a>`}</div>
        </div>
        <div class="sp-stage bg-dark" id="spStage"><div id="spBox"></div><div class="sp-hint">Molette : zoom · glisser : déplacer · double-clic : recadrer</div></div>
        <div class="sp-bar">
          <button class="btn" id="spPlay" title="Lecture / pause (Espace)">⏸</button>
          <button class="btn ghost" id="spStep" title="Image suivante (.)">⏭ image</button>
          <label class="sp-ctl">Vitesse <select id="spSpeed">${[0.1, 0.25, 0.5, 0.75, 1, 1.5, 2].map(v => `<option value="${v}" ${v === 1 ? "selected" : ""}>×${v}</option>`).join("")}</select></label>
          <label class="sp-ctl"><input type="checkbox" id="spLoop" checked> En boucle</label>
          <span class="sp-ctl">Fond
            <button class="bgbtn bg-dark on" data-bg="bg-dark" title="Sombre"></button><button class="bgbtn bg-light" data-bg="bg-light" title="Clair"></button>
            <button class="bgbtn bg-check" data-bg="bg-check" title="Damier (transparence)"></button><button class="bgbtn bg-green" data-bg="bg-green" title="Vert (incrustation)"></button></span>
          <button class="btn ghost" id="spFit" title="Recadrer (R)">⟲ Recadrer</button>
          <button class="btn ghost" id="spShot" title="Enregistrer l'image affichée (PNG transparent)">📷 Image PNG</button>
          <span class="sp-time" id="spTime"></span>
        </div>
        <h2 class="sp-h2">Animations <small class="kv">(← → pour changer)</small></h2>
        <div class="anims" id="spAnims"></div>
        <div id="spSkinsBox" hidden><h2 class="sp-h2">Skins du squelette</h2><div class="anims" id="spSkins"></div></div>
      </section>
    </div>`;

  // ---------------- liste latérale (héros / Lounge / autres), recherche, miniature
  let tab = c.kind === "personnage" ? "personnage" : c.kind;
  const TABS = [["personnage", "Héros"], ["lounge", "Lounge"], ["autre", "Autres"]];
  const drawList = () => {
    const s = $("#spFind").value.trim().toLowerCase();
    $("#spTabs").innerHTML = TABS.map(([k, l]) => `<button class="chip ${k === tab ? "on" : ""}" data-k="${k}">${l} <small>${list.filter(x => x.kind === k).length}</small></button>`).join("");
    $("#spTabs").querySelectorAll("button").forEach(b => b.onclick = () => { tab = b.dataset.k; drawList(); });
    const items = list.filter(x => (s ? true : x.kind === tab) && (!s || `${title(x)} ${skinLabel(x)} ${x.bundle} ${x.skel}`.toLowerCase().includes(s)))
      .sort((a, b) => title(a).localeCompare(title(b)) || String(skinLabel(a)).localeCompare(String(skinLabel(b))));
    $("#spList").innerHTML = items.map(x => `<a class="sp-item ${x.id === c.id ? "on" : ""}" href="#/spine/${x.id.split("/").map(encodeURIComponent).join("/")}">
      <img loading="lazy" src="${esc(x.thumb)}" alt=""><span><b>${esc(title(x))}</b>${skinLabel(x) ? `<small>${esc(skinLabel(x))}</small>` : ""}</span></a>`).join("") || `<p class="kv">Aucun résultat.</p>`;
    const on = $("#spList .on"); if (on && !s) on.scrollIntoView({ block: "nearest" });
  };
  $("#spFind").oninput = drawList; drawList();

  // ---------------- lecteur (sans les contrôles intégrés : les nôtres en dessous)
  if (spinePlayer) { try { spinePlayer.dispose(); } catch (e) {} spinePlayer = null; }
  const base = c.spine.dir;
  let P = null, cur = null, loop = true, baseVP = null, zoom = 1, panX = 0, panY = 0;
  const order = a => (/^idle/i.test(a) ? 0 : /^touch/i.test(a) ? 1 : /^chuchang/i.test(a) ? 2 : 3);
  const setBaseVP = () => { baseVP = P && P.currentViewport ? { ...P.currentViewport } : null; zoom = 1; panX = panY = 0; };
  const play = (name, keepView) => {
    if (!P) return; cur = name; P.setAnimation(name, loop); if (!keepView) setBaseVP(); P.play(); $("#spPlay").textContent = "⏸";
    [...$("#spAnims").children].forEach(b => b.classList.toggle("on", b.dataset.k === name));
  };
  spinePlayer = new spine.SpinePlayer("spBox", {
    skelUrl: `${base}/${c.spine.skel}`, atlasUrl: `${base}/${c.spine.atlas}`, premultipliedAlpha: false,
    backgroundColor: "#00000000", alpha: true, showControls: false, preserveDrawingBuffer: true,
    viewport: { transitionTime: 0, padLeft: "6%", padRight: "6%", padTop: "6%", padBottom: "6%" },
    animation: c.anims.find(a => /^idle/i.test(a)) || undefined,
    // zoom / déplacement : appliqués au cadrage calculé par le lecteur, avant le placement de la caméra
    update: p => {
      if (!baseVP && p.currentViewport) setBaseVP();
      if (baseVP) { const w = baseVP.width / zoom, h = baseVP.height / zoom;
        p.currentViewport = { ...baseVP, x: baseVP.x + (baseVP.width - w) / 2 + panX, y: baseVP.y + (baseVP.height - h) / 2 + panY, width: w, height: h,
          padLeft: baseVP.padLeft / zoom, padRight: baseVP.padRight / zoom, padTop: baseVP.padTop / zoom, padBottom: baseVP.padBottom / zoom }; }
      const t = p.animationState && p.animationState.getCurrent(0);
      if (t && $("#spTime")) $("#spTime").textContent = `${(t.trackTime % (t.animation.duration || 1)).toFixed(2)} / ${t.animation.duration.toFixed(2)} s`;
    },
    success: p => {
      P = p;
      // Correctif runtime JS 4.1 : régions « rotate:270 » mal calculées (pièces décalées)
      const data = p.skeleton.data; let fixed = 0;
      for (const skin of data.skins) for (const m of skin.attachments) if (m) for (const a of Object.values(m)) {
        const r = a.region;
        if (r && r.degrees === 270 && r.page) { r.u2 = (r.x + r.height) / r.page.width; r.v2 = (r.y + r.width) / r.page.height; if (a.updateRegion) a.updateRegion(); fixed++; }
      }
      const anims = data.animations.map(a => a.name).sort((a, b) => order(a) - order(b) || a.localeCompare(b));
      $("#spInfo").textContent = `${anims.length} animations · ${data.skins.length} skin${data.skins.length > 1 ? "s" : ""} · squelette ${c.skel}${fixed ? ` · ${fixed} pièces corrigées` : ""}`;
      $("#spAnims").innerHTML = anims.map(a => `<button class="chip" data-k="${esc(a)}" title="${esc(a)}">${esc(animLabel(a))}</button>`).join("");
      $("#spAnims").querySelectorAll("button").forEach(b => b.onclick = () => play(b.dataset.k));
      if (data.skins.length > 1) {
        $("#spSkinsBox").hidden = false;
        $("#spSkins").innerHTML = data.skins.map(s => `<button class="chip ${s.name === (p.skeleton.skin || data.defaultSkin).name ? "on" : ""}" data-k="${esc(s.name)}">${esc(s.name)}</button>`).join("");
        $("#spSkins").querySelectorAll("button").forEach(b => b.onclick = () => { p.skeleton.setSkinByName(b.dataset.k); p.skeleton.setSlotsToSetupPose();
          [...$("#spSkins").children].forEach(x => x.classList.toggle("on", x === b)); });
      }
      play(anims.find(a => /^idle/i.test(a)) || anims[0]);
    },
    error: (p, msg) => { if ($("#spInfo")) $("#spInfo").textContent = "Erreur : " + msg + " — ouvrez le site via « Ouvrir le site.bat » (serveur local requis)."; },
  });

  // ---------------- contrôles
  const stage = $("#spStage");
  $("#spPlay").onclick = () => { if (!P) return; if (P.paused) { P.play(); $("#spPlay").textContent = "⏸"; } else { P.pause(); $("#spPlay").textContent = "▶"; } };
  $("#spStep").onclick = () => { if (!P) return; P.pause(); $("#spPlay").textContent = "▶"; P.animationState.update(1 / 30); P.animationState.apply(P.skeleton); P.skeleton.updateWorldTransform(); };
  $("#spSpeed").onchange = e => { if (P) P.speed = +e.target.value; };
  $("#spLoop").onchange = e => { loop = e.target.checked; if (cur) play(cur, true); };
  document.querySelectorAll(".bgbtn").forEach(b => b.onclick = () => { stage.className = "sp-stage " + b.dataset.bg; document.querySelectorAll(".bgbtn").forEach(x => x.classList.toggle("on", x === b)); });
  $("#spFit").onclick = () => { zoom = 1; panX = panY = 0; };
  $("#spShot").onclick = () => { const cv = $("#spBox canvas"); if (!cv) return; const a = document.createElement("a");
    a.download = `${c.skel}_${cur || "image"}.png`; a.href = cv.toDataURL("image/png"); a.click(); };
  stage.addEventListener("wheel", e => { e.preventDefault(); zoom = Math.min(20, Math.max(0.2, zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15))); }, { passive: false });
  let drag = null;
  stage.addEventListener("pointerdown", e => { drag = [e.clientX, e.clientY]; stage.setPointerCapture(e.pointerId); stage.classList.add("grab"); });
  stage.addEventListener("pointermove", e => { if (!drag || !baseVP) return; const k = baseVP.width / zoom / stage.clientWidth;
    panX -= (e.clientX - drag[0]) * k; panY += (e.clientY - drag[1]) * k; drag = [e.clientX, e.clientY]; });
  stage.addEventListener("pointerup", () => { drag = null; stage.classList.remove("grab"); });
  stage.addEventListener("dblclick", () => { zoom = 1; panX = panY = 0; });
  const keys = e => {
    if (!document.body.contains(stage)) { document.removeEventListener("keydown", keys); return; }
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    const btns = [...$("#spAnims").children], i = btns.findIndex(b => b.dataset.k === cur);
    if (e.key === " ") { e.preventDefault(); $("#spPlay").click(); }
    else if (e.key === "ArrowRight" && btns.length) { e.preventDefault(); btns[(i + 1) % btns.length].click(); }
    else if (e.key === "ArrowLeft" && btns.length) { e.preventDefault(); btns[(i - 1 + btns.length) % btns.length].click(); }
    else if (e.key === "." ) $("#spStep").click();
    else if (e.key === "r" || e.key === "R") $("#spFit").click();
  };
  document.addEventListener("keydown", keys);
}

// ---------------------------------------------------------------- portraits
function portraitsPage(...parts) {
  const group = parts.filter(Boolean).join("/");
  const all = D.portraits || [];
  if (group) {  // une galerie : un héros ou une catégorie
    window.onSearch = null;
    const items = all.filter(p => p.group === group);
    view.innerHTML = `<p><a href="#/portraits">← Portraits</a></p>`;
    header(group, `${items.length} images`);
    const h = items[0] && items[0].hero ? heroOf(items[0].hero) : null;
    if (h) view.insertAdjacentHTML("beforeend", `<p><a class="btn ghost" href="${heroHref(h)}">Voir la fiche du héros</a></p>`);
    const body = document.createElement("div"); view.appendChild(body);
    // sous-groupes par atlas (illustrations de tenue, expressions par tenue, attachement…)
    const byAtlas = new Map(); items.forEach(p => { if (!byAtlas.has(p.atlas)) byAtlas.set(p.atlas, []); byAtlas.get(p.atlas).push(p); });
    for (const [atlas, list] of byAtlas) {
      const label = atlas === "Atlas_Roleskin" ? "Illustrations de tenue" : /^Atlas_Attract_/.test(atlas) ? "Scènes d'attachement"
        : /003$/.test(atlas) ? "Expressions · " + atlas.replace(/^Atlas_/, "").replace(/003$/, "").replace(/_/g, " ") : atlas.replace(/^Atlas_/, "").replace(/_/g, " ");
      body.insertAdjacentHTML("beforeend", `<div class="group-title">${esc(label)} <small>${list.length}</small></div>`);
      paged(body, list, (p, i) => card({ img: p.thumb, title: p.name.replace(/^.*?\d{3}_?/, "") || p.name, onClick: () => lightbox(list, i) }), "grid small");
    }
    return;
  }
  header("Portraits", "Illustrations de tenue, expressions de dialogue, têtes de joueur, cartes et vignettes, regroupées par héros puis par catégorie.");
  const body = document.createElement("div"); view.appendChild(body);
  const draw = () => {
    body.innerHTML = ""; const s = q();
    const groups = new Map();
    all.filter(p => !s || `${p.name} ${p.group}`.toLowerCase().includes(s)).forEach(p => { if (!groups.has(p.group)) groups.set(p.group, []); groups.get(p.group).push(p); });
    const heroesG = [...groups].filter(([g, l]) => l[0].hero).sort((a, b) => a[0].localeCompare(b[0]));
    const otherG = [...groups].filter(([g, l]) => !l[0].hero).sort((a, b) => b[1].length - a[1].length);
    const pick = l => (l.find(p => p.atlas === "Atlas_Roleskin") || l.find(p => /003$/.test(p.atlas)) || l[0]).thumb;
    const tile = ([g, l]) => card({ img: pick(l), title: g, sub: `${l.length} images`, href: `#/portraits/${g.split("/").map(encodeURIComponent).join("/")}` });
    body.insertAdjacentHTML("beforeend", `<div class="group-title">Héros <small>${heroesG.length} · ${heroesG.reduce((n, g) => n + g[1].length, 0)} images</small></div>`);
    paged(body, heroesG, tile);
    body.insertAdjacentHTML("beforeend", `<div class="group-title">Autres catégories <small>${otherG.reduce((n, g) => n + g[1].length, 0)} images</small></div>`);
    paged(body, otherG, tile);
  };
  window.onSearch = draw; draw();
}

// ---------------------------------------------------------------- galeries d'images
function imageGallery(key, title, sub, wide) {
  header(title, sub);
  const body = document.createElement("div"); view.appendChild(body);
  const draw = () => {
    body.innerHTML = ""; const s = q();
    const items = (D[key] || []).filter(p => !s || p.name.toLowerCase().includes(s));
    body.insertAdjacentHTML("beforeend", `<div class="toolbar"><span class="count">${items.length} images</span></div>`);
    paged(body, items, (p, i) => card({ img: p.thumb, title: p.name, onClick: () => lightbox(items, i) }), wide ? "grid wide" : "grid");
  };
  window.onSearch = draw; draw();
}

// ---------------------------------------------------------------- textures
function texturesPage(...parts) {
  const group = parts.filter(Boolean).join("/") || undefined;  // les dossiers contiennent des « / »
  header("Toutes les textures", "Les quelque 36 000 images extraites du jeu (textures, sprites, ciels 360° dans « Cubemaps »), classées par dossier d'origine. Recherche par nom d'image ou de dossier.");
  view.insertAdjacentHTML("beforeend", `<p class="empty" id="ld">Chargement de l'index…</p>`);
  need("textures").then(T => {
    $("#ld")?.remove();
    const groups = Object.keys(T);
    const wrap = document.createElement("div"); wrap.className = "layout2"; view.appendChild(wrap);
    wrap.innerHTML = `<div class="side" id="tside"></div><div id="tmain"></div>`;
    const flat = () => groups.flatMap(g => T[g].map(n => ({ g, n })));
    const draw = () => {
      const s = q();
      const gs = groups.filter(g => !s || g.toLowerCase().includes(s) || T[g].some(n => n.toLowerCase().includes(s)));
      $("#tside").innerHTML = `<a href="#/textures" class="${!group ? "on" : ""}">Tous les dossiers (${gs.length})</a>` +
        gs.map(g => `<a href="#/textures/${encodeURIComponent(g)}" class="${g === group ? "on" : ""}" title="${esc(g)}">${esc(g)} <span style="opacity:.6">${T[g].length}</span></a>`).join("");
      const main = $("#tmain"); main.innerHTML = "";
      let items;
      if (group && !T[group]) { main.insertAdjacentHTML("beforeend", `<p class="empty">Le dossier « ${esc(group)} » n'existe pas (images identiques regroupées dans un autre dossier).</p>`); return; }
      if (group && T[group]) items = T[group].filter(n => !s || n.toLowerCase().includes(s) || group.toLowerCase().includes(s)).map(n => ({ g: group, n }));
      else items = s ? flat().filter(x => x.n.toLowerCase().includes(s) || x.g.toLowerCase().includes(s)) : flat();
      const list = items.map(x => ({ name: `${x.g}/${x.n}`, file: `img/PNG/${x.g}/${x.n}.webp`, png: "", thumb: `thumbs/PNG/${x.g}/${x.n}.webp`, tex3d: true }));
      main.insertAdjacentHTML("beforeend", `<div class="toolbar"><b>${esc(group || "Tous les dossiers")}</b><span class="count">${list.length} images</span></div>`);
      paged(main, list, (p, i) => card({ img: p.thumb, title: p.name.split("/").pop(), sub: group ? "" : p.name.split("/").slice(0, -1).join("/"), onClick: () => lightbox(list, i) }), "grid small");
    };
    window.onSearch = draw; draw();
  });
}

// ---------------------------------------------------------------- modèles 3D
let modelCat = "personnages", viewer3d = null;
const MODEL_CATS = [["personnages", "Personnages"], ["monstres", "Monstres"], ["pnj", "PNJ & mascottes"], ["cartes", "Cartes & zones"], ["decors", "Décors"], ["objets", "Objets"], ["cinematiques", "Cinématiques"]];
function modelsPage(cat, name) {
  if (viewer3d) { viewer3d.dispose(); viewer3d = null; }
  if (name) return modelDetail(cat, name);
  header("Modèles 3D", "Personnages, monstres, PNJ, cartes, décors, objets et éléments de cinématiques du jeu, en glTF avec leurs textures, squelette et animations quand le jeu les fournit. Glisser pour tourner, molette pour zoomer ; rendu « Jeu (toon) » ou « Lumineux » au choix.");
  view.insertAdjacentHTML("beforeend", `<p class="empty" id="ld">Chargement…</p>`);
  need("models").then(M => {
    $("#ld")?.remove();
    const body = document.createElement("div"); view.appendChild(body);
    const draw = () => {
      body.innerHTML = ""; const s = q();
      body.appendChild(chips(MODEL_CATS.map(([k, l]) => [k, `${l} (${M.filter(m => m.cat === k).length})`]), modelCat, v => { modelCat = v; draw(); }));
      const items = M.filter(m => m.cat === modelCat && (!s || m.name.toLowerCase().includes(s)));
      body.firstChild.insertAdjacentHTML("beforeend", `<span class="count">${items.length} modèles</span>`);
      paged(body, items, m => card({ img: m.thumb || "", title: m.name.replace(/^[CM]_/, "").replace(/_/g, " "), sub: `${m.size} Mo${m.clips ? ` · ${m.clips} anim.` : ""}`,
        href: `#/modeles/${encodeURIComponent(m.cat)}/${encodeURIComponent(m.name)}` }));
    };
    window.onSearch = draw; draw();
  });
}
function modelDetail(cat, name) {
  window.onSearch = null;
  need("models").then(M => {
    const list = M.filter(m => m.cat === cat), i = list.findIndex(m => m.name === name), m = list[i];
    if (!m) { view.innerHTML = `<p class="empty">Introuvable.</p>`; return; }
    view.innerHTML = `<p><a href="#/modeles">← Modèles 3D</a></p><h1>${esc(m.name.replace(/^[CM]_/, "").replace(/_/g, " "))}</h1>
      <p class="kv">Fichier <b>${esc(m.name)}</b> · <span id="m3info">chargement…</span></p>
      <div class="spine-box" id="m3"></div>
      <p class="toolbar">${i > 0 ? `<a class="btn ghost" href="#/modeles/${cat}/${encodeURIComponent(list[i - 1].name)}">← Précédent</a>` : ""}
        ${i < list.length - 1 ? `<a class="btn ghost" href="#/modeles/${cat}/${encodeURIComponent(list[i + 1].name)}">Suivant →</a>` : ""}
        ${m.rig ? "" : `<a class="btn ghost" href="${esc(m.file)}" download>Télécharger le GLB</a>`}
        ${m.rig ? `<a class="btn ghost" href="${esc(m.rig)}" download>GLB riggé + animations</a>` : ""}
</p>
      <div id="m3mode"></div><div id="m3clips"></div>`;
    // rendu : « Jeu (toon) » pour les personnages, « Lumineux » pour les cartes et décors ; choix mémorisé par famille
    const fam = ["cartes", "decors", "objets", "cinematiques"].includes(cat) ? "scene" : "perso";
    let mode = (() => { try { return localStorage.getItem("rendu3d_" + fam); } catch (e) { return null; } })() || (fam === "scene" ? "lumineux" : "jeu");
    const start = () => {
      const drawMode = () => {
        const box = $("#m3mode"); if (!box) return; box.innerHTML = "";
        const bar = chips(window.Viewer3D.MODES, mode, k => { mode = k; try { localStorage.setItem("rendu3d_" + fam, k); } catch (e) {} v.setMode(k); drawMode(); });
        bar.insertAdjacentHTML("afterbegin", `<span class="kv" style="margin-right:6px">Rendu</span>`); box.appendChild(bar);
      };
      const v = viewer3d = window.Viewer3D.show($("#m3"), m.rig || m.file, info => {
        const el = $("#m3info"); if (!el || viewer3d !== v) return;  // page quittée avant la fin du chargement
        el.textContent = info.error ? "erreur : " + info.error : `${info.meshes} pièces · ${info.tris.toLocaleString("fr")} triangles`
          + (m.bones ? ` · ${m.bones} os` : "") + (info.clips && info.clips.length ? ` · ${info.clips.length} animations` : "");
        const box = $("#m3clips"); if (!box || !info.clips || !info.clips.length) return;
        const first = (info.clips.find(c => /^idle/i.test(c.name)) || info.clips[0]).name;
        const draw = cur => {
          box.innerHTML = "";
          box.appendChild(chips(info.clips.map(c => [c.name, `${c.name} (${c.duration}s)`]), cur, n => { v.play(n); draw(n); }));
        };
        v.play(first); draw(first);
      }, { mode, shadow: fam !== "scene" });
      drawMode();
    };
    window.Viewer3D ? start() : window.addEventListener("viewer3d-ready", start, { once: true });
  });
}

// ---------------------------------------------------------------- shaders
// Coloration légère du code (GLSL / ShaderLab) : commentaires, chaînes, directives, mots-clés, types, nombres, uniformes « _Nom »
const GLSL_KW = /\b(if|else|for|while|return|discard|break|continue|in|out|inout|uniform|layout|precision|highp|mediump|lowp|const|struct|flat|void|true|false|Shader|Properties|SubShader|Pass|Tags|Cull|ZWrite|ZTest|Blend|LOD|Fallback|Off|On|Back|Front)\b/;
const GLSL_TY = /\b(float|int|uint|bool|vec[234]|ivec[234]|uvec[234]|bvec[234]|mat[234](x[234])?|sampler2D|samplerCube|sampler3D|sampler2DShadow|sampler2DArray|Color|Vector|Float|Range|2D|Cube|Int)\b/;
function highlight(code) {
  const rx = /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("[^"\n]*")|(^[ \t]*#[^\n]*)|(\b\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\b)|(\b_[A-Za-z][A-Za-z0-9_]*\b)|(\b[A-Za-z_][A-Za-z0-9_]*\b)/gm;
  return code.replace(rx, (m, com, str, dir, num, uni, word) => {
    if (com) return `<span class="c-com">${esc(com)}</span>`;
    if (str) return `<span class="c-str">${esc(str)}</span>`;
    if (dir) return `<span class="c-dir">${esc(dir)}</span>`;
    if (num) return `<span class="c-num">${num}</span>`;
    if (uni) return `<span class="c-uni">${uni}</span>`;
    if (GLSL_KW.test(word) && word.match(GLSL_KW)[0] === word) return `<span class="c-kw">${word}</span>`;
    if (GLSL_TY.test(word) && word.match(GLSL_TY)[0] === word) return `<span class="c-ty">${word}</span>`;
    return esc(word);
  });
}
// propriétés lues dans le bloc Properties du .shader : [attributs] _Nom ("Libellé", Type) = défaut
function shaderProps(txt) {
  const m = txt.match(/Properties \{\n([\s\S]*?)\n  \}/); if (!m) return [];
  return m[1].split("\n").map(l => l.trim().match(/^((?:\[[^\]]*\]\s*)*)(\w+) \("(.*)", (.+?)\) = (.*)$/)).filter(Boolean)
    .map(x => ({ attrs: x[1].trim(), name: x[2], label: x[3], type: x[4], def: x[5] }));
}
let shaderView = null, shaderPrev = null;
const SHADER_NOTES = {
  "Sprites/Mask": "Ce shader n'écrit qu'un masque (stencil) pour découper d'autres sprites : il n'affiche rien seul.",
  "Unlit/PlanarShadow": "Projette l'ombre d'un personnage sur le sol (plan défini à l'exécution) : rien à voir seul.",
  "TextMeshPro/Distance Field SSD": "Texte en champ de distance : il lui faut l'atlas de la police, chargé à l'exécution (absent du téléphone).",
  "Skybox/Procedural": "Ciel calculé par Unity : aucune variante n'a été compilée pour le jeu.",
  "Hidden/Shader Graph/FallbackError": "Shader d'erreur de Unity : le magenta est voulu (matériau invalide).",
  "Hidden/Universal Render Pipeline/FallbackError": "Shader d'erreur de Unity : le magenta est voulu (matériau invalide).",
  "Nova/Chara_01_Transparent": "Pièces translucides (voiles, cristaux) : le rendu est volontairement léger.",
};
function shadersPage(...parts) {
  if (shaderPrev) { shaderPrev.dispose(); shaderPrev = null; }
  const id = parts.filter(Boolean).join("/");
  need("shaders").then(S => {
    if (id) return shaderDetail(S, id);
    header("Shaders", "Les shaders du jeu tels que livrés sur Android : définition lisible (propriétés, passes, états de rendu) et code GPU GLSL de chaque variante. Les shaders « Nova » sont ceux écrits pour Blood and Silver.");
    const body = document.createElement("div"); view.appendChild(body);
    const draw = () => {
      body.innerHTML = ""; const s = q();
      const items = S.filter(x => !s || `${x.name} ${x.desc}`.toLowerCase().includes(s));
      for (const fam of ["Jeu (Nova)", "Unity / URP / bibliothèques"]) {
        const list = items.filter(x => x.family === fam); if (!list.length) continue;
        body.insertAdjacentHTML("beforeend", `<div class="group-title">${esc(fam)} <small>${list.length} shaders · ${list.reduce((n, x) => n + x.glsl.length, 0)} programmes</small></div>`);
        const tbl = document.createElement("div"); tbl.className = "shader-list";
        tbl.innerHTML = list.map(x => `<a class="shader-row" href="#/shaders/${x.name.split("/").map(encodeURIComponent).join("/")}">
          <b>${esc(x.name)}</b><span>${esc(x.desc || "—")}</span>
          <small>${x.props} propriétés · ${x.passes} passes · ${x.glsl.length} programmes · ${x.bundles} bundle${x.bundles > 1 ? "s" : ""}</small></a>`).join("");
        body.appendChild(tbl);
      }
      if (!items.length) body.innerHTML = `<p class="empty">Aucun résultat.</p>`;
    };
    window.onSearch = draw; draw();
  });
}
function shaderDetail(S, id) {
  window.onSearch = null;
  const sh = S.find(x => x.name === id);
  if (!sh) { view.innerHTML = `<p class="empty">Introuvable.</p>`; return; }
  // programmes regroupés par variante : NNN_PLATEFORME.vert/.frag
  const variants = new Map();
  sh.glsl.forEach(f => { const m = f.match(/(\d{3})_(\w+)\.(vert|frag)\.glsl$/); if (!m) return;
    const k = m[1]; if (!variants.has(k)) variants.set(k, {}); variants.get(k)[m[3]] = f; variants.get(k).plat = m[2]; });
  view.innerHTML = `<p><a href="#/shaders">← Shaders</a></p>
    <h1>${esc(sh.name)}</h1>
    <p class="kv">${esc(sh.desc || sh.family)} · ${sh.props} propriétés · ${sh.passes} passes · ${sh.glsl.length} programmes GPU · présent dans ${sh.bundles} bundle${sh.bundles > 1 ? "s" : ""}</p>
    <div class="sh-prev"><canvas id="shCanvas"></canvas><div class="sh-ctrl" id="shCtrl"><p class="kv">Aperçu : compilation du shader du jeu…</p></div></div>
    <p class="toolbar"><a class="btn ghost" href="${esc(sh.header)}" download>Télécharger le .shader</a></p>
    <div id="shProps"></div>
    <div class="shader-layout">
      <div class="side shader-files" id="shFiles"></div>
      <div><div class="toolbar"><b id="shTitle"></b><span class="count" id="shInfo"></span>
        <button class="btn ghost" id="shCopy">Copier</button><a class="btn ghost" id="shDl" download>Télécharger</a></div>
        <pre class="code" id="shCode"></pre></div>
    </div>`;
  // aperçu en direct : le vrai code GLSL du jeu exécuté en WebGL2 sur une pièce du jeu (ou boule / plan)
  if (shaderPrev) { shaderPrev.dispose(); shaderPrev = null; }
  try {
    const P = shaderPrev = window.ShaderPreview.create($("#shCanvas"), sh);
    const ctrl = () => {
      const box = $("#shCtrl"); if (!box || shaderPrev !== P) return;
      const m = P.materials[P.material];
      box.innerHTML = `
        ${P.materials.length ? `<label>Matériau du jeu <select id="spMat">${P.materials.map((x, i) => `<option value="${i}" ${i === P.material ? "selected" : ""}>${esc(x.material)}${x.object ? " — " + esc(x.object) : ""}</option>`).join("")}</select></label>` : `<p class="kv">Aucun matériau du jeu trouvé : valeurs par défaut du shader.</p>`}
        <label>Géométrie <select id="spGeo">${[["piece", "Pièce du jeu"], ["boule", "Boule"], ["plan", "Plan"]].filter(([k]) => k !== "piece" || (m && m.mesh)).map(([k, l]) => `<option value="${k}" ${k === P.geometry ? "selected" : ""}>${l}</option>`).join("")}</select></label>
        ${P.variants.length > 1 ? `<label>Variante compilée <select id="spVar">${P.variants.map((v, i) => `<option value="${i}" ${i === P.variant ? "selected" : ""}>Variante ${+v.id + 1}${i === 0 ? " (la plus complète)" : ""}</option>`).join("")}</select></label>` : ""}
        <p class="kv">${m ? `Textures : ${Object.entries(m.textures).filter(([k, t]) => t.file || t.cube).map(([k]) => esc(k)).join(", ") || "aucune"}<br>` : ""}
        ${P.error ? `<span style="color:#ff8a8a">${esc(P.error)}</span>` : "Glisser pour tourner, molette pour zoomer."}</p>
        ${SHADER_NOTES[sh.name] ? `<p class="kv">ℹ ${esc(SHADER_NOTES[sh.name])}</p>` : ""}`;
      $("#spMat") && ($("#spMat").onchange = e => P.setMaterial(+e.target.value).then(ctrl));
      $("#spGeo").onchange = e => P.setGeometry(e.target.value).then(ctrl);
      $("#spVar") && ($("#spVar").onchange = e => P.setVariant(+e.target.value).then(ctrl));
    };
    P.onInfo = ctrl; P.ready.then(ctrl).catch(e => { if ($("#shCtrl")) $("#shCtrl").innerHTML = `<p class="kv">Aperçu impossible : ${esc(e.message)}</p>`; });
  } catch (e) { $("#shCtrl").innerHTML = `<p class="kv">Aperçu impossible : ${esc(e.message)}</p>`; }
  const files = [["Définition (.shader)", sh.header]];
  for (const [k, v] of variants) {
    if (v.vert) files.push([`Variante ${+k + 1} · sommets (${v.plat})`, v.vert]);
    if (v.frag) files.push([`Variante ${+k + 1} · fragments (${v.plat})`, v.frag]);
  }
  const box = $("#shFiles");
  box.innerHTML = files.map(([l, f], i) => `<a data-i="${i}" href="javascript:void 0">${esc(l)}</a>`).join("");
  let cur = "";
  const open = i => {
    const [label, f] = files[i]; cur = f; const tok = shaderView = {};
    [...box.children].forEach((a, j) => a.classList.toggle("on", j === i));
    $("#shTitle").textContent = label; $("#shDl").href = f; $("#shCode").textContent = "Chargement…";
    fetch(f).then(r => r.text()).then(t => {
      if (shaderView !== tok || !$("#shCode")) return;
      const lines = t.replace(/\r\n/g, "\n").split("\n");
      $("#shInfo").textContent = `${lines.length} lignes`;
      $("#shCode").innerHTML = highlight(t.replace(/\r\n/g, "\n")).split("\n").map((l, n) => `<span class="ln">${n + 1}</span>${l}`).join("\n");
      $("#shCopy").onclick = () => navigator.clipboard?.writeText(t).then(() => { $("#shCopy").textContent = "Copié ✓"; setTimeout(() => { if ($("#shCopy")) $("#shCopy").textContent = "Copier"; }, 1500); });
      if (i === 0 && $("#shProps") && !$("#shProps").childElementCount) {
        const P = shaderProps(t.replace(/\r\n/g, "\n"));
        if (P.length) $("#shProps").innerHTML = `<details class="props" open><summary>Propriétés réglables (${P.length})</summary><table class="ptable">
          <tr><th>Nom</th><th>Libellé d'origine</th><th>Type</th><th>Défaut</th></tr>
          ${P.map(p => `<tr><td><code>${esc(p.name)}</code>${p.attrs ? `<br><small>${esc(p.attrs)}</small>` : ""}</td><td>${esc(p.label)}</td><td>${esc(p.type)}</td><td><code>${esc(p.def)}</code></td></tr>`).join("")}
          </table></details>`;
      }
    });
  };
  box.querySelectorAll("a").forEach(a => a.onclick = () => open(+a.dataset.i));
  open(0);
}

// ---------------------------------------------------------------- pixel art (mode AFK)
let pixKind = "heros";
const PIX_KINDS = [["heros", "Héros"], ["monstre", "Monstres"], ["objet", "Objets & décor"], ["sol", "Cartes de sol"]];
function pixelPage(name) {
  need("pixel").then(P => {
    if (name) return pixelDetail(P, name);
    header("Pixel art (mode AFK)", "Les versions pixel des héros, monstres et objets du mode « AFK », recomposées à partir des sprites et des animations du jeu, et les cartes de sol défilantes.");
    const body = document.createElement("div"); view.appendChild(body);
    const draw = () => {
      body.innerHTML = ""; const s = q();
      body.appendChild(chips(PIX_KINDS.map(([k, l]) => [k, `${l} (${P.filter(x => x.kind === k).length})`]), pixKind, v => { pixKind = v; draw(); }));
      const items = P.filter(x => x.kind === pixKind && (!s || `${x.label} ${x.name}`.toLowerCase().includes(s)));
      paged(body, items, x => { const c = card({ img: x.thumb, title: x.label, sub: x.clips.length ? `${x.clips.length} animations` : x.kind === "sol" ? "carte défilante" : "image",
        href: `#/pixel/${encodeURIComponent(x.name)}` }); c.classList.add("pix"); return c; }, pixKind === "sol" ? "grid wide" : "grid");
    };
    window.onSearch = draw; draw();
  });
}
function pixelDetail(P, name) {
  window.onSearch = null;
  const x = P.find(p => p.name === name);
  if (!x) { view.innerHTML = `<p class="empty">Introuvable.</p>`; return; }
  const h = x.hero ? heroOf(x.hero) : null;
  view.innerHTML = `<p><a href="#/pixel">← Pixel art</a></p><h1>${esc(x.label)}</h1>
    <p class="kv">Fichier <b>${esc(x.name)}</b>${h ? ` · <a href="${heroHref(h)}">fiche du héros</a>` : ""}</p>
    <div class="detail"><div><div class="stage pixstage ${x.kind === "sol" ? "wide" : ""}"><img id="pxImg" src="${esc(x.still)}" alt=""></div></div>
      <div><h2 style="margin-top:0">Affichage</h2><div class="anims" id="pxAnims"></div><p class="kv" id="pxInfo"></p>
      <p><a class="btn ghost" id="pxDl" href="${esc(x.png)}" download>Télécharger</a> <a class="btn ghost" id="pxFull" href="${esc(x.png)}" target="_blank">Taille réelle</a></p></div></div>`;
  const set = c => {
    [...$("#pxAnims").children].forEach(b => b.classList.toggle("on", b.dataset.k === (c ? c.name : "")));
    const src = c ? c.file : x.still; $("#pxImg").src = src; $("#pxDl").href = c ? c.file : x.png; $("#pxFull").href = c ? c.file : x.png;
    $("#pxInfo").textContent = c ? `Animation « ${c.name} » — ${c.duration} s, WebP animé sans perte (pixels nets)` : "Image fixe (PNG transparent)";
  };
  const btn = (c, label) => { const b = document.createElement("button"); b.className = "chip"; b.dataset.k = c ? c.name : ""; b.textContent = label; b.onclick = () => set(c); $("#pxAnims").appendChild(b); };
  btn(null, "Image fixe"); x.clips.forEach(c => btn(c, c.name.replace(/_/g, " ")));
  set(x.clips.find(c => /^idle/i.test(c.name)) || null);
}

// ---------------------------------------------------------------- polices
function fontsPage() {
  need("fonts").then(F => {
    header("Polices", "Les polices de caractères livrées avec le jeu (TrueType), avec un aperçu modifiable.");
    const css = F.map(f => `@font-face{font-family:"bns_${f.name}";src:url("${f.file}")}`).join("");
    view.insertAdjacentHTML("beforeend", `<style>${css}</style>
      <div class="toolbar"><input id="fontTxt" style="flex:1;min-width:240px" value="Blood and Silver — Le sang et l'argent 0123456789 · 血与银 · 銀と血 · 은과 피"><input id="fontSz" type="range" min="14" max="72" value="34"></div>
      <div id="fontList"></div>`);
    const draw = () => {
      const t = $("#fontTxt").value, sz = $("#fontSz").value;
      $("#fontList").innerHTML = F.map(f => `<div class="font-row"><div class="kv"><b>${esc(f.name)}</b> · ${f.size} Ko · <a href="${esc(f.file)}" download>télécharger</a></div>
        <div class="font-sample" style="font-family:'bns_${esc(f.name)}';font-size:${sz}px">${esc(t)}</div></div>`).join("");
    };
    $("#fontTxt").oninput = draw; $("#fontSz").oninput = draw; draw();
  });
}

// ---------------------------------------------------------------- vidéos
let vidKind = "tout";
function videosPage(name) {
  if (name) return videoDetail(name);
  header("Vidéos", "Cinématiques d'ultime et séquences du jeu. Sous-titres disponibles en 9 langues quand le jeu en fournit.");
  const body = document.createElement("div"); view.appendChild(body);
  const draw = () => {
    body.innerHTML = ""; const s = q();
    const kinds = ["tout", ...new Set((D.videos || []).map(v => v.kind))];
    body.appendChild(chips(kinds.map(k => [k, k === "tout" ? "Toutes" : k]), vidKind, v => { vidKind = v; draw(); }));
    const items = (D.videos || []).filter(v => (vidKind === "tout" || v.kind === vidKind) && (!s || v.name.toLowerCase().includes(s)));
    paged(body, items, v => card({ img: v.poster, title: v.name, sub: `${v.kind}${v.subs.length ? " · sous-titres" : ""}`, href: `#/videos/${encodeURIComponent(v.name)}` }), "grid wide");
  };
  window.onSearch = draw; draw();
}
function videoDetail(name) {
  window.onSearch = null;
  const all = D.videos || [], i = all.findIndex(v => v.name === name), v = all[i];
  if (!v) { view.innerHTML = `<p class="empty">Introuvable.</p>`; return; }
  view.innerHTML = `<p><a href="#/videos">← Vidéos</a></p><h1>${esc(v.name)}</h1>
    <div class="video-stage"><video controls autoplay preload="metadata" poster="${esc(v.poster)}">
      ${v.webm ? `<source src="${esc(v.webm)}" type='video/webm; codecs="vp9, opus"'>` : ""}
      <source src="${esc(v.file)}" type="video/mp4">
      ${v.subs.map((s, k) => `<track kind="subtitles" srclang="${esc(s.lang)}" label="${esc(s.label)}" src="${esc(s.src)}" ${k === 0 ? "default" : ""}>`).join("")}
    </video></div>
    <p class="toolbar">${i > 0 ? `<a class="btn ghost" href="#/videos/${encodeURIComponent(all[i - 1].name)}">← Précédente</a>` : ""}
      ${i < all.length - 1 ? `<a class="btn ghost" href="#/videos/${encodeURIComponent(all[i + 1].name)}">Suivante →</a>` : ""}
      ${v.webm ? `<a class="btn ghost" href="${esc(v.webm)}" download>Télécharger (WebM)</a>` : ""}
      <a class="btn ghost" href="${esc(v.file)}" download>Télécharger (MP4)</a></p>`;
}

// ---------------------------------------------------------------- audio
let audCat = "Musiques", audLang = "";
function audioPage() {
  header("Audio", "Toutes les pistes du jeu, converties depuis les banques Wwise et nommées d'après les fichiers du jeu.");
  const body = document.createElement("div"); view.appendChild(body);
  const all = D.audio || [];
  const cats = [...new Set(all.map(a => a.cat))].sort();
  const draw = () => {
    body.innerHTML = ""; const s = q();
    body.appendChild(chips(cats.map(c => [c, `${c} (${all.filter(a => a.cat === c).length})`]), audCat, v => { audCat = v; audLang = ""; draw(); }));
    const langs = [...new Set(all.filter(a => a.cat === audCat).map(a => a.lang))].sort();
    if (langs.length > 1) body.appendChild(chips([["", "Toutes langues"], ...langs.map(l => [l, l])], audLang, v => { audLang = v; draw(); }));
    const items = all.filter(a => a.cat === audCat && (!audLang || a.lang === audLang) &&
      (!s || `${a.name} ${(a.events || []).join(" ")} ${(a.banks || []).join(" ")}`.toLowerCase().includes(s)));
    body.insertAdjacentHTML("beforeend", `<div class="toolbar"><span class="count">${items.length} pistes</span></div>`);
    paged(body, items, a => {
      const r = document.createElement("div"); r.className = "arow" + (PL.cur === a ? " playing" : "");
      r.innerHTML = `<div class="p">▶</div><div class="n" title="${esc(a.name)}">${esc(a.name)}${a.subs ? " 💬" : ""}</div><div class="m">${esc(a.lang !== "SFX" ? a.lang : "")} ${esc((a.banks || [])[0] || "")}</div>`;
      r.onclick = () => { play(a, items); document.querySelectorAll(".arow.playing").forEach(x => x.classList.remove("playing")); r.classList.add("playing"); };
      return r;
    }, "alist");
  };
  window.onSearch = draw; draw();
}
const PL = { el: $("#player"), audio: $("#player audio"), cur: null, list: [], cues: [] };
function fmt(t) { t = Math.max(0, t || 0); return `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`; }
async function loadCues(src) {
  try {
    const txt = (await (await fetch(src)).text()).replace(/\r/g, ""); const toS = h => { const [a, b, c] = h.split(":"); return +a * 3600 + +b * 60 + parseFloat(c); };
    return [...txt.matchAll(/(\d\d:\d\d:\d\d\.\d+)\s*-->\s*(\d\d:\d\d:\d\d\.\d+)[^\n]*\n([\s\S]*?)(?:\n\n|$)/g)].map(m => ({ a: toS(m[1]), b: toS(m[2]), t: m[3].trim() }));
  } catch (e) { return []; }
}
async function play(a, list) {
  PL.cur = a; PL.list = list || [a]; PL.el.hidden = false;
  $(".pl-title", PL.el).textContent = a.name;
  $(".pl-meta", PL.el).textContent = [a.cat, a.lang !== "SFX" ? a.lang : "", (a.events || [])[0]].filter(Boolean).join(" · ");
  PL.audio.src = a.file; PL.audio.play();
  $(".pl-dl", PL.el).innerHTML = `<a href="${esc(a.file)}" download>OGG</a>`;
  PL.cues = [];
  const sub = (a.subs || []).find(s => s.lang === "fr") || (a.subs || [])[0];
  if (sub) PL.cues = await loadCues(sub.src);
}
PL.audio.addEventListener("timeupdate", () => {
  const t = PL.audio.currentTime, d = PL.audio.duration || 0;
  $(".pl-seek", PL.el).value = d ? (t / d) * 1000 : 0;
  $(".pl-time", PL.el).textContent = `${fmt(t)} / ${fmt(d)}`;
  const c = PL.cues.find(c => t >= c.a && t <= c.b); $(".pl-sub", PL.el).textContent = c ? c.t : "";
});
PL.audio.addEventListener("play", () => $(".pl-play", PL.el).textContent = "❚❚");
PL.audio.addEventListener("pause", () => $(".pl-play", PL.el).textContent = "▶");
PL.audio.addEventListener("ended", () => { const i = PL.list.indexOf(PL.cur); if (i >= 0 && i < PL.list.length - 1) play(PL.list[i + 1], PL.list); });
$(".pl-play", PL.el).onclick = () => PL.audio.paused ? PL.audio.play() : PL.audio.pause();
$(".pl-seek", PL.el).oninput = e => { if (PL.audio.duration) PL.audio.currentTime = e.target.value / 1000 * PL.audio.duration; };
$(".pl-close", PL.el).onclick = () => { PL.audio.pause(); PL.el.hidden = true; };

// ---------------------------------------------------------------- textes & données
function textsPage(sub, name) {
  const T = D.texts || { interface: [], activites: [] };
  header("Données du jeu", "Textes d'interface en 9 langues, textes d'événements, et contenu brut des 372 tables de configuration du jeu.");
  view.appendChild(chips([["interface", `Interface multilingue (${T.interface.length})`], ["activites", `Événements (${T.activites.length})`], ["tables", "Tables du jeu (372)"]],
    sub || "interface", v => { location.hash = `#/textes/${v}`; }));
  const body = document.createElement("div"); view.appendChild(body);
  if (!sub || sub === "interface") {
    const langs = [...new Set(T.interface.flatMap(r => Object.keys(r)))];
    const order = ["Français", "English", ...langs.filter(l => l !== "Français" && l !== "English")];
    const draw = () => {
      const s = q(); const rows = T.interface.filter(r => !s || Object.values(r).join(" ").toLowerCase().includes(s));
      body.innerHTML = `<table class="tx"><tr>${order.map(l => `<th>${esc(l)}</th>`).join("")}</tr>${rows.map(r => `<tr>${order.map(l => `<td>${esc(r[l] || "")}</td>`).join("")}</tr>`).join("")}</table>`;
    };
    window.onSearch = draw; draw();
  } else if (sub === "activites") {
    const draw = () => {
      const s = q(); const rows = T.activites.filter(r => !s || (r.key + r.text).toLowerCase().includes(s));
      body.innerHTML = `<table class="tx"><tr><th>Clé</th><th>Texte</th></tr>${rows.map(r => `<tr><td class="kv">${esc(r.key)}</td><td>${esc(r.text).replace(/\n/g, "<br>")}</td></tr>`).join("")}</table>`;
    };
    window.onSearch = draw; draw();
  } else {
    body.innerHTML = `<p class="empty">Chargement…</p>`;
    need("tables").then(TB => {
      const names = Object.keys(TB);
      const draw = () => {
        const s = q();
        const ns = names.filter(n => !s || n.toLowerCase().includes(s) || TB[n].some(x => x.toLowerCase().includes(s)));
        const cur = name && TB[name] ? name : ns[0];
        body.innerHTML = `<div class="layout2"><div class="side">${ns.map(n => `<a href="#/textes/tables/${encodeURIComponent(n)}" class="${n === cur ? "on" : ""}">${esc(n)} <span style="opacity:.6">${TB[n].length}</span></a>`).join("")}</div>
          <div><h2 style="margin-top:0">${esc(cur || "")}</h2><p class="kv">Chaînes lisibles extraites de la table (identifiants, noms, textes).</p>
          <pre class="strings">${esc((TB[cur] || []).filter(x => !s || x.toLowerCase().includes(s) || (cur || "").toLowerCase().includes(s)).join("\n"))}</pre></div></div>`;
      };
      window.onSearch = draw; draw();
    });
  }
}

route();
