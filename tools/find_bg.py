"""Repère les fonds d'écran parmi les textures extraites (PNG/) :
grandes images (>= 1000 px de large), en paysage, quasi entièrement opaques.
Écrit la liste dans bg_candidates.json."""
from config import PROJECT, TOOLS_DIR  # chemins : voir tools/config.py
import glob, json, os
from concurrent.futures import ProcessPoolExecutor
from PIL import Image

ROOT = PROJECT + r"\PNG"

def check(p):
    try:
        im = Image.open(p)
        w, h = im.size
        if w < 1000 or h < 500 or w / h < 1.2:
            return None
        im = im.convert("RGBA")
        small = im.resize((64, max(1, int(64 * h / w))))
        a = small.getchannel("A")
        opaque = sum(1 for v in a.getdata() if v > 240) / (small.width * small.height)
        if opaque < 0.97:
            return None
        # écarte les images quasi unies (masques, dégradés plats)
        rgb = small.convert("L")
        lo, hi = rgb.getextrema()
        if hi - lo < 40:
            return None
        return {"path": p, "w": w, "h": h}
    except Exception:
        return None

if __name__ == "__main__":
    files = glob.glob(os.path.join(ROOT, "**", "*.png"), recursive=True)
    with ProcessPoolExecutor() as ex:
        res = [r for r in ex.map(check, files, chunksize=64) if r]
    res.sort(key=lambda r: -r["w"] * r["h"])
    json.dump(res, open(TOOLS_DIR + r"\bg_candidates.json", "w", encoding="utf-8"), indent=1)
    print(len(files), "images analysées,", len(res), "candidats")
    from collections import Counter
    print(Counter(os.path.relpath(r["path"], ROOT).split(os.sep)[0] for r in res))
