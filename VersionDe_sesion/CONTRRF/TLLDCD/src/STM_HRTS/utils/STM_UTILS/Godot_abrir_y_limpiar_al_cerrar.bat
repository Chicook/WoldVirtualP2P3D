@echo off
rem Abre el editor de Godot del proyecto de este arbol y limpia la cache al cerrar.
rem Godot se toma de GODOT_BIN, del PATH o del escritorio, en ese orden.
setlocal
for %%I in ("%~dp0..\..\MTBGT\WoldVirtualP2P3D") do set "PROJ=%%~fI"
set "GODOT=%GODOT_BIN%"
if not defined GODOT set "GODOT=C:\Users\User\Desktop\Godot_v4.7.2-stable_win64_console.exe"
if not exist "%GODOT%" for %%G in (Godot_v4.7.2-stable_win64_console.exe) do set "GODOT=%%~$PATH:G"
if not exist "%GODOT%" (
  echo No se encontro Godot. Define GODOT_BIN con la ruta del ejecutable.
  exit /b 1
)
if not exist "%PROJ%\project.godot" (
  echo No se encontro el proyecto Godot en "%PROJ%".
  exit /b 1
)
"%GODOT%" --path "%PROJ%" -e
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0limpiar_cache_godot.ps1" "%PROJ%"
