@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Preparar_Previa_IslaModular.ps1"
if errorlevel 1 pause
endlocal
