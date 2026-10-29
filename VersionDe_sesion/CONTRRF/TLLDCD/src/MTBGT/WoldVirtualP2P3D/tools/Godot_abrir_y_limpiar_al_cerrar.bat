@echo off
rem Abre el editor de Godot y, al cerrarlo, limpia la cache automaticamente.
setlocal
set "PROJ=F:\WoldVirtualP2P3D"
set "GODOT=C:\Users\User\Desktop\Godot_v4.7.2-stable_win64_console.exe"
"%GODOT%" --path "%PROJ%" -e
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0limpiar_cache_godot.ps1" "%PROJ%"
