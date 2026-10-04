"""Cherche une regex dans tous les TextAssets des bundles lua/ et BytesData/ et affiche le contexte."""
import glob, os, re, sys
import UnityPy

A = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets"
pat = re.compile(sys.argv[1].encode())
ctx = int(sys.argv[2]) if len(sys.argv) > 2 else 400
files = glob.glob(os.path.join(A, "lua", "*.unity3d")) + glob.glob(os.path.join(A, "BytesData", "**", "*.unity3d"), recursive=True)
hits = 0
for f in files:
    d = open(f, "rb").read(); i = d.find(b"UnityFS\x00")
    try: env = UnityPy.load(d[i:] if i > 0 else d)
    except Exception: continue
    for o in env.objects:
        if o.type.name != "TextAsset": continue
        t = o.read(); s = t.m_Script
        b = s.encode("utf-8", "surrogateescape") if isinstance(s, str) else bytes(s)
        for m in pat.finditer(b):
            hits += 1
            seg = b[max(0, m.start() - ctx): m.end() + ctx]
            txt = " | ".join(x.decode("latin1") for x in re.findall(rb"[\x20-\x7e]{3,}", seg))
            print(f"### {os.path.basename(f)} :: {t.m_Name}\n{txt}\n")
            if hits >= int(os.environ.get("MAXHITS", "6")): sys.exit()
print("hits", hits)
