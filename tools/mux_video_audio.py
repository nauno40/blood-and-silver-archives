"""Ajoute aux vidéos muettes du site la piste audio que le jeu joue à part (même nom dans les sons Wwise).
Image copiée sans perte, son encodé en AAC 192k, index en tête."""
import json, os, re, subprocess, shutil

SITE = r"E:\Projets\BloodAndSilver\Site"
FF = r"C:\Users\Nauno\.bns_tools\venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
t = open(os.path.join(SITE, "data", "videos.js"), encoding="utf-8").read()
vids = json.loads(t[t.index("] = ") + 4: t.rstrip().rindex(";")])
audio = json.load(open(os.path.join(SITE, "audio", "audio.json"), encoding="utf-8"))
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower().replace("cutln", "cutin"))
by = {}
for a in audio: by.setdefault(norm(a["name"]), a)
done = 0
for v in vids:
    src = os.path.join(SITE, v["file"])
    info = subprocess.run([FF, "-hide_banner", "-i", src], capture_output=True, text=True).stderr
    a = by.get(norm(v["name"]))
    if "Audio:" in info or not a: continue
    tmp = src + ".tmp.mp4"
    r = subprocess.run([FF, "-v", "error", "-y", "-i", src, "-i", os.path.join(SITE, a["file"]), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", tmp], capture_output=True, text=True)
    if r.returncode == 0:
        os.replace(tmp, src); done += 1
    else:
        print("échec", v["name"], r.stderr[-200:])
        if os.path.exists(tmp): os.remove(tmp)
print(done, "vidéos ont maintenant leur son")
