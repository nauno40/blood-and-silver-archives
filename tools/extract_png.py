"""Extrait toutes les textures (Texture2D) et sprites (Sprite) des bundles Unity de
Blood and Silver en PNG.

- Les bundles ont un préfixe custom avant 'UnityFS' : on le retire avant chargement.
- Sortie : PNG/<dossier assets>/<bundle>/<nom>.png
- Doublons (même image dans plusieurs bundles) ignorés via un marqueur de hash atomique.
- Reprise : un bundle déjà traité (marqueur dans PNG/.done) est sauté.
"""
from config import PROJECT, ASSETS  # chemins : voir tools/config.py
import os, sys, glob, hashlib, re, time, traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

ASSETS = ASSETS
OUT = PROJECT + r"\PNG"
HASHES = os.path.join(OUT, ".hashes")
DONE = os.path.join(OUT, ".done")
LOG = os.path.join(OUT, "extract_errors.txt")

def safe(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip() or "unnamed"

def claim(key):
    """True si c'est la première fois qu'on voit ce contenu (atomique entre processus)."""
    try:
        fd = os.open(os.path.join(HASHES, key), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False

def unique_path(folder, name):
    p = os.path.join(folder, name + ".png")
    n = 1
    while os.path.exists(p):
        n += 1
        p = os.path.join(folder, f"{name}_{n}.png")
    return p

def process(path):
    import UnityPy
    rel = os.path.relpath(path, ASSETS)
    marker = os.path.join(DONE, hashlib.md5(rel.encode()).hexdigest())
    if os.path.exists(marker):
        return rel, 0, 0, None
    top = rel.split(os.sep)[0]
    stem = os.path.splitext(os.path.basename(path))[0]
    folder = os.path.join(OUT, safe(top), safe(stem))
    written = dups = 0
    try:
        data = open(path, "rb").read()
        i = data.find(b"UnityFS\x00")
        env = UnityPy.load(data[i:] if i > 0 else data)
        tex_sizes = {}
        objs = [o for o in env.objects if o.type.name in ("Texture2D", "Sprite")]
        # textures d'abord, pour savoir quels sprites sont des découpes
        objs.sort(key=lambda o: o.type.name != "Texture2D")
        for o in objs:
            try:
                d = o.read()
                if o.type.name == "Texture2D":
                    if d.m_Width == 0 or d.m_Height == 0:
                        continue
                    tex_sizes[d.m_Name] = (d.m_Width, d.m_Height)
                    img = d.image
                    name = d.m_Name
                else:
                    r = d.m_Rect
                    size = (round(r.width), round(r.height))
                    # sprite couvrant toute la texture = doublon de la texture
                    if size in tex_sizes.values() and d.m_Name in tex_sizes:
                        continue
                    img = d.image
                    name = d.m_Name + "_sprite" if d.m_Name in tex_sizes else d.m_Name
                key = hashlib.md5(img.tobytes() + repr(img.size).encode()).hexdigest()
                if not claim(key):
                    dups += 1
                    continue
                os.makedirs(folder, exist_ok=True)
                img.save(unique_path(folder, safe(name)))
                written += 1
            except Exception as e:
                with open(LOG, "a", encoding="utf-8") as f:
                    f.write(f"OBJ\t{rel}\t{o.type.name}\t{type(e).__name__}: {e}\n")
        open(marker, "w").close()
        return rel, written, dups, None
    except Exception as e:
        return rel, written, dups, f"{type(e).__name__}: {e}"

def main():
    os.makedirs(HASHES, exist_ok=True)
    os.makedirs(DONE, exist_ok=True)
    files = glob.glob(os.path.join(ASSETS, "**", "*.unity3d"), recursive=True)
    # UI et textures en premier
    prio = {"UI": 0, "Texture2DRes": 1, "Art": 2, "ABResourceSingle": 3, "ABResource": 4}
    files.sort(key=lambda p: prio.get(os.path.relpath(p, ASSETS).split(os.sep)[0], 9))
    total = len(files)
    print(f"{total} bundles à traiter", flush=True)
    t0 = time.time(); n = w = du = err = 0
    workers = max(2, (os.cpu_count() or 4) - 2)
    with ProcessPoolExecutor(workers) as ex:
        for fut in as_completed([ex.submit(process, f) for f in files]):
            rel, a, b, e = fut.result()
            n += 1; w += a; du += b
            if e:
                err += 1
                with open(LOG, "a", encoding="utf-8") as f:
                    f.write(f"BUNDLE\t{rel}\t{e}\n")
            if n % 500 == 0:
                print(f"{n}/{total} bundles  png={w}  doublons={du}  erreurs={err}  {int(time.time()-t0)}s", flush=True)
    print(f"TERMINE {n}/{total} bundles  png={w}  doublons={du}  erreurs={err}  {int(time.time()-t0)}s", flush=True)

if __name__ == "__main__":
    main()
