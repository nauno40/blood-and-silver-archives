r"""Convertit tous les GLB du site en FBX (textures intégrées) avec 4 Blender en parallèle,
puis vérifie chaque FBX par réimport. Site\models\<cat>\<n>.glb -> Site\models_fbx\<cat>\<n>.fbx"""
import os, glob, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor

SITE = r"E:\Projets\BloodAndSilver\Site"
BL = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
TOOLS = r"C:\Users\Nauno\.bns_tools"
pairs = []
for g in sorted(glob.glob(os.path.join(SITE, "models", "*", "*.glb"))):
    f = os.path.join(SITE, "models_fbx", os.path.basename(os.path.dirname(g)), os.path.splitext(os.path.basename(g))[0] + ".fbx")
    pairs.append((g, f))
todo = [p for p in pairs if not os.path.exists(p[1])]
print(len(pairs), "modèles,", len(todo), "à convertir", flush=True)

def run(script, chunk):
    lst = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    lst.write("\n".join("\t".join(p) for p in chunk)); lst.close()
    out = subprocess.run([BL, "-b", "--factory-startup", "-P", os.path.join(TOOLS, script), "--", lst.name],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    os.remove(lst.name)
    return [l for l in out.splitlines() if l.startswith(("OK", "ERREUR", "IDENTIQUE", "DIFFERENT"))]

def split(lst, n): return [lst[i::n] for i in range(n)]

with ThreadPoolExecutor(4) as ex:
    res = [l for r in ex.map(lambda c: run("glb2fbx.py", c), split(todo, 4)) for l in r]
err = [l for l in res if l.startswith("ERREUR")]
print("conversion :", sum(1 for l in res if l.startswith("OK")), "OK,", len(err), "erreurs", err[:5], flush=True)

done = [p for p in pairs if os.path.exists(p[1])]
with ThreadPoolExecutor(4) as ex:
    chk = [l for r in ex.map(lambda c: run("check_fbx.py", c), split(done, 4)) for l in r]
diff = [l for l in chk if l.startswith("DIFFERENT")]
sz = sum(os.path.getsize(p[1]) for p in done)
print(f"TERMINE {len(done)}/{len(pairs)} FBX, vérifiés identiques {len(chk) - len(diff)}, différents {len(diff)}, {sz/2**20:.0f} Mo", flush=True)
for l in diff[:10]: print(l, flush=True)
