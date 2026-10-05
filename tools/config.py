"""Chemins du projet et des programmes externes, communs à tous les scripts de tools/.

Par défaut tout est calculé depuis l'emplacement du dépôt :
  PROJECT   = racine du dépôt (dossier parent de tools/) ; les données du téléphone vont dans PROJECT\\data\\
  TOOLS_DIR = ce dossier tools/ (scripts + caches générés : census.json, cab_index.json…)
Variables d'environnement pour adapter : BNS_PROJECT, BNS_FFMPEG, BNS_VGMSTREAM."""
import os

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.environ.get("BNS_PROJECT") or os.path.dirname(TOOLS_DIR)
# dossier des fichiers du jeu copiés depuis le téléphone (Android/data/com.moonton.silverblood.eu/files/dragon2019/assets)
ASSETS = os.path.join(PROJECT, "data", "com.moonton.silverblood.eu", "files", "dragon2019", "assets")


def _ffmpeg():
    if os.environ.get("BNS_FFMPEG"):
        return os.environ["BNS_FFMPEG"]
    try:  # FFmpeg fourni par le paquet pip imageio-ffmpeg (libwebp, libvpx-vp9, libopus, libmp3lame inclus)
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


FFMPEG = _ffmpeg()
VGMSTREAM = os.environ.get("BNS_VGMSTREAM") or os.path.join(TOOLS_DIR, "vgmstream", "vgmstream-cli.exe")
