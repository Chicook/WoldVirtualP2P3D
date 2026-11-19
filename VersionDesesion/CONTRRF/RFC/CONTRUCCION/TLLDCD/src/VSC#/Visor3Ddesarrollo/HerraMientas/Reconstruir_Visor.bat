@echo off
setlocal
title Reconstruir Visor 3D (.dev)
set "GESTOR=%~dp0..\..\..\..\..\.dev\gestor_entorno.py"
set "PY=%~dp0..\..\..\..\..\.dev\.python\python.exe"
if not exist "%PY%" set "PY=%~dp0..\..\..\..\..\.dev\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [*] Reconstruyendo Visor3D a traves del gestor de entorno .dev...
"%PY%" "%GESTOR%" reconstruir-visor %*
pause
