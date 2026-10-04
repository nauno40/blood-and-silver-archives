"""Nom de matériau (minuscules, sans _timeline) -> nom du shader, d'après les bundles où le shader est présent."""
from config import ASSETS  # chemins : voir tools/config.py
import os, json, re
from concurrent.futures import ProcessPoolExecutor
A = ASSETS
def scan(rel):
    import UnityPy
    out = {}
    try:
        d = open(os.path.join(A, rel), "rb").read(); i = d.find(b"UnityFS\x00"); env = UnityPy.load(d[i:])
        sh = {o.path_id: o.read_typetree()["m_ParsedForm"]["m_Name"] for o in env.objects if o.type.name == "Shader"}
        for o in env.objects:
            if o.type.name == "Material":
                m = o.read_typetree(); p = m.get("m_Shader", {})
                if p.get("m_FileID") == 0 and p.get("m_PathID") in sh:
                    out[re.sub(r"_timeli+ne$", "", m["m_Name"].lower())] = sh[p["m_PathID"]]
    except Exception: pass
    return out
if __name__ == "__main__":
    C = json.load(open("census.json", encoding="utf-8"))
    rels = [k for k, x in C.items() if x.get("types", {}).get("Shader") and x["types"].get("Material")]
    res = {}
    with ProcessPoolExecutor(10) as ex:
        for r in ex.map(scan, rels, chunksize=8): res.update(r)
    json.dump(res, open("shader_by_material.json", "w"), indent=0)
    import collections; print(len(res), collections.Counter(res.values()).most_common(12))
