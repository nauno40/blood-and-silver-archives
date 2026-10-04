r"""Exporte les modèles 3D du jeu AVEC squelette (rig) et animations en GLB (glTF 2.0).

- Squelette : hiérarchie des Transform du prefab -> nœuds glTF (TRS locaux).
- Maillages skinnés : poids/indices d'os par sommet, matrices de liaison (bindposes) -> skin glTF.
- Animations : clips des bundles ABResourceSingle\Ani_<modèle>*.unity3d. Les courbes Unity (streamed = polynômes
  cubiques par segment, dense = échantillons, constantes) sont décodées puis échantillonnées à 30 i/s ; chaque
  liaison est rattachée à son os par le hash CRC32 du chemin (table m_TOS de l'Avatar).
- Repère : Unity (main gauche) -> glTF (main droite) par symétrie X : position (-x,y,z), quaternion (x,-y,-z,w),
  matrices S·M·S, ordre des triangles inversé.
Sortie : Site\models_anim\<cat>\<nom>.glb + anim.json (liste des clips par modèle)."""
from config import PROJECT, TOOLS_DIR, ASSETS  # chemins : voir tools/config.py
import os, re, sys, glob, json, struct, zlib, io, traceback, math
import numpy as np
from concurrent.futures import ProcessPoolExecutor

ASSETS = ASSETS
A = os.path.join(ASSETS, "ABResource")
ANI = os.path.join(ASSETS, "ABResourceSingle")
FPS = 30

# réutilise le chargement, la résolution inter-bundles, la recherche de texture et la règle d'alpha d'export_3d.py
_src = open(TOOLS_DIR + r"\export_3d.py", encoding="utf-8-sig").read()
exec(_src.split("def category")[0])
OUT = PROJECT + r"\Site\models_anim"  # après l'exec : export_3d.py définit aussi OUT

S = np.diag([-1.0, 1, 1, 1])

def conv_pos(p): return np.array([-p[0], p[1], p[2]], dtype=np.float64)
def conv_quat(q):  # (x,y,z,w) Unity -> glTF
    q = np.array([q[0], -q[1], -q[2], q[3]], dtype=np.float64)
    n = np.linalg.norm(q); return q / n if n > 1e-12 else np.array([0, 0, 0, 1.0])

def euler_to_quat(ex, ey, ez):
    """Courbes d'Euler (degrés) des clips du jeu : rotation X, puis Y, puis Z -> q = qZ * qY * qX.
    (Ordre « XYZ » hérité de l'export 3ds Max, vérifié contre la pose de repos ; ce n'est PAS l'ordre ZXY de
    Quaternion.Euler.)"""
    def ax(axis, deg):
        h = math.radians(deg) / 2; s = math.sin(h)
        return np.array([axis[0] * s, axis[1] * s, axis[2] * s, math.cos(h)])
    def mul(a, b):
        ax_, ay, az, aw = a; bx, by, bz, bw = b
        return np.array([aw * bx + ax_ * bw + ay * bz - az * by, aw * by - ax_ * bz + ay * bw + az * bx,
                         aw * bz + ax_ * by - ay * bx + az * bw, aw * bw - ax_ * bx - ay * by - az * bz])
    return mul(mul(ax((0, 0, 1), ez), ax((0, 1, 0), ey)), ax((1, 0, 0), ex))

def mat_from_unity(m):
    M = np.array([[m.e00, m.e01, m.e02, m.e03], [m.e10, m.e11, m.e12, m.e13],
                  [m.e20, m.e21, m.e22, m.e23], [m.e30, m.e31, m.e32, m.e33]], dtype=np.float64)
    return S @ M @ S

# ---------------------------------------------------------------------------------- décodage des clips
def decode_clip(t):
    """Renvoie (durée, fonction curve(index, temps) -> valeur, nombre de courbes)."""
    mc = t["m_MuscleClip"]
    clip = mc["m_Clip"]["data"] if "data" in mc["m_Clip"] else mc["m_Clip"]
    start, stop = mc.get("m_StartTime", 0.0), mc.get("m_StopTime", 0.0)
    # streamed : suite de frames { temps, nb, nb × (index, c0, c1, c2, c3) }
    sc = clip["m_StreamedClip"]; raw = struct.pack(f"<{len(sc['data'])}I", *sc["data"])
    nstream = sc["curveCount"]
    keys = [[] for _ in range(nstream)]
    pos = 0
    while pos + 8 <= len(raw):
        tm, n = struct.unpack_from("<fi", raw, pos); pos += 8
        for _ in range(n):
            idx, c0, c1, c2, c3 = struct.unpack_from("<iffff", raw, pos); pos += 20
            if 0 <= idx < nstream: keys[idx].append((tm, c0, c1, c2, c3))
    ktimes = [np.array([k[0] for k in ks]) for ks in keys]
    dc = clip["m_DenseClip"]; ndense = dc["m_CurveCount"]
    dense = np.array(dc["m_SampleArray"], dtype=np.float64).reshape(-1, ndense) if ndense and dc["m_FrameCount"] else np.zeros((0, 0))
    rate, begin = dc.get("m_SampleRate", 30.0) or 30.0, dc.get("m_BeginTime", 0.0)
    const = clip["m_ConstantClip"]["data"]

    def curve(i, tt):
        if i < nstream:
            ks, kt = keys[i], ktimes[i]
            if not ks: return 0.0
            j = int(np.searchsorted(kt, tt, side="right")) - 1
            if j < 0: j = 0
            k = ks[j]; dt = tt - k[0] if k[0] > -1e30 else 0.0
            return ((k[1] * dt + k[2]) * dt + k[3]) * dt + k[4]
        i -= nstream
        if i < ndense:
            if not len(dense): return 0.0
            f = (tt - begin) * rate
            f0 = int(np.clip(math.floor(f), 0, len(dense) - 1)); f1 = min(f0 + 1, len(dense) - 1); a = float(np.clip(f - f0, 0, 1))
            return dense[f0, i] * (1 - a) + dense[f1, i] * a
        i -= ndense
        return const[i] if i < len(const) else 0.0
    return max(stop - start, 1.0 / FPS), start, curve

# ---------------------------------------------------------------------------------- écriture glTF
class GLB:
    def __init__(self):
        self.j = {"asset": {"version": "2.0", "generator": "Blood and Silver Archives"}, "scenes": [{"nodes": []}], "scene": 0,
                  "nodes": [], "meshes": [], "skins": [], "materials": [], "textures": [], "images": [], "samplers": [{}],
                  "accessors": [], "bufferViews": [], "buffers": [], "animations": []}
        self.bin = bytearray()
    def view(self, data, target=None):
        while len(self.bin) % 4: self.bin.append(0)
        v = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target: v["target"] = target
        self.bin += data; self.j["bufferViews"].append(v); return len(self.j["bufferViews"]) - 1
    def acc(self, arr, ctype, typ, target=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        a = {"bufferView": self.view(arr.tobytes(), target), "componentType": ctype, "count": int(arr.shape[0]), "type": typ}
        if minmax: a["min"] = arr.min(axis=0).tolist(); a["max"] = arr.max(axis=0).tolist()
        self.j["accessors"].append(a); return len(self.j["accessors"]) - 1
    def save(self, path):
        for k in [k for k, v in self.j.items() if isinstance(v, list) and not v and k not in ("scenes",)]: del self.j[k]
        while len(self.bin) % 4: self.bin.append(0)
        self.j["buffers"] = [{"byteLength": len(self.bin)}]
        js = json.dumps(self.j, separators=(",", ":")).encode()
        js += b" " * ((4 - len(js) % 4) % 4)
        with open(path, "wb") as f:
            f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(self.bin)))
            f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
            f.write(struct.pack("<II", len(self.bin), 0x004E4942)); f.write(bytes(self.bin))

FLOAT, U16, U32, U8 = 5126, 5123, 5125, 5121

def export(path):
    from PIL import Image
    from UnityPy.helpers.MeshHelper import MeshHandler
    name = os.path.splitext(os.path.basename(path))[0]
    _xf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra_cats.json")
    _ex = json.load(open(_xf)) if os.path.exists(_xf) else {}  # généré par list_extra_models.py
    cat = _ex.get(name) or ("personnages" if name.startswith("C_") else "monstres" if name.startswith("M_") else "decors")
    dst = os.path.join(OUT, cat, name + ".glb")
    try:
        env = load(path)
        objs = {o.path_id: o for o in env.objects}
        tt = {}
        def T(pid):
            if pid not in tt: tt[pid] = objs[pid].read_typetree()
            return tt[pid]
        trs = {pid: o for pid, o in objs.items() if o.type.name in ("Transform", "RectTransform")}
        go_of = {pid: T(pid)["m_GameObject"]["m_PathID"] for pid in trs}
        tr_of_go = {v: k for k, v in go_of.items()}
        roots = [pid for pid in trs if T(pid)["m_Father"]["m_PathID"] not in trs]
        g = GLB(); nidx, paths = {}, {}
        # --- nœuds (squelette complet)
        def add_node(pid, parent_path):
            t = T(pid); nm = T(go_of[pid])["m_Name"]
            p = t["m_LocalPosition"]; q = t["m_LocalRotation"]; s = t["m_LocalScale"]
            node = {"name": nm, "translation": conv_pos((p["x"], p["y"], p["z"])).tolist(),
                    "rotation": conv_quat((q["x"], q["y"], q["z"], q["w"])).tolist(), "scale": [s["x"], s["y"], s["z"]]}
            g.j["nodes"].append(node); i = len(g.j["nodes"]) - 1; nidx[pid] = i
            path_ = nm if parent_path is None else (f"{parent_path}/{nm}" if parent_path else nm)
            paths[i] = path_
            kids = [add_node(c["m_PathID"], "" if parent_path is None else path_) for c in t["m_Children"] if c["m_PathID"] in trs]
            if kids: node["children"] = kids
            return i
        for r in roots: g.j["scenes"][0]["nodes"].append(add_node(r, None))
        # --- squelette « optimisé » (Optimize Game Objects, ex. M_Shield_New_Base_Rogue) : les os ne sont pas dans
        #     la hiérarchie, on les reconstruit depuis l'Avatar (m_AvatarSkeleton + pose de repos), indexés par hash de chemin
        opt_bones = {}
        for o in env.objects:
            if o.type.name != "Animator": continue
            at = T(o.path_id); gop = at["m_GameObject"]["m_PathID"]
            av = resolve(o.assets_file, at.get("m_Avatar")) if at.get("m_Avatar", {}).get("m_PathID") else None
            if av is None or gop not in tr_of_go: continue
            avt = av.read_typetree(); sk = avt["m_Avatar"]["m_AvatarSkeleton"]["data"]
            pose = avt["m_Avatar"]["m_AvatarSkeletonPose"]["data"]["m_X"]; tos_ = dict(avt["m_TOS"])
            have = set()
            def walk(pid, pre):
                for c in T(pid)["m_Children"]:
                    if c["m_PathID"] in trs:
                        p_ = (pre + "/" if pre else "") + T(go_of[c["m_PathID"]])["m_Name"]; have.add(p_); walk(c["m_PathID"], p_)
            walk(tr_of_go[gop], "")
            ids = sk["m_ID"]
            if sum(1 for h in ids[1:] if tos_.get(h) in have) > len(ids) / 2: continue  # hiérarchie complète : rien à faire
            idx = {0: nidx[tr_of_go[gop]]}
            for k in range(1, len(ids)):
                pth = tos_.get(ids[k], f"bone{k}"); x = pose[k]; tq, qq, sq = x["t"], x["q"], x["s"]
                node = {"name": pth.split("/")[-1], "translation": conv_pos((tq["x"], tq["y"], tq["z"])).tolist(),
                        "rotation": conv_quat((qq["x"], qq["y"], qq["z"], qq["w"])).tolist(), "scale": [sq["x"], sq["y"], sq["z"]]}
                g.j["nodes"].append(node); idx[k] = len(g.j["nodes"]) - 1
                g.j["nodes"][idx[sk["m_Node"][k]["m_ParentId"]]].setdefault("children", []).append(idx[k])
                opt_bones[ids[k]] = idx[k]
        # chemins relatifs à la racine (comme les liaisons d'animation Unity)
        rel = {}
        for i, p in paths.items():
            rel[i] = p
        # --- matériaux
        mat_cache, tex_cache = {}, {}
        def texture_of(mat_ptr, owner):  # même logique qu'export_3d.py
            mo = resolve(owner.assets_file, mat_ptr) if mat_ptr else None
            if mo is None or mo.type.name != "Material": return None
            mat = mo.read_typetree(); envs = mat.get("m_SavedProperties", {}).get("m_TexEnvs", [])
            items = [(k, v) for k, v in envs] if envs and isinstance(envs[0], (list, tuple)) else [(e.get("first"), e.get("second")) for e in envs]
            items = [(k, v) for k, v in items if v and v.get("m_Texture", {}).get("m_PathID")]
            main = [v["m_Texture"] for k, v in items if k and MAIN_TEX.match(k)]
            others = [v["m_Texture"] for k, v in items if not (k and re.search(r"(?i)normal|bump|mask|ramp|matcap|noise|emis|light|spec|flow|dissolve|control|splat", k))]
            # texture principale introuvable : la texture de même nom ailleurs dans le jeu vaut mieux qu'une
            # texture secondaire (masque, détail… souvent noire, ex. ExHall_bu_StatueStand01d)
            byname = None
            for ptr in main + ["BYNAME"] + others:
                if ptr == "BYNAME":
                    byname = texture_by_name(mat.get("m_Name", "") + ("_terrain" if any(k and k.startswith("_Control") for k, v in items) else ""), tex_cache)
                    if byname is not None and byname is not SKIP: break
                    continue
                key = (id(mo.assets_file), ptr["m_FileID"], ptr["m_PathID"])
                if key not in tex_cache:
                    to = resolve(mo.assets_file, ptr)
                    try: tex_cache[key] = (key, to.read().image.convert("RGBA")) if to is not None and to.type.name == "Texture2D" else None
                    except Exception: tex_cache[key] = None
                if tex_cache[key] is not None: return tex_cache[key]
            img = byname
            return img if img is SKIP or img is None else (("png", mat.get("m_Name", "")), img)
        def material(mat_ptr, owner):
            tx = texture_of(mat_ptr, owner)
            if tx is SKIP: return SKIP
            key = tx[0] if tx else None
            if key in mat_cache: return mat_cache[key]
            m = {"pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 0.9}, "doubleSided": True}
            if tx:
                buf = io.BytesIO(); tx[1].save(buf, "PNG")
                g.j["images"].append({"bufferView": g.view(buf.getvalue()), "mimeType": "image/png"})
                g.j["textures"].append({"source": len(g.j["images"]) - 1, "sampler": 0})
                m["pbrMetallicRoughness"]["baseColorTexture"] = {"index": len(g.j["textures"]) - 1}
                am = alpha_mode(tx[1])
                if am == "MASK": m["alphaMode"] = "MASK"; m["alphaCutoff"] = 0.3
            g.j["materials"].append(m); mat_cache[key] = len(g.j["materials"]) - 1
            return mat_cache[key]
        # --- maillages
        nmesh = 0
        for pid, o in objs.items():
            if o.type.name not in ("SkinnedMeshRenderer", "MeshRenderer"): continue
            r = T(pid)
            if not r.get("m_Enabled", 1): continue
            gopid = r["m_GameObject"]["m_PathID"]
            if not T(gopid).get("m_IsActive", 1) or gopid not in tr_of_go: continue
            if o.type.name == "SkinnedMeshRenderer":
                mptr = r["m_Mesh"]
            else:
                mf = [objs[c["component"]["m_PathID"]] for c in T(gopid)["m_Component"]
                      if c["component"]["m_FileID"] == 0 and c["component"]["m_PathID"] in objs and objs[c["component"]["m_PathID"]].type.name == "MeshFilter"]
                mptr = T(mf[0].path_id)["m_Mesh"] if mf else None
            mo = resolve(o.assets_file, mptr) if mptr else None
            if mo is None or mo.type.name != "Mesh": continue
            mesh = mo.read(); h = MeshHandler(mesh); h.process()
            nv = h.m_VertexCount
            if not nv: continue
            def arr(a, keep):
                a = np.array(a, dtype=np.float64)
                if not len(a) or len(a) % nv: return None
                return a.reshape(nv, -1)[:, :keep]
            V = arr(h.m_Vertices, 3)
            if V is None: continue
            V = V * np.array([-1, 1, 1])
            N = arr(h.m_Normals, 3) if h.m_Normals else None
            if N is not None: N = N * np.array([-1, 1, 1]); N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
            UV = arr(h.m_UV0, 2) if h.m_UV0 else None
            bones = [b["m_PathID"] for b in r.get("m_Bones", [])] if o.type.name == "SkinnedMeshRenderer" else []
            joints = [nidx[b] for b in bones if b in nidx] if len(bones) and all(b in nidx for b in bones) else []
            if not bones and opt_bones and o.type.name == "SkinnedMeshRenderer":  # os reconstruits depuis l'Avatar
                bh = list(getattr(mesh, "m_BoneNameHashes", None) or [])
                if bh and all(x in opt_bones for x in bh): joints = [opt_bones[x] for x in bh]
            skinned = bool(joints) and h.m_BoneIndices and len(mesh.m_BindPose) == len(joints)
            attrs = {"POSITION": g.acc(V.astype(np.float32), FLOAT, "VEC3", 34962, True)}
            if N is not None and len(N) == nv: attrs["NORMAL"] = g.acc(N.astype(np.float32), FLOAT, "VEC3", 34962)
            if UV is not None: attrs["TEXCOORD_0"] = g.acc(UV.astype(np.float32) * np.array([1, -1], np.float32) + np.array([0, 1], np.float32), FLOAT, "VEC2", 34962)
            if skinned:
                J = np.zeros((nv, 4), np.uint16); Wt = np.zeros((nv, 4), np.float32)
                weights = h.m_BoneWeights or [[1.0]] * nv  # un seul os par sommet : poids implicite de 100 %
                for k, (ji, wi) in enumerate(zip(h.m_BoneIndices, weights)):
                    ji = ji if isinstance(ji, (list, tuple)) else [ji]; wi = wi if isinstance(wi, (list, tuple)) else [wi]
                    n = min(4, len(ji)); J[k, :n] = ji[:n]; Wt[k, :min(4, len(wi))] = wi[:4]
                sw = Wt.sum(axis=1, keepdims=True); Wt = np.where(sw > 0, Wt / np.maximum(sw, 1e-9), np.array([1, 0, 0, 0], np.float32))
                J = np.clip(J, 0, len(joints) - 1)
                attrs["JOINTS_0"] = g.acc(J, U16, "VEC4", 34962); attrs["WEIGHTS_0"] = g.acc(Wt, FLOAT, "VEC4", 34962)
            prims, mats = [], r.get("m_Materials", [])
            for si, tris in enumerate(h.get_triangles()):
                F = np.array(tris, dtype=np.uint32).reshape(-1, 3)[:, ::-1]
                if not len(F): continue
                mi_ = material(mats[si] if si < len(mats) else (mats[-1] if mats else None), o)
                if mi_ is SKIP: continue  # effet visuel sans texture
                prims.append({"attributes": attrs, "indices": g.acc(F.reshape(-1), U32, "SCALAR", 34963), "material": mi_})
            if not prims: continue
            g.j["meshes"].append({"name": mesh.m_Name, "primitives": prims}); mi = len(g.j["meshes"]) - 1
            if skinned:
                ibm = np.stack([mat_from_unity(b).T.reshape(-1) for b in mesh.m_BindPose]).astype(np.float32)  # colonne-major
                g.j["skins"].append({"joints": joints, "inverseBindMatrices": g.acc(ibm, FLOAT, "MAT4")})
                g.j["nodes"].append({"name": T(gopid)["m_Name"] + "_skin", "mesh": mi, "skin": len(g.j["skins"]) - 1})
                g.j["scenes"][0]["nodes"].append(len(g.j["nodes"]) - 1)
            else:
                g.j["nodes"][nidx[tr_of_go[gopid]]]["mesh"] = mi
            nmesh += 1
        if not nmesh: return {"name": name, "cat": cat, "empty": True}
        # --- animations : chemins des os relatifs à l'objet qui porte l'Animator (comme dans Unity)
        anim_roots = [tr_of_go[T(o.path_id)["m_GameObject"]["m_PathID"]] for o in env.objects
                      if o.type.name == "Animator" and T(o.path_id)["m_GameObject"]["m_PathID"] in tr_of_go]
        def relpath(pid, root_pid):
            parts = []
            while pid != root_pid:
                if pid not in trs: return None
                parts.append(T(go_of[pid])["m_Name"]); pid = T(pid)["m_Father"]["m_PathID"]
            return "/".join(reversed(parts))
        hash2node = {}
        for ar in (anim_roots or roots):
            for pid in trs:
                p = relpath(pid, ar)
                if p is not None and pid in nidx: hash2node.setdefault(zlib.crc32(p.encode("utf-8")), nidx[pid])
        for o in env.objects:  # table officielle hash -> chemin de l'Avatar
            if o.type.name == "Avatar":
                for ar in (anim_roots or roots):
                    bypath = {relpath(pid, ar): nidx[pid] for pid in trs if pid in nidx}
                    for hsh, pth in T(o.path_id)["m_TOS"]:
                        if pth in bypath: hash2node[hsh] = bypath[pth]
        hash2node.update(opt_bones)
        clips_out = []
        # 1) clips du contrôleur réellement branché sur l'Animator du modèle (référence du jeu)
        sources, seen = [], set()
        for o in env.objects:
            if o.type.name != "Animator": continue
            ctrl = resolve(o.assets_file, T(o.path_id).get("m_Controller"))
            if ctrl is None: continue
            ct_ = ctrl.read_typetree()
            if ctrl.type.name == "AnimatorOverrideController":  # contrôleur dérivé : clips remplacés + clips du parent
                base = resolve(ctrl.assets_file, ct_.get("m_Controller"))
                for pair in ct_.get("m_Clips", []):
                    co = resolve(ctrl.assets_file, pair.get("m_OverrideClip") or {})
                    if co is not None: sources.append(("", co))
                if base is not None: ctrl, ct_ = base, base.read_typetree()
            for ptr in ct_.get("m_AnimationClips", []):
                co = resolve(ctrl.assets_file, ptr)
                if co is not None and co.type.name == "AnimationClip": sources.append(("", co))
        # 2) variantes nommées comme le modèle (Ani_<modèle>_study, _councilhall…)
        for ap in sorted(glob.glob(os.path.join(ANI, "Ani_" + name + ".unity3d")) + glob.glob(os.path.join(ANI, "Ani_" + name + "_*.unity3d"))):
            suffix = os.path.splitext(os.path.basename(ap))[0][len("Ani_" + name):].strip("_")
            try: aenv = load(ap)
            except Exception: continue
            sources += [(suffix, co) for co in aenv.objects if co.type.name == "AnimationClip"]
        def add(sources, min_match):
          for suffix, co in sources:
                key = (co.assets_file.name if hasattr(co.assets_file, "name") else id(co.assets_file), co.path_id)
                if key in seen: continue
                seen.add(key)
                try:
                    if min_match:
                        gb_ = co.read_typetree()["m_ClipBindingConstant"]["genericBindings"]
                        tb = [b for b in gb_ if b["typeID"] == 4]
                        if not tb or sum(1 for b in tb if b["path"] in hash2node) / len(tb) < min_match: continue
                    ct = co.read_typetree()
                    dur, t0, curve = decode_clip(ct)
                    times = np.arange(0, dur + 1e-6, 1.0 / FPS); times[-1] = min(times[-1], dur)
                    gb = ct["m_ClipBindingConstant"]["genericBindings"]
                    channels, samplers, cidx = [], [], 0
                    tacc = None
                    for b in gb:
                        size = {1: 3, 2: 4, 3: 3, 4: 3}.get(b["attribute"], 1) if b["typeID"] == 4 else 1
                        node = hash2node.get(b["path"]) if b["typeID"] == 4 else None
                        if node is not None and b["attribute"] in (1, 2, 3, 4):
                            vals = np.array([[curve(cidx + c, t0 + x) for c in range(size)] for x in times], dtype=np.float64)
                            if b["attribute"] == 1: out, path_ = vals * np.array([-1, 1, 1]), "translation"
                            elif b["attribute"] == 3: out, path_ = vals, "scale"
                            else:
                                qs = [conv_quat(v) for v in vals] if b["attribute"] == 2 else [conv_quat(euler_to_quat(*v)) for v in vals]
                                for k in range(1, len(qs)):
                                    if np.dot(qs[k], qs[k - 1]) < 0: qs[k] = -qs[k]
                                out, path_ = np.array(qs), "rotation"
                            if tacc is None: tacc = g.acc(times.astype(np.float32).reshape(-1, 1), FLOAT, "SCALAR", None, True)
                            samplers.append({"input": tacc, "output": g.acc(out.astype(np.float32), FLOAT, {3: "VEC3", 4: "VEC4"}[out.shape[1]]), "interpolation": "LINEAR"})
                            channels.append({"sampler": len(samplers) - 1, "target": {"node": node, "path": path_}})
                        cidx += size
                    if channels:
                        cname = ct["m_Name"] + (f" ({suffix})" if suffix else "")
                        g.j["animations"].append({"name": cname, "channels": channels, "samplers": samplers})
                        clips_out.append({"name": cname, "duration": round(float(dur), 2)})
                except Exception as e:
                    print("clip ignoré", name, co.peek_name(), type(e).__name__, e, flush=True)
        add(sources, 0.0)
        # 3) repli (contrôleur branché à l'exécution, ex. M_Cat_Base05, ou variantes de couleur) : clips de la
        #    même famille (Ani_*Cat_Base*, puis en raccourcissant le nom : Shield_New_Base_purple -> Shield_New_Base…),
        #    gardés seulement si >= 70 % de leurs courbes d'os correspondent à ce squelette
        if not clips_out:
            parts = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", re.sub(r"^[CM]_", "", name)).split("_")
            for k in range(len(parts), 0, -1):
                core = "_".join(parts[:k])
                if len(core) < 3: break
                cands = sorted(glob.glob(os.path.join(ANI, f"Ani_*{core}*.unity3d")))
                cands = [x for x in cands if not os.path.basename(x).startswith("Ani_B_")] or cands
                cands.sort(key=lambda x: (not re.match(rf"Ani_[CM]_{re.escape(core)}(_|\.)", os.path.basename(x), re.I), x))
                fam = []
                for ap in cands[:16]:
                    try: aenv = load(ap)
                    except Exception: continue
                    fam += [(os.path.splitext(os.path.basename(ap))[0][4:], co) for co in aenv.objects if co.type.name == "AnimationClip"]
                add(fam, 0.7)
                if clips_out: break
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        g.save(dst)
        return {"name": name, "cat": cat, "file": f"models_anim/{cat}/{name}.glb", "clips": clips_out,
                "bones": len(nidx) + len(opt_bones), "size": round(os.path.getsize(dst) / 1e6, 2)}
    except Exception as e:
        return {"name": name, "cat": cat, "error": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-600:]}

if __name__ == "__main__":
    names = [os.path.splitext(os.path.basename(p))[0] for p in glob.glob(PROJECT + r"\Site\models\*\*.glb")]
    if len(sys.argv) > 1: names = [n for n in names if any(re.fullmatch(a, n) for a in sys.argv[1:])]
    _xl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra_files.txt")
    _paths = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(_xl, encoding="utf-8")} if os.path.exists(_xl) else {}
    files = [_paths.get(n, os.path.join(A, n + ".unity3d")) for n in sorted(names)]
    print(len(files), "modèles", flush=True)
    res = []
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 4)) as ex:
        for k, r in enumerate(ex.map(export, files), 1):
            res.append(r)
            if "error" in r: print("ERREUR", r["name"], r["error"], r.get("tb", "")[-300:], flush=True)
            if k % 25 == 0: print(f"{k}/{len(files)}", flush=True)
    mj = os.path.join(OUT, "anim.json")
    old = json.load(open(mj, encoding="utf-8")) if os.path.exists(mj) else []
    done = {r["name"] for r in res}
    allr = [o for o in old if o["name"] not in done] + [r for r in res if "file" in r]
    os.makedirs(OUT, exist_ok=True)
    json.dump(sorted(allr, key=lambda m: (m["cat"], m["name"].lower())), open(mj, "w", encoding="utf-8"), ensure_ascii=False)
    print("TERMINE", len([r for r in res if "file" in r]), "modèles riggés,",
          sum(len(r.get("clips", [])) for r in res), "animations,", sum(1 for r in res if "error" in r), "erreurs", flush=True)
