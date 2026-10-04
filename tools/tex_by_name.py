"""Index des textures extraites (PNG) par nom normalisé, pour retexturer les matériaux dont la texture
d'origine est dans un bundle absent du téléphone (décors ExHall/Ophall…)."""
import os, re, json
PNG = r"E:\Projets\BloodAndSilver\PNG"
IDX = r"C:\Users\Nauno\.bns_tools\tex_by_name.json"
SUFFIX = {"d": "diffuse", "diffuse": "diffuse", "albedo": "diffuse", "c": "diffuse", "col": "diffuse", "color": "diffuse", "basecolor": "diffuse",
          "ems": "emissive", "emissive": "emissive", "e": "emissive", "emi": "emissive"}

def norm(n):
    n = n.lower()
    n = re.sub(r"^(3dui_)+", "", n)
    return n

def build():
    idx = {}
    for root, _, files in os.walk(PNG):
        for f in files:
            if not f.lower().endswith(".png"): continue
            stem = f[:-4]
            m = re.match(r"(.+?)_([a-z]+)$", stem, re.I)
            if not m or m.group(2).lower() not in SUFFIX: continue
            key, kind = norm(m.group(1)), SUFFIX[m.group(2).lower()]
            p = os.path.join(root, f)
            cur = idx.setdefault(key, {})
            # préfère le fichier le plus gros (meilleure résolution) en cas de doublon
            if kind not in cur or os.path.getsize(p) > os.path.getsize(cur[kind]): cur[kind] = p
    json.dump(idx, open(IDX, "w", encoding="utf-8"))
    return idx

_I = None
_TAIL = None
def lookup(mat_name):
    """Textures {'diffuse': png, 'emissive': png?, 'approx': bool} pour un nom de matériau, ou {}.
    1) même nom (sans préfixe 3DUI_ ni suffixe _Low)  2) autre variante a/b/c du même objet
    3) même objet dans une autre zone du jeu (ExHall_BU_Pillar04a -> SealCastle_BU_Pillar04a) : approximatif."""
    global _I, _TAIL
    if _I is None:
        _I = json.load(open(IDX, encoding="utf-8")) if os.path.exists(IDX) else build()
        _TAIL = {}
        for k in _I:
            if "diffuse" in _I[k] and "_" in k: _TAIL.setdefault(k.split("_", 1)[1], []).append(k)
    n = norm(re.sub(r"\s*\(Instance\)$", "", mat_name)).replace(" ", "")
    has = lambda k: k in _I and "diffuse" in _I[k]
    # montagnes lointaines des cartes homeland : texture de montagne commune de la zone Island
    if re.match(r"homeland_mountain.*_(bright|dark)\d*$", n) and has("lsland_st_mountain01a"): return dict(_I["lsland_st_mountain01a"], approx=True)
    # variantes de nuit / fonds de bassin / bordures : texture de nuit si elle existe, sinon celle de jour
    night = n.endswith("_night")
    core = re.sub(r"(_bottom|_edge|_night)+$", "", n)
    if core != n:
        if night and has(core + "_night"): return dict(_I[core + "_night"], approx=False)
        r = lookup(core)
        if r: return r
    # herbe des cinématiques (lsland_GR_Timeline, SeaSide_GR_Timeline01) : herbe de la zone
    m = re.match(r"([a-z]+)_gr_timeline", n)
    if m:
        g = sorted(k for k in _I if k.startswith(m.group(1) + "_gr_grass") and "diffuse" in _I[k])
        if g: return dict(_I[g[0]], approx=True)
    # terrains homeland : herbe de l'île
    if re.match(r"homeland_.*terrain", n):
        k = "island_tr_grass01a_night" if night and has("island_tr_grass01a_night") else "island_tr_grass01a"
        if has(k): return dict(_I[k], approx=True)
    n = re.sub(r"(_low|_lod\d|_mat|_material|_frenel\d*(_\d+)?)+$", "", n)
    base = re.sub(r"(_glass|_alpha|_add|_trans|_ems|_light)$", "", n).replace("structue", "structure")  # coquille dans le jeu
    cands = [n, base] + [re.sub(r"[a-z]$", "", base) + x for x in "abcdef"]
    for c in cands:
        if c in _I and "diffuse" in _I[c]: return dict(_I[c], approx=False)
    for c in cands:
        if "_" not in c: continue
        tail = c.split("_", 1)[1]
        if len(tail) < 8: continue
        ks = sorted(_TAIL.get(tail, []), key=lambda k: (not k.startswith("sealcastle"), k))
        if ks: return dict(_I[ks[0]], approx=True)
    # 4) même famille d'objet (ExHall_BU_Well01a -> ExHall_BU_Well02a) puis nom très proche (Structue -> Structure)
    stem = re.sub(r"\d+[a-z]?\d*$", "", base)
    if len(stem) >= 8:
        fam = sorted(k for k in _I if "diffuse" in _I[k] and re.sub(r"\d+[a-z]?\d*$", "", k) == stem)
        if fam: return dict(_I[fam[0]], approx=True)
    import difflib
    close = difflib.get_close_matches(base, [k for k in _I if "diffuse" in _I[k]], 1, 0.9)
    if close: return dict(_I[close[0]], approx=True)
    return {}

if __name__ == "__main__":
    i = build(); print(len(i), "noms de textures indexés")
