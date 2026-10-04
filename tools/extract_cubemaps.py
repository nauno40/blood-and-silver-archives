r"""Extrait les Cubemap (ciels 360° / reflets des cartes) en image « croix » 4x3 faces :
            +Y
       -X   +Z   +X   -Z
            -Y
Sortie : <projet>\PNG\Cubemaps\<bundle>\<nom>.png (doublons de pixels ignorés)."""
from config import PROJECT, TOOLS_DIR, ASSETS  # chemins : voir tools/config.py
import os, re, json, hashlib
from concurrent.futures import ProcessPoolExecutor

ASSETS = ASSETS
OUT = PROJECT + r"\PNG\Cubemaps"
CENSUS = TOOLS_DIR + r"\census.json"
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

def faces(t):
    from UnityPy.export.Texture2DConverter import parse_image_data
    from UnityPy.enums import BuildTarget
    data = t.get_image_data(); n = 6
    if not data or len(data) % n: return None
    step = len(data) // n
    r = t.object_reader
    return [parse_image_data(data[k * step:(k + 1) * step], t.m_Width, t.m_Height, t.m_TextureFormat,
                             getattr(r, "version", (0, 0, 0, 0)), getattr(r, "platform", BuildTarget.UnknownPlatform),
                             getattr(t, "m_PlatformBlob", None), True).convert("RGBA") for k in range(n)]

def cross(fs):
    from PIL import Image
    w, h = fs[0].size
    im = Image.new("RGBA", (4 * w, 3 * h), (0, 0, 0, 0))
    px, nx, py, ny, pz, nz = fs  # ordre Unity : +X -X +Y -Y +Z -Z
    for f, (cx, cy) in ((py, (1, 0)), (nx, (0, 1)), (pz, (1, 1)), (px, (2, 1)), (nz, (3, 1)), (ny, (1, 2))):
        im.paste(f, (cx * w, cy * h))
    return im

def job(rel):
    import UnityPy
    out = []
    try:
        d = open(os.path.join(ASSETS, rel), "rb").read(); i = d.find(b"UnityFS\x00"); env = UnityPy.load(d[i:])
        for o in env.objects:
            if o.type.name != "Cubemap": continue
            try:
                t = o.read(); fs = faces(t)
                if not fs: continue
                im = cross(fs); h = hashlib.md5(im.tobytes()).hexdigest()
                out.append((t.m_Name, h, im))
            except Exception as e:
                out.append((getattr(o, "path_id", "?"), "ERR", str(e)[:120]))
    except Exception as e:
        out.append(("bundle", "ERR", str(e)[:120]))
    return rel, out

if __name__ == "__main__":
    C = json.load(open(CENSUS, encoding="utf-8"))
    rels = [k for k, v in C.items() if v.get("types", {}).get("Cubemap")]
    seen, n, err = set(), 0, 0
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for rel, items in ex.map(job, rels, chunksize=4):
            for name, h, im in items:
                if h == "ERR": err += 1; print("ERREUR", rel, name, im, flush=True); continue
                if h in seen: continue
                seen.add(h)
                folder = os.path.join(OUT, os.path.splitext(os.path.basename(rel))[0]); os.makedirs(folder, exist_ok=True)
                safe = BAD.sub("_", str(name)).strip(" .") or "cubemap"
                im.save(os.path.join(folder, safe + ".png"), "PNG"); n += 1
    print("TERMINE", n, "cubemaps uniques,", err, "erreurs", flush=True)
