r"""Mode AFK (pixel art) : rend les personnages / monstres 2D (AFK_C_*, AFK_M_*, AFK_*) et compose les cartes de sol (Afk_Ground_*).

Personnage = hiérarchie de SpriteRenderer animée par des AnimationClip Unity : position / rotation (Euler) / échelle des
Transform (liaisons génériques, chemins = CRC32 relatifs à l'Animator) + échange de sprite (courbes PPtr). On rejoue
chaque clip à 15 i/s, on compose les sprites (ordre de tri, couleur, retournement), agrandissement x3 au plus proche voisin
(pixels nets) -> WebP animé sans perte + image fixe. Les ombres de sol colorées (Shadow_Desert / Snow / Grass) sont ignorées.
Sortie : <projet>\Site\pixel\<bundle>\<clip>.webp, _image_fixe.png ; Cartes : Site\pixel\_sols\<nom>.png ; index.json"""
from config import PROJECT, TOOLS_DIR, ASSETS  # chemins : voir tools/config.py
import os, sys, re, json, math, zlib, glob, traceback
import numpy as np
from concurrent.futures import ProcessPoolExecutor

TOOLS = TOOLS_DIR
ASSETS = ASSETS
AFK_OUT = PROJECT + r"\Site\pixel"
FPS, UP = 15, 3

def setup():
    sys.argv = ["x"]
    src = open(os.path.join(TOOLS, "export_rigged.py"), encoding="utf-8-sig").read().split('if __name__ == "__main__":')[0]
    exec(src, globals())

def mat2(pos, rot_deg, scale):
    """Matrice 3x3 (2D homogène) : translation * rotation Z * échelle (repère Unity, y vers le haut)."""
    c, s = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))
    return np.array([[c * scale[0], -s * scale[1], pos[0]], [s * scale[0], c * scale[1], pos[1]], [0, 0, 1]])

def quat_z(q):  # angle Z (degrés) d'un quaternion Unity (rotation 2D)
    return math.degrees(2 * math.atan2(q["z"], q["w"]))

def sprite_info(o):
    sp = o.read(); im = sp.image.convert("RGBA")
    r = sp.m_Rect; pv = sp.m_Pivot; ppu = sp.m_PixelsToUnits or 100
    return {"img": im, "w": r.width, "h": r.height, "px": pv.x, "py": pv.y, "ppu": ppu}

def render_bundle(path):
    from PIL import Image
    setup()
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        env = load(path); objs = {o.path_id: o for o in env.objects}
        T = {pid: o.read_typetree() for pid, o in objs.items() if o.type.name == "Transform"}
        go_name = {pid: objs[t["m_GameObject"]["m_PathID"]].read_typetree()["m_Name"] for pid, t in T.items()}
        tr_of_go = {t["m_GameObject"]["m_PathID"]: pid for pid, t in T.items()}
        sprites = {}
        def spr(ptr):
            pid = ptr.get("m_PathID") if ptr else 0
            if not pid: return None
            if pid not in sprites:
                so = resolve(objs[next(iter(objs))].assets_file, ptr) if ptr.get("m_FileID") else objs.get(pid)
                try: sprites[pid] = sprite_info(so) if so is not None and so.type.name == "Sprite" else None
                except Exception: sprites[pid] = None
            return sprites[pid]
        rends = []
        for o in env.objects:
            if o.type.name != "SpriteRenderer": continue
            t = o.read_typetree(); gp = t["m_GameObject"]["m_PathID"]
            gname = objs[gp].read_typetree()["m_Name"]
            if re.match(r"(?i)shadow", gname) or not t.get("m_Enabled", 1): continue
            rends.append({"tr": tr_of_go.get(gp), "sprite": t["m_Sprite"], "order": t.get("m_SortingOrder", 0), "color": t.get("m_Color", {"r": 1, "g": 1, "b": 1, "a": 1}),
                          "flipx": t.get("m_FlipX", 0), "flipy": t.get("m_FlipY", 0)})
        if not rends: return {"name": name, "empty": True}
        # racine de l'Animator et chemins (CRC32) des Transform
        anim = next((o for o in env.objects if o.type.name == "Animator"), None)
        root = tr_of_go.get(anim.read_typetree()["m_GameObject"]["m_PathID"]) if anim else None
        def relpath(pid):
            parts = []
            while pid is not None and pid != root and pid in T:
                parts.append(go_name[pid]); f = T[pid]["m_Father"]["m_PathID"]; pid = f if f in T else None
            return "/".join(reversed(parts))
        h2tr = {zlib.crc32(relpath(pid).encode()): pid for pid in T}
        h2go = {zlib.crc32(relpath(pid).encode()): T[pid]["m_GameObject"]["m_PathID"] for pid in T}
        # clips du contrôleur
        clips = []
        if anim is not None:
            ct = resolve(anim.assets_file, anim.read_typetree().get("m_Controller"))
            if ct is not None:
                c_ = ct.read_typetree()
                for ptr in c_.get("m_AnimationClips", []):
                    co = resolve(ct.assets_file, ptr)
                    if co is not None and co.type.name == "AnimationClip" and all(x.path_id != co.path_id for x in clips): clips.append(co)
        if not clips: clips = [o for o in env.objects if o.type.name == "AnimationClip"]

        def pose(overrides, sprite_over):
            """Liste (ordre, image, matrice monde) pour la pose donnée."""
            def world(pid):
                m = np.eye(3)
                chain = []
                while pid in T: chain.append(pid); f = T[pid]["m_Father"]["m_PathID"]; pid = f if f in T else None
                for p in reversed(chain):
                    t = T[p]; ov = overrides.get(p, {})
                    pos = ov.get("pos", (t["m_LocalPosition"]["x"], t["m_LocalPosition"]["y"]))
                    rot = ov.get("rot", quat_z(t["m_LocalRotation"]))
                    sc = ov.get("scale", (t["m_LocalScale"]["x"], t["m_LocalScale"]["y"]))
                    m = m @ mat2(pos, rot, sc)
                return m
            out = []
            for r in rends:
                if r["tr"] is None: continue
                s = spr(sprite_over.get(T[r["tr"]]["m_GameObject"]["m_PathID"], r["sprite"]))
                if s is None: continue
                out.append((r["order"], s, world(r["tr"]), r))
            return sorted(out, key=lambda x: x[0])

        def corners(s, m):
            w, h = s["w"] / s["ppu"], s["h"] / s["ppu"]
            pts = [(-s["px"] * w, -s["py"] * h), ((1 - s["px"]) * w, -s["py"] * h), ((1 - s["px"]) * w, (1 - s["py"]) * h), (-s["px"] * w, (1 - s["py"]) * h)]
            return [tuple((m @ np.array([x, y, 1]))[:2]) for x, y in pts]

        def draw(items, box, ppu):
            x0, y0, x1, y1 = box; W = max(1, int(round((x1 - x0) * ppu))); H = max(1, int(round((y1 - y0) * ppu)))
            canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            for order, s, m, r in items:
                im = s["img"]
                if r["flipx"]: im = im.transpose(Image.FLIP_LEFT_RIGHT)
                if r["flipy"]: im = im.transpose(Image.FLIP_TOP_BOTTOM)
                c = r["color"]
                if (c["r"], c["g"], c["b"], c["a"]) != (1, 1, 1, 1):
                    ch = im.split(); im = Image.merge("RGBA", [x.point(lambda v, k=k: int(v * k)) for x, k in zip(ch, (c["r"], c["g"], c["b"], c["a"]))])
                # pixel sprite (u,v) -> monde -> pixel canevas ; on donne à PIL l'inverse (canevas -> sprite)
                sx, sy = s["w"] / im.width, s["h"] / im.height
                A_ = np.array([[1 / s["ppu"] * sx, 0, -s["px"] * s["w"] / s["ppu"]], [0, -1 / s["ppu"] * sy, (1 - s["py"]) * s["h"] / s["ppu"]], [0, 0, 1]])
                C_ = np.array([[ppu, 0, -x0 * ppu], [0, -ppu, y1 * ppu], [0, 0, 1]])
                full = C_ @ m @ A_
                if abs(np.linalg.det(full[:2, :2])) < 1e-9: continue  # pièce cachée (échelle 0)
                inv = np.linalg.inv(full)
                layer = im.transform((W, H), Image.AFFINE, tuple(inv[:2].ravel()), resample=Image.NEAREST)
                canvas.alpha_composite(layer)
            return canvas

        # échantillonnage de chaque clip
        frames_by_clip = {}
        for co in clips:
            ct = co.read_typetree(); dur, t0, curve = decode_clip(ct)
            gb = ct["m_ClipBindingConstant"]["genericBindings"]; pmap = ct["m_ClipBindingConstant"].get("pptrCurveMapping", [])
            n = max(1, int(round(dur * FPS))); seq = []
            for f in range(n):
                tt = t0 + min(dur, f / FPS); ov = {}; so = {}; ci = 0
                for b in gb:
                    size = {1: 3, 2: 4, 3: 3, 4: 3}.get(b["attribute"], 1) if b["typeID"] == 4 else 1
                    vals = [curve(ci + k, tt) for k in range(size)]
                    if b["typeID"] == 4 and b["path"] in h2tr:
                        p = h2tr[b["path"]]; d = ov.setdefault(p, {})
                        if b["attribute"] == 1: d["pos"] = (vals[0], vals[1])
                        elif b["attribute"] == 3: d["scale"] = (vals[0], vals[1])
                        elif b["attribute"] == 4: d["rot"] = vals[2]
                        elif b["attribute"] == 2: d["rot"] = math.degrees(2 * math.atan2(vals[2], vals[3]))
                    elif b.get("isPPtrCurve") and b["path"] in h2go and pmap:
                        k = int(round(vals[0]))
                        if 0 <= k < len(pmap): so[h2go[b["path"]]] = pmap[k]
                    ci += size
                seq.append(pose(ov, so))
            frames_by_clip[ct["m_Name"]] = (seq, dur)
        if not frames_by_clip: frames_by_clip["Pose"] = ([pose({}, {})], 0)
        # boîte commune à tous les clips (taille fixe d'une animation à l'autre), ppu = celui du sprite principal
        pts = [c for seq, _ in frames_by_clip.values() for items in seq for (_, s, m, _) in items for c in corners(s, m)]
        if not pts: return {"name": name, "empty": True}
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]; pad = 0.05
        box = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
        ppu = max(s["ppu"] for s in sprites.values() if s) or 100
        folder = os.path.join(AFK_OUT, name); os.makedirs(folder, exist_ok=True)
        info = {"name": name, "clips": [], "size": None}
        for cname, (seq, dur) in frames_by_clip.items():
            ims = [draw(items, box, ppu) for items in seq]
            ims = [im.resize((im.width * UP, im.height * UP), Image.NEAREST) for im in ims]
            safe = re.sub(r"[^\w\-]+", "_", re.sub(r"_?AFK_.*$", "", cname)) or "clip"
            fn = os.path.join(folder, safe + ".webp")
            if len(ims) > 1: ims[0].save(fn, save_all=True, append_images=ims[1:], duration=int(1000 / FPS), loop=0, lossless=True)
            else: ims[0].save(fn, lossless=True)
            info["clips"].append({"name": safe, "file": os.path.basename(fn), "frames": len(ims), "duration": round(dur, 2)})
            info["size"] = ims[0].size
        idle = next((c for c in frames_by_clip if re.match(r"(?i)idle", c)), next(iter(frames_by_clip)))
        still = draw(frames_by_clip[idle][0][0], box, ppu); still = still.resize((still.width * UP, still.height * UP), Image.NEAREST)
        still.save(os.path.join(folder, "_image_fixe.png"))
        return info
    except Exception as e:
        return {"name": name, "error": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-500:]}

def compose_ground(path):
    """Carte de sol AFK : tous les SpriteRenderer à leur position monde, dans l'ordre de tri."""
    from PIL import Image
    setup()
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        env = load(path); objs = {o.path_id: o for o in env.objects}
        T = {pid: o.read_typetree() for pid, o in objs.items() if o.type.name == "Transform"}
        tr_of_go = {t["m_GameObject"]["m_PathID"]: pid for pid, t in T.items()}
        def world(pid):
            m = np.eye(3); chain = []
            while pid in T: chain.append(pid); f = T[pid]["m_Father"]["m_PathID"]; pid = f if f in T else None
            for p in reversed(chain):
                t = T[p]; m = m @ mat2((t["m_LocalPosition"]["x"], t["m_LocalPosition"]["y"]), quat_z(t["m_LocalRotation"]), (t["m_LocalScale"]["x"], t["m_LocalScale"]["y"]))
            return m
        cache, items = {}, []
        for o in env.objects:
            if o.type.name != "SpriteRenderer": continue
            t = o.read_typetree(); pid = t["m_Sprite"]["m_PathID"]
            if not pid or not t.get("m_Enabled", 1): continue
            if pid not in cache:
                so = objs.get(pid) if t["m_Sprite"]["m_FileID"] == 0 else resolve(o.assets_file, t["m_Sprite"])
                try: cache[pid] = sprite_info(so) if so is not None else None
                except Exception: cache[pid] = None
            s = cache[pid]; tp = tr_of_go.get(t["m_GameObject"]["m_PathID"])
            if s is None or tp is None: continue
            m = world(tp); items.append((t.get("m_SortingLayerID", 0), t.get("m_SortingOrder", 0), -m[1, 2], s, m, t))
        if not items: return {"name": name, "empty": True}
        items.sort(key=lambda x: (x[0], x[1], x[2]))
        ppu = max(it[3]["ppu"] for it in items)
        pts = []
        for *_, s, m, t in items:
            w, h = s["w"] / s["ppu"], s["h"] / s["ppu"]
            for x, y in [(-s["px"] * w, -s["py"] * h), ((1 - s["px"]) * w, (1 - s["py"]) * h), (-s["px"] * w, (1 - s["py"]) * h), ((1 - s["px"]) * w, -s["py"] * h)]:
                pts.append((m @ np.array([x, y, 1]))[:2])
        pts = np.array(pts); x0, y0 = pts.min(0); x1, y1 = pts.max(0)
        scale = min(1.0, 6000 / max((x1 - x0) * ppu, (y1 - y0) * ppu))  # limite ~6000 px
        W, H = int((x1 - x0) * ppu * scale) + 1, int((y1 - y0) * ppu * scale) + 1
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for *_, s, m, t in items:
            im = s["img"]
            if t.get("m_FlipX"): im = im.transpose(Image.FLIP_LEFT_RIGHT)
            sx, sy = s["w"] / im.width, s["h"] / im.height
            A_ = np.array([[1 / s["ppu"] * sx, 0, -s["px"] * s["w"] / s["ppu"]], [0, -1 / s["ppu"] * sy, (1 - s["py"]) * s["h"] / s["ppu"]], [0, 0, 1]])
            C_ = np.array([[ppu * scale, 0, -x0 * ppu * scale], [0, -ppu * scale, y1 * ppu * scale], [0, 0, 1]])
            if abs(np.linalg.det((C_ @ m @ A_)[:2, :2])) < 1e-9: continue
            inv = np.linalg.inv(C_ @ m @ A_)
            # rendu limité à la zone du sprite (accélère les grandes cartes)
            cs = [(C_ @ m @ np.array([x, y, 1]))[:2] for x, y in [(-s["px"] * s["w"] / s["ppu"], -s["py"] * s["h"] / s["ppu"]), ((1 - s["px"]) * s["w"] / s["ppu"], (1 - s["py"]) * s["h"] / s["ppu"]),
                                                                    (-s["px"] * s["w"] / s["ppu"], (1 - s["py"]) * s["h"] / s["ppu"]), ((1 - s["px"]) * s["w"] / s["ppu"], -s["py"] * s["h"] / s["ppu"])]]
            bx0, by0 = max(0, int(min(c[0] for c in cs)) - 1), max(0, int(min(c[1] for c in cs)) - 1)
            bx1, by1 = min(W, int(max(c[0] for c in cs)) + 2), min(H, int(max(c[1] for c in cs)) + 2)
            if bx1 <= bx0 or by1 <= by0: continue
            sh = np.array([[1, 0, bx0], [0, 1, by0], [0, 0, 1]])
            inv2 = inv @ sh
            layer = im.transform((bx1 - bx0, by1 - by0), Image.AFFINE, tuple(inv2[:2].ravel()), resample=Image.NEAREST)
            canvas.alpha_composite(layer, (bx0, by0))
        os.makedirs(os.path.join(AFK_OUT, "_sols"), exist_ok=True)
        canvas.save(os.path.join(AFK_OUT, "_sols", name + ".png"))
        return {"name": name, "ground": True, "size": canvas.size, "tiles": len(items)}
    except Exception as e:
        return {"name": name, "error": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-500:]}

if __name__ == "__main__":
    allb = sorted(glob.glob(os.path.join(ASSETS, "ABResource", "AFK_*.unity3d")) + glob.glob(os.path.join(ASSETS, "ABResource", "Afk_*.unity3d")), key=str.lower)
    grounds = [b for b in allb if re.search(r"(?i)afk_ground", os.path.basename(b))]
    chars = [b for b in allb if b not in grounds and not re.search(r"(?i)afk_(texture|animroot)", os.path.basename(b))]
    if len(sys.argv) > 1: chars = [b for b in chars if any(re.search(a, os.path.basename(b)) for a in sys.argv[1:])]; grounds = [g for g in grounds if any(re.search(a, os.path.basename(g)) for a in sys.argv[1:])]
    print(len(chars), "personnages / objets,", len(grounds), "cartes de sol", flush=True)
    res = []
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as ex:
        res += list(ex.map(render_bundle, chars)); res += list(ex.map(compose_ground, grounds))
    os.makedirs(AFK_OUT, exist_ok=True)
    idx_path = os.path.join(AFK_OUT, "index.json")
    old = {r["name"]: r for r in (json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else [])}
    for r in res:
        if "error" not in r and not r.get("empty"): old[r["name"]] = r
    json.dump(sorted(old.values(), key=lambda r: r["name"].lower()), open(idx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    errs = [r for r in res if "error" in r]
    print("TERMINE", sum(1 for r in res if r.get("clips")), "animés,", sum(len(r.get("clips", [])) for r in res), "animations,",
          sum(1 for r in res if r.get("ground")), "cartes,", sum(1 for r in res if r.get("empty")), "vides,", len(errs), "erreurs", flush=True)
    for e in errs[:8]: print("ERREUR", e["name"], e["error"], e["tb"][-300:], flush=True)
