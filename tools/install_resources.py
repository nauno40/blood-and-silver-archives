"""Télécharge et installe les ressources du site (images, animations, modèles 3D, sons, vidéos…) depuis la Release GitHub.

Usage : python tools/install_resources.py            (ou double-clic sur « Installer les ressources.bat »)
Les archives sont téléchargées une par une, vérifiées (SHA-256), décompressées à la racine du projet puis supprimées.
Relancer la commande reprend là où elle s'était arrêtée (archives déjà installées sautées)."""
import json, os, sys, hashlib, zipfile, urllib.request, time

REPO = "nauno40/blood-and-silver-archives"
TAG = "ressources-v1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, ".ressources_installees")

def get(url, accept="application/octet-stream"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "bns-installer"})
    return urllib.request.urlopen(req, timeout=60)

def download(url, dest, size):
    tmp = dest + ".part"; done = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    req = urllib.request.Request(url, headers={"User-Agent": "bns-installer", **({"Range": f"bytes={done}-"} if done else {})})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "ab" if done else "wb") as f:
        t0, last = time.time(), 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk: break
            f.write(chunk); done += len(chunk)
            if time.time() - last > 1:
                last = time.time(); speed = done / max(1e-3, last - t0) / 1e6
                sys.stdout.write(f"\r    {done / 1e9:.2f} / {size / 1e9:.2f} Go"); sys.stdout.flush()
    print()
    os.replace(tmp, dest)

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""): h.update(chunk)
    return h.hexdigest()

def main():
    print(f"Ressources de Blood and Silver — Archives ({REPO}, {TAG})")
    rel = json.load(get(f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}", "application/vnd.github+json"))
    assets = {a["name"]: a for a in rel["assets"]}
    manifest = json.load(get(assets["manifest.json"]["browser_download_url"]))
    done = set(open(STATE, encoding="utf-8").read().split()) if os.path.exists(STATE) else set()
    todo = [a for a in manifest["archives"] if a["name"] not in done]
    total = sum(a["size"] for a in todo)
    print(f"{len(manifest['archives'])} archives, {len(todo)} à installer ({total / 1e9:.1f} Go). Espace libre nécessaire : ~{total * 2 / 1e9:.0f} Go pendant l'installation.")
    for k, a in enumerate(todo, 1):
        print(f"[{k}/{len(todo)}] {a['name']} ({a['size'] / 1e9:.2f} Go)")
        dest = os.path.join(ROOT, a["name"])
        if not (os.path.exists(dest) and os.path.getsize(dest) == a["size"]):
            download(assets[a["name"]]["browser_download_url"], dest, a["size"])
        if sha256(dest) != a["sha256"]:
            os.remove(dest); sys.exit(f"    archive corrompue, relancez l'installation : {a['name']}")
        print("    décompression…")
        with zipfile.ZipFile(dest) as z: z.extractall(ROOT)
        os.remove(dest)
        with open(STATE, "a", encoding="utf-8") as f: f.write(a["name"] + "\n")
    print("Terminé : lancez « Ouvrir le site.bat ».")

if __name__ == "__main__":
    main()
