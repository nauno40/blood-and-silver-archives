"""Liste les modèles 3D « en plus » des personnages / monstres / décors : cartes et zones, PNJ et mascottes, objets,
éléments de cinématiques (à partir du recensement census.json). Écrit :
  extra_cats.json  {bundle: catégorie}  (lu par export_3d.py / export_rigged.py pour ranger les modèles)
  extra_files.txt  chemins complets des bundles (entrée de « export_3d.py @extra_files.txt »)"""
import os, re, json
from config import ASSETS, TOOLS_DIR  # chemins : voir tools/config.py

C = json.load(open(os.path.join(TOOLS_DIR, "census.json"), encoding="utf-8"))
EXCL = re.compile(r"(?i)_shadow|rogue_inst|_mob$|_annex$|cameraani|_U$")
cats, files = {}, []
for rel, v in sorted(C.items()):
    t = v.get("types", {}); mr = t.get("MeshRenderer", 0) + t.get("SkinnedMeshRenderer", 0)
    if not mr: continue
    b = os.path.splitext(os.path.basename(rel))[0]; folder = rel.split(os.sep)[0]
    if folder == "UI" or re.match(r"(?i)^(fx|form|ui)", b) or EXCL.search(b): continue
    if folder == "ABResource" and (b.startswith(("C_", "M_")) or "SceneRoot" in b): continue  # export standard
    if b.startswith(("T_", "G_", "H_")): c = "pnj"
    elif b.startswith(("B_", "E_")): c = "cinematiques"
    elif b.startswith(("C_", "M_")): continue
    elif mr >= 15 or folder == "Scenes": c = "cartes"
    else: c = "objets"
    cats[b] = c; files.append(os.path.join(ASSETS, rel))
json.dump(cats, open(os.path.join(TOOLS_DIR, "extra_cats.json"), "w"), indent=0)
open(os.path.join(TOOLS_DIR, "extra_files.txt"), "w", encoding="utf-8").write("\n".join(files))
from collections import Counter
print(len(cats), "modèles en plus :", dict(Counter(cats.values())))
