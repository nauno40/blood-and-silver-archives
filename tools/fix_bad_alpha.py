"""Réexporte les modèles listés dans bad_alpha.json (GLB + FBX) avec la règle de transparence corrigée."""
import json, os, glob, subprocess

SITE = r"E:\Projets\BloodAndSilver\Site"
PY = r"C:\Users\Nauno\.bns_tools\venv\Scripts\python.exe"
names = json.load(open(r"C:\Users\Nauno\.bns_tools\bad_alpha.json"))
for n in names:
    for p in glob.glob(os.path.join(SITE, "models", "*", n + ".glb")) + glob.glob(os.path.join(SITE, "models", "*", n + ".webp")) + \
             glob.glob(os.path.join(SITE, "models_fbx", "*", n + ".fbx")):
        os.remove(p)
print(len(names), "modèles à refaire", flush=True)
# export_3d.py saute les GLB déjà présents : seuls les modèles supprimés sont refaits
r = subprocess.run([PY, "-u", r"C:\Users\Nauno\.bns_tools\export_3d.py"] + [n + ".unity3d" for n in names], capture_output=True, text=True)
print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-500:], flush=True)
r = subprocess.run([PY, "-u", r"C:\Users\Nauno\.bns_tools\run_fbx.py"], capture_output=True, text=True)
print("\n".join(r.stdout.strip().splitlines()[-3:]), flush=True)
missing = [n for n in names if not glob.glob(os.path.join(SITE, "models", "*", n + ".glb"))]
print("GLB manquants après réexport :", missing, flush=True)
