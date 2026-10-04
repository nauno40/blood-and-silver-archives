r"""Rend toutes les animations de tous les squelettes Spine extraits.
Sortie : E:\Projets\BloodAndSilver\Animations\<bundle>\<squelette>\<animation>.(webm|webp|gif|png)
Reprise : un squelette déjà terminé (fichier .done) est sauté."""
import hashlib, json, os, subprocess, time
from concurrent.futures import ThreadPoolExecutor, as_completed

SPINE = r"E:\Projets\BloodAndSilver\Spine"
OUT = r"E:\Projets\BloodAndSilver\Animations"
RENDER = r"C:\Users\Nauno\.bns_tools\render\render.mjs"
LOG = os.path.join(OUT, "render_errors.txt")
WORKERS = 6  # chaque rendu lance aussi ffmpeg (multi-thread)

def job(folder):
    src = os.path.join(SPINE, folder)
    dst = os.path.join(OUT, folder)
    marker = os.path.join(dst, ".done")
    if os.path.exists(marker):
        return folder, 0, None
    p = subprocess.run(["node", RENDER, src, dst], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=4 * 3600)
    if p.returncode != 0:
        return folder, 0, (p.stderr or p.stdout).strip()[-800:]
    info = json.loads(p.stdout.strip().splitlines()[-1])
    open(marker, "w").close()
    return folder, info["rendered"], None

def main():
    os.makedirs(OUT, exist_ok=True)
    inv = json.load(open(os.path.join(SPINE, "inventory.json"), encoding="utf-8"))
    # doublons (ex. *_Mecanim = même squelette que la version Lounge) : un seul rendu
    folders, seen = [], {}
    for folder in sorted({r["folder"] for r in inv}):
        d = os.path.join(SPINE, folder)
        skel = next(f for f in os.listdir(d) if f.endswith((".skel", ".json")))
        h = hashlib.md5(open(os.path.join(d, skel), "rb").read()).hexdigest()
        if h in seen:
            print(f"doublon ignoré : {folder} (= {seen[h]})", flush=True)
            continue
        seen[h] = folder
        folders.append(folder)
    print(f"{len(folders)} squelettes", flush=True)
    t0 = time.time(); n = anims = err = 0
    with ThreadPoolExecutor(WORKERS) as ex:
        for fut in as_completed([ex.submit(job, f) for f in folders]):
            folder, a, e = fut.result()
            n += 1; anims += a
            if e:
                err += 1
                with open(LOG, "a", encoding="utf-8") as f:
                    f.write(f"{folder}\n{e}\n\n")
            print(f"{n}/{len(folders)}  animations={anims}  erreurs={err}  {int(time.time()-t0)}s  ({folder})", flush=True)
    print(f"TERMINE {n}/{len(folders)} squelettes  animations={anims}  erreurs={err}  {int(time.time()-t0)}s", flush=True)

if __name__ == "__main__":
    main()
