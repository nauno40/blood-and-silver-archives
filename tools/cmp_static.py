"""Compare anciens / nouveaux GLB statiques : ordre des triangles (miroirs) et textures."""
import json, struct, glob, os, hashlib
import numpy as np
NEW = r"E:\Projets\BloodAndSilver\Site\models"; OLD = r"C:\Users\Nauno\AppData\Local\Temp\static_bak"
def info(p):
    d = open(p, "rb").read(); jl = struct.unpack("<I", d[12:16])[0]; j = json.loads(d[20:20 + jl]); b0 = 20 + jl + 8
    def view(i):
        bv = j["bufferViews"][i]; o = b0 + bv.get("byteOffset", 0); return d[o:o + bv["byteLength"]]
    idx = hashlib.md5(b"".join(view(j["accessors"][pr["indices"]]["bufferView"]) for m in j["meshes"] for pr in m["primitives"] if "indices" in pr)).hexdigest()
    imgs = sorted(hashlib.md5(view(im["bufferView"])).hexdigest() for im in j.get("images", []))
    return idx, imgs, len(j["meshes"])
res = {"winding": [], "textures": [], "missing": []}
for c in ("personnages", "monstres"):
    for p in sorted(glob.glob(os.path.join(OLD, c, "*.glb"))):
        n = os.path.basename(p)[:-4]; q = os.path.join(NEW, c, n + ".glb")
        if not os.path.exists(q): res["missing"].append(n); continue
        a, b = info(p), info(q)
        if a[0] != b[0]: res["winding"].append(n)
        if a[1] != b[1]: res["textures"].append(n)
for k, v in res.items(): print(k, len(v), v[:30])
json.dump(res, open("cmp_static.json", "w"))
