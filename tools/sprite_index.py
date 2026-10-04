"""Index m_PathID -> (bundle, type) de tous les Sprite / Texture2D, pour retrouver un sprite référencé
depuis un CAB absent (même identifiant d'objet dans un autre bundle). Sortie : sprite_index.json"""
import os, json
from concurrent.futures import ProcessPoolExecutor
ASSETS = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets"

def scan(rel):
    import UnityPy
    try:
        d = open(os.path.join(ASSETS, rel), "rb").read(); i = d.find(b"UnityFS\x00"); env = UnityPy.load(d[i:])
        return rel, [(o.path_id, o.type.name) for o in env.objects if o.type.name in ("Sprite", "Texture2D")]
    except Exception:
        return rel, []

if __name__ == "__main__":
    C = json.load(open(r"C:\Users\Nauno\.bns_tools\census.json", encoding="utf-8"))
    rels = [k for k, v in C.items() if v.get("types", {}).get("Sprite") or v.get("types", {}).get("Texture2D")]
    idx = {}
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for rel, items in ex.map(scan, rels, chunksize=16):
            for pid, t in items: idx.setdefault(str(pid), []).append([rel, t])
    json.dump(idx, open(r"C:\Users\Nauno\.bns_tools\sprite_index.json", "w"))
    print("TERMINE", len(idx), "identifiants", flush=True)
