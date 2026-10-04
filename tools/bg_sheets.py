"""Planches numérotées des candidats fonds d'écran (60 par planche) pour la revue."""
import json, os
from PIL import Image, ImageDraw

cands = json.load(open(r"C:\Users\Nauno\.bns_tools\bg_candidates.json", encoding="utf-8"))
OUT = r"C:\Users\Nauno\.bns_tools\bg_sheets"
os.makedirs(OUT, exist_ok=True)
cw, ch, cols, per = 300, 180, 6, 60
for s in range(0, len(cands), per):
    chunk = cands[s:s + per]
    rows = (len(chunk) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * (ch + 16)), (28, 28, 34))
    d = ImageDraw.Draw(sheet)
    for i, c in enumerate(chunk):
        im = Image.open(c["path"]).convert("RGB"); im.thumbnail((cw - 6, ch - 6))
        x, y = (i % cols) * cw, (i // cols) * (ch + 16)
        sheet.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2))
        d.text((x + 3, y + ch), f"{s + i}: {os.path.basename(os.path.dirname(c['path']))[:34]}", fill=(230, 230, 230))
    sheet.save(os.path.join(OUT, f"sheet_{s // per:02d}.jpg"), quality=85)
print("planches :", (len(cands) + per - 1) // per)
