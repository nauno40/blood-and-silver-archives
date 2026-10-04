"""Extraction complémentaire : toute Texture2D / Sprite dont les pixels ne sont pas déjà présents dans PNG\
(comparaison par empreinte des pixels RGBA) est écrite dans PNG/<dossier>/<bundle>/<nom>.png.
1) index des empreintes des PNG existants (pixel_index.json, réutilisé)  2) parcours de tous les bundles."""
import os, re, json, hashlib
from concurrent.futures import ProcessPoolExecutor

ASSETS = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets"
OUT = r"E:\Projets\BloodAndSilver\PNG"
IDX = r"C:\Users\Nauno\.bns_tools\pixel_index.json"

def safe(n): return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", n).strip() or "unnamed"

def phash(im):
    import numpy as np
    a = np.asarray(im.convert("RGBA")); return hashlib.md5(a.tobytes() + str(a.shape).encode()).hexdigest()

def hash_png(p):
    from PIL import Image
    try: return phash(Image.open(p))
    except Exception: return None

def scan(path):
    import UnityPy
    out = []
    try:
        d = open(path, "rb").read(); i = d.find(b"UnityFS\x00")
        if i < 0: return out
        env = UnityPy.load(d[i:])
        for o in env.objects:
            if o.type.name not in ("Texture2D", "Sprite"): continue
            try:
                t = o.read()
                if o.type.name == "Texture2D" and (not t.m_Width or not t.m_Height): continue
                im = t.image
                if im is None or im.width * im.height == 0: continue
                out.append((o.type.name, t.m_Name, phash(im), im))
            except Exception:
                pass
    except Exception:
        pass
    return [(path, ty, n, h, im) for ty, n, h, im in out]

def work(path):
    """Renvoie [(chemin_png, empreinte)] écrits ; le tri des doublons se fait côté parent."""
    return [(ty, n, h) for _, ty, n, h, _ in scan(path)]

def write(path, keep):
    """Réouvre le bundle et écrit les images dont l'empreinte est dans keep."""
    res = []
    rel = os.path.relpath(path, ASSETS)
    folder = os.path.join(OUT, safe(rel.split(os.sep)[0]), safe(os.path.splitext(os.path.basename(path))[0]))
    for _, ty, n, h, im in scan(path):
        if h not in keep: continue
        os.makedirs(folder, exist_ok=True)
        p = os.path.join(folder, safe(n) + ".png"); k = 2
        while os.path.exists(p): p = os.path.join(folder, f"{safe(n)}_{k}.png"); k += 1
        im.save(p); res.append(h)
    return res

if __name__ == "__main__":
    pngs = [os.path.join(r, f) for r, _, fs in os.walk(OUT) for f in fs if f.endswith(".png")]
    known = json.load(open(IDX)) if os.path.exists(IDX) else {}
    todo = [p for p in pngs if p not in known]
    print(len(pngs), "PNG existants,", len(todo), "à indexer", flush=True)
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for p, h in zip(todo, ex.map(hash_png, todo, chunksize=64)): known[p] = h
    json.dump(known, open(IDX, "w"))
    have = set(known.values())
    bundles = [os.path.join(r, f) for r, _, fs in os.walk(ASSETS) for f in fs if os.path.getsize(os.path.join(r, f)) > 64]
    print(len(bundles), "fichiers à parcourir", flush=True)
    need = {}  # empreinte manquante -> premier bundle qui la contient
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for k, (b, items) in enumerate(zip(bundles, ex.map(work, bundles, chunksize=8)), 1):
            for ty, n, h in items:
                if h not in have and h not in need: need[h] = b
            if k % 2000 == 0: print(k, "bundles,", len(need), "images manquantes", flush=True)
    print(len(need), "images absentes de PNG\\ à écrire", flush=True)
    per = {}
    for h, b in need.items(): per.setdefault(b, set()).add(h)
    written = 0
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for r in ex.map(write, list(per), [per[b] for b in per]): written += len(r)
    print("TERMINE", written, "nouvelles images écrites", flush=True)
