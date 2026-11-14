@echo off
setlocal
title Wold Virtual 3D - PCK exportado
set "GODOT=%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.8.2\Servidor3D\Godot_v4.7.2-stable_win64.exe"
set "PCK=%~dp0wvp3d.pck"

if not exist "%GODOT%" (
  echo No se encuentra el motor Godot: %GODOT%
  pause
  exit /b 1
)
if not exist "%PCK%" (
  echo No se encuentra el PCK: %PCK%
  pause
  exit /b 1
)

echo Lanzando el mundo exportado (wvp3d.pck)...
start "" "%GODOT%" --main-pack "%PCK%" %*
exit /b 0
