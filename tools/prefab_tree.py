"""Affiche l'arbre d'un prefab UI : RectTransform, Image/RawImage/SkeletonGraphic, sprite, couleur."""
import sys, os
import UnityPy

A = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets\UI"

def load(name):
    d = open(os.path.join(A, name + ".unity3d"), "rb").read(); i = d.find(b"UnityFS\x00")
    return UnityPy.load(d[i:] if i > 0 else d)

env = load(sys.argv[1])
objs = {o.path_id: o for o in env.objects}
gos = {pid: o.read_typetree() for pid, o in objs.items() if o.type.name == "GameObject"}
def comp(go):
    out = []
    for c in go["m_Component"]:
        ptr = c["component"]
        if ptr["m_FileID"] != 0 or ptr["m_PathID"] not in objs: out.append(("ext", None)); continue
        o = objs[ptr["m_PathID"]]
        out.append((o.type.name, o))
    return out

def script_name(o):
    try:
        t = o.read_typetree(); s = t["m_Script"]
        if s["m_FileID"] == 0: return objs[s["m_PathID"]].read_typetree()["m_ClassName"]
        return f"ext{s['m_FileID']}:{s['m_PathID']}"
    except Exception as e: return "?"

def show(rt_pid, depth=0):
    rt = objs[rt_pid].read_typetree()
    go = gos[rt["m_GameObject"]["m_PathID"]]
    info = []
    for tn, o in comp(go):
        if tn == "MonoBehaviour":
            t = o.read_typetree()
            keys = [k for k in ("m_Sprite", "m_Texture", "m_Color", "skeletonDataAsset", "startingAnimation", "m_Type", "m_Enabled", "m_Material") if k in t]
            info.append(f"MB({ {k: t[k] for k in keys} })")
        elif tn not in ("RectTransform",): info.append(tn)
    if "m_AnchoredPosition" not in rt:  # Transform simple (particules, objets 3D)
        print("  " * depth + f"- {go['m_Name']} active={go['m_IsActive']} [Transform] " + " ".join(info))
        for ch in rt["m_Children"]: show(ch["m_PathID"], depth + 1)
        return
    print("  " * depth + f"- {go['m_Name']} active={go['m_IsActive']} pos={tuple(round(v,1) for v in rt['m_AnchoredPosition'].values())} size={tuple(round(v,1) for v in rt['m_SizeDelta'].values())} "
          f"amin={tuple(rt['m_AnchorMin'].values())} amax={tuple(rt['m_AnchorMax'].values())} scale={tuple(round(v,2) for v in rt['m_LocalScale'].values())} " + " ".join(info))
    for ch in rt["m_Children"]: show(ch["m_PathID"], depth + 1)

roots = [pid for pid, o in objs.items() if o.type.name == "RectTransform" and o.read_typetree()["m_Father"]["m_PathID"] == 0]
for r in roots: show(r)
