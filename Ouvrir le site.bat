@echo off
chcp 65001 >nul
title Blood and Silver - Archives
rem Lance le serveur local du site puis ouvre le navigateur. Fermez cette fenetre pour arreter le site.
cd /d "%~dp0"

where python >nul 2>nul
if not errorlevel 1 goto avec_python
where py >nul 2>nul
if not errorlevel 1 goto avec_py
echo Python est introuvable. Installez-le depuis https://www.python.org/downloads/ puis relancez ce fichier.
goto fin

:avec_python
python "Site\serveur.py" 8777
goto fin

:avec_py
py -3 "Site\serveur.py" 8777
goto fin

:fin
echo.
echo Le serveur s'est arrete. Si une erreur est affichee ci-dessus, elle explique pourquoi.
pause
