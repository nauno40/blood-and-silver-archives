r"""Exemples d'aperçu pour chaque shader, pris sur les modèles du jeu : pour chaque pièce de maillage (personnages, monstres,
PNJ, cartes…), matériau -> shader ; on garde par shader les 3 meilleurs exemples (le plus de textures trouvées, pièce assez grande)
et on exporte la pièce (mesh_mK.json), les valeurs du matériau et ses textures. Complète shader_preview\<dossier>\material.json :
les matériaux sans pièce trouvés par export_shader_materials.py restent en fin de liste (aperçu sur boule / plan)."""
import os, re, json, glob
import numpy as np
from concurrent.futures import ProcessPoolExecutor

ROOT = r"E:\Projets\BloodAndSilver"
A = os.path.join(ROOT, r"data\com.moonton.silverblood.eu\files\dragon2019\assets")
OUT = os.path.join(ROOT, "Site", "shader_preview")
TOOLS = r"C:\Users\Nauno\.bns_tools"
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

def scan(path):
    exec(open(os.path.join(TOOLS, "export_3d.py"), encoding="utf-8-sig").read().split("_EXTRA = None")[0], globals())
    exec(open(os.path.join(TOOLS, "extract_cubemaps.py"), encoding="utf-8").read().split("def cross")[0], globals())
    from UnityPy.helpers.MeshHelper import MeshHandler
    SBM = json.load(open(os.path.join(TOOLS, "shader_by_material.json")))
    out = []
    try:
        env = load(path); objs = {o.path_id: o for o in env.objects}; seen = set()
        TT = {}
        def T(pid):
            if pid not in TT: TT[pid] = objs[pid].read_typetree()
            return TT[pid]
        tr_of_go = {}
        for pid, ob in objs.items():
            if ob.type.name in ("Transform", "RectTransform"): tr_of_go[T(pid)["m_GameObject"]["m_PathID"]] = pid
        def W(tp):  # matrice monde (repère Unity) d'un Transform, comme export_3d.py
            t = T(tp); m = np.eye(4)
            m[:3, :3] = quat_mat(t["m_LocalRotation"]) * np.array([t["m_LocalScale"][k] for k in "xyz"])
            m[:3, 3] = [t["m_LocalPosition"][k] for k in "xyz"]
            par = t["m_Father"]["m_PathID"]
            return (W(par) @ m) if par and par in objs else m
        for o in env.objects:
            if o.type.name not in ("SkinnedMeshRenderer", "MeshRenderer"): continue
            r = o.read_typetree(); mats = r.get("m_Materials", [])
            for si, mp in enumerate(mats):
                mo = resolve(o.assets_file, mp)
                if mo is None or mo.type.name != "Material": continue
                m = mo.read_typetree()
                if m["m_Name"] in seen: continue
                so = resolve(mo.assets_file, m.get("m_Shader", {}))
                try: sname = so.read_typetree()["m_ParsedForm"]["m_Name"] if so is not None else None
                except Exception: sname = None
                if not sname:  # shader absent du téléphone : déduit du matériau « _timeline » de même nom, sinon du type de pièce
                    key = re.sub(r"_timeli+ne$", "", m["m_Name"].lower())
                    sname = SBM.get(key)
                    if not sname and os.path.basename(path).startswith(("C_", "T_")):
                        sname = "Nova/Face_01" if "face" in key else "Nova/Hair_01" if "hair" in key else None
                if not sname: continue
                seen.add(m["m_Name"])
                props = m.get("m_SavedProperties", {})
                def items(x): return [(k, v) for k, v in x] if x and isinstance(x[0], (list, tuple)) else [(e.get("first"), e.get("second")) for e in x]
                texs, imgs = {}, {}
                for k, v in items(props.get("m_TexEnvs", [])):
                    texs[k] = {"st": [v["m_Scale"]["x"], v["m_Scale"]["y"], v["m_Offset"]["x"], v["m_Offset"]["y"]]}
                    to = resolve(mo.assets_file, v.get("m_Texture", {})) if v.get("m_Texture", {}).get("m_PathID") else None
                    if to is None: continue
                    try:
                        t = to.read()
                        if to.type.name == "Texture2D": im = t.image.convert("RGBA"); im.thumbnail((1024, 1024)); imgs[k] = ("2D", im)
                        elif to.type.name == "Cubemap":
                            fs = faces(t)
                            if fs: imgs[k] = ("Cube", [f.resize((256, 256)) for f in fs])
                    except Exception: pass
                # pièce de maillage
                if o.type.name == "SkinnedMeshRenderer": mptr = r["m_Mesh"]
                else:
                    go = objs[r["m_GameObject"]["m_PathID"]].read_typetree()
                    mf = [objs[c["component"]["m_PathID"]] for c in go["m_Component"] if c["component"]["m_PathID"] in objs and objs[c["component"]["m_PathID"]].type.name == "MeshFilter"]
                    mptr = mf[0].read_typetree()["m_Mesh"] if mf else None
                meo = resolve(o.assets_file, mptr) if mptr else None
                geo = None
                if meo is not None:
                    mesh = meo.read(); h = MeshHandler(mesh); h.process(); nv = h.m_VertexCount; subs = h.get_triangles()
                    def arr(a, keep):
                        a = np.array(a, dtype=np.float64) if a else None
                        return a.reshape(nv, -1)[:, :keep] if a is not None and len(a) and len(a) % nv == 0 else None
                    V, N, UV, TG, CL = arr(h.m_Vertices, 3), arr(h.m_Normals, 3), arr(h.m_UV0, 2), arr(h.m_Tangents, 4), arr(h.m_Colors, 4)
                    if V is not None and si < len(subs) and len(subs[si]) >= 60:
                        gp = r["m_GameObject"]["m_PathID"]
                        Mw = W(tr_of_go[gp]) if gp in tr_of_go else np.eye(4)
                        V = (np.c_[V, np.ones(len(V))] @ Mw.T)[:, :3]  # pièce placée comme dans le jeu (debout)
                        R3 = Mw[:3, :3]
                        if N is not None: N = N @ np.linalg.inv(R3).T; N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
                        if TG is not None: TG = TG.copy(); TG[:, :3] = TG[:, :3] @ R3.T; TG[:, :3] /= np.maximum(np.linalg.norm(TG[:, :3], axis=1, keepdims=True), 1e-9)
                        F = np.array(subs[si], dtype=np.int64).reshape(-1, 3); used = np.unique(F)
                        if np.linalg.det(R3) < 0: F = F[:, ::-1]
                        remap = -np.ones(nv, dtype=np.int64); remap[used] = np.arange(len(used))
                        def fx(a): b = a[used].copy(); b[:, 0] *= -1; return b
                        geo = {"position": fx(V).round(5).ravel().tolist(), "index": remap[F][:, ::-1].ravel().tolist()}
                        if N is not None: geo["normal"] = fx(N).round(4).ravel().tolist()
                        if UV is not None: geo["uv"] = UV[used].round(5).ravel().tolist()
                        if TG is not None: t_ = TG[used].copy(); t_[:, 0] *= -1; t_[:, 3] *= -1; geo["tangent"] = t_.round(4).ravel().tolist()
                        if CL is not None: geo["color"] = CL[used].round(3).ravel().tolist()
                if geo is None: continue
                mat = {"material": m["m_Name"], "bundle": os.path.basename(path), "object": objs[r["m_GameObject"]["m_PathID"]].read_typetree().get("m_Name"),
                       "floats": {k: v for k, v in items(props.get("m_Floats", []))},
                       "colors": {k: [v["r"], v["g"], v["b"], v["a"]] for k, v in items(props.get("m_Colors", []))},
                       "textures": texs, "keywords": m.get("m_ValidKeywords") or (m.get("m_ShaderKeywords") or "").split()}
                out.append((sname, len(imgs) * 100000 + min(len(geo["position"]) // 3, 99999), mat, imgs, geo))
    except Exception:
        pass
    return out

if __name__ == "__main__":
    idx = json.load(open(os.path.join(ROOT, "Shaders", "index.json"), encoding="utf-8"))
    wanted = {s["name"]: s["folder"] for s in idx}
    files = sorted(glob.glob(os.path.join(A, "ABResource", "[CMT]_*.unity3d")) + glob.glob(os.path.join(A, "ABResource", "*SceneRoot*.unity3d")) +
                   [l.strip() for l in open(os.path.join(TOOLS, "extra_files.txt"), encoding="utf-8") if l.strip()])
    files = [f for f in dict.fromkeys(files) if not re.search(r"(?i)_shadow|rogue_inst|_mob$|_annex$", os.path.basename(f)[:-8])]
    print(len(files), "bundles de modèles", flush=True)
    best = {}
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for k, res in enumerate(ex.map(scan, files, chunksize=2), 1):
            for sname, score, mat, imgs, geo in res:
                if sname not in wanted: continue
                L = best.setdefault(sname, [])
                if any(x[2]["material"] == mat["material"] for x in L): continue
                L.append((score, k, mat, imgs, geo)); L.sort(key=lambda x: -x[0]); del L[3:]
            if k % 200 == 0: print(k, "/", len(files), flush=True)
    n = 0
    for sname, L in best.items():
        folder = os.path.join(OUT, BAD.sub("_", wanted[sname])); os.makedirs(os.path.join(folder, "textures"), exist_ok=True)
        old = json.load(open(os.path.join(folder, "material.json"), encoding="utf-8"))["materials"] if os.path.exists(os.path.join(folder, "material.json")) else []
        for f in glob.glob(os.path.join(folder, "mesh_m*.json")) + glob.glob(os.path.join(folder, "textures", "g*")): os.remove(f)
        mats = []
        for k, (score, _, mat, imgs, geo) in enumerate(L):
            for prop, (kind, im) in imgs.items():
                if kind == "2D": fn = f"g{k}_{BAD.sub('_', prop)}.png"; im.save(os.path.join(folder, "textures", fn)); mat["textures"][prop]["file"] = "textures/" + fn
                else:
                    fns = []
                    for fi, f in enumerate(im): fn = f"g{k}_{BAD.sub('_', prop)}_{fi}.png"; f.save(os.path.join(folder, "textures", fn)); fns.append("textures/" + fn)
                    mat["textures"][prop]["cube"] = fns
            json.dump(geo, open(os.path.join(folder, f"mesh_g{k}.json"), "w"), separators=(",", ":"))
            mat["mesh"] = f"mesh_g{k}.json"; mats.append(mat); n += 1
        mats += [m for m in old if m["material"] not in {x["material"] for x in mats}]
        json.dump({"shader": sname, "materials": mats}, open(os.path.join(folder, "material.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("TERMINE", n, "exemples avec pièce de maillage", flush=True)
    for s in sorted(wanted): print(f"  {s:50}", [f'{x[2]["material"]} ({x[2]["object"]})' for x in best.get(s, [])], flush=True)
