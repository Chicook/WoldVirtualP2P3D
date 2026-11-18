@echo off
title SERVIDOR NEURONAL BLOK1 - GODOT
cd /d "%~dp0..\LC_STM\RedNeuronal\CELEBRO\BLOK1"
if not exist "ejecutar_servidor.py" cd /d "E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\Refactorizacion\src\LC_STM\RedNeuronal\CELEBRO\BLOK1"
set "PY=E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\.python\python.exe"
if not exist "%PY%" set "PY=E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\venv\Scripts\python.exe"
set "PYTHONPYCACHEPREFIX=E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\pycache"
"%PY%" "ejecutar_servidor.py"
pause
