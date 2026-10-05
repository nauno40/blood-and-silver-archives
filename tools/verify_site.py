r"""Vérification complète du site : chaque fichier référencé par les données existe et n'est pas vide."""
from config import PROJECT  # chemins : voir tools/config.py
import json, os, urllib.parse
from collections import Counter

SITE = PROJECT + r"\Site"
def load(n):
    t = open(os.path.join(SITE, "data", n + ".js"), encoding="utf-8").read()
    return json.loads(t[t.index("] = ") + 4: t.rstrip().rindex(";")])
checked, bad = Counter(), []
REL = load("stats").get("release", False)
# racines distribuées dans les archives de la Release (tout fichier référencé doit s'y trouver)
PACK = ["Site/img", "Site/thumbs", "Site/anim", "Site/audio", "Site/videos", "Site/videos_webm", "Site/posters", "Site/subs",
        "Site/models", "Site/models_anim", "Site/shader_preview", "Site/spine", "Site/pixel", "Site/shaders", "Site/polices"]
ROOTDIR = os.path.dirname(SITE); outside = Counter()
def chk(kind, p):
    if not p:
        bad.append((kind, "(chemin vide)")); return
    f = os.path.normpath(os.path.join(SITE, urllib.parse.unquote(p)))
    checked[kind] += 1
    if not os.path.isfile(f) or os.path.getsize(f) == 0: bad.append((kind, p))
    r_ = os.path.relpath(f, ROOTDIR).replace(os.sep, "/")
    if not r_.startswith("Site/") or r_.count("/") > 1:
        if not any(r_.startswith(x + "/") for x in PACK) and not r_.startswith(("Site/lib/", "Site/data/")) and r_.count("/") > 1: outside[kind] += 1

for c in load("characters"):
    chk("personnage: image fixe (WebP)", c["still"]); chk("personnage: image fixe (PNG)", c["stillPng"]); chk("personnage: miniature", c["thumb"])
    for a in c["anims"]:
        if c.get("webp", True): chk("animation WebP", f'{c["dir"]}/{a}.webp')
        chk("animation WebM", f'anim/{c["bundle"]}/{c["skel"]}/{a}.webm')
    if c["spine"]:
        chk("Spine (skel+atlas)", f'{c["spine"]["dir"]}/{c["spine"]["skel"]}'); chk("Spine (skel+atlas)", f'{c["spine"]["dir"]}/{c["spine"]["atlas"]}')
for n in ("portraits", "mainbg", "backgrounds"):
    for p in load(n):
        chk(f"{n} (WebP)", p["file"])
        if p.get("png"): chk(f"{n} (PNG)", p["png"])
        chk(f"{n} (miniature)", p["thumb"])
for g, names in load("textures").items():
    for x in names:
        chk("texture (WebP)", f"img/PNG/{g}/{x}.webp")
        if not REL: chk("texture (PNG)", f"../PNG/{g}/{x}.png")
        chk("texture (miniature)", f"thumbs/PNG/{g}/{x}.webp")
for v in load("videos"):
    chk("vidéo MP4", v["file"]); chk("vidéo WebM", v.get("webm")); chk("vidéo affiche", v["poster"])
    for s in v["subs"]: chk("sous-titres", s["src"])
for a in load("audio"):
    chk("son Ogg", a["file"])
    for s in a.get("subs", []): chk("sous-titres", s["src"])
for m in load("models"):
    chk("modèle GLB", m["file"]); chk("modèle vignette", m["thumb"])
for m in load("models"):
    if m.get("rig"): chk("modèle riggé GLB", m["rig"])
for h in load("heroes"):
    for s_ in h["skins"]:
        if s_.get("illus"): chk("héros: illustration de tenue", s_["illus"]); chk("héros: miniature tenue", s_["illusThumb"])
for sh in load("shaders"):
    chk("shader: définition", sh["header"])
    for g in sh["glsl"]: chk("shader: GLSL", g)
    if sh.get("preview"):
        mj = os.path.join(SITE, sh["preview"], "material.json"); chk("shader: aperçu material.json", sh["preview"] + "/material.json")
        for mt in json.load(open(mj, encoding="utf-8"))["materials"]:
            if mt.get("mesh"): chk("shader: pièce de maillage", sh["preview"] + "/" + mt["mesh"])
            for t in mt["textures"].values():
                if t.get("file"): chk("shader: texture", sh["preview"] + "/" + t["file"])
                for c in t.get("cube", []): chk("shader: texture cube", sh["preview"] + "/" + c)
for x in load("pixel"):
    chk("pixel: image fixe", x["still"]); chk("pixel: PNG", x["png"]); chk("pixel: miniature", x["thumb"])
    for c in x["clips"]: chk("pixel: animation", c["file"])
for f in load("fonts"): chk("police", f["file"])
for f in ("index.html", "app.js", "style.css", "viewer3d.js", "serveur.py", "shader_preview.js", "lib/spine-player.min.js", "lib/three/three.module.min.js",
          "lib/three/GLTFLoader.js", "lib/three/OrbitControls.js", "lib/three/BufferGeometryUtils.js", "data/tables.js", "data/texts.js", "data/heroes.js", "data/shaders.js", "data/pixel.js", "data/fonts.js"):
    chk("fichiers du site", f)

print(f"{sum(checked.values())} fichiers vérifiés")
for k, n in sorted(checked.items()): print(f"  {n:7}  {k}")
print(f"PROBLEMES : {len(bad)}")
for k, n in Counter(k for k, _ in bad).items(): print(f"  {n:7}  {k}")
for b in bad[:15]: print("   ", b)

# --- cohérence entre rubriques ----------------------------------------------------------------------
print("\nCOHÉRENCE")
H, C, M, P, S = load("heroes"), load("characters"), load("models"), load("pixel"), load("shaders")
ids = {c["id"] for c in C}
pb = []
names = Counter(h["label"] for h in H); pb += [f"héros en double : {n}" for n, k in names.items() if k > 1]
for h in H:
    if not h["skins"]: pb.append(f"héros sans tenue : {h['label']}")
for c in C:
    if c["kind"] == "personnage" and not c.get("heroId"): pb.append(f"Spine « personnage » non rattaché à un héros : {c['id']}")
mn = Counter((m["cat"], m["name"]) for m in M); pb += [f"modèle en double : {k}" for k, n in mn.items() if n > 1]
for m in M:
    if not m.get("thumb", "").endswith(".webp"): pb.append(f"modèle sans vignette : {m['name']}")
hid = {h["id"] for h in H}
for x in P:
    if x.get("hero") and x["hero"] not in hid: pb.append(f"pixel rattaché à un héros inconnu : {x['name']}")
port = load("portraits")
for p_ in port:
    if p_.get("hero") and p_["hero"] not in hid: pb.append(f"portrait rattaché à un héros inconnu : {p_['name']}")
print(f"  héros {len(H)} (animés {len({c.get('heroId') for c in C if c.get('heroId')})}) · tenues {sum(len(h['skins']) for h in H)} · Spine {len(C)}")
print(f"  modèles 3D {len(M)} · riggés {sum(1 for m in M if m.get('rig'))} · shaders {len(S)} (aperçu {sum(1 for x in S if x.get('preview'))}) · pixel {len(P)}")
print(f"  PROBLEMES DE COHERENCE : {len(pb)}")
for x in pb[:30]: print("   ", x)

print(f"MODE RELEASE : {REL} — fichiers référencés hors des archives : {sum(outside.values())}", dict(outside))
