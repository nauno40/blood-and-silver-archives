r"""Version MP3 (LAME VBR V2, ~190 kb/s) de chaque son du site, pour une compatibilité maximale.
Site\audio\<cat>\<nom>.ogg -> Site\audio_mp3\<cat>\<nom>.mp3"""
from config import PROJECT, FFMPEG  # chemins : voir tools/config.py
import os, glob, subprocess
from concurrent.futures import ThreadPoolExecutor

SITE = PROJECT + r"\Site"
FF = FFMPEG

def job(src):
    dst = os.path.join(SITE, "audio_mp3", os.path.splitext(os.path.relpath(src, os.path.join(SITE, "audio")))[0] + ".mp3")
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src): return 0
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    r = subprocess.run([FF, "-v", "error", "-y", "-i", src, "-map_metadata", "-1", "-c:a", "libmp3lame", "-q:a", "2", dst],
                       capture_output=True, text=True)
    return 1 if r.returncode == 0 else f"ERREUR {src} {r.stderr[-150:]}"

if __name__ == "__main__":
    files = glob.glob(os.path.join(SITE, "audio", "**", "*.ogg"), recursive=True)
    print(len(files), "sons", flush=True)
    n = 0
    with ThreadPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        for k, r in enumerate(ex.map(job, files), 1):
            if isinstance(r, str): print(r, flush=True)
            else: n += r
            if k % 4000 == 0: print(f"{k}/{len(files)}", flush=True)
    sz = sum(os.path.getsize(f) for f in glob.glob(os.path.join(SITE, "audio_mp3", "**", "*.mp3"), recursive=True))
    print(f"TERMINE {n} convertis, {sz/2**30:.2f} Go", flush=True)
