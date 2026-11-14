@echo off
setlocal
title Wold Virtual 3D - PCK + servidores
set "GODOT=%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.8.2\Servidor3D\Godot_v4.7.2-stable_win64.exe"
set "PY=E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\LC_STM\python\python.exe"
set "PYW=E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\LC_STM\python\pythonw.exe"
set "SRV=E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\STM_BKCH\servidor_oficial.py"
set "LUCIA=E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
set "PCK=%~dp0wvp3d.pck"

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
