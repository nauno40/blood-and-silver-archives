# Blood and Silver — Archives

Archive non officielle et hors ligne du jeu mobile **Blood and Silver** (Moonton, `com.moonton.silverblood.eu`) :
outils d'extraction des données du jeu installées sur un téléphone Android et site web local pour tout consulter.

## Installation

1. Télécharger le dépôt (bouton **Code → Download ZIP**, ou `git clone`) et le décompresser.
2. Installer [Python 3](https://www.python.org/downloads/) si ce n'est pas déjà fait.
3. Double-cliquer sur **`Installer les ressources.bat`** : il télécharge depuis la Release
   [`ressources-v1`](../../releases/tag/ressources-v1) les archives de ressources (~24 Go : images, animations, modèles 3D
   GLB + FBX, sons, vidéos…), les vérifie et les décompresse au bon endroit. Prévoir ~50 Go libres pendant l'installation ;
   en cas de coupure, relancer : l'installation reprend où elle s'était arrêtée.
   (Équivalent manuel : télécharger les `bns-ressources-NN.zip` de la Release et les décompresser à la racine du projet.)
4. Double-cliquer sur **`Ouvrir le site.bat`**.

Le code du site, les outils et les données générées (`Site/data/`) sont dans Git ; les médias sont dans la Release.

## Organisation

```
Ouvrir le site.bat             lance le site
Installer les ressources.bat   télécharge les médias depuis la Release
Site/                          le site complet, autonome
  index.html  app.js  style.css  viewer3d.js  shader_preview.js  serveur.py  lib/
  data/                        données générées (dans Git)
  img/  thumbs/                images WebP et miniatures                 ┐
  anim/  spine/                animations Spine (WebM) et squelettes     │
  models/  models_fbx/         modèles 3D statiques (GLB / FBX)          │ médias :
  models_anim/  models_anim_fbx/   modèles riggés et animations          │ Release,
  pixel/                       pixel art du mode AFK                     │ pas Git
  shaders/  shader_preview/    shaders et leurs aperçus                  │
  polices/  audio/  audio_mp3/  videos/  videos_webm/  posters/  subs/   ┘
tools/                         scripts d'extraction et de génération
```

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

`Ouvrir le site.bat` démarre `Site/serveur.py` (port 8777 par défaut, port suivant si occupé, requêtes Range pour les
vidéos et sons) et ouvre le navigateur. Le site doit être servi par ce serveur (pas ouvert en `file://`).

## Les outils (`tools/`) — régénérer les ressources

Inutile pour simplement consulter le site (les ressources sont dans la Release). Pour tout refaire à partir du jeu :

**Prérequis** : Python 3.12 (`pip install -r tools/requirements.txt` : UnityPy, numpy, Pillow, trimesh, lz4, imageio-ffmpeg —
ce dernier fournit FFmpeg), Node.js (`npm install` dans `tools/render/`), [vgmstream](https://vgmstream.org) (audio Wwise, dans
`tools/vgmstream/`) et Blender 5.x (FBX). Les chemins sont calculés depuis l'emplacement du dépôt (`tools/config.py`) ;
variables `BNS_PROJECT`, `BNS_FFMPEG`, `BNS_BLENDER`, `BNS_VGMSTREAM` pour les adapter.

**Données du jeu** : copier le dossier `Android/data/com.moonton.silverblood.eu/` du téléphone dans `data/` à la racine du dépôt.

**Ordre d'exécution** (`python tools/<script>.py`) :

| # | Étape | Scripts |
|---|---|---|
| 1 | Recensement des bundles Unity | `census.py`, `cab_index.py`, `sprite_index.py` |
| 2 | Images | `extract_png.py`, `extract_png_missing.py`, `extract_cubemaps.py` |
| 3 | Fonds d'écran | `find_bg.py`, `copy_bg.py`, `compose_mainbg.py` (écran principal recomposé) |
| 4 | Spine 2D | `dump_spine.py`, `render_all.py` (Node : `render/render.mjs`, `layers.mjs`), `make_webm.py` |
| 5 | Modèles 3D | `list_extra_models.py`, `export_3d.py` puis `export_3d.py @tools/extra_files.txt`, `export_rigged.py`, `run_fbx.py`, `run_fbx_anim.py` (Blender : `glb2fbx*.py`, `check_fbx.py`) — textures retrouvées par nom avec `tex_by_name.py` |
| 6 | Shaders | `extract_shaders.py`, `shader_by_material.py`, `export_shader_materials.py`, `export_shader_examples.py` |
| 7 | Pixel art (AFK) | `render_afk.py` |
| 8 | Audio / vidéo | `convert_audio.py`, `make_mp3.py`, `remux_videos.py`, `mux_video_audio.py`, `make_video_webm.py` |
| 9 | Images pour le site | `make_webp.py`, `make_thumbs.py` |
| 10 | Données du site | `build_site.py` (génère `Site/data/*.js`) |
| 11 | Vérification | `verify_site.py` (chaque fichier référencé existe + cohérence entre rubriques), `decode_check.py` (décodage des médias) |
| 12 | Distribution | `pack_release.py` (archives ≤ 1,9 Go pour la Release) ; `install_resources.py` côté utilisateur |

Les vignettes des modèles 3D ont été rendues dans le navigateur avec le visualiseur du site (`Site/viewer3d.js`).
`build_site.py` génère par défaut les données « release » (sans liens vers les originaux PNG / animations WebP, non distribués) ;
`BNS_FULL=1` pour un site local qui les référence.

### Points techniques notables

- bundles Unity précédés d'un en-tête propriétaire (on lit à partir de `UnityFS`) ; références entre bundles résolues par un index des CAB ;
- runtime Spine JS 4.1 : correctif des régions `rotate:270` ; animations Lounge recomposées en couches ;
- clips d'animation Unity décodés (courbes streamées / denses / constantes), Euler en ordre **XYZ**, conversion main gauche → glTF ;
- squelettes « optimisés » reconstruits depuis l'Avatar (`m_AvatarSkeleton`, `m_BoneNameHashes`) ;
- shaders : blob LZ4 décompressé à la main (le convertisseur UnityPy ne gère pas cette version), GLSL ES 3 vérifié en WebGL2 ;
- textures de décors absentes du téléphone retrouvées par nom de matériau (copies `3DUI_`, zones jumelles, variantes nuit…).

## Avertissement

Projet de fan, sans lien avec Moonton. Blood and Silver et tous ses contenus appartiennent à leurs propriétaires respectifs.
