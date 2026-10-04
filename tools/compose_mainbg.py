"""Recompose les fonds de l'écran principal (table MainBackground) tels qu'affichés dans le jeu.

Chaque fond est un prefab UGUI (canevas 2880x1440) : on parcourt la hiérarchie dans l'ordre
de dessin, on ignore les objets inactifs, les composants désactivés et les particules, puis on
dessine :
  - Image / RawImage : sprite étiré dans son RectTransform, teinté par m_Color (x alpha des CanvasGroup) ;
  - SkeletonGraphic  : squelette Spine rendu à son emplacement (render.mjs --fixedscale), pose
                       de départ de startingAnimation.
Sortie : <projet>\\Fonds_ecran_principal\\NN - <prefab>.png
"""
from config import PROJECT, TOOLS_DIR, ASSETS  # chemins : voir tools/config.py
import os, re, subprocess, tempfile, json
import UnityPy
from PIL import Image

A = ASSETS + r"\UI"
SPINE = PROJECT + r"\Site\spine"
OUT = PROJECT + r"\Fonds_ecran_principal"
RENDER = TOOLS_DIR + r"\render\render.mjs"
SS = 1  # facteur de rendu (1 = 2880x1440, résolution native du canevas)

def load(path):
    d = open(path, "rb").read(); i = d.find(b"UnityFS\x00")
    return UnityPy.load(d[i:] if i > 0 else d)

def _table(name):  # table de configuration du jeu (TextAsset du bundle Document)
    env = load(os.path.join(ASSETS, "Document", "Document.unity3d"))
    for o in env.objects:
        if o.type.name == "TextAsset" and o.peek_name() == name:
            sc = o.read().m_Script
            return sc.encode("utf-8", "surrogateescape") if isinstance(sc, str) else bytes(sc)
    raise SystemExit(f"table {name} introuvable")

table = _table("MainBackground")
prefabs = [m.decode().split("Atlas")[0] for m in re.findall(rb"ui_panel_[A-Za-z0-9_]+", table)]
prefabs = [p[:-1] if not os.path.exists(os.path.join(A, p + ".unity3d")) else p for p in prefabs]

def v2(d): return (d["x"], d["y"])

def compose(name, idx):
    env = load(os.path.join(A, name + ".unity3d"))
    objs = {o.path_id: o for o in env.objects}
    tt = {}
    def T(pid):
        if pid not in tt: tt[pid] = objs[pid].read_typetree()
        return tt[pid]
    roots = [pid for pid, o in objs.items() if o.type.name == "RectTransform" and T(pid)["m_Father"]["m_PathID"] == 0]
    root = roots[0]
    W, H = v2(T(root)["m_SizeDelta"])
    W, H = int(W) or 2880, int(H) or 1440
    canvas = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    log = []

    def comps(go):
        for c in go["m_Component"]:
            p = c["component"]
            if p["m_FileID"] == 0 and p["m_PathID"] in objs:
                yield objs[p["m_PathID"]]

    def sprite_img(ptr):
        if ptr["m_FileID"] != 0 or ptr["m_PathID"] == 0 or ptr["m_PathID"] not in objs: return None
        o = objs[ptr["m_PathID"]]
        try: return o.read().image.convert("RGBA")
        except Exception as e: log.append(f"sprite illisible {e}"); return None

    def skel_name(ptr):
        sda = T(ptr["m_PathID"])
        js = sda.get("skeletonJSON")
        return objs[js["m_PathID"]].peek_name().rsplit(".", 1)[0]

    def draw(img, cx, cy, w, h, color, alpha):
        """img étiré dans le rectangle de centre (cx,cy) (repère canevas, y vers le haut)."""
        if w <= 0 or h <= 0: return
        r, g, b, a = color["r"], color["g"], color["b"], color["a"] * alpha
        if a <= 0.003: return
        im = img.resize((max(1, round(w * SS)), max(1, round(h * SS))), Image.LANCZOS)
        if (r, g, b) != (1, 1, 1) or a < 1:
            ch = im.split()
            ch = [c.point(lambda v, k=k: v * k) for c, k in zip(ch, (r, g, b, a))]
            im = Image.merge("RGBA", ch)
        x = round((cx - w / 2 + W / 2) * SS); y = round((H / 2 - cy - h / 2) * SS)
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0)); layer.paste(im, (x, y))
        canvas.alpha_composite(layer)

    def walk(pid, prect, alpha, sx, sy):
        rt = T(pid)
        go = T(rt["m_GameObject"]["m_PathID"])
        if not go["m_IsActive"]: return
        cs = list(comps(go))
        if any(o.type.name in ("ParticleSystem", "ParticleSystemRenderer") for o in cs): return
        if "m_AnchoredPosition" not in rt:  # Transform 3D : on descend sans géométrie
            for ch in rt["m_Children"]: walk(ch["m_PathID"], prect, alpha, sx, sy)
            return
        px0, py0, pw, ph = prect  # parent : coin bas-gauche + taille (repère centré du canevas)
        amin, amax, piv = v2(rt["m_AnchorMin"]), v2(rt["m_AnchorMax"]), v2(rt["m_Pivot"])
        ap, sd = v2(rt["m_AnchoredPosition"]), v2(rt["m_SizeDelta"])
        lsx, lsy = rt["m_LocalScale"]["x"], rt["m_LocalScale"]["y"]
        if pid == root:  # échelle de la racine animée à l'ouverture (ex. 0.01 -> 1) : affichage final = 1
            lsx = lsy = 1.0
        w = pw * (amax[0] - amin[0]) + sd[0]; h = ph * (amax[1] - amin[1]) + sd[1]
        ax = px0 + pw * (amin[0] + amax[0]) / 2; ay = py0 + ph * (amin[1] + amax[1]) / 2
        # position du pivot
        pvx = ax + ap[0] * sx + (piv[0] - 0.5) * (pw * (amax[0] - amin[0])) * 0
        pvy = ay + ap[1] * sy
        nsx, nsy = sx * lsx, sy * lsy
        if nsx == 0 or nsy == 0: return
        # rectangle (centre) en tenant compte du pivot et de l'échelle cumulée
        cx = pvx + (0.5 - piv[0]) * w * nsx; cy = pvy + (0.5 - piv[1]) * h * nsy
        rect = (cx - w * nsx / 2, cy - h * nsy / 2, w * nsx, h * nsy)
        a = alpha
        for o in cs:
            if o.type.name == "CanvasGroup":
                a *= T(o.path_id).get("m_Alpha", 1.0)
        for o in cs:
            if o.type.name != "MonoBehaviour": continue
            t = T(o.path_id)
            if not t.get("m_Enabled", 1): continue
            if "skeletonDataAsset" in t:
                skel = skel_name(t["skeletonDataAsset"])
                folder = os.path.join(SPINE, name, skel)
                if not os.path.isdir(folder):
                    log.append(f"squelette introuvable {skel}"); continue
                # repère squelette : unités = pixels UI, origine au pivot, échelle nsx
                k = nsx
                fr = [(-W / 2 - pvx) / k, (-H / 2 - pvy) / k, (W / 2 - pvx) / k, (H / 2 - pvy) / k]
                tmp = tempfile.mkdtemp()
                cmd = ["node", RENDER, folder, tmp, "--only", "none", "--t0", "--fixedscale", str(k * SS),
                       "--frame", ",".join(f"{v:.3f}" for v in fr), "--base", t.get("startingAnimation") or "idle"]
                p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
                f = os.path.join(tmp, "_image_fixe.png")
                if p.returncode == 0 and os.path.exists(f):
                    im = Image.open(f).convert("RGBA").resize(canvas.size, Image.LANCZOS)
                    col = t.get("m_Color", {"a": 1})
                    if a * col.get("a", 1) < 1:
                        im.putalpha(im.getchannel("A").point(lambda v: v * a * col.get("a", 1)))
                    canvas.alpha_composite(im)
                    log.append(f"spine {skel}")
                else:
                    log.append(f"échec spine {skel}: {p.stderr[-200:]}")
            elif "m_Sprite" in t or "m_Texture" in t:
                ptr = t.get("m_Sprite") or t.get("m_Texture")
                img = sprite_img(ptr) if "m_Sprite" in t else None
                if img is None and "m_Texture" in t and t["m_Texture"]["m_FileID"] == 0 and t["m_Texture"]["m_PathID"] in objs:
                    img = objs[t["m_Texture"]["m_PathID"]].read().image.convert("RGBA")
                if img is None:
                    if ptr and ptr["m_FileID"] != 0: log.append(f"sprite externe ignoré ({go['m_Name']})")
                    continue
                draw(img, cx, cy, w * nsx, h * nsy, t.get("m_Color", {"r": 1, "g": 1, "b": 1, "a": 1}), a)
                log.append(f"image {go['m_Name']} {img.size}")
        for ch in rt["m_Children"]:
            walk(ch["m_PathID"], rect, a, nsx, nsy)

    walk(root, (-W / 2, -H / 2, W, H), 1.0, 1.0, 1.0)
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, f"{idx:02d} - {name}.png")
    canvas.save(out)
    return out, log

if __name__ == "__main__":
    import sys
    only = sys.argv[1:]
    for i, p in enumerate(prefabs, 1):
        if only and p not in only: continue
        out, log = compose(p, i)
        print(f"{os.path.basename(out)}  ->  " + "; ".join(log[:12]) + (" ..." if len(log) > 12 else ""), flush=True)
