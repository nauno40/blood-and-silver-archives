r"""Copie sans perte des vidéos du jeu vers Site\videos, index (moov) placé en tête pour une lecture
immédiate dans le navigateur (-c copy -movflags +faststart : aucun ré-encodage)."""
import os, glob, subprocess
from concurrent.futures import ThreadPoolExecutor

SRC = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets\Video"
DST = r"E:\Projets\BloodAndSilver\Site\videos"
FF = r"C:\Users\Nauno\.bns_tools\venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
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
