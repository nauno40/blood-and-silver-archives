r"""Extrait chaque squelette Spine (skel/json + atlas + textures de l'atlas) dans
E:\Projets\BloodAndSilver\Spine\<bundle>\<squelette>\ et Ã©crit un inventaire."""
import os, glob, re, json
from concurrent.futures import ProcessPoolExecutor, as_completed

ASSETS = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets"
OUT = r"E:\Projets\BloodAndSilver\Spine"

def safe(n):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", n).strip() or "unnamed"

def raw_bytes(t):
    s = t.m_Script
    return s.encode("utf-8", "surrogateescape") if isinstance(s, str) else bytes(s)

def process(path):
    import UnityPy
    data = open(path, "rb").read()
    if b".skel" not in data and b".atlas" not in data and b"skeleton" not in data:
        # filtre rapide ; les bundles compressÃ©s passent quand mÃªme
        pass
    i = data.find(b"UnityFS\x00")
    try:
        env = UnityPy.load(data[i:] if i > 0 else data)
    except Exception as e:
        return []
    texts, texs = {}, {}
    for o in env.objects:
        n = o.type.name
        if n == "TextAsset":
            texts[o.path_id] = o
        elif n == "Texture2D":
            texs[o.path_id] = o
    skels = {pid: o for pid, o in texts.items() if o.peek_name().endswith((".skel", ".json"))}
    if not skels:
        return []
    atlases = {pid: o for pid, o in texts.items() if o.peek_name().endswith(".atlas")}
    tex_by_name = {}
    for o in texs.values():
        tex_by_name.setdefault(o.peek_name(), o)
    stem = os.path.splitext(os.path.basename(path))[0]
    results = []
    for pid, so in skels.items():
        sname = so.peek_name()
        base = sname.rsplit(".", 1)[0]
        folder = os.path.join(OUT, safe(stem), safe(base))
        os.makedirs(folder, exist_ok=True)
        sraw = raw_bytes(so.read())
        open(os.path.join(folder, safe(sname)), "wb").write(sraw)
        # atlas : mÃªme nom de base, sinon le seul du bundle
        cand = [a for a in atlases.values() if a.peek_name().rsplit(".", 1)[0] == base] or list(atlases.values())
        pages = []
        for a in cand[:1]:
            araw = raw_bytes(a.read())
            open(os.path.join(folder, safe(base) + ".atlas"), "wb").write(araw)
            text = araw.decode("utf-8", "replace").replace("\r", "")
            blocks = text.split("\n")
            # une page = ligne finissant par .png suivie de size:
            for k, line in enumerate(blocks):
                if line.strip().lower().endswith((".png", ".jpg")):
                    pages.append(line.strip())
        missing = []
        for pg in pages:
            tn = pg.rsplit(".", 1)[0]
            t = tex_by_name.get(tn)
            if t is None:
                missing.append(pg)
                continue
            t.read().image.save(os.path.join(folder, pg))
        results.append({"bundle": os.path.relpath(path, ASSETS), "skeleton": sname,
                        "folder": os.path.relpath(folder, OUT), "pages": pages,
                        "missing": missing, "has_atlas": bool(cand),
                        "version": sraw[8:30].decode("latin1") if sname.endswith(".skel") else ""})
    return results

def main():
    os.makedirs(OUT, exist_ok=True)
    files = glob.glob(os.path.join(ASSETS, "**", "*.unity3d"), recursive=True)
    inv = []
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        futs = [ex.submit(process, f) for f in files]
        for k, fut in enumerate(as_completed(futs), 1):
            try:
                inv.extend(fut.result())
            except Exception as e:
                pass
            if k % 2000 == 0:
                print(f"{k}/{len(files)}  squelettes={len(inv)}", flush=True)
    json.dump(inv, open(os.path.join(OUT, "inventory.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"TERMINE squelettes={len(inv)}  sans_atlas={sum(not r['has_atlas'] for r in inv)}  "
          f"textures_manquantes={sum(bool(r['missing']) for r in inv)}", flush=True)

if __name__ == "__main__":
    main()

