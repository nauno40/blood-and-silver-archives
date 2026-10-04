# Blood and Silver — Archives

Archive non officielle et hors ligne du jeu mobile **Blood and Silver** (Moonton, `com.moonton.silverblood.eu`) :
outils d'extraction des données du jeu installées sur un téléphone Android et site web local pour tout consulter.

> ⚠️ Ce dépôt ne contient **aucun média du jeu** (images, modèles 3D, animations, sons, vidéos) : ils restent la propriété
> de leurs ayants droit et se régénèrent localement à partir d'une installation du jeu avec les scripts de `tools/`.
> Seuls le code du site, les outils et les fichiers de données générés (`Site/data/`) sont versionnés.

## Le site

Application web statique (HTML / JS / CSS, sans framework), servie par un petit serveur Python local.

| Rubrique | Contenu |
|---|---|
| Personnages | les 75 héros (table `CharacterInfo`) et leurs tenues : image fixe, animations Spine précalculées, illustrations, portraits |
| Spine interactif | lecteur Spine 4.1 : liste, recherche, zoom / déplacement, vitesse, image par image, fonds, capture PNG, raccourcis clavier |
| Portraits | expressions et illustrations regroupées par héros |
| Écran principal / Fonds | fonds de l'écran d'accueil recomposés (prefabs UGUI) et illustrations |
| Textures | toutes les images du jeu par dossier, aperçu « boule / cube / ciel 360° » |
| Modèles 3D | personnages, monstres, PNJ, cartes, décors, objets, cinématiques (glTF + FBX), squelettes et animations, rendu toon avec contour |
| Shaders | 29 shaders (définition lisible + GLSL ES 3) avec **aperçu en direct exécutant le vrai code GPU du jeu** en WebGL2 |
| Pixel art | personnages et monstres du mode AFK recomposés et animés, cartes de sol |
| Polices, Vidéos, Audio, Données | polices du jeu, cinématiques sous-titrées, ~24 000 sons Wwise, textes et tables de configuration |

Lancement : double-cliquer sur **`Ouvrir le site.bat`** (Python requis), qui démarre `Site/serveur.py`
(port 8777 par défaut, prise exclusive, port suivant si occupé, prise en charge des requêtes Range) et ouvre le navigateur.
Sans les médias régénérés, le site s'ouvre mais les images / modèles / sons sont absents.

## Les outils (`tools/`)

Scripts Python (UnityPy, trimesh, Pillow, numpy) et Node (rendu Spine avec `@esotericsoftware/spine-core` + `@napi-rs/canvas`),
FFmpeg, vgmstream (audio Wwise) et Blender (conversion FBX). Principales étapes :

| Étape | Scripts |
|---|---|
| Recensement des bundles Unity | `census.py`, `cab_index.py`, `sprite_index.py` |
| Images | `extract_png.py`, `extract_png_missing.py`, `extract_cubemaps.py`, `make_webp.py`, `make_thumbs.py` |
| Spine | `dump_spine.py`, `render/render.mjs` (+ `layers.mjs`), `render_all.py`, `make_webm.py` |
| Fonds de l'écran principal | `compose_mainbg.py` |
| Modèles 3D | `export_3d.py` (GLB statiques, textures retrouvées par nom avec `tex_by_name.py`), `export_rigged.py` (squelettes + animations), `run_fbx.py`, `run_fbx_anim.py` (Blender) |
| Shaders | `extract_shaders.py`, `shader_by_material.py`, `export_shader_materials.py`, `export_shader_examples.py` |
| Pixel art (AFK) | `render_afk.py` |
| Audio / vidéo | `convert_audio.py`, `make_mp3.py`, `remux_videos.py`, `mux_video_audio.py`, `make_video_webm.py` |
| Données du site | `build_site.py` (génère `Site/data/*.js`) |
| Vérification | `verify_site.py` (chaque fichier référencé existe + cohérence entre rubriques) |

Les chemins sont ceux de la machine d'origine (`E:\Projets\BloodAndSilver\…`, outils dans `C:\Users\…\.bns_tools`) :
à adapter en tête de chaque script.

### Points techniques notables

- bundles Unity précédés d'un en-tête propriétaire (on lit à partir de `UnityFS`) ; références entre bundles résolues par un index des CAB ;
- runtime Spine JS 4.1 : correctif des régions `rotate:270` ; animations Lounge recomposées en couches ;
- clips d'animation Unity décodés (courbes streamées / denses / constantes), Euler en ordre **XYZ**, conversion main gauche → glTF ;
- squelettes « optimisés » reconstruits depuis l'Avatar (`m_AvatarSkeleton`, `m_BoneNameHashes`) ;
- shaders : blob LZ4 décompressé à la main (le convertisseur UnityPy ne gère pas cette version), GLSL ES 3 vérifié en WebGL2 ;
- textures de décors absentes du téléphone retrouvées par nom de matériau (copies `3DUI_`, zones jumelles, variantes nuit…).

## Avertissement

Projet de fan, sans lien avec Moonton. Blood and Silver et tous ses contenus appartiennent à leurs propriétaires respectifs.
