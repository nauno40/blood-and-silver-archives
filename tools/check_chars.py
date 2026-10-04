"""Compare les prefabs Spine de CharacterInfo, FashionInfo et LoungeChar avec ce qui est rendu."""
import os, re, UnityPy

A = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets"
ANIM = r"E:\Projets\BloodAndSilver\Animations"
d = open(os.path.join(A, "Document", "Document.unity3d"), "rb").read(); i = d.find(b"UnityFS\x00")
env = UnityPy.load(d[i:])
tables = {}
for o in env.objects:
    if o.type.name == "TextAsset" and o.peek_name() in ("CharacterInfo", "FashionInfo", "LoungeChar", "LoungeCharParts", "LinkCharacterInfo", "MultiLanguage", "UILanguage", "CommonText"):
        t = o.read(); s = t.m_Script
        tables[t.m_Name] = s.encode("utf-8", "surrogateescape") if isinstance(s, str) else bytes(s)

ui = {os.path.splitext(f)[0].lower() for f in os.listdir(os.path.join(A, "UI"))}
manifest = open(os.path.join(A, "..", "DownloadResourceMD5.txt"), encoding="latin1").read()
srv = {m.lower() for m in re.findall(r"^UI/([^.,]+)\.unity3d", manifest, re.M)}
rendered = {x.lower() for x in os.listdir(ANIM)}

def spine_names(b):
    # noms de prefab Spine : minuscules/majuscules + _base/_final/_lounge... présents comme bundles UI
    cands = {x.decode("latin1") for x in re.findall(rb"[A-Za-z][A-Za-z0-9_]{3,40}", b)}
    return {c for c in cands if c.lower() in srv and re.search(r"(?i)_(base|final|lounge|summer|origin|ur|covenant|sp)|_a\d_|_b\d_", c)}

for name in ("CharacterInfo", "FashionInfo", "LoungeChar", "LoungeCharParts", "LinkCharacterInfo"):
    if name not in tables: continue
    s = spine_names(tables[name])
    miss_phone = sorted(x for x in s if x.lower() not in ui)
    not_rendered = sorted(x for x in s if x.lower() in ui and x.lower() not in rendered)
    print(f"{name:18} prefabs={len(s):3}  absents du téléphone={miss_phone}  présents non rendus={not_rendered}")

for name in ("MultiLanguage", "UILanguage", "CommonText"):
    b = tables.get(name, b"")
    hits = sorted({m.decode("utf-8", "replace") for m in re.findall(rb"[^\x00-\x1f\"]{0,30}[Cc]ompagnon[^\x00-\x1f\"]{0,30}", b)})
    print(name, len(b), hits[:15])
