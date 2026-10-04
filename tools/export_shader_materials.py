r"""Pour chaque shader extrait (Shaders\index.json), retrouve des matériaux du jeu qui l'utilisent et exporte de quoi
faire un aperçu en direct sur le site : valeurs (floats, couleurs), textures (PNG), échelle/décalage, mots-clés.
Sortie : <projet>\Site\shader_preview\<dossier>\material.json + textures\*.png"""
from config import PROJECT, TOOLS_DIR, ASSETS  # chemins : voir tools/config.py
import os, re, json, hashlib
from concurrent.futures import ProcessPoolExecutor

ROOT = PROJECT
ASSETS = ASSETS
OUT = os.path.join(ROOT, "Site", "shader_preview")
TOOLS = TOOLS_DIR
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

def scan(rel):
    """Matériaux de ce bundle qui pointent vers un Shader du même bundle -> [(nom_shader, matériau, score)]."""
    exec(open(os.path.join(TOOLS, "export_3d.py"), encoding="utf-8-sig").read().split("_EXTRA = None")[0], globals())
    out = []
    try:
        env = load(os.path.join(ASSETS, rel))
        shaders = {}
        for o in env.objects:
            if o.type.name == "Shader":
                try: shaders[o.path_id] = o.read_typetree()["m_ParsedForm"]["m_Name"]
                except Exception: pass
        for o in env.objects:
            if o.type.name != "Material": continue
            m = o.read_typetree(); sp = m.get("m_Shader", {})
            name = shaders.get(sp.get("m_PathID")) if sp.get("m_FileID") == 0 else None
            if not name:
                so = resolve(o.assets_file, sp)
                try: name = so.read_typetree()["m_ParsedForm"]["m_Name"] if so is not None else None
                except Exception: name = None
            if not name: continue
            props = m.get("m_SavedProperties", {})
            def items(x): return [(k, v) for k, v in x] if x and isinstance(x[0], (list, tuple)) else [(e.get("first"), e.get("second")) for e in x]
            floats = {k: v for k, v in items(props.get("m_Floats", []))}
            colors = {k: [v["r"], v["g"], v["b"], v["a"]] for k, v in items(props.get("m_Colors", []))}
            texs, imgs = {}, {}
            for k, v in items(props.get("m_TexEnvs", [])):
                st = [v["m_Scale"]["x"], v["m_Scale"]["y"], v["m_Offset"]["x"], v["m_Offset"]["y"]]
                texs[k] = {"st": st}
                ptr = v.get("m_Texture", {})
                if not ptr.get("m_PathID"): continue
                to = resolve(o.assets_file, ptr)
                if to is None: continue
                try:
                    t = to.read()
                    if to.type.name == "Texture2D":
                        im = t.image.convert("RGBA"); im.thumbnail((1024, 1024)); imgs[k] = ("2D", im)
                    elif to.type.name == "Cubemap":
                        exec(open(os.path.join(TOOLS, "extract_cubemaps.py"), encoding="utf-8").read().split("def cross")[0], globals())
                        fs = faces(t)
                        if fs: imgs[k] = ("Cube", [f.resize((256, 256)) for f in fs])
                except Exception:
                    pass
            kw = m.get("m_ValidKeywords") or (m.get("m_ShaderKeywords") or "").split()
            out.append((name, {"material": m.get("m_Name"), "bundle": rel, "floats": floats, "colors": colors, "textures": texs,
                               "keywords": kw, "renderQueue": m.get("m_CustomRenderQueue", -1)}, imgs, len(imgs)))
    except Exception:
        pass
    return out

if __name__ == "__main__":
    C = json.load(open(os.path.join(TOOLS, "census.json"), encoding="utf-8"))
    idx = json.load(open(os.path.join(ROOT, "Shaders", "index.json"), encoding="utf-8"))
    wanted = {s["name"]: s["folder"] for s in idx}
    rels = [k for k, x in C.items() if x.get("types", {}).get("Shader") and x["types"].get("Material")]
    best = {}  # shader -> liste (score, matériau, images), les 3 meilleurs matériaux distincts
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for res in ex.map(scan, rels, chunksize=4):
            for name, mat, imgs, score in res:
                if name not in wanted: continue
                L = best.setdefault(name, [])
                if any(x[1]["material"] == mat["material"] for x in L): continue
                L.append((score, mat, imgs)); L.sort(key=lambda x: -x[0]); del L[3:]
    total = 0
    for name, L in best.items():
        folder = os.path.join(OUT, BAD.sub("_", wanted[name])); os.makedirs(os.path.join(folder, "textures"), exist_ok=True)
        mats = []
        for k, (score, mat, imgs) in enumerate(L):
            for prop, (kind, im) in imgs.items():
                if kind == "2D":
                    fn = f"m{k}_{BAD.sub('_', prop)}.png"; im.save(os.path.join(folder, "textures", fn)); mat["textures"][prop]["file"] = "textures/" + fn
                else:
                    fns = []
                    for fi, f in enumerate(im):
                        fn = f"m{k}_{BAD.sub('_', prop)}_{fi}.png"; f.save(os.path.join(folder, "textures", fn)); fns.append("textures/" + fn)
                    mat["textures"][prop]["cube"] = fns
                total += 1
            mats.append(mat)
        json.dump({"shader": name, "materials": mats}, open(os.path.join(folder, "material.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("TERMINE", len(best), "shaders avec matériaux,", total, "textures", flush=True)
    for name in sorted(wanted):
        L = best.get(name, [])
        print(f"  {name:50} {len(L)} matériau(x)", [f'{x[1]["material"]}({x[0]} tex)' for x in L], flush=True)
