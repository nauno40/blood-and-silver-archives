r"""Exporte les modèles 3D du jeu (personnages C_*, monstres M_*, décors *_SceneRoot) en GLB texturé.

Pour chaque bundle : chaque (Skinned)MeshRenderer actif -> maillage en pose de référence, placé avec la
matrice monde de son GameObject, matériau = texture principale du matériau Unity. Repère Unity (main gauche)
converti en glTF (main droite) : X inversé + ordre des triangles inversé.
Sortie : <projet>\Site\models\<categorie>\<bundle>.glb + models.json + vignette PNG."""
from config import PROJECT, TOOLS_DIR, ASSETS  # chemins : voir tools/config.py
import os, re, sys, glob, json, io, traceback
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor

A = ASSETS + r"\ABResource"
OUT = PROJECT + r"\Site\models"

def load(p):
    import UnityPy
    d = open(p, "rb").read(); i = d.find(b"UnityFS\x00")
    return UnityPy.load(d[i:] if i > 0 else d)

_CAB = None
_EXT = {}
def resolve(assets_file, ptr):
    """Objet pointé par ptr ({m_FileID, m_PathID}), y compris dans un autre bundle (via cab_index.json)."""
    global _CAB
    if not ptr or not ptr.get("m_PathID"): return None
    fid = ptr["m_FileID"]
    if fid == 0:
        return assets_file.objects.get(ptr["m_PathID"])
    try:
        ext = assets_file.externals[fid - 1].path
    except Exception:
        return None
    cab = ext.split("/")[-1].split(".")[0].lower()
    if _CAB is None:
        _CAB = json.load(open(TOOLS_DIR + r"\cab_index.json"))
    p = _CAB.get(cab)
    if not p: return None
    if p not in _EXT:
        if len(_EXT) > 40: _EXT.clear()
        e = load(p)
        _EXT[p] = {k.lower().split(".")[0]: f for f in e.files.values() for k, f in getattr(f, "files", {}).items()}
    f = _EXT[p].get(cab)
    return f.objects.get(ptr["m_PathID"]) if f is not None and hasattr(f, "objects") else None

def quat_mat(q):
    x, y, z, w = q["x"], q["y"], q["z"], q["w"]
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])

MAIN_TEX = re.compile(r"(?i)^_(MainTex|BaseMap|BaseColorMap|Albedo|AlbedoMap|Diffuse|DiffuseTex|ColorTex|BaseTex|MainTexture)$")

SKIP = "SKIP"
def texture_by_name(mat_name, cache):
    """Repli quand la texture du matériau est dans un bundle absent du téléphone (décors ExHall/Ophall) :
    texture de même nom ailleurs dans le jeu (voir tex_by_name.py). SKIP pour les effets sans texture."""
    from tex_by_name import lookup
    hit = lookup(mat_name)
    if hit:
        k = ("png", hit["diffuse"])
        if k not in cache:
            from PIL import Image
            try: cache[k] = Image.open(hit["diffuse"]).convert("RGBA")
            except Exception: cache[k] = None
        return cache[k]
    return SKIP if re.match(r"(?i)(fx_|panner|.*_(fx|light|smoke|fire)\d*$|.*(fogbase|_far\d*$|mask_window))", mat_name) else None

def alpha_mode(tex):
    """Masque de découpe seulement si l'alpha sert vraiment de transparence : une part nette de pixels
    vides ET une part nette de pixels pleins. Sinon (alpha utilisé pour autre chose : brillance, masque
    d'effet… ex. M_Cat_Base05 dont l'alpha vaut ~30 % partout) le matériau est opaque."""
    a = np.asarray(tex.getchannel("A"), dtype=np.uint8)
    if a.min() >= 250: return "OPAQUE"
    empty, full = (a < 20).mean(), (a > 200).mean()
    return "MASK" if empty > 0.02 and full > 0.10 else "OPAQUE"

_EXTRA = None
def category(name):
    global _EXTRA
    if _EXTRA is None:
        f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra_cats.json")
        _EXTRA = json.load(open(f)) if os.path.exists(f) else {}
    if name in _EXTRA: return _EXTRA[name]  # cartes, pnj, objets, cinematiques
    if name.startswith("C_"): return "personnages"
    if name.startswith("M_"): return "monstres"
    return "decors"

def export(path):
    import trimesh
    from PIL import Image
    from UnityPy.helpers.MeshHelper import MeshHandler
    name = os.path.splitext(os.path.basename(path))[0]
    cat = category(name)
    dst = os.path.join(OUT, cat, name + ".glb")
    if os.path.exists(dst): return {"name": name, "cat": cat, "skip": True}
    try:
        env = load(path)
        objs = {o.path_id: o for o in env.objects}
        tt = {}
        def T(pid):
            if pid not in tt: tt[pid] = objs[pid].read_typetree()
            return tt[pid]
        # matrices monde des Transform
        tr_of_go, world = {}, {}
        for pid, o in objs.items():
            if o.type.name in ("Transform", "RectTransform"):
                tr_of_go[T(pid)["m_GameObject"]["m_PathID"]] = pid
        def W(tpid):
            if tpid in world: return world[tpid]
            t = T(tpid)
            m = np.eye(4)
            m[:3, :3] = quat_mat(t["m_LocalRotation"]) * np.array([t["m_LocalScale"][k] for k in "xyz"])
            m[:3, 3] = [t["m_LocalPosition"][k] for k in "xyz"]
            par = t["m_Father"]["m_PathID"]
            world[tpid] = (W(par) @ m) if par and par in objs else m
            return world[tpid]
        def active(gopid):  # actif seulement si toute la chaîne de parents l'est
            tp = tr_of_go.get(gopid)
            while tp:
                go = T(T(tp)["m_GameObject"]["m_PathID"])
                if not go.get("m_IsActive", 1): return False
                par = T(tp)["m_Father"]["m_PathID"]
                tp = par if par in objs else None
            return True
        tex_cache = {}
        def texture_of(mat_ptr, owner):
            mo = resolve(owner.assets_file, mat_ptr) if mat_ptr else None
            if mo is None or mo.type.name != "Material": return None
            mat = mo.read_typetree()
            envs = mat.get("m_SavedProperties", {}).get("m_TexEnvs", [])
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
                    try: tex_cache[key] = to.read().image.convert("RGBA") if to is not None and to.type.name == "Texture2D" else None
                    except Exception: tex_cache[key] = None
                if tex_cache[key] is not None: return tex_cache[key]
            return byname

        scene = trimesh.Scene()
        flip = np.diag([-1.0, 1, 1, 1])
        nmesh = 0; ntex = 0
        for pid, o in objs.items():
            if o.type.name not in ("SkinnedMeshRenderer", "MeshRenderer"): continue
            r = T(pid)
            if not r.get("m_Enabled", 1): continue
            gopid = r["m_GameObject"]["m_PathID"]
            if not active(gopid): continue
            if o.type.name == "SkinnedMeshRenderer":
                mptr = r["m_Mesh"]
            else:  # MeshFilter du même GameObject
                mf = [objs[c["component"]["m_PathID"]] for c in T(gopid)["m_Component"]
                      if c["component"]["m_FileID"] == 0 and c["component"]["m_PathID"] in objs and objs[c["component"]["m_PathID"]].type.name == "MeshFilter"]
                mptr = T(mf[0].path_id)["m_Mesh"] if mf else None
            mo = resolve(o.assets_file, mptr) if mptr else None
            if mo is None or mo.type.name != "Mesh": continue
            mesh = mo.read()
            h = MeshHandler(mesh); h.process()
            if not h.m_VertexCount or not h.m_Vertices: continue
            nv = h.m_VertexCount
            def arr(a, keep):  # tableaux à 2, 3 ou 4 composantes selon le format du maillage
                a = np.array(a, dtype=np.float64)
                if not len(a) or len(a) % nv: return None
                return a.reshape(nv, -1)[:, :keep]
            V = arr(h.m_Vertices, 3)
            if V is None: continue
            N = arr(h.m_Normals, 3) if h.m_Normals else None
            UV = arr(h.m_UV0, 2) if h.m_UV0 else None
            # Les SkinnedMesh sont déjà exprimés dans le repère de la racine du personnage : matrice du renderer
            M = flip @ W(tr_of_go[gopid]) if gopid in tr_of_go else flip
            Vw = (np.c_[V, np.ones(len(V))] @ M.T)[:, :3]
            Nw = None
            if N is not None and len(N) == len(V):
                Nw = N @ np.linalg.inv(M[:3, :3]).T
                Nw /= np.maximum(np.linalg.norm(Nw, axis=1, keepdims=True), 1e-9)
            mats = r.get("m_Materials", [])
            subs = h.get_triangles()
            for si, tris in enumerate(subs):
                F = np.array(tris, dtype=np.int64).reshape(-1, 3)
                if not len(F): continue
                if np.linalg.det(M[:3, :3]) < 0: F = F[:, ::-1]  # changement de main ; pas pour les objets en miroir (échelle négative)
                used = np.unique(F); remap = -np.ones(len(V), dtype=np.int64); remap[used] = np.arange(len(used))
                tex = texture_of(mats[si] if si < len(mats) else (mats[-1] if mats else None), o)
                if tex is SKIP: continue  # effet visuel (feu, fumée, rayons) sans texture : panneau gris inutile
                vis = None
                uv = None
                if UV is not None and len(UV) == len(V): uv = UV[used].copy()
                elif tex is not None:  # pas d'UV : le shader du jeu projette la texture depuis la position (triplanaire) -> projection vue de dessus
                    uv = Vw[used][:, [0, 2]] / 6.0
                if uv is not None:
                    if tex is not None:
                        mat = trimesh.visual.material.PBRMaterial(baseColorTexture=tex, metallicFactor=0.0, roughnessFactor=0.9, doubleSided=True,
                                                                  alphaMode=alpha_mode(tex), alphaCutoff=0.3)
                        vis = trimesh.visual.TextureVisuals(uv=uv, material=mat); ntex += 1
                if vis is None:  # sans texture : eau translucide, sinon couleur du matériau (_BaseColor) plutôt que blanc
                    mp_ = mats[si] if si < len(mats) else (mats[-1] if mats else None)
                    mo_ = resolve(o.assets_file, mp_) if mp_ else None
                    col, mname = None, ""
                    if mo_ is not None and mo_.type.name == "Material":
                        mt_ = mo_.read_typetree(); mname = mt_.get("m_Name", "")
                        cl = mt_.get("m_SavedProperties", {}).get("m_Colors", [])
                        cl = [(k, v) for k, v in cl] if cl and isinstance(cl[0], (list, tuple)) else [(e.get("first"), e.get("second")) for e in cl]
                        col = next(([v["r"], v["g"], v["b"], 1.0] for k, v in cl if k in ("_BaseColor", "_Color", "_MainColor") and v), None)
                    if re.search(r"(?i)water|sea|ocean|pool.*water|lake|river", mname + " " + T(gopid)["m_Name"]):
                        mat = trimesh.visual.material.PBRMaterial(baseColorFactor=[0.12, 0.30, 0.40, 0.75], metallicFactor=0.0, roughnessFactor=0.15,
                                                                  alphaMode="BLEND", doubleSided=True)
                        vis = trimesh.visual.TextureVisuals(material=mat); ntex += 1
                    elif col and max(col[:3]) > 0.05 and min(col[:3]) < 0.97 and max(col[:3]) - min(col[:3]) < 0.45:  # couleurs « naturelles » seulement (pas le rouge/vert de débogage)
                        mat = trimesh.visual.material.PBRMaterial(baseColorFactor=[min(1, c) for c in col], metallicFactor=0.0, roughnessFactor=0.9, doubleSided=True)
                        vis = trimesh.visual.TextureVisuals(material=mat)
                tm = trimesh.Trimesh(vertices=Vw[used], faces=remap[F], vertex_normals=Nw[used] if Nw is not None else None,
                                     visual=vis, process=False)
                scene.add_geometry(tm, node_name=f"{T(gopid)['m_Name']}_{si}", geom_name=f"{mesh.m_Name}_{si}")
                nmesh += 1
        if not nmesh: return {"name": name, "cat": cat, "empty": True}
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        scene.export(dst, file_type="glb")
        b = scene.bounds
        return {"name": name, "cat": cat, "file": f"models/{cat}/{name}.glb", "meshes": nmesh, "textured": ntex,
                "size": round(os.path.getsize(dst) / 1e6, 2), "bounds": b.tolist() if b is not None else None}
    except Exception as e:
        return {"name": name, "cat": cat, "error": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-400:]}

if __name__ == "__main__":
    pats = sys.argv[1:] or ["C_*.unity3d", "M_*.unity3d", "*SceneRoot*.unity3d"]
    if pats and pats[0].startswith("@"):  # @liste.txt : chemins complets (autres dossiers que ABResource, ex. Scenes)
        pats = [l.strip() for l in open(pats[0][1:], encoding="utf-8-sig") if l.strip()]
    files = sorted({f for p in pats for f in glob.glob(p if os.path.isabs(p) else os.path.join(A, p))})
    files = [f for f in files if not re.search(r"(?i)_shadow|rogue_inst|_mob$|_annex$|cameraani|_U$", os.path.basename(f)[:-8])]
    print(len(files), "bundles", flush=True)
    res = []
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 4)) as ex:
        for k, r in enumerate(ex.map(export, files), 1):
            res.append(r)
            if "error" in r: print("ERREUR", r["name"], r["error"], flush=True)
            if k % 50 == 0: print(f"{k}/{len(files)}", flush=True)
    old = []
    mj = os.path.join(OUT, "models.json")
    if os.path.exists(mj): old = [m for m in json.load(open(mj, encoding="utf-8")) if m["name"] not in {r["name"] for r in res}]
    ok = [r for r in res if "file" in r] + [m for m in old if "file" in m]
    # modèles déjà exportés lors d'un passage précédent
    for r in res:
        if r.get("skip"):
            f = os.path.join(OUT, r["cat"], r["name"] + ".glb")
            ok.append({"name": r["name"], "cat": r["cat"], "file": f"models/{r['cat']}/{r['name']}.glb", "size": round(os.path.getsize(f) / 1e6, 2)})
    os.makedirs(OUT, exist_ok=True)
    json.dump(sorted(ok, key=lambda m: (m["cat"], m["name"].lower())), open(mj, "w", encoding="utf-8"), ensure_ascii=False)
    from collections import Counter
    print("TERMINE", Counter(m["cat"] for m in ok), "vides", sum(1 for r in res if r.get("empty")), "erreurs", sum(1 for r in res if "error" in r), flush=True)
