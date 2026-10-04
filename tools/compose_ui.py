r"""Recompose les écrans d'interface (prefabs UGUI Form_*, ui_*, hero_* …) en images, tels qu'à l'ouverture.

Canevas de référence 1920x1080 (CanvasScaler du jeu). On parcourt la hiérarchie dans l'ordre de dessin :
objets inactifs / composants désactivés / particules ignorés ; CanvasGroup (alpha), Mask et RectMask2D
(découpe rectangulaire) appliqués.
  - Image : simple, découpée en 9 (Sliced, bordures du sprite), mosaïque (Tiled), remplie (Filled, linéaire),
            préservation du ratio ; sprites résolus aussi dans les atlas d'autres bundles (cab_index.json) ;
  - RawImage : texture + m_UVRect ;
  - TextMeshPro / Text : texte du prefab dessiné avec la police du jeu (taille, couleur, alignement, retour à la ligne) ;
  - SkeletonGraphic : squelette Spine rendu en pose de départ (render.mjs), si extrait.
Sortie : E:\Projets\BloodAndSilver\Interfaces\<bundle>.png (1920x1080) + index.json"""
import os, re, sys, json, subprocess, tempfile, traceback
from concurrent.futures import ProcessPoolExecutor

TOOLS = r"C:\Users\Nauno\.bns_tools"
exec(open(os.path.join(TOOLS, "export_3d.py"), encoding="utf-8-sig").read().split("_EXTRA = None")[0])
U = r"E:\Projets\BloodAndSilver\data\com.moonton.silverblood.eu\files\dragon2019\assets\UI"
SPINE = r"E:\Projets\BloodAndSilver\Spine"
OUT = r"E:\Projets\BloodAndSilver\Interfaces"
FONT = r"E:\Projets\BloodAndSilver\Polices\Font_Regular_Full.ttf"
RENDER = os.path.join(TOOLS, "render", "render.mjs")
W0, H0 = 1920, 1080
PLACEHOLDER = re.compile(r"(?i)^(new text|text|texte|label|\d+|x\d+|\.+|-+|0/0|00:00(:00)?|name|title|desc|content)$")

def compose(name):
    from PIL import Image, ImageDraw, ImageFont
    env = load(os.path.join(U, name + ".unity3d"))
    objs = {o.path_id: o for o in env.objects}
    tt, cls_cache, img_cache = {}, {}, {}
    def T(pid):
        if pid not in tt: tt[pid] = objs[pid].read_typetree()
        return tt[pid]
    def cls(o):
        t = T(o.path_id); sp = t.get("m_Script", {})
        k = (sp.get("m_FileID"), sp.get("m_PathID"))
        if k not in cls_cache:
            so = resolve(o.assets_file, sp)
            try: cls_cache[k] = so.read_typetree().get("m_ClassName", "") if so is not None else ""
            except Exception: cls_cache[k] = ""
        return cls_cache[k]
    def sprite(o_owner, ptr):
        if not ptr or not ptr.get("m_PathID"): return None
        k = (ptr["m_FileID"], ptr["m_PathID"], id(o_owner.assets_file))
        if k not in img_cache:
            so = resolve(o_owner.assets_file, ptr); img_cache[k] = None
            if so is not None:
                try:
                    d = so.read(); im = d.image.convert("RGBA")
                    border = None; ppu = 100.0
                    if so.type.name == "Sprite":
                        b = d.m_Border; border = (b.x, b.y, b.z, b.w); ppu = d.m_PixelsToUnits or 100.0
                    img_cache[k] = (im, border, ppu)
                except Exception: pass
        return img_cache[k]
    roots = [pid for pid, o in objs.items() if o.type.name == "RectTransform" and T(pid)["m_Father"]["m_PathID"] == 0]
    if not roots: return None, ["pas de RectTransform racine"]
    canvas = Image.new("RGBA", (W0, H0), (0, 0, 0, 0))
    log, stats = [], {"images": 0, "textes": 0, "spine": 0, "manquants": 0}
    fonts = {}
    def font(sz):
        sz = max(6, int(round(sz)))
        if sz not in fonts: fonts[sz] = ImageFont.truetype(FONT, sz)
        return fonts[sz]

    def paste(im, x, y, clip, alpha=1.0):
        """colle im (déjà à la bonne taille) en (x,y) haut-gauche, repère image, découpé par clip (x0,y0,x1,y1)."""
        cx0, cy0, cx1, cy1 = clip
        x0, y0 = max(int(x), int(cx0)), max(int(y), int(cy0))
        x1, y1 = min(int(x) + im.width, int(cx1)), min(int(y) + im.height, int(cy1))
        if x1 <= x0 or y1 <= y0: return
        part = im.crop((x0 - int(x), y0 - int(y), x1 - int(x), y1 - int(y)))
        canvas.alpha_composite(part, (x0, y0))

    def tint(im, col, alpha):
        r, g, b, a = col.get("r", 1), col.get("g", 1), col.get("b", 1), col.get("a", 1) * alpha
        if (r, g, b, a) == (1, 1, 1, 1): return im
        ch = im.split()
        return Image.merge("RGBA", [c.point(lambda v, k=k: int(v * k)) for c, k in zip(ch, (r, g, b, a))])

    def nine(im, border, ppu, mult, w, h):
        """9-slice : bordures (gauche, bas, droite, haut) en pixels du sprite."""
        l, b, r, t = border
        k = (100.0 / ppu) / (mult or 1)  # pixels sprite -> unités canevas
        L, B, R, Tp = l * k, b * k, r * k, t * k
        sc = min(1.0, w / max(L + R, 1e-6), h / max(B + Tp, 1e-6))  # bordures réduites si le rectangle est trop petit
        L, B, R, Tp = L * sc, B * sc, R * sc, Tp * sc
        W, H = im.size
        xs_src = [0, l, W - r, W]; ys_src = [0, t, H - b, H]
        xs_dst = [0, L, w - R, w]; ys_dst = [0, Tp, h - B, h]
        out = Image.new("RGBA", (max(1, int(round(w))), max(1, int(round(h)))), (0, 0, 0, 0))
        for i in range(3):
            for j in range(3):
                sx0, sx1, sy0, sy1 = xs_src[i], xs_src[i + 1], ys_src[j], ys_src[j + 1]
                dx0, dx1, dy0, dy1 = xs_dst[i], xs_dst[i + 1], ys_dst[j], ys_dst[j + 1]
                if sx1 - sx0 < 1 or sy1 - sy0 < 1 or dx1 - dx0 < 0.5 or dy1 - dy0 < 0.5: continue
                piece = im.crop((int(sx0), int(sy0), int(sx1), int(sy1))).resize((max(1, int(round(dx1 - dx0))), max(1, int(round(dy1 - dy0)))), Image.BILINEAR)
                out.alpha_composite(piece, (int(round(dx0)), int(round(dy0))))
        return out

    def draw_image(o, t, rect, clip, alpha, cname):
        x0, y0, w, h = rect  # canevas (y vers le bas), coin haut-gauche
        if w < 0.5 or h < 0.5: return
        col = t.get("m_Color", {"r": 1, "g": 1, "b": 1, "a": 1})
        if col.get("a", 1) * alpha <= 0.003: return
        if cname == "RawImage" or ("m_Texture" in t and "m_Sprite" not in t):
            sp = sprite(o, t.get("m_Texture"))
            if sp is None: stats["manquants"] += t.get("m_Texture", {}).get("m_PathID", 0) != 0; return
            im = sp[0]; uv = t.get("m_UVRect", {"x": 0, "y": 0, "width": 1, "height": 1})
            if (uv["x"], uv["y"], uv["width"], uv["height"]) != (0, 0, 1, 1) and uv["width"] > 0 and uv["height"] > 0:
                W, H = im.size
                im = im.crop((int(uv["x"] * W), int((1 - uv["y"] - uv["height"]) * H), int((uv["x"] + uv["width"]) * W), int((1 - uv["y"]) * H)))
            border, ppu, typ = None, 100, 0
        else:
            sp = sprite(o, t.get("m_Sprite"))
            if sp is None:
                if t.get("m_Sprite", {}).get("m_PathID"): stats["manquants"] += 1
                return  # Image sans sprite = rectangle de couleur (souvent zone de clic invisible) : ignoré
            im, border, ppu = sp; typ = t.get("m_Type", 0)
        if im.width == 0 or im.height == 0: return
        if typ == 1 and border and any(border):
            out = nine(im, border, ppu, t.get("m_PixelsPerUnitMultiplier", 1), w, h)
        elif typ == 2:  # mosaïque
            k = 100.0 / ppu / (t.get("m_PixelsPerUnitMultiplier", 1) or 1)
            tw, th = max(1, int(im.width * k)), max(1, int(im.height * k)); tile = im.resize((tw, th))
            out = Image.new("RGBA", (max(1, int(w)), max(1, int(h))))
            for yy in range(0, out.height, th):
                for xx in range(0, out.width, tw): out.alpha_composite(tile, (xx, yy))
        else:
            if t.get("m_PreserveAspect"):
                s = min(w / im.width, h / im.height); nw, nh = im.width * s, im.height * s
                x0, y0, w, h = x0 + (w - nw) / 2, y0 + (h - nh) / 2, nw, nh
            out = im.resize((max(1, int(round(w))), max(1, int(round(h)))), Image.LANCZOS)
            if typ == 3:  # remplissage : horizontal (0) / vertical (1) ; radial dessiné entier
                fa, fm, fo = t.get("m_FillAmount", 1), t.get("m_FillMethod", 4), t.get("m_FillOrigin", 0)
                if fa <= 0: return
                if fm in (0, 1) and fa < 1:
                    if fm == 0:
                        cw = int(out.width * fa); out = out.crop((0, 0, cw, out.height)) if fo == 0 else out.crop((out.width - cw, 0, out.width, out.height))
                        if fo != 0: x0 += w - cw
                    else:
                        ch = int(out.height * fa); out = out.crop((0, out.height - ch, out.width, out.height)) if fo == 0 else out.crop((0, 0, out.width, ch))
                        if fo == 0: y0 += h - ch
        paste(tint(out, col, alpha), round(x0), round(y0), clip)
        stats["images"] += 1

    def draw_text(t, rect, clip, alpha, cname):
        txt = t.get("m_text") if cname != "TextPro" and "m_text" in t else t.get("m_Text")
        if not txt or not txt.strip() or PLACEHOLDER.match(txt.strip()): return
        txt = re.sub(r"<[^>]+>", "", txt)  # balises riches
        if cname == "TextPro" or "m_FontData" in t:
            fd = t.get("m_FontData", {}); size = fd.get("m_FontSize", 24); col = t.get("m_Color", {"r": 1, "g": 1, "b": 1, "a": 1})
            al = fd.get("m_Alignment", 0); ha = ["l", "c", "r"][al % 3]; va = ["t", "m", "b"][al // 3]
        else:
            size = t.get("m_fontSize", 24); col = t.get("m_fontColor", {"r": 1, "g": 1, "b": 1, "a": 1})
            h_ = t.get("m_HorizontalAlignment", 1); v_ = t.get("m_VerticalAlignment", 256)
            ha = "c" if h_ == 2 else "r" if h_ == 4 else "l"; va = "m" if v_ == 512 else "b" if v_ == 1024 else "t"
        x0, y0, w, h = rect
        f = font(size); d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        lines = []
        for para in txt.split("\n"):  # retour à la ligne dans la largeur du rectangle
            cur = ""
            for word in re.split(r"(\s+)", para):
                test = cur + word
                if cur and w > 4 and d.textlength(test, font=f) > w: lines.append(cur.rstrip()); cur = word.lstrip()
                else: cur = test
            lines.append(cur)
        lh = size * 1.2; th = lh * len(lines)
        ty = y0 if va == "t" else y0 + (h - th) / 2 if va == "m" else y0 + h - th
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(layer)
        fill = tuple(int(255 * c) for c in (col.get("r", 1), col.get("g", 1), col.get("b", 1))) + (int(255 * col.get("a", 1) * alpha),)
        for k, ln in enumerate(lines):
            lw = d.textlength(ln, font=f)
            tx = x0 if ha == "l" else x0 + (w - lw) / 2 if ha == "c" else x0 + w - lw
            dl.text((tx, ty + k * lh), ln, font=f, fill=fill, stroke_width=max(1, int(size / 18)), stroke_fill=(0, 0, 0, fill[3] // 2))
        cx0, cy0, cx1, cy1 = clip
        layer = layer.crop((max(0, int(cx0)), max(0, int(cy0)), min(W0, int(cx1)), min(H0, int(cy1))))
        canvas.alpha_composite(layer, (max(0, int(cx0)), max(0, int(cy0))))
        stats["textes"] += 1

    def draw_spine(t, piv, scale, clip, alpha):
        sda = resolve(objs[next(iter(objs))].assets_file, t["skeletonDataAsset"])
        if sda is None: return
        js = sda.read_typetree().get("skeletonJSON")
        jo = resolve(sda.assets_file, js) if js else None
        if jo is None: return
        skel = jo.peek_name().rsplit(".", 1)[0]
        cands = [os.path.join(SPINE, name, skel)] + [os.path.join(SPINE, d, skel) for d in os.listdir(SPINE) if os.path.isdir(os.path.join(SPINE, d, skel))]
        folder = next((c for c in cands if os.path.isdir(c)), None)
        if not folder: log.append(f"spine absent {skel}"); return
        px, py = piv; k = scale
        fr = [(0 - px) / k, -(H0 - py) / k, (W0 - px) / k, py / k]  # repère squelette (y vers le haut)
        tmp = tempfile.mkdtemp()
        cmd = ["node", RENDER, folder, tmp, "--only", "none", "--t0", "--fixedscale", str(k), "--frame", ",".join(f"{v:.3f}" for v in fr),
               "--base", t.get("startingAnimation") or "idle"]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        f = os.path.join(tmp, "_image_fixe.png")
        if p.returncode == 0 and os.path.exists(f):
            im = Image.open(f).convert("RGBA").resize(canvas.size, Image.LANCZOS)
            col = t.get("m_Color", {"a": 1})
            if alpha * col.get("a", 1) < 1: im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha * col.get("a", 1))))
            paste(im.crop((0, 0, W0, H0)), 0, 0, clip); stats["spine"] += 1

    def walk(pid, parent_rect, origin, scale, clip, alpha, is_root=False):
        """parent_rect : rectangle du parent dans son repère local (x0, y0, w, h ; y vers le haut) ;
        origin/scale : passage repère local du parent -> canevas (y vers le haut, origine en bas à gauche)."""
        rt = T(pid); go = T(rt["m_GameObject"]["m_PathID"])
        if not go.get("m_IsActive", 1) and not is_root: return
        comps = [objs[c["component"]["m_PathID"]] for c in go["m_Component"] if c["component"]["m_FileID"] == 0 and c["component"]["m_PathID"] in objs]
        if any(o.type.name in ("ParticleSystem", "ParticleSystemRenderer", "Camera") for o in comps): return
        if "m_AnchoredPosition" not in rt:  # Transform 3D sous l'UI : ignoré (modèles 3D, effets)
            return
        px0, py0, pw, ph = parent_rect
        amin, amax, pv = rt["m_AnchorMin"], rt["m_AnchorMax"], rt["m_Pivot"]
        ap, sd, ls = rt["m_AnchoredPosition"], rt["m_SizeDelta"], rt["m_LocalScale"]
        if is_root: amin, amax, ap, sd, ls = {"x": 0, "y": 0}, {"x": 1, "y": 1}, {"x": 0, "y": 0}, {"x": 0, "y": 0}, {"x": 1, "y": 1}
        ax0, ax1 = px0 + pw * amin["x"], px0 + pw * amax["x"]; ay0, ay1 = py0 + ph * amin["y"], py0 + ph * amax["y"]
        w, h = (ax1 - ax0) + sd["x"], (ay1 - ay0) + sd["y"]
        pvx, pvy = ax0 + (ax1 - ax0) * pv["x"] + ap["x"], ay0 + (ay1 - ay0) * pv["y"] + ap["y"]
        ox, oy = origin[0] + scale[0] * pvx, origin[1] + scale[1] * pvy
        sx, sy = scale[0] * ls["x"], scale[1] * ls["y"]
        if abs(sx) < 1e-6 or abs(sy) < 1e-6: return
        local = (-pv["x"] * w, -pv["y"] * h, w, h)
        cx0, cy0 = ox + sx * local[0], oy + sy * local[1]; cw, ch = sx * w, sy * h
        if cw < 0: cx0, cw = cx0 + cw, -cw
        if ch < 0: cy0, ch = cy0 + ch, -ch
        rect_img = (cx0, H0 - (cy0 + ch), cw, ch)  # repère image (y vers le bas)
        a = alpha; newclip = clip
        for o in comps:
            if o.type.name == "CanvasGroup":
                tg = T(o.path_id)
                if tg.get("m_Enabled", 1): a *= tg.get("m_Alpha", 1.0)
        if a <= 0.003: return
        for o in comps:
            if o.type.name != "MonoBehaviour": continue
            t = T(o.path_id)
            if not t.get("m_Enabled", 1): continue
            c = cls(o)
            if c in ("Mask", "RectMask2D"):
                x, y, ww, hh = rect_img; newclip = (max(clip[0], x), max(clip[1], y), min(clip[2], x + ww), min(clip[3], y + hh))
            try:
                if "skeletonDataAsset" in t and c.startswith("Skeleton"): draw_spine(t, (ox, oy), sx, newclip, a)
                elif c in ("TMPPro", "TextMeshProUGUI", "TextPro", "Text") or "m_text" in t or ("m_Text" in t and "m_FontData" in t): draw_text(t, rect_img, newclip, a, c)
                elif "m_Sprite" in t or "m_Texture" in t: draw_image(o, t, rect_img, newclip, a, c)
            except Exception as e:
                log.append(f"{go.get('m_Name')}: {type(e).__name__} {e}"[:160])
        for chd in rt["m_Children"]:
            if chd["m_PathID"] in objs: walk(chd["m_PathID"], local, (ox, oy), (sx, sy), newclip, a)

    root = max(roots, key=lambda r: len(T(r)["m_Children"]))
    walk(root, (0, 0, W0, H0), (0, 0), (1, 1), (0, 0, W0, H0), 1.0, is_root=True)
    return canvas, [stats] + log[:20]

def job(name):
    try:
        im, info = compose(name)
        if im is None: return name, None, info
        bbox = im.getbbox()
        if not bbox: return name, None, info + ["image vide"]
        os.makedirs(OUT, exist_ok=True)
        p = os.path.join(OUT, name + ".png"); im.save(p, optimize=False)
        return name, p, info
    except Exception as e:
        return name, None, [f"{type(e).__name__}: {e}", traceback.format_exc()[-400:]]

if __name__ == "__main__":
    C = json.load(open(os.path.join(TOOLS, "census.json"), encoding="utf-8"))
    names = sorted(os.path.splitext(os.path.basename(k))[0] for k, v in C.items()
                   if k.startswith("UI" + os.sep) and v.get("types", {}).get("RectTransform", 0) > 3)
    if len(sys.argv) > 1: names = [n for n in names if any(re.fullmatch(a, n) for a in sys.argv[1:])]
    print(len(names), "prefabs d'interface", flush=True)
    res = {}
    with ProcessPoolExecutor(max(2, (os.cpu_count() or 4) - 4)) as ex:
        for k, (n, p, info) in enumerate(ex.map(job, names), 1):
            res[n] = {"file": p, "info": info}
            if k % 50 == 0 or len(names) < 20: print(k, n, "->", "OK" if p else "rien", info[:2], flush=True)
    old = {}
    ij = os.path.join(OUT, "index.json")
    if os.path.exists(ij): old = json.load(open(ij, encoding="utf-8"))
    old.update(res); json.dump(old, open(ij, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("TERMINE", sum(1 for r in res.values() if r["file"]), "écrans composés sur", len(res), flush=True)
