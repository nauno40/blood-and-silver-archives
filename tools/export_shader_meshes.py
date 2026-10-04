r"""Pour chaque matériau d'aperçu (shader_preview\*\material.json), cherche dans les modèles du jeu la pièce de maillage
qui l'utilise et l'exporte (pose de repos, repère glTF) : mesh_m<k>.json = positions, normales, uv, tangentes, couleurs, indices.
Le site fait tourner le vrai shader GLSL du jeu sur cette géométrie."""
import os, re, json, glob
import numpy as np
from concurrent.futures import ProcessPoolExecutor

ROOT = r"E:\Projets\BloodAndSilver"
OUT = os.path.join(ROOT, "Site", "shader_preview")
TOOLS = r"C:\Users\Nauno\.bns_tools"

def tokens(matname):
    t = [x for x in re.split(r"[_\W]+", matname.lower()) if x and not re.match(r"^(c|m|t|fx|base|body\d*|timeline|weapon\d*|face|hair|\d+)$", x)]
    return t[:2]

def scan(args):
    path, wanted = args
    exec(open(os.path.join(TOOLS, "export_3d.py"), encoding="utf-8-sig").read().split("_EXTRA = None")[0], globals())
    from UnityPy.helpers.MeshHelper import MeshHandler
    found = {}
    try:
        env = load(path); objs = {o.path_id: o for o in env.objects}
        for o in env.objects:
            if o.type.name not in ("SkinnedMeshRenderer", "MeshRenderer"): continue
            r = o.read_typetree(); mats = r.get("m_Materials", [])
            names = []
            for mp in mats:
                mo = resolve(o.assets_file, mp)
                names.append(mo.read_typetree().get("m_Name") if mo is not None and mo.type.name == "Material" else None)
            hits = [(si, n) for si, n in enumerate(names) if n in wanted and n not in found]
            if not hits: continue
            if o.type.name == "SkinnedMeshRenderer": mptr = r["m_Mesh"]
            else:
                go = objs[r["m_GameObject"]["m_PathID"]].read_typetree()
                mf = [objs[c["component"]["m_PathID"]] for c in go["m_Component"] if c["component"]["m_PathID"] in objs and objs[c["component"]["m_PathID"]].type.name == "MeshFilter"]
                mptr = mf[0].read_typetree()["m_Mesh"] if mf else None
            mo = resolve(o.assets_file, mptr) if mptr else None
            if mo is None: continue
            mesh = mo.read(); h = MeshHandler(mesh); h.process(); nv = h.m_VertexCount
            def arr(a, keep):
                a = np.array(a, dtype=np.float64) if a else None
                return a.reshape(nv, -1)[:, :keep] if a is not None and len(a) and len(a) % nv == 0 else None
            V, N, UV, TG, CL = arr(h.m_Vertices, 3), arr(h.m_Normals, 3), arr(h.m_UV0, 2), arr(h.m_Tangents, 4), arr(h.m_Colors, 4)
            if V is None: continue
            subs = h.get_triangles()
            for si, n in hits:
                if si >= len(subs): continue
                F = np.array(subs[si], dtype=np.int64).reshape(-1, 3)
                used = np.unique(F); remap = -np.ones(nv, dtype=np.int64); remap[used] = np.arange(len(used))
                # repère Unity (main gauche) -> droite : X inversé, ordre des triangles inversé
                def fx(a, k=3): b = a[used].copy(); b[:, 0] *= -1; return b
                d = {"position": fx(V).round(5).ravel().tolist(), "index": remap[F][:, ::-1].ravel().tolist()}
                if N is not None: d["normal"] = fx(N).round(4).ravel().tolist()
                if UV is not None: d["uv"] = UV[used].round(5).ravel().tolist()
                if TG is not None: t = TG[used].copy(); t[:, 0] *= -1; t[:, 3] *= -1; d["tangent"] = t.round(4).ravel().tolist()
                if CL is not None: d["color"] = CL[used].round(3).ravel().tolist()
                found[n] = d
    except Exception:
        pass
    return found

if __name__ == "__main__":
    A = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets"
    previews = {}
    for f in glob.glob(os.path.join(OUT, "*", "material.json")):
        j = json.load(open(f, encoding="utf-8"))
        for k, m in enumerate(j["materials"]): previews[m["material"]] = (os.path.dirname(f), k)
    wanted = set(previews)
    # bundles candidats : modèles dont le nom partage un mot significatif avec le matériau
    bundles = glob.glob(os.path.join(A, "ABResource", "*.unity3d")) + glob.glob(os.path.join(A, "Scenes", "*.unity3d"))
    toks = {t for m in wanted for t in tokens(m)}
    cands = [b for b in bundles if any(t in os.path.basename(b).lower() for t in toks) and not re.search(r"(?i)^(fx|ani_|ui)", os.path.basename(b))]
    print(len(wanted), "matériaux,", len(cands), "bundles candidats", flush=True)
    got = {}
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for res in ex.map(scan, [(b, wanted) for b in cands], chunksize=4):
            for n, d in res.items():
                if n not in got or len(d["position"]) > len(got[n]["position"]): got[n] = d
    for n, d in got.items():
        folder, k = previews[n]
        json.dump(d, open(os.path.join(folder, f"mesh_m{k}.json"), "w"), separators=(",", ":"))
    print("TERMINE", len(got), "pièces exportées sur", len(wanted), "matériaux", flush=True)
    print("sans pièce :", sorted(wanted - set(got)), flush=True)
