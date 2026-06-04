@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -File "%SCRIPT_DIR%Prepare-LocalVisor.ps1" -Run
endlocal
