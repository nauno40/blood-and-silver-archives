"""Régénère séquentiellement toutes les images fixes puis reconstruit Images_fixes."""
import os, shutil, subprocess

SPINE = r"E:\Projets\BloodAndSilver\Spine"
ANIM = r"E:\Projets\BloodAndSilver\Animations"
STILLS = r"E:\Projets\BloodAndSilver\Images_fixes"
RENDER = r"C:\Users\Nauno\.bns_tools\render\render.mjs"

folders = sorted(os.path.relpath(os.path.join(r, d), ANIM) for r, ds, _ in os.walk(ANIM) for d in ds
                 if os.path.exists(os.path.join(r, d, "_image_fixe.png")))
err = 0
for i, folder in enumerate(folders, 1):
    p = subprocess.run(["node", RENDER, os.path.join(SPINE, folder), os.path.join(ANIM, folder), "--only", "none"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        err += 1
        print("ERREUR", folder, (p.stderr or "")[-300:], flush=True)
    if i % 25 == 0:
        print(f"{i}/{len(folders)} erreurs={err}", flush=True)

shutil.rmtree(STILLS, ignore_errors=True); os.makedirs(STILLS)
for folder in folders:
    bundle, skel = folder.split(os.sep)
    multi = len([d for d in os.listdir(os.path.join(ANIM, bundle)) if os.path.isdir(os.path.join(ANIM, bundle, d))]) > 1
    shutil.copy2(os.path.join(ANIM, folder, "_image_fixe.png"),
                 os.path.join(STILLS, (f"{bundle} - {skel}" if multi else bundle) + ".png"))
print(f"TERMINE {len(folders)} images fixes, erreurs={err}", flush=True)
