@echo off
setlocal
title Wold Virtual 3D - Desarrollo
set "GODOT=%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.8.5\Servidor3D\Godot_v4.7.2-stable_win64.exe"
if not exist "%GODOT%" set "GODOT=%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.8.4\Servidor3D\Godot_v4.7.2-stable_win64.exe"
if not exist "%GODOT%" set "GODOT=%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.8.3\Servidor3D\Godot_v4.7.2-stable_win64.exe"
REM Arbol activo del proyecto Godot (..\..\..\.. desde esta carpeta = TLLDCD\src)
set "PROY=%~dp0..\..\..\..\MTBGT\WoldVirtualP2P3D"

if not exist "%GODOT%" (
  echo No se encuentra el motor Godot en:
  echo   %GODOT%
  echo Extrae primero el runtime con el visor o ajusta la ruta.
  pause
  exit /b 1
)
if not exist "%PROY%\project.godot" (
  echo No se encuentra el proyecto Godot en:
  echo   %PROY%
  pause
  exit /b 1
)

echo Lanzando Wold Virtual 3D (proyecto de desarrollo)...
start "" "%GODOT%" --path "%PROY%" %*
exit /b 0
