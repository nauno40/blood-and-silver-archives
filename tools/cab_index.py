r"""Index « nom interne CAB-xxxx -> fichier bundle » pour résoudre les références entre bundles
(textures partagées des décors / personnages). Sortie : C:\Users\Nauno\.bns_tools\cab_index.json"""
import os, glob, json
from concurrent.futures import ProcessPoolExecutor

A = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets"

def job(p):
    import UnityPy
    try:
        d = open(p, "rb").read(); i = d.find(b"UnityFS\x00")
        env = UnityPy.load(d[i:] if i > 0 else d)
        return p, [k for f in env.files.values() for k in getattr(f, "files", {}).keys() if k.upper().startswith("CAB-")]
    except Exception:
        return p, []

if __name__ == "__main__":
    files = [f for d in ("ABResource", "ABResourceSingle", "Art", "Scenes", "Texture2DRes", "UI", "Fonts", "Document", "lua", "BytesData") for f in glob.glob(os.path.join(A, d, "**", "*.unity3d"), recursive=True)]
    idx = {}
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 4)) as ex:
        for k, (p, cabs) in enumerate(ex.map(job, files, chunksize=32), 1):
            for c in cabs: idx[c.split(".")[0].lower()] = p
            if k % 2000 == 0: print(k, len(files), flush=True)
    json.dump(idx, open(r"C:\Users\Nauno\.bns_tools\cab_index.json", "w"), indent=0)
    print("TERMINE", len(idx), "CAB indexés", flush=True)
