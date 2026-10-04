r"""Miniatures WebP (360 px max) de toutes les images pour le site.
Source -> <projet>\Site\thumbs\<même chemin relatif>.webp"""
from config import PROJECT  # chemins : voir tools/config.py
import os, glob
from concurrent.futures import ProcessPoolExecutor
from PIL import Image

ROOT = PROJECT
DIRS = ["PNG", "Images_fixes", "Fonds_ecran", "Fonds_ecran_principal", "Pixel_AFK"]
OUT = os.path.join(ROOT, "Site", "thumbs")

def job(src):
    rel = os.path.relpath(src, ROOT)
    dst = os.path.join(OUT, os.path.splitext(rel)[0] + ".webp")
    if os.path.exists(dst): return 0
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im = Image.open(src); im.thumbnail((360, 360))
        im.save(dst, "WEBP", quality=80, method=4)
        return 1
    except Exception:
        return 0

if __name__ == "__main__":
    files = [f for d in DIRS for f in glob.glob(os.path.join(ROOT, d, "**", "*.*"), recursive=True)
             if f.lower().endswith((".png", ".jpg"))]
    # images fixes des animations (_image_fixe.png) aussi
    files += glob.glob(os.path.join(ROOT, "Animations", "*", "*", "_image_fixe.png"))
    print(len(files), "images", flush=True)
    n = 0
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 4)) as ex:
        for k, r in enumerate(ex.map(job, files, chunksize=64), 1):
            n += r
            if k % 5000 == 0: print(k, flush=True)
    print("TERMINE", n, "miniatures", flush=True)
