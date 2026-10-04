r"""Version WebM (VP9 CRF 28 + Opus 160k) de chaque vidéo du site : Site\videos\<nom>.mp4 -> Site\videos_webm\<nom>.webm.
Les sous-titres restent des fichiers .vtt séparés (inchangés)."""
import os, glob, subprocess
from concurrent.futures import ThreadPoolExecutor

SITE = r"E:\Projets\BloodAndSilver\Site"
FF = r"C:\Users\Nauno\.bns_tools\venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
OUT = os.path.join(SITE, "videos_webm")
os.makedirs(OUT, exist_ok=True)

def job(src):
    dst = os.path.join(OUT, os.path.splitext(os.path.basename(src))[0] + ".webm")
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src): return 0
    tmp = dst + ".tmp.webm"
    r = subprocess.run([FF, "-v", "error", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a?",
                        "-c:v", "libvpx-vp9", "-crf", "28", "-b:v", "0", "-row-mt", "1", "-tile-columns", "2",
                        "-deadline", "good", "-cpu-used", "2", "-pix_fmt", "yuv420p",
                        "-c:a", "libopus", "-b:a", "160k", tmp], capture_output=True, text=True)
    if r.returncode != 0:
        if os.path.exists(tmp): os.remove(tmp)
        return f"ERREUR {os.path.basename(src)} {r.stderr[-200:]}"
    os.replace(tmp, dst)
    return 1

if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(SITE, "videos", "*.mp4")))
    print(len(files), "vidéos", flush=True)
    n = 0
    with ThreadPoolExecutor(3) as ex:  # VP9 est déjà multi-thread
        for k, r in enumerate(ex.map(job, files), 1):
            if isinstance(r, str): print(r, flush=True)
            else: n += r
            if k % 10 == 0: print(f"{k}/{len(files)}", flush=True)
    a = sum(os.path.getsize(f) for f in files); b = sum(os.path.getsize(f) for f in glob.glob(os.path.join(OUT, "*.webm")))
    print(f"TERMINE {n} converties, MP4 {a/2**20:.0f} Mo -> WebM {b/2**20:.0f} Mo", flush=True)
