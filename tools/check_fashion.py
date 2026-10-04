"""Compare la liste des tenues du jeu (FashionInfo) avec les bundles présents et les rendus."""
import os, re, json

A = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets"
ANIM = r"E:\Projets\BloodAndSilver\Animations"
b = open(r"C:\Users\Nauno\.bns_tools\FashionInfo.bin", "rb").read()
strs = [x.decode("latin1") for x in re.findall(rb"[\x20-\x7e]{3,}", b)]
# motif : Atlas_Role/<portrait> | Atlas_Roleskin/<id> | <prefab spine>
skins = []
for k, s in enumerate(strs):
    m = re.match(r"Atlas_Roleskin/(\d+)$", s)
    if m and k + 1 < len(strs):
        portrait = strs[k - 1].split("/")[-1] if k > 0 else ""
        skins.append((m.group(1), portrait, strs[k + 1]))
print(len(skins), "tenues dans FashionInfo")

ui = {os.path.splitext(f)[0].lower(): f for f in os.listdir(os.path.join(A, "UI"))}
rendered = {d.lower() for d in os.listdir(ANIM) if os.path.isdir(os.path.join(ANIM, d))}
inv = json.load(open(r"E:\Projets\BloodAndSilver\Spine\inventory.json", encoding="utf-8"))
skel_bundles = {r["bundle"].split("\\")[-1][:-8].lower() for r in inv}

rows = []
for sid, portrait, prefab in skins:
    p = prefab.lower()
    present = p in ui
    has_skel = p in skel_bundles
    done = p in rendered
    rows.append((sid, portrait, prefab, present, has_skel, done))
ok = [r for r in rows if r[5]]
miss_bundle = [r for r in rows if not r[3]]
no_skel = [r for r in rows if r[3] and not r[4]]
print(f"rendus : {len(ok)}   bundle absent du téléphone : {len(miss_bundle)}   bundle présent sans squelette : {len(no_skel)}")
print("\n-- bundle absent du téléphone --")
for r in miss_bundle: print(f"  {r[0]}  {r[1]:28} {r[2]}")
print("\n-- présent mais sans squelette Spine --")
for r in no_skel: print(f"  {r[0]}  {r[1]:28} {r[2]}  ({ui[r[2].lower()]})")
fashion_prefabs = {r[2].lower() for r in rows}
print("\n-- rendus hors FashionInfo (scènes, lounge, UI) --")
print(sorted(rendered - fashion_prefabs))
