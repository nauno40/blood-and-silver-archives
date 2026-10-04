"""Recensement de tous les bundles Unity du jeu : types d'objets contenus (sans les décoder) + quelques noms.
Sortie : census.json  {chemin relatif: {"types": {type: n}, "names": {type: [noms…]}, "size": octets}}"""
import os, sys, json, collections
from concurrent.futures import ProcessPoolExecutor

ROOT = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets"
OUT = r"C:\Users\Nauno\.bns_tools\census.json"
KEEP = {"Mesh", "SkinnedMeshRenderer", "MeshRenderer", "Sprite", "Texture2D", "AnimationClip", "Animator", "Animation",
        "AnimatorController", "AudioClip", "VideoClip", "TextAsset", "MonoBehaviour", "ParticleSystem", "Material",
        "Font", "Shader", "Terrain", "TerrainData", "LightmapSettings", "RenderSettings", "SpriteAtlas", "Canvas",
        "RectTransform", "Transform", "GameObject", "Avatar", "Camera", "Light", "LineRenderer", "TrailRenderer", "Tilemap"}

def scan(p):
    try:
        import UnityPy
        d = open(p, "rb").read(); i = d.find(b"UnityFS\x00")
        if i < 0: return p, {"error": "pas un bundle"}
        env = UnityPy.load(d[i:])
        types = collections.Counter(); names = collections.defaultdict(list)
        for o in env.objects:
            t = o.type.name; types[t] += 1
            if t in ("Mesh", "AnimationClip", "Sprite", "TextAsset", "AudioClip", "VideoClip", "GameObject") and len(names[t]) < 6:
                try: names[t].append(o.peek_name())
                except Exception: pass
        scene = any(getattr(f, "is_scene", False) or str(k).lower().endswith(".unity") or "BuildPlayer-" in str(k)
                    for k, f in env.files.items()) if hasattr(env, "files") else False
        return p, {"types": {k: v for k, v in types.items() if k in KEEP or v > 0}, "names": dict(names),
                   "size": os.path.getsize(p), "scene": scene}
    except Exception as e:
        return p, {"error": f"{type(e).__name__}: {e}"[:200], "size": os.path.getsize(p)}

if __name__ == "__main__":
    files = []
    for r, _, fs in os.walk(ROOT):
        for f in fs:
            p = os.path.join(r, f)
            if os.path.getsize(p) > 64: files.append(p)
    print(len(files), "fichiers", flush=True)
    res = {}
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for k, (p, r) in enumerate(ex.map(scan, files, chunksize=8), 1):
            res[os.path.relpath(p, ROOT)] = r
            if k % 1000 == 0: print(k, flush=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"))
    ok = sum(1 for r in res.values() if "types" in r)
    print("TERMINE", ok, "bundles lus,", len(res) - ok, "autres fichiers", flush=True)
