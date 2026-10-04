r"""Extrait les shaders du jeu (objets Shader des bundles) : pour chaque shader distinct,
  <projet>\Site\shaders\<Nom>\<Nom>.shader  : squelette ShaderLab lisible (propriétés + valeurs par défaut,
                                                          sous-shaders, passes, états de rendu, tags, mots-clés)
  <projet>\Site\shaders\<Nom>\glsl\NNN_<etape>.glsl : programmes GPU OpenGL ES 3 (source GLSL, plateforme 9),
                                                          décompressés (LZ4) du blob du shader, doublons retirés.
Toutes les copies d'un même shader (une par bundle, souvent partielles) sont fusionnées. Index : Shaders\index.json"""
from config import PROJECT, TOOLS_DIR, ASSETS  # chemins : voir tools/config.py
import os, re, json, hashlib
from concurrent.futures import ProcessPoolExecutor

ASSETS = ASSETS
OUT = PROJECT + r"\Site\shaders"
CENSUS = TOOLS_DIR + r"\census.json"
PLATFORMS = {0: "OpenGL", 4: "D3D11", 5: "GLES2", 9: "GLES3", 14: "Metal", 15: "OpenGLCore", 18: "Vulkan", 19: "Switch"}
PROPTYPE = {0: "Color", 1: "Vector", 2: "Float", 3: "Range", 4: "2D", 5: "Int"}
TEXDIM = {2: "2D", 3: "3D", 4: "Cube", 5: "2DArray", 6: "CubeArray"}
CULL = {0: "Off", 1: "Front", 2: "Back"}; ZTEST = {0: "Disabled", 1: "Never", 2: "Less", 3: "Equal", 4: "LEqual", 5: "Greater", 6: "NotEqual", 7: "GEqual", 8: "Always"}
BLEND = {0: "Zero", 1: "One", 2: "DstColor", 3: "SrcColor", 4: "OneMinusDstColor", 5: "SrcAlpha", 6: "OneMinusSrcColor", 7: "DstAlpha",
         8: "OneMinusDstAlpha", 9: "SrcAlphaSaturate", 10: "OneMinusSrcAlpha"}
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

def programs(t):
    """Textes GLSL contenus dans le blob compressé (toutes plateformes GLES)."""
    import lz4.block
    blob = bytes(t.get("compressedBlob") or b""); out = []
    def lst(x): return x if isinstance(x, list) else [x]
    for pi, plat in enumerate(t.get("platforms", [])):
        offs, cl, dl = lst(t["offsets"][pi]), lst(t["compressedLengths"][pi]), lst(t["decompressedLengths"][pi])
        for a, b, c in zip(offs, cl, dl):
            try: raw = lz4.block.decompress(blob[a:a + b], uncompressed_size=c)
            except Exception: continue
            for m in re.finditer(rb"#version [^\x00]+", raw):
                out.append((PLATFORMS.get(plat, str(plat)), m.group(0).decode("utf-8", "replace")))
    return out

def v(x): return x.get("val", x) if isinstance(x, dict) else x

def header(pf):
    L = [f'Shader "{pf["m_Name"]}"', "{"]
    props = pf.get("m_PropInfo", {}).get("m_Props", [])
    if props:
        L.append("  Properties {")
        for p in props:
            ty = PROPTYPE.get(p["m_Type"], str(p["m_Type"])); dv = p.get("m_DefValue[0]", None)
            vals = [p.get(f"m_DefValue[{k}]", 0) for k in range(4)]
            if ty == "Range": dflt, ty = f"{vals[0]:g}", f"Range({vals[1]:g}, {vals[2]:g})"
            elif ty in ("Color", "Vector"): dflt = "(" + ", ".join(f"{x:g}" for x in vals) + ")"
            elif ty == "2D": ty = TEXDIM.get(p.get("m_DefTexture", {}).get("m_TexDim", 2), "2D"); dflt = f'"{p.get("m_DefTexture", {}).get("m_DefaultName", "")}" {{}}'
            else: dflt = f"{vals[0]:g}"
            attrs = "".join(f"[{a}] " for a in p.get("m_Attributes", []))
            L.append(f'    {attrs}{p["m_Name"]} ("{p["m_Description"]}", {ty}) = {dflt}')
        L.append("  }")
    for ss in pf.get("m_SubShaders", []):
        L.append("  SubShader {")
        tags = ss.get("m_Tags", {}).get("tags", [])
        if tags: L.append("    Tags { " + " ".join(f'"{k}"="{val}"' for k, val in tags) + " }")
        if ss.get("m_LOD"): L.append(f"    LOD {ss['m_LOD']}")
        for p in ss.get("m_Passes", []):
            st = p.get("m_State", {}); name = st.get("m_Name") or p.get("m_Name") or ""
            L.append(f'    Pass {{  // {"Pass" if p.get("m_Type", 0) == 0 else "UsePass/GrabPass"}' + (f' "{name}"' if name else ""))
            pt = p.get("m_Tags", {}).get("tags", [])
            if pt: L.append("      Tags { " + " ".join(f'"{k}"="{val}"' for k, val in pt) + " }")
            if st:
                b = st.get("rtBlend0", {})
                src, dst = int(v(b.get("srcBlend", 1))), int(v(b.get("destBlend", 0)))
                L.append(f"      Cull {CULL.get(int(v(st.get('culling', 2))), '?')}  ZWrite {'On' if v(st.get('zWrite', 1)) else 'Off'}  ZTest {ZTEST.get(int(v(st.get('zTest', 4))), '?')}"
                         + ("" if (src, dst) == (1, 0) else f"  Blend {BLEND.get(src, src)} {BLEND.get(dst, dst)}"))
            L.append("    }")
        L.append("  }")
    if pf.get("m_FallbackName"): L.append(f'  Fallback "{pf["m_FallbackName"]}"')
    kws = pf.get("m_KeywordNames", [])
    if kws: L.append("  // mots-clés (variantes) : " + " ".join(kws))
    L.append("}")
    return "\n".join(L)

def scan(rel):
    import UnityPy
    res = []
    try:
        d = open(os.path.join(ASSETS, rel), "rb").read(); i = d.find(b"UnityFS\x00"); env = UnityPy.load(d[i:])
        for o in env.objects:
            if o.type.name != "Shader": continue
            try:
                t = o.read_typetree(); pf = t["m_ParsedForm"]
                res.append((pf["m_Name"], header(pf), len(pf.get("m_PropInfo", {}).get("m_Props", [])),
                            sum(len(s.get("m_Passes", [])) for s in pf.get("m_SubShaders", [])), programs(t), rel))
            except Exception as e:
                res.append(("?erreur", f"{type(e).__name__}: {e}", 0, 0, [], rel))
    except Exception:
        pass
    return res

if __name__ == "__main__":
    C = json.load(open(CENSUS, encoding="utf-8"))
    rels = [k for k, x in C.items() if x.get("types", {}).get("Shader")]
    shaders = {}
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for items in ex.map(scan, rels, chunksize=8):
            for name, hdr, nprops, npass, progs, rel in items:
                s = shaders.setdefault(name, {"best": (-1, -1, ""), "progs": {}, "bundles": set()})
                s["bundles"].add(rel)
                if (nprops, npass) > s["best"][:2]: s["best"] = (nprops, npass, hdr)
                for plat, code in progs:
                    s["progs"].setdefault(hashlib.md5(code.encode()).hexdigest(), (plat, code))
    index = []
    for name, s in sorted(shaders.items()):
        if name.startswith("?"): continue
        folder = os.path.join(OUT, BAD.sub("_", name.replace("/", "_")))
        os.makedirs(os.path.join(folder, "glsl"), exist_ok=True)
        files = []
        for k, (plat, code) in enumerate(sorted(s["progs"].values(), key=lambda x: (x[0], len(x[1])))):
            # un programme = shader de sommets puis shader de fragments, chacun commençant par « #version »
            parts = [x for x in re.split(r"(?=#version )", code) if x.strip()]
            for part in parts:
                end = part.rfind("\n}")  # fin du main : on retire les restes d'emballage (#endif, octets binaires)
                if end > 0: part = part[:end + 2] + "\n"
                stage = "frag" if re.search(r"(?i)out\s+\w*\s*vec4\s+SV_Target", part) or "gl_Position" not in part else "vert"
                fn = f"{k:03d}_{plat}.{stage}.glsl"
                open(os.path.join(folder, "glsl", fn), "w", encoding="utf-8").write(part); files.append(fn)
        hdr = s["best"][2] + "\n\n// Programmes GPU extraits (" + str(len(files)) + ") : dossier glsl\\\n" + "".join(f"//   {f}\n" for f in files) \
              + "// Présent dans " + str(len(s["bundles"])) + " bundle(s), ex. : " + ", ".join(sorted(s["bundles"])[:3]) + "\n"
        open(os.path.join(folder, BAD.sub("_", name.replace("/", "_")) + ".shader"), "w", encoding="utf-8").write(hdr)
        index.append({"name": name, "folder": os.path.relpath(folder, OUT), "props": s["best"][0], "passes": s["best"][1], "programs": len(files), "bundles": len(s["bundles"])})
    json.dump(index, open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    errs = shaders.get("?erreur", {}).get("bundles", set())
    print("TERMINE", len(index), "shaders,", sum(x["programs"] for x in index), "programmes GLSL,", len(errs), "copies illisibles", flush=True)
    for x in index: print(f'  {x["name"]:52} props={x["props"]:3} passes={x["passes"]:2} glsl={x["programs"]:4} bundles={x["bundles"]}', flush=True)
