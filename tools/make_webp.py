r"""Versions WebP pleine résolution de toutes les images, pour l'affichage dans le site.
Qualité 92 (visuellement identique), canal alpha sans perte. Les PNG d'origine restent la référence
(boutons « Télécharger »). Sortie : <projet>\Site\img\<chemin relatif>.webp"""
from config import PROJECT  # chemins : voir tools/config.py
import os, glob, sys
from concurrent.futures import ProcessPoolExecutor
from PIL import Image

ROOT = PROJECT
OUT = os.path.join(ROOT, "Site", "img")
SOURCES = ["PNG", "Images_fixes", "Fonds_ecran", "Fonds_ecran_principal", "Site/pixel"]  # images sources (originaux)

def job(src):
    dst = os.path.join(OUT, os.path.splitext(os.path.relpath(src, ROOT))[0] + ".webp")
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return 0, os.path.getsize(src), os.path.getsize(dst)
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im = Image.open(src); im.load()
        if im.mode not in ("RGB", "RGBA"): im = im.convert("RGBA" if "A" in im.getbands() or im.mode == "P" else "RGB")
        # WebP est limité à 16383 px de côté
        if max(im.size) > 16383: im.thumbnail((16383, 16383))
        im.save(dst, "WEBP", quality=92, alpha_quality=100, method=5)
        return 1, os.path.getsize(src), os.path.getsize(dst)
    except Exception as e:
        print("ERREUR", src, e, flush=True)
        return -1, 0, 0

if __name__ == "__main__":
    files = [f for d in SOURCES for f in glob.glob(os.path.join(ROOT, d, "**", "*.png"), recursive=True)]
    files += glob.glob(os.path.join(ROOT, "Animations", "*", "*", "_image_fixe.png"))
    print(len(files), "images", flush=True)
    n = err = 0; s_in = s_out = 0
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for k, (r, a, b) in enumerate(ex.map(job, files, chunksize=32), 1):
            if r < 0: err += 1
            n += r > 0; s_in += a; s_out += b
            if k % 3000 == 0: print(f"{k}/{len(files)}", flush=True)
    print(f"TERMINE {n} converties, {err} erreurs, PNG {s_in/2**30:.2f} Go -> WebP {s_out/2**30:.2f} Go", flush=True)
