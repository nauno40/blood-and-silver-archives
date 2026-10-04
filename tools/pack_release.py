r"""Prépare les archives de ressources pour la Release GitHub (fichiers <= 2 Gio) : médias utilisés par le site,
chemins relatifs à la racine du projet, sans recompression (les médias sont déjà compressés).
Sortie : <projet>\release\bns-ressources-NN.zip + manifest.json"""
from config import PROJECT  # chemins : voir tools/config.py
import os, json, zipfile, hashlib, time

ROOT = PROJECT
OUT = os.path.join(ROOT, "release")
PACK = ["Site/img", "Site/thumbs", "Site/anim", "Site/audio", "Site/audio_mp3", "Site/videos", "Site/videos_webm", "Site/posters", "Site/subs",
        "Site/models", "Site/models_fbx", "Site/models_anim", "Site/models_anim_fbx", "Site/shader_preview", "Site/spine", "Site/pixel", "Site/shaders", "Site/polices"]
LIMIT = 1_900_000_000  # marge sous la limite GitHub de 2 Gio par fichier

def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".zip") or f == "manifest.json": os.remove(os.path.join(OUT, f))
    files = []
    for d in PACK:
        for r, _, fs in os.walk(os.path.join(ROOT, d)):
            for f in sorted(fs):
                p = os.path.join(r, f); files.append((os.path.relpath(p, ROOT).replace(os.sep, "/"), os.path.getsize(p)))
    files.sort()
    print(len(files), "fichiers,", round(sum(s for _, s in files) / 1e9, 2), "Go", flush=True)
    parts, cur, size = [], [], 0
    for rel, s in files:
        if cur and size + s + 200 > LIMIT: parts.append(cur); cur, size = [], 0
        cur.append(rel); size += s + 200
    if cur: parts.append(cur)
    manifest = {"created": time.strftime("%Y-%m-%d"), "archives": []}
    for k, part in enumerate(parts, 1):
        name = f"bns-ressources-{k:02d}.zip"; path = os.path.join(OUT, name)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            for rel in part: z.write(os.path.join(ROOT, rel), rel)
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 22), b""): h.update(chunk)
        manifest["archives"].append({"name": name, "size": os.path.getsize(path), "files": len(part), "sha256": h.hexdigest(),
                                     "dirs": sorted({"/".join(r.split("/")[:2]) for r in part})})
        print(f"{name} : {len(part)} fichiers, {os.path.getsize(path) / 1e9:.2f} Go", flush=True)
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("TERMINE", len(parts), "archives", flush=True)

if __name__ == "__main__":
    main()
