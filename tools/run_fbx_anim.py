r"""Convertit les GLB riggés (Site\models_anim, modèles avec animations) en FBX armature + animations,
4 Blender en parallèle. -> Site\models_anim_fbx\<cat>\<n>.fbx"""
from config import PROJECT, TOOLS_DIR, BLENDER  # chemins : voir tools/config.py
import os, json, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor

SITE = PROJECT + r"\Site"
BL = BLENDER
A = json.load(open(os.path.join(SITE, "models_anim", "anim.json"), encoding="utf-8"))
pairs = [(os.path.join(SITE, a["file"]), os.path.join(SITE, "models_anim_fbx", a["cat"], a["name"] + ".fbx")) for a in A if a["clips"]]
todo = [p for p in pairs if not os.path.exists(p[1])]
print(len(pairs), "modèles animés,", len(todo), "à convertir", flush=True)

def run(chunk):
    lst = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    lst.write("\n".join("\t".join(p) for p in chunk)); lst.close()
    out = subprocess.run([BL, "-b", "--factory-startup", "-P", TOOLS_DIR + r"\glb2fbx_anim.py", "--", lst.name],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    os.remove(lst.name)
    return [l for l in out.splitlines() if l.startswith(("OK", "ERREUR"))]

with ThreadPoolExecutor(4) as ex:
    res = [l for r in ex.map(run, [todo[i::4] for i in range(4)]) for l in r]
want = {a["name"]: len(a["clips"]) for a in A}
bad = []
for l in res:
    if l.startswith("ERREUR"): bad.append(l); continue
    n = l.split()[1][:-4]; got = int(l.split("clips=")[1].split("/")[0])
    if got < want.get(n, 0): bad.append(f"{n}: {got}/{want[n]} clips après réimport")
sz = sum(os.path.getsize(p[1]) for p in pairs if os.path.exists(p[1]))
print(f"TERMINE {sum(os.path.exists(p[1]) for p in pairs)}/{len(pairs)} FBX animés, {len(bad)} problèmes, {sz/2**30:.1f} Go", flush=True)
for b in bad[:20]: print(b, flush=True)
