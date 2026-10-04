"""Inventaire des prefabs de fonds de l'écran principal (table MainBackground)."""
import os, re, collections
import UnityPy

A = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets\UI"
b = open(r"C:\Users\Nauno\.bns_tools\MainBackground.bin", "rb").read()
prefabs = list(dict.fromkeys(m.decode() for m in re.findall(rb"(ui_panel_(?:bgmain|activity_[a-z0-9_]+?))(?=[0-9]?Atlas|\x00|4Atlas|0Atlas)", b)))
# nettoyage du chiffre de longueur collé à la fin du nom
prefabs = [p for p in re.findall(r"ui_panel_[a-z0-9_]+", " ".join(prefabs))]
names = []
for m in re.finditer(rb"ui_panel_[A-Za-z0-9_]+", b):
    s = m.group().decode()
    # la chaîne est suivie d'un octet de longueur (protobuf) puis de « Atlas_... » : on coupe
    s = s.split("Atlas")[0]
    names.append(s)
print(len(names), names)
for raw in names:
    cand = [raw, raw[:-1]]
    f = next((os.path.join(A, c + ".unity3d") for c in cand if os.path.exists(os.path.join(A, c + ".unity3d"))), None)
    if not f:
        print("ABSENT", raw); continue
    d = open(f, "rb").read(); i = d.find(b"UnityFS\x00"); env = UnityPy.load(d[i:] if i > 0 else d)
    c = collections.Counter(o.type.name for o in env.objects)
    tex = [(o.peek_name(), ) for o in env.objects if o.type.name == "Texture2D"]
    skel = [o.peek_name() for o in env.objects if o.type.name == "TextAsset" and (o.peek_name() or "").endswith((".skel", ".json"))]
    deps = env.assets[0].externals if env.assets else []
    print(f"{os.path.basename(f)[:-8]:38} tex={c['Texture2D']:2} img={c['MonoBehaviour']:3} GO={c['GameObject']:3} skel={skel} deps={[e.path for e in deps][:4]}")
