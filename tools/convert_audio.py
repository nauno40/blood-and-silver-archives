r"""Convertit tous les sons Wwise du jeu (.wem isolés + contenu des banques .bnk) en .ogg (Vorbis q6),
nommés d'après SoundbanksInfo.xml et classés par catégorie.
Sortie : <projet>\Site\audio\<categorie>\<nom>.ogg + audio.json (manifeste pour le site)."""
from config import PROJECT, ASSETS, FFMPEG, VGMSTREAM  # chemins : voir tools/config.py
import os, re, json, glob, shutil, subprocess, tempfile, hashlib
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

SRC = ASSETS + r"\Audio\Android"
OUT = PROJECT + r"\Site\audio"
VGM = VGMSTREAM
FF = FFMPEG

# --- 1. noms : identifiant de média -> (nom court, langue, banques, événements) ------------------
root = ET.parse(os.path.join(SRC, "SoundbanksInfo.xml")).getroot()
info = {}
def note(fid, short, lang, bank=None, events=()):
    e = info.setdefault(fid, {"name": os.path.splitext(short)[0], "lang": lang, "banks": set(), "events": set()})
    if bank: e["banks"].add(bank)
    e["events"].update(events)
for f in root.iter("File"):
    if f.find("ShortName") is not None:
        note(f.get("Id"), f.findtext("ShortName"), f.get("Language"))
for sb in root.iter("SoundBank"):
    bname = sb.findtext("ShortName") or sb.get("Id")
    evs = [e.get("Name") for e in sb.iter("Event")]
    for tag in ("IncludedMemoryFiles", "ReferencedStreamedFiles"):
        for f in sb.findall(f"./{tag}/File"):
            if f.find("ShortName") is not None:
                note(f.get("Id"), f.findtext("ShortName"), f.get("Language"), bname, evs if len(evs) <= 3 else ())

def category(name, lang):
    n = name.lower()
    if lang not in ("SFX", None) or n.startswith(("vo_", "vo-")) or "_vo_" in n: return "Voix"
    if re.match(r"m\d{3}|mus_|.*_mus_", n): return "Musiques"
    if n.startswith("amb") or "_amb_" in n: return "Ambiances"
    if n.startswith(("mainlevel", "avg", "story", "cine")): return "Cinematiques"
    if n.startswith(("ui_", "ui-")): return "Interface"
    return "Effets"

def safe(s): return re.sub(r'[<>:"/\\|?*]', "_", s)

done, manifest = set(), []
def to_ogg(wav, fid, bank=None):
    if fid in done: return
    done.add(fid)
    meta = info.get(fid, {"name": fid, "lang": "SFX", "banks": set(), "events": set()})
    lang = meta["lang"] or "SFX"
    cat = category(meta["name"], lang)
    sub = os.path.join(cat, safe(lang)) if cat == "Voix" else cat
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    rel = os.path.join(sub, safe(meta["name"]) + ".ogg")
    if os.path.exists(os.path.join(OUT, rel)):  # même nom, autre média
        rel = os.path.join(sub, safe(meta["name"]) + f"_{fid}.ogg")
    r = subprocess.run([FF, "-v", "error", "-y", "-i", wav, "-c:a", "libvorbis", "-q:a", "6", os.path.join(OUT, rel)])
    if r.returncode == 0:
        manifest.append({"id": fid, "name": meta["name"], "cat": cat, "lang": lang, "file": "audio/" + rel.replace("\\", "/"),
                         "banks": sorted(meta["banks"] | ({bank} if bank else set())), "events": sorted(meta["events"])[:5]})

def convert_wem(path):
    tmp = tempfile.mkdtemp()
    try:
        wav = os.path.join(tmp, "a.wav")
        if subprocess.run([VGM, "-o", wav, path], capture_output=True).returncode == 0:
            to_ogg(wav, os.path.splitext(os.path.basename(path))[0])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def convert_bnk(path):
    tmp = tempfile.mkdtemp()
    try:
        # -S 0 : toutes les sous-pistes ; ?n = nom de la piste (= identifiant du média dans Wwise)
        subprocess.run([VGM, "-S", "0", "-o", os.path.join(tmp, "?n.wav"), path], capture_output=True)
        for w in glob.glob(os.path.join(tmp, "*.wav")):
            to_ogg(w, os.path.splitext(os.path.basename(w))[0], os.path.splitext(os.path.basename(path))[0])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    wems = glob.glob(os.path.join(SRC, "*.wem"))
    bnks = glob.glob(os.path.join(SRC, "*.bnk")) + glob.glob(os.path.join(SRC, "*", "*.bnk"))
    print(len(wems), "wem,", len(bnks), "bnk,", len(info), "noms connus", flush=True)
    # done/manifest partagés : traitement séquentiel par fichier, conversions ffmpeg en parallèle par lot
    with ThreadPoolExecutor(8) as ex:
        for k, _ in enumerate(ex.map(convert_wem, wems), 1):
            if k % 100 == 0: print("wem", k, flush=True)
    with ThreadPoolExecutor(8) as ex:
        for k, _ in enumerate(ex.map(convert_bnk, bnks), 1):
            if k % 100 == 0: print("bnk", k, len(manifest), "sons", flush=True)
    manifest.sort(key=lambda m: (m["cat"], m["lang"], m["name"].lower()))
    json.dump(manifest, open(os.path.join(OUT, "audio.json"), "w", encoding="utf-8"), ensure_ascii=False)
    from collections import Counter
    print("TERMINE", len(manifest), "sons", dict(Counter((m["cat"], m["lang"]) for m in manifest)), flush=True)
