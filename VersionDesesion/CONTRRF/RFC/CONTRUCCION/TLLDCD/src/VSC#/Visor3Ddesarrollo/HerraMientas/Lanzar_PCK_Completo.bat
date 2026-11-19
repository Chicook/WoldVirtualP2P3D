@echo off
setlocal
title Wold Virtual 3D - PCK + servidores
set "GODOT=%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.8.4\Servidor3D\Godot_v4.7.2-stable_win64.exe"
if not exist "%GODOT%" set "GODOT=%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.8.3\Servidor3D\Godot_v4.7.2-stable_win64.exe"
REM Arbol activo (..\..\.. desde HerraMientas = TLLDCD\src) y archivo de
REM versiones anteriores, donde vive el Python embebido que no se versiona.
set "SRC=%~dp0..\..\.."
if not defined WVP_LEGACY_SRC set "WVP_LEGACY_SRC=%~dp0..\..\..\..\..\..\..\..\..\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"
if not exist "%WVP_LEGACY_SRC%" set "WVP_LEGACY_SRC=%~dp0..\..\..\..\..\..\..\..\..\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"
set "DEV_DIR=%~dp0..\..\..\..\..\.dev"
set "PYTHONPYCACHEPREFIX=%DEV_DIR%\pycache"
set "PY="
if exist "%DEV_DIR%\.python\python.exe" set "PY=%DEV_DIR%\.python\python.exe"
if not defined PY if exist "%DEV_DIR%\venv\Scripts\python.exe" set "PY=%DEV_DIR%\venv\Scripts\python.exe"
if not defined PY set "PY=%SRC%\LC_STM\python\python.exe"
if not exist "%PY%" set "PY=%WVP_LEGACY_SRC%\LC_STM\python\python.exe"
if not exist "%PY%" set "PY=E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\.python\python.exe"

set "PYW="
if exist "%DEV_DIR%\.python\pythonw.exe" set "PYW=%DEV_DIR%\.python\pythonw.exe"
if not defined PYW if exist "%DEV_DIR%\venv\Scripts\pythonw.exe" set "PYW=%DEV_DIR%\venv\Scripts\pythonw.exe"
if not defined PYW set "PYW=%SRC%\LC_STM\python\pythonw.exe"
if not exist "%PYW%" set "PYW=%WVP_LEGACY_SRC%\LC_STM\python\pythonw.exe"
if not exist "%PYW%" set "PYW=E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\.python\pythonw.exe"
REM Rutas.json fija el servidor oficial en STM_BKCH\stm_bkch1
set "SRV=%SRC%\STM_BKCH\stm_bkch1\servidor_oficial.py"
if not exist "%SRV%" set "SRV=%SRC%\STM_BKCH\servidor_oficial.py"
if not exist "%SRV%" set "SRV=%WVP_LEGACY_SRC%\STM_BKCH\servidor_oficial.py"
set "LUCIA=%SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
if not exist "%LUCIA%" set "LUCIA=%WVP_LEGACY_SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
set "PCK=%~dp0..\CopiaDeSeguridad\wvp3d.pck"
if not exist "%PCK%" set "PCK=%~dp0wvp3d.pck"

if not exist "%GODOT%" (
  echo No se encuentra el motor Godot: %GODOT%
  pause
  exit /b 1
)
if not exist "%PY%" (
  echo No se encuentra el Python del servidor: %PY%
  pause
  exit /b 1
)
if not exist "%SRV%" (
  echo No se encuentra el servidor oficial: %SRV%
  pause
  exit /b 1
)
if not exist "%LUCIA%" (
  echo No se encuentra el servidor de LucIA: %LUCIA%
  pause
  exit /b 1
)
if not exist "%PCK%" (
  echo No se encuentra el PCK: %PCK%
  pause
  exit /b 1
)

echo Arrancando servidor oficial en el puerto 8545...
start "WoldVirtual - Servidor 8545" /min "%PY%" "%SRV%" --puerto 8545 --sin-cuota-ubicacion
timeout /t 2 /nobreak >nul

echo Arrancando cerebro de LucIA en el puerto 8765...
start "WoldVirtual - LucIA 8765" /min "%PYW%" "%LUCIA%" --modelo qwen2.5:7b --puerto 8765
timeout /t 3 /nobreak >nul

echo Lanzando el mundo exportado (wvp3d.pck)...
start "" "%GODOT%" --main-pack "%PCK%" %*
exit /b 0
