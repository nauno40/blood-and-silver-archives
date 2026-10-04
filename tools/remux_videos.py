r"""Copie sans perte des vidéos du jeu vers Site\videos, index (moov) placé en tête pour une lecture
immédiate dans le navigateur (-c copy -movflags +faststart : aucun ré-encodage)."""
from config import PROJECT, ASSETS, FFMPEG  # chemins : voir tools/config.py
import os, glob, subprocess
from concurrent.futures import ThreadPoolExecutor

SRC = ASSETS + r"\Video"
DST = PROJECT + r"\Site\videos"
FF = FFMPEG
os.makedirs(DST, exist_ok=True)

def job(src):
    dst = os.path.join(DST, os.path.basename(src))
    r = subprocess.run([FF, "-v", "error", "-y", "-i", src, "-map", "0", "-c", "copy", "-movflags", "+faststart", dst],
                       capture_output=True, text=True)
    return os.path.basename(src), r.returncode, r.stderr.strip()[-200:]

files = sorted(glob.glob(os.path.join(SRC, "*.mp4")))
with ThreadPoolExecutor(4) as ex:
    res = list(ex.map(job, files))
bad = [r for r in res if r[1] != 0]
print(f"{len(files) - len(bad)}/{len(files)} vidéos copiées", bad[:5])
