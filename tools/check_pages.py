"""Vérifie que chaque page PNG correspond à son atlas : taille attendue et régions non vides.
Usage : check_pages.py <dossier_squelette> [...]"""
import sys, os, re
from PIL import Image

def parse_atlas(path):
    pages, cur = [], None
    lines = open(path, encoding="utf-8", errors="replace").read().replace("\r", "").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            cur = None; i += 1; continue
        if cur is None:  # nouvelle page
            cur = {"name": line, "size": None, "regions": []}; pages.append(cur); i += 1
            while i < len(lines) and ":" in lines[i]:
                k, v = lines[i].split(":", 1)
                if k.strip() == "size": cur["size"] = tuple(int(x) for x in v.split(","))
                i += 1
            continue
        reg = {"name": line}; i += 1
        while i < len(lines) and ":" in lines[i]:
            k, v = lines[i].split(":", 1); reg[k.strip()] = v.strip(); i += 1
        cur["regions"].append(reg)
    return pages

for d in sys.argv[1:]:
    atlas = next(f for f in os.listdir(d) if f.endswith(".atlas"))
    for p in parse_atlas(os.path.join(d, atlas)):
        img = Image.open(os.path.join(d, p["name"])).convert("RGBA")
        sx = img.width / p["size"][0]; sy = img.height / p["size"][1]
        a = img.getchannel("A")
        empty = 0
        for r in p["regions"]:
            x, y, w, h = (int(v) for v in r["bounds"].split(","))
            if r.get("rotate") in ("90", "true", "270"): w, h = h, w
            box = (int(x * sx), int(y * sy), max(int((x + w) * sx), int(x * sx) + 1), max(int((y + h) * sy), int(y * sy) + 1))
            if a.crop(box).getextrema()[1] == 0: empty += 1
        print(f"{os.path.basename(d):22} {p['name']:28} atlas={p['size']} png={img.size} régions={len(p['regions'])} vides={empty}")
