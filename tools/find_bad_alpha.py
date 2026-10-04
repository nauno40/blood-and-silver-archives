"""Liste les GLB dont au moins un matériau est en mode MASK alors que sa texture n'a pas de vraie transparence
(règle alpha_mode d'export_3d.py) : ces pièces sont (partiellement) invisibles et doivent être réexportées."""
import glob, os, sys, json
from concurrent.futures import ProcessPoolExecutor
sys.argv = ["x"]
exec(open(r"C:\Users\Nauno\.bns_tools\export_3d.py", encoding="utf-8-sig").read().split("def category")[0])

def check(p):
    import trimesh
    try:
        s = trimesh.load(p)
        bad = 0
        for g in s.geometry.values():
            m = getattr(g.visual, "material", None); t = getattr(m, "baseColorTexture", None)
            if t is not None and getattr(m, "alphaMode", None) == "MASK" and alpha_mode(t.convert("RGBA")) == "OPAQUE":
                bad += 1
        return p, bad, len(s.geometry)
    except Exception as e:
        return p, -1, 0

if __name__ == "__main__":
    files = sorted(glob.glob(r"E:\Projets\BloodAndSilver\Site\models\*\*.glb"))
    with ProcessPoolExecutor(8) as ex:
        res = list(ex.map(check, files))
    bad = [(os.path.basename(p), b, n) for p, b, n in res if b]
    print(len(files), "modèles analysés,", len(bad), "avec des pièces masquées à tort")
    for x in bad[:40]: print("  ", x)
    json.dump([os.path.basename(p)[:-4] for p, b, n in res if b], open(r"C:\Users\Nauno\.bns_tools\bad_alpha.json", "w"))
