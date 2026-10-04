r"""Convertit chaque animation WebP (Animations\<bundle>\<squelette>\<anim>.webp) en WebM VP9 avec
transparence pour le site : Site\anim\<bundle>\<squelette>\<anim>.webm (même cadence, boucle gérée par le lecteur)."""
from config import PROJECT, FFMPEG  # chemins : voir tools/config.py
import os, glob, subprocess
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageSequence

ROOT = PROJECT
OUT = os.path.join(ROOT, "Site", "anim")
FF = FFMPEG

def job(src):
    rel = os.path.relpath(src, os.path.join(ROOT, "Animations"))
    dst = os.path.join(OUT, os.path.splitext(rel)[0] + ".webm")
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src): return 0
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im = Image.open(src)
    w, h = im.size
    w2, h2 = w + (w & 1), h + (h & 1)  # VP9 : dimensions paires
    dur = im.info.get("duration", 50) or 50
    fps = round(1000 / dur, 3)
    tmp = dst + ".tmp.webm"
    p = subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w2}x{h2}", "-r", str(fps), "-i", "-",
                          "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", "18", "-b:v", "0", "-row-mt", "1",
                          "-auto-alt-ref", "0", "-deadline", "good", "-cpu-used", "2", tmp],
                         stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fr in ImageSequence.Iterator(im):
            f = fr.convert("RGBA")
            if (w2, h2) != (w, h):
                c = Image.new("RGBA", (w2, h2)); c.paste(f, (0, 0)); f = c
            p.stdin.write(f.tobytes())
        p.stdin.close()
        err = p.stderr.read().decode("utf-8", "replace"); p.wait()
    except Exception as e:
        p.kill(); return f"ERREUR {rel} {e}"
    if p.returncode != 0: return f"ERREUR {rel} {err[-200:]}"
    os.replace(tmp, dst)
    return 1

if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(ROOT, "Animations", "*", "*", "*.webp")))
    print(len(files), "animations", flush=True)
    n = 0
    with ThreadPoolExecutor(4) as ex:
        for k, r in enumerate(ex.map(job, files), 1):
            if isinstance(r, str): print(r, flush=True)
            else: n += r
            if k % 50 == 0: print(f"{k}/{len(files)}", flush=True)
    sz = sum(os.path.getsize(f) for f in glob.glob(os.path.join(OUT, "**", "*.webm"), recursive=True))
    print(f"TERMINE {n} converties, {sz/2**30:.2f} Go", flush=True)
