@echo off
setlocal
title Reconstruir Visor 3D (.dev)
cd /d "%~dp0"
set "PY=%~dp0.python\python.exe"
if not exist "%PY%" set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" gestor_entorno.py reconstruir-visor %*
pause
