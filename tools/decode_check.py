r"""Décode intégralement chaque image WebP et chaque MP3 du site pour détecter les fichiers corrompus.
Images : PIL (décodage complet). MP3 : ffmpeg décode tout le flux sans sortie (-f null), erreurs comptées."""
import os, glob, subprocess, sys
from concurrent.futures import ProcessPoolExecutor

SITE = r"E:\Projets\BloodAndSilver\Site"
FF = r"C:\Users\Nauno\.bns_tools\venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"

def img(p):
    from PIL import Image
    try:
        im = Image.open(p); im.load()
        return None if im.size[0] > 0 else f"vide {p}"
    except Exception as e:
        return f"{type(e).__name__} {p}"

def snd(p):
    r = subprocess.run([FF, "-v", "error", "-xerror", "-i", p, "-f", "null", "-"], capture_output=True, text=True)
    return None if r.returncode == 0 and not r.stderr.strip() else f"{r.stderr.strip()[:120]} {p}"

def run(fn, files, label):
    bad = []
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for k, r in enumerate(ex.map(fn, files, chunksize=64), 1):
            if r: bad.append(r)
            if k % 10000 == 0: print(f"{label} {k}/{len(files)}", flush=True)
    print(f"{label}: {len(files)} décodés, {len(bad)} en erreur", flush=True)
    for b in bad[:10]: print("   ", b, flush=True)

if __name__ == "__main__":
    imgs = glob.glob(os.path.join(SITE, "img", "**", "*.webp"), recursive=True) + \
           glob.glob(os.path.join(SITE, "thumbs", "**", "*.webp"), recursive=True) + \
           glob.glob(os.path.join(SITE, "models", "*", "*.webp"), recursive=True) + glob.glob(os.path.join(SITE, "posters", "*.webp"))
    run(img, imgs, "IMAGES")
    run(snd, glob.glob(os.path.join(SITE, "audio_mp3", "**", "*.mp3"), recursive=True), "MP3")
    print("TERMINE", flush=True)
