"""Copie les fonds d'écran retenus (bg_candidates.json moins les exclusions issues de la revue
visuelle) dans E:\\Projets\\BloodAndSilver\\Fonds_ecran, en gardant le nom de texture du jeu."""
import json, os, shutil
from collections import Counter

cands = json.load(open(r"C:\Users\Nauno\.bns_tools\bg_candidates.json", encoding="utf-8"))
OUT = r"E:\Projets\BloodAndSilver\Fonds_ecran"

# Indices écartés à la revue : captures de tutoriel / plans de jeu avec interface, fonds unis ou
# presque vides, parchemins et cartes vierges, gabarits.
EXCLUDE = {0, 14, 34, 60, 125, 126, 127, 129, 130, 131, 132, 135, 138, 142, 152, 163, 166, 169, 172,
           282, 288, 440, 443, 445, 452, 455, 459, 461, 467, 468, 470, 473, 478, 480, 481, 482, 483,
           494, 497, 498, 499, 530, 531, 547, 548, 549, 551, 562, 564, 565, 567, 576, 578, 586, 587}
EXCLUDE |= set(range(306, 317))   # écrans de chargement « carte » avec interface
EXCLUDE |= set(range(463, 467))   # cartes vierges
EXCLUDE |= set(range(500, 527))   # captures de combat / guide
EXCLUDE |= set(range(532, 547))   # tutoriels
EXCLUDE |= set(range(559, 562))   # guide

os.makedirs(OUT, exist_ok=True)
keep = [c for i, c in enumerate(cands) if i not in EXCLUDE]
names = Counter(os.path.basename(c["path"]) for c in keep)
for c in keep:
    base = os.path.basename(c["path"])
    if names[base] > 1:  # même nom de texture dans plusieurs bundles : préfixe du bundle
        base = os.path.basename(os.path.dirname(c["path"])) + "__" + base
    shutil.copy2(c["path"], os.path.join(OUT, base))
print(len(keep), "fonds copiés sur", len(cands), "candidats")
