@echo off
chcp 65001 >nul
title Blood and Silver - Installation des ressources
rem Télécharge les ressources du site (images, animations, modèles 3D, sons, vidéos) depuis la Release GitHub.
cd /d "%~dp0"

where python >/dev/null 2>nul
if not errorlevel 1 goto avec_python
where py >/dev/null 2>nul
if not errorlevel 1 goto avec_py
echo Python est introuvable. Installez-le depuis https://www.python.org/downloads/ puis relancez ce fichier.
goto fin

:avec_python
python "tools\install_resources.py"
goto fin

:avec_py
py -3 "tools\install_resources.py"
goto fin

:fin
echo.
pause
