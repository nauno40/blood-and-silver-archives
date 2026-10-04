"""Régénère toutes les images fixes, refait entièrement les squelettes listés dans FULL,
puis reconstruit le dossier Images_fixes."""
import json, os, shutil, subprocess
from concurrent.futures import ThreadPoolExecutor

SPINE = r"E:\Projets\BloodAndSilver\Spine"
ANIM = r"E:\Projets\BloodAndSilver\Animations"
STILLS = r"E:\Projets\BloodAndSilver\Images_fixes"
RENDER = r"C:\Users\Nauno\.bns_tools\render\render.mjs"
FULL = {r"Joan_Final_Lounge\Joan_Final_Lounge", r"Typhoeus_Base_Lounge_Mecanim\20730_Typhoeus"}

# mêmes squelettes que le rendu (doublons exclus) = dossiers présents dans Animations
folders = [os.path.relpath(os.path.join(r, d), ANIM) for r, ds, _ in os.walk(ANIM) for d in ds
           if os.path.exists(os.path.join(r, d, "_image_fixe.png"))]

def job(folder):
    args = ["node", RENDER, os.path.join(SPINE, folder), os.path.join(ANIM, folder)]
    if folder not in FULL:
        args += ["--only", "none"]
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return folder, p.returncode, (p.stderr or "")[-300:]

with ThreadPoolExecutor(6) as ex:
    for folder, rc, err in ex.map(job, folders):
        print(("OK " if rc == 0 else "ERREUR ") + folder + ("" if rc == 0 else " " + err), flush=True)

# reconstruction du dossier des images fixes (même nommage qu'avant)
shutil.rmtree(STILLS, ignore_errors=True); os.makedirs(STILLS)
for folder in folders:
    bundle, skel = folder.split(os.sep)
    multi = len([d for d in os.listdir(os.path.join(ANIM, bundle)) if os.path.isdir(os.path.join(ANIM, bundle, d))]) > 1
    name = f"{bundle} - {skel}" if multi else bundle
    shutil.copy2(os.path.join(ANIM, folder, "_image_fixe.png"), os.path.join(STILLS, name + ".png"))
print("TERMINE", len(folders), "images fixes")
