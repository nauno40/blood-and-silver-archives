"""Traite les pistes « <id> [pre] » (début préchargé des sons en streaming) :
- si le son complet existe déjà : supprime l'extrait ;
- sinon : renomme l'extrait avec le vrai nom (+ « (extrait) ») et le reclasse."""
import json, os, re, shutil, sys
sys.argv = ["x"]
exec(open(r"C:\Users\Nauno\.bns_tools\convert_audio.py", encoding="utf-8").read().split("done, manifest = set(), []")[0])

man_path = os.path.join(OUT, "audio.json")
man = json.load(open(man_path, encoding="utf-8"))
full_ids = {m["id"] for m in man if not m["id"].endswith("[pre]")}
keep, removed, renamed = [], 0, 0
for m in man:
    mm = re.match(r"^(\d+) \[pre\]$", m["id"])
    if not mm:
        keep.append(m); continue
    fid = mm.group(1)
    src = os.path.join(SITE_ROOT := os.path.dirname(OUT), m["file"].replace("/", os.sep))
    if fid in full_ids:
        if os.path.exists(src): os.remove(src)
        removed += 1; continue
    meta = info.get(fid)
    name = (meta["name"] if meta else fid) + " (extrait)"
    lang = (meta or {}).get("lang") or "SFX"
    cat = category(name, lang)
    sub = os.path.join(cat, safe(lang)) if cat == "Voix" else cat
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    dst_rel = os.path.join(sub, safe(name) + ".ogg")
    if os.path.exists(os.path.join(OUT, dst_rel)): dst_rel = os.path.join(sub, safe(name) + f"_{fid}.ogg")
    if os.path.exists(src): shutil.move(src, os.path.join(OUT, dst_rel))
    m.update({"id": fid, "name": name, "cat": cat, "lang": lang, "file": "audio/" + dst_rel.replace("\\", "/"),
              "events": sorted((meta or {}).get("events", []))[:5]})
    keep.append(m); renamed += 1
keep.sort(key=lambda m: (m["cat"], m["lang"], m["name"].lower()))
json.dump(keep, open(man_path, "w", encoding="utf-8"), ensure_ascii=False)
from collections import Counter
print(f"extraits supprimés (doublons) : {removed}, renommés : {renamed}, total : {len(keep)}")
print(Counter(m["cat"] for m in keep))
print("encore sans nom :", sum(1 for m in keep if re.fullmatch(r"\d+( \(extrait\))?", m["name"])))
