"""Planche contact : sheet.py <sortie.png> <motif glob> [cellule px]"""
import sys, glob, os
from PIL import Image, ImageDraw

out, pattern = sys.argv[1], sys.argv[2]
cell = int(sys.argv[3]) if len(sys.argv) > 3 else 220
files = sorted(glob.glob(pattern, recursive=True))[:48]
cols = 8
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * cell, rows * (cell + 14)), (28, 28, 34))
d = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(f).convert("RGBA")
    im.thumbnail((cell - 4, cell - 4))
    x, y = (i % cols) * cell, (i // cols) * (cell + 14)
    sheet.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2), im)
    label = os.path.basename(os.path.dirname(f)) + "/" + os.path.splitext(os.path.basename(f))[0]
    d.text((x + 3, y + cell), label[:40], fill=(220, 220, 220))
sheet.save(out)
print(len(files), "images")
