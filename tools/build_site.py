r"""Génère les données du site E:\Projets\BloodAndSilver\Site (fichiers data/*.js chargés par index.html).
Chemins des médias relatifs au dossier Site (../Animations/..., ../PNG/..., etc.)."""
import os, re, json, glob, shutil, subprocess, struct
from collections import defaultdict
import UnityPy

ROOT = r"E:\Projets\BloodAndSilver"
SITE = os.path.join(ROOT, "Site")
ASSETS = os.path.join(ROOT, r"data\com.moonton.silverblood.eu\files\dragon2019\assets")
FF = r"C:\Users\Nauno\.bns_tools\venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
DATA = os.path.join(SITE, "data")
os.makedirs(DATA, exist_ok=True)

def rel(p): return os.path.relpath(p, SITE).replace("\\", "/")
def web(p):
    w = os.path.join(SITE, "img", os.path.splitext(os.path.relpath(p, ROOT))[0] + ".webp")
    return rel(w) if os.path.exists(w) else rel(p)
def thumb(p):
    t = os.path.join(SITE, "thumbs", os.path.splitext(os.path.relpath(p, ROOT))[0] + ".webp")
    return rel(t) if os.path.exists(t) else rel(p)
def write(name, obj):
    with open(os.path.join(DATA, name + ".js"), "w", encoding="utf-8") as f:
        f.write(f"window.DATA = window.DATA || {{}}; window.DATA[{json.dumps(name)}] = ")
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print("data/%s.js" % name, len(obj) if hasattr(obj, "__len__") else "")

# --- tables de configuration (Document) ------------------------------------------------------
d = open(os.path.join(ASSETS, "Document", "Document.unity3d"), "rb").read(); i = d.find(b"UnityFS\x00")
env = UnityPy.load(d[i:])
tables = {}
for o in env.objects:
    if o.type.name == "TextAsset":
        t = o.read(); s = t.m_Script
        tables[t.m_Name] = s.encode("utf-8", "surrogateescape") if isinstance(s, str) else bytes(s)

def strings(b, minlen=2):
    txt = b.decode("utf-8", "replace")
    return [s.strip() for s in re.findall(r"[^\x00-\x1f\ufffd]{%d,}" % minlen, txt) if s.strip()]

# --- personnages : nom + tenue depuis FashionInfo -------------------------------------------
fs = [x.decode("latin1") for x in re.findall(rb"[\x20-\x7e]{3,}", tables["FashionInfo"])]
fashion = {}
for k, s in enumerate(fs):
    m = re.match(r"Atlas_Roleskin/(\d+)$", s)
    if m and k + 1 < len(fs):
        portrait = fs[k - 1].split("/")[-1]
        base = re.sub(r"\d+$", "", portrait)  # Agares_Past003 -> Agares_Past
        parts = base.split("_", 1)
        fashion.setdefault(fs[k + 1].lower(), {"name": parts[0], "skin": parts[1] if len(parts) > 1 else "Base",
                                              "skinId": m.group(1), "portrait": portrait})

ANIM = os.path.join(ROOT, "Animations")
SPINE = os.path.join(ROOT, "Spine")
chars = []
for still in sorted(glob.glob(os.path.join(ANIM, "*", "*", "_image_fixe.png")), key=str.lower):
    sdir = os.path.dirname(still); bundle = os.path.basename(os.path.dirname(sdir)); skel = os.path.basename(sdir)
    f = fashion.get(bundle.lower())
    anims = sorted(os.path.splitext(os.path.basename(w))[0] for w in glob.glob(os.path.join(sdir, "*.webp")))
    # dossier Spine source (le nom de bundle a pu être renommé pour les doublons)
    spdir = os.path.join(SPINE, bundle, skel)
    if not os.path.isdir(spdir):
        cand = glob.glob(os.path.join(SPINE, "*", skel))
        spdir = cand[0] if cand else None
    spine = None
    if spdir:
        files = os.listdir(spdir)
        sk = next((x for x in files if x.endswith(".skel")), None); at = next((x for x in files if x.endswith(".atlas")), None)
        if sk and at: spine = {"dir": rel(spdir), "skel": sk, "atlas": at}
    kind = "personnage" if f else ("lounge" if "lounge" in bundle.lower() or bundle.lower().startswith("ui_lounge") else "autre")
    chars.append({"id": f"{bundle}/{skel}", "bundle": bundle, "skel": skel,
                  "name": f["name"] if f else bundle, "skin": f["skin"] if f else "", "skinId": f["skinId"] if f else "",
                  "kind": kind, "still": web(still), "stillPng": rel(still), "thumb": thumb(still),
                  "dir": rel(sdir), "anims": anims, "spine": spine})
write("characters", chars)

# portraits / cartes des personnages (atlas d'interface)
# portraits : expressions de dialogue (Atlas_<Perso>_<Tenue>003), illustrations de tenue (Atlas_Roleskin),
# têtes de joueur, cartes et vignettes de héros
portraits = []
pdirs = [d_ for d_ in glob.glob(os.path.join(ROOT, "PNG", "UI", "Atlas_*"))
         if re.search(r"\d{3}$", os.path.basename(d_)) or re.match(r"Atlas_(Roleskin|Playerhead|AFKRole|Hero-\d|HeroShow|PersonCard|MallRoleTrial)",
                                                                  os.path.basename(d_))]
for d_ in sorted(pdirs, key=str.lower):
    for p in sorted(glob.glob(os.path.join(d_, "*.png"))):
        portraits.append({"file": web(p), "png": rel(p), "thumb": thumb(p), "name": os.path.splitext(os.path.basename(p))[0],
                          "atlas": os.path.basename(d_)})
write("portraits", portraits)
for c in chars:
    f = fashion.get(c["bundle"].lower())
    c["portraitKey"] = re.sub(r"\d+$", "", f["portrait"]) if f else ""

# --- héros officiels (table CharacterInfo) et leurs tenues (FashionInfo) ---------------------------
def hero_id_before(b, pos):
    for off in range(pos - 4, max(0, pos - 400), -1):
        v = struct.unpack_from("<I", b, off)[0]
        if 20000 <= v <= 20999 and v % 10 == 0: return v
    return None
heroes = {}
ci = tables["CharacterInfo"]
for m in re.finditer(rb"Atlas_Role/([A-Za-z_]+?)_([A-Za-z]+)\d{3}", ci):
    hid = hero_id_before(ci, m.start())
    if hid is None or hid in heroes: continue
    nm, var = m.group(1).decode(), m.group(2).decode()
    label = nm.replace("_", " ") + ("" if var in ("Base", "Full", "Veil", "Doll") or var.lower() in nm.lower() else f" {var}")
    heroes[hid] = {"id": hid, "name": nm, "label": label, "skins": []}
fi = tables["FashionInfo"]
bundle_hero = {}
for m in re.finditer(rb"Atlas_Roleskin/(\d+)", fi):
    hid = hero_id_before(fi, m.start())
    after = re.findall(rb"[\x20-\x7e]{3,}", fi[m.end():m.end() + 80]); before = re.findall(rb"[\x20-\x7e]{3,}", fi[max(0, m.start() - 120):m.start()])
    bundle = after[0].decode() if after else ""; portrait = before[-1].decode().split("/")[-1] if before else ""
    if hid not in heroes: continue
    h = heroes[hid]; sid = m.group(1).decode()
    if any(s["skinId"] == sid for s in h["skins"]):  # même tenue, autre bundle (ex. nevernight_final)
        bundle_hero.setdefault(bundle.lower(), (hid, sid)); continue
    pbase = re.sub(r"\d+$", "", portrait)
    skin_label = pbase[len(h["name"]):].strip("_") if pbase.lower().startswith(h["name"].lower()) else pbase
    variant = h["label"][len(h["name"].replace("_", " ")):].strip()  # ex. « Covenant » pour Aiona Covenant
    if variant and skin_label.lower().startswith(variant.lower()): skin_label = skin_label[len(variant):].strip("_ ")
    illus = os.path.join(ROOT, "PNG", "UI", "Atlas_Roleskin", sid + ".png")
    h["skins"].append({"skinId": sid, "bundle": bundle, "label": skin_label.replace("_", " ") or "Base", "portraitBase": pbase,
                       "illus": web(illus) if os.path.exists(illus) else "", "illusThumb": thumb(illus) if os.path.exists(illus) else ""})
    bundle_hero.setdefault(bundle.lower(), (hid, sid))
heroes = {k: v for k, v in heroes.items() if v["skins"]}  # fiche 20000 (Noah de l'histoire) : aucune tenue jouable
for c in chars:
    hs = bundle_hero.get(c["bundle"].lower())
    if hs: c["heroId"], c["skinId"] = hs[0], hs[1]
# portraits rattachés à leur héros (illustrations de tenue, expressions, attachement) ou à une catégorie
pb2hero = {s["portraitBase"].lower(): hid for hid, h in heroes.items() for s in h["skins"]}
name2hero = {}
for hid, h in sorted(heroes.items()):
    name2hero.setdefault(h["name"].lower(), hid)
sid2hero = {s["skinId"]: hid for hid, h in heroes.items() for s in h["skins"]}
CATS = [(r"^Atlas_Playerhead", "Têtes de joueur"), (r"^Atlas_AFKRole", "Personnages pixel (AFK)"), (r"^Atlas_Hero", "Icônes de héros"),
        (r"^Atlas_MallRoleTrial", "Essais en boutique"), (r"^Atlas_(Activity|MiniGame)", "Événements et mini-jeux"), (r"^Atlas_PersonCard", "Cartes")]
for p in portraits:
    a = p["atlas"]; hid = None
    if a == "Atlas_Roleskin": hid = sid2hero.get(re.sub(r"_\d+$", "", p["name"]))
    elif re.match(r"Atlas_Attract_(\d+)", a): hid = int(re.match(r"Atlas_Attract_(\d+)", a).group(1))
    else:
        base = re.sub(r"\d{3}$", "", a[6:]).lower()
        hid = pb2hero.get(base) or name2hero.get(base.split("_")[0])
    if hid in heroes: p["hero"] = hid; p["group"] = heroes[hid]["label"]
    else: p["group"] = next((g for rx, g in CATS if re.match(rx, a)), "Autres personnages")
write("portraits", portraits)
write("heroes", sorted(heroes.values(), key=lambda h: h["label"].lower()))
print(len(heroes), "héros,", sum(len(h["skins"]) for h in heroes.values()), "tenues")
write("characters", chars)

# --- fonds ------------------------------------------------------------------------------------
write("mainbg", [{"file": web(p), "png": rel(p), "thumb": thumb(p), "name": os.path.splitext(os.path.basename(p))[0]}
                 for p in sorted(glob.glob(os.path.join(ROOT, "Fonds_ecran_principal", "*.png")))])
write("backgrounds", [{"file": web(p), "png": rel(p), "thumb": thumb(p), "name": os.path.splitext(os.path.basename(p))[0]}
                      for p in sorted(glob.glob(os.path.join(ROOT, "Fonds_ecran", "*.png")), key=str.lower)])

# --- toutes les textures (PNG/<dossier>/<bundle>/*.png) ---------------------------------------
tex = defaultdict(list)
for p in glob.glob(os.path.join(ROOT, "PNG", "**", "*.png"), recursive=True):
    r = os.path.relpath(p, os.path.join(ROOT, "PNG")).split(os.sep)
    group = "/".join(r[:-1])
    tex[group].append(os.path.splitext(r[-1])[0])
write("textures", {g: sorted(v, key=str.lower) for g, v in sorted(tex.items(), key=lambda kv: kv[0].lower())})

# --- vidéos + sous-titres (srt -> vtt) + affiches ----------------------------------------------
SUBS = os.path.join(SITE, "subs"); POST = os.path.join(SITE, "posters")
os.makedirs(SUBS, exist_ok=True); os.makedirs(POST, exist_ok=True)
LANGS = {"fr": "Français", "en": "English", "de": "Deutsch", "es": "Español", "ja": "日本語", "ko": "한국어",
         "th": "ไทย", "zh-CHS": "简体中文", "zh-CHT": "繁體中文"}
subs = defaultdict(dict)
for s in glob.glob(os.path.join(ASSETS, "Subtitle", "*.srt")):
    m = re.match(r"(.+)_([a-z]{2}(?:-[A-Za-z]+)?)$", os.path.splitext(os.path.basename(s))[0])
    if not m: continue
    base, lang = m.groups()
    txt = open(s, encoding="utf-8-sig", errors="replace").read().replace("\r\n", "\n").replace("\r", "\n")
    vtt = "WEBVTT\n\n" + re.sub(r"(\d\d:\d\d:\d\d),(\d\d\d)", r"\1.\2", txt)
    out = os.path.join(SUBS, f"{base}_{lang}.vtt"); open(out, "w", encoding="utf-8").write(vtt)
    subs[base][lang] = rel(out)
videos = []
for v in sorted(glob.glob(os.path.join(ASSETS, "Video", "*.mp4")), key=str.lower):
    base = os.path.splitext(os.path.basename(v))[0]
    mp4 = os.path.join(SITE, "videos", base + ".mp4")  # copie sans perte, index en tête (remux_videos.py)
    if os.path.exists(mp4): v = mp4
    poster = os.path.join(POST, base + ".webp")
    if not os.path.exists(poster):
        subprocess.run([FF, "-v", "error", "-y", "-ss", "1.5", "-i", v, "-frames:v", "1", "-vf", "scale=480:-2", poster])
    kind = "Ultime (cut-in)" if re.search(r"(?i)maxskill|cut[il]n", base) else ("Histoire" if re.match(r"(?i)[A-E]_\d", base) else "Autre")
    wm = os.path.join(SITE, "videos_webm", base + ".webm")
    videos.append({"file": rel(v), "webm": rel(wm) if os.path.exists(wm) else "", "name": base, "kind": kind, "poster": rel(poster) if os.path.exists(poster) else "",
                   "subs": [{"lang": l, "label": LANGS.get(l, l), "src": p} for l, p in sorted(subs.get(base, {}).items(), key=lambda kv: kv[0] != "fr")]})
write("videos", videos)

# --- audio (manifeste produit par convert_audio.py) + sous-titres des cinématiques audio ----------
aj = os.path.join(SITE, "audio", "audio.json")
audio = json.load(open(aj, encoding="utf-8")) if os.path.exists(aj) else []
for a in audio:
    mp3 = "audio_mp3/" + os.path.splitext(a["file"][len("audio/"):])[0] + ".mp3"
    if os.path.exists(os.path.join(SITE, mp3)): a["mp3"] = mp3  # MP3 lu en priorité, Ogg en secours
    if a["name"] in subs: a["subs"] = [{"lang": l, "label": LANGS.get(l, l), "src": p} for l, p in subs[a["name"]].items()]
write("audio", audio)

# --- textes : multilingue (InitLangTxt), activités, tables de configuration ---------------------
LANGID = {"6": "简体中文", "10": "English", "14": "Français", "15": "Deutsch", "22": "日本語", "23": "한국어",
          "34": "Español", "36": "ไทย", "41": "繁體中文"}
init = []
for blob in re.split(r"[\x00-\x08]", tables.get("InitLangTxt", b"").decode("utf-8", "replace")):
    parts = re.findall(r"##(\d+):([^#]*)", blob)
    if parts:
        init.append({LANGID.get(k, k): v.strip() for k, v in parts})
acts = []
act = os.path.join(ROOT, r"data\com.moonton.silverblood.eu\files\Activity.tmp")
if os.path.exists(act):
    raw = open(act, "rb").read().decode("utf-8", "replace")
    for k, v in re.findall(r'\["([A-Za-z0-9_]+)"\]="((?:[^"\\]|\\.)*)"', raw):
        if len(v) > 2: acts.append({"key": k, "text": v.replace("\\n", "\n")})
write("texts", {"interface": init, "activites": acts})
mj = os.path.join(SITE, "models", "models.json")
models = json.load(open(mj, encoding="utf-8")) if os.path.exists(mj) else []
for m in models:
    t = os.path.join(SITE, "models", m["cat"], m["name"] + ".webp")
    m["thumb"] = rel(t) if os.path.exists(t) else ""
    fb = os.path.join(SITE, "models_fbx", m["cat"], m["name"] + ".fbx")
    m["fbx"] = rel(fb) if os.path.exists(fb) else ""
aj = os.path.join(SITE, "models_anim", "anim.json")
anims = {a["name"]: a for a in json.load(open(aj, encoding="utf-8"))} if os.path.exists(aj) else {}
for m in models:
    a = anims.get(m["name"])
    if a and a["clips"] and os.path.exists(os.path.join(SITE, a["file"])):
        m["rig"] = a["file"]; m["clips"] = len(a["clips"]); m["bones"] = a.get("bones", 0)
        fb = os.path.join(SITE, "models_anim_fbx", m["cat"], m["name"] + ".fbx")
        m["rigfbx"] = rel(fb) if os.path.exists(fb) else ""
write("models", models)

# --- shaders (Shaders\<dossier>\<nom>.shader + glsl\*.glsl, voir extract_shaders.py) -------------------
SH = os.path.join(ROOT, "Shaders"); shaders = []
DESC = {"Nova/Chara_01": "Personnages : ombrage toon par rampe, contour, liseré, matcap, scintillement, dissolution",
        "Nova/Chara_Fast_01": "Personnages, version allégée", "Nova/Chara_01_Transparent": "Personnages, pièces transparentes",
        "Nova/Chara_Fire": "Personnages en feu", "Nova/Hair_01": "Cheveux des personnages", "Nova/Face_01": "Visages des personnages",
        "Nova/FX/General": "Effets visuels (sorts, impacts…)", "Nova/FX/Transparent": "Effets visuels transparents",
        "Nova/FX/Transition": "Transitions d'écran", "Nova/Scene/Beach": "Décor de plage", "Nova/SLM": "Décors (éclairage précalculé)",
        "Nova/LHQ": "Décors haute qualité", "Nova/Sprite": "Sprites 2D", "Unlit/PlanarShadow": "Ombre projetée au sol des personnages",
        "Skybox/Cubemap": "Ciel des cartes (cubemap)", "Spine/SkeletonGraphic Additive": "Animations Spine dans l'interface"}
if os.path.exists(os.path.join(SH, "index.json")):
    for s in json.load(open(os.path.join(SH, "index.json"), encoding="utf-8")):
        d = os.path.join(SH, s["folder"])
        hdr = next((f for f in os.listdir(d) if f.endswith(".shader")), None)
        glsl = sorted(os.listdir(os.path.join(d, "glsl"))) if os.path.isdir(os.path.join(d, "glsl")) else []
        shaders.append({**s, "family": "Jeu (Nova)" if s["name"].startswith("Nova/") else "Unity / URP / bibliothèques",
                        "desc": DESC.get(s["name"], ""), "header": rel(os.path.join(d, hdr)) if hdr else "",
                        "glsl": [rel(os.path.join(d, "glsl", f)) for f in glsl],
                        "preview": "shader_preview/" + s["folder"] if os.path.exists(os.path.join(SITE, "shader_preview", s["folder"], "material.json")) else ""})
write("shaders", shaders)

# --- mode AFK (pixel art) : personnages / monstres / objets animés + cartes de sol (render_afk.py) -------------
PX = os.path.join(ROOT, "Pixel_AFK"); pixel = []
hero_by_tok = {}
for h in heroes.values():
    for s_ in h["skins"]: hero_by_tok.setdefault(s_["bundle"].lower().split("_")[0], h["id"])
    hero_by_tok.setdefault(h["name"].lower(), h["id"])
if os.path.exists(os.path.join(PX, "index.json")):
    for it in json.load(open(os.path.join(PX, "index.json"), encoding="utf-8")):
        n = it["name"]
        if it.get("ground"):
            p = os.path.join(PX, "_sols", n + ".png")
            pixel.append({"name": n, "label": "Sol " + n.split("_")[-1], "kind": "sol", "still": web(p), "png": rel(p), "thumb": thumb(p), "clips": []})
            continue
        d = os.path.join(PX, n); still = os.path.join(d, "_image_fixe.png")
        m = re.match(r"(?i)AFK_([CM])_(.+)$", n)
        kind = ("heros" if m.group(1).upper() == "C" else "monstre") if m else "objet"
        core = m.group(2) if m else re.sub(r"(?i)^afk_", "", n)
        hid = hero_by_tok.get(core.lower().split("_")[0]) if kind == "heros" else None
        pixel.append({"name": n, "label": (heroes[hid]["label"] if hid else core.replace("_", " ")) + ("" if not hid or core.lower() == heroes[hid]["name"].lower() else f" ({core.replace('_', ' ')})"),
                      "kind": kind, "hero": hid, "still": web(still), "png": rel(still), "thumb": thumb(still),
                      "clips": [{"name": c["name"], "file": rel(os.path.join(d, c["file"])), "duration": c["duration"]} for c in it.get("clips", [])]})
write("pixel", sorted(pixel, key=lambda x: x["label"].lower()))

# --- polices du jeu --------------------------------------------------------------------------------------
write("fonts", [{"name": os.path.splitext(f)[0], "file": rel(os.path.join(ROOT, "Polices", f)), "size": round(os.path.getsize(os.path.join(ROOT, "Polices", f)) / 1024)}
                for f in sorted(os.listdir(os.path.join(ROOT, "Polices"))) if f.lower().endswith((".ttf", ".otf"))] if os.path.isdir(os.path.join(ROOT, "Polices")) else [])
# --- chiffres clés pour l'accueil (petit fichier chargé d'emblée) ---------------------------------------
stats = {"heroes": len(heroes), "heroesAnimated": len({c.get("heroId") for c in chars if c.get("heroId")}), "skins": sum(len(h["skins"]) for h in heroes.values()),
         "spine": len(chars), "spineAnims": sum(len(c["anims"]) for c in chars), "portraits": len(portraits),
         "textures": sum(len(v) for v in tex.values()), "models": len(models), "modelsAnimated": sum(1 for m in models if m.get("rig")),
         "modelCats": {c_: sum(1 for m in models if m["cat"] == c_) for c_ in sorted({m["cat"] for m in models})},
         "shaders": len(shaders), "pixel": len(pixel), "pixelAnims": sum(len(x["clips"]) for x in pixel),
         "tables": len(tables),
         "modelSamples": [m["thumb"] for m in models if m["cat"] in ("personnages", "monstres") and m.get("rig")][:400:8],
         "mapSamples": [m["thumb"] for m in models if m["cat"] == "cartes" and (m.get("meshes") or 0) >= 400 and (m.get("textured") or 0) >= 0.95 * m["meshes"]]}
write("stats", stats)
write("tables",{name: strings(b)[:4000] for name, b in sorted(tables.items())})
print("OK")
