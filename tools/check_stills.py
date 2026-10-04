"""Contrôle des images fixes : taille, couverture opaque, puis planches numérotées sur fond gris."""
import glob, os
from PIL import Image, ImageDraw

files = sorted(glob.glob(r"E:\Projets\BloodAndSilver\Images_fixes\*.png"), key=str.lower)
OUT = r"C:\Users\Nauno\.bns_tools\still_sheets"
os.makedirs(OUT, exist_ok=True)
print(f"{len(files)} images")
for i, f in enumerate(files):
    im = Image.open(f).convert("RGBA")
    a = im.getchannel("A").resize((128, 128))
    cov = sum(1 for v in a.getdata() if v > 128) / 128 ** 2
    flag = "  <-- A VERIFIER" if cov < 0.08 or min(im.size) < 300 else ""
    print(f"{i:3} {os.path.basename(f)[:45]:45} {im.width}x{im.height}  opaque={cov:.0%}{flag}")

cw, ch, cols, per = 300, 320, 6, 30
for s in range(0, len(files), per):
    chunk = files[s:s + per]
    rows = (len(chunk) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * (ch + 16)), (40, 40, 48))
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(chunk):
        im = Image.open(f).convert("RGBA"); im.thumbnail((cw - 8, ch - 8))
        cell = Image.new("RGBA", (cw - 4, ch - 4), (128, 128, 140, 255))
        cell.alpha_composite(im, ((cell.width - im.width) // 2, (cell.height - im.height) // 2))
        x, y = (i % cols) * cw, (i // cols) * (ch + 16)
        sheet.paste(cell.convert("RGB"), (x + 2, y + 2))
        d.text((x + 3, y + ch), f"{s + i}: {os.path.splitext(os.path.basename(f))[0][:38]}", fill=(235, 235, 235))
    sheet.save(os.path.join(OUT, f"stills_{s // per}.jpg"), quality=88)
