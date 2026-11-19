@echo off
title Wold Virtual 3D v2.9.3
cd /d "%~dp0"
set "DOTNET_ROLL_FORWARD=Major"
set "DOTNET_CLI_TELEMETRY_OPTOUT=1"
set "DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1"

echo =======================================================================
echo   Iniciando DAOLCDMWoldVirtualP2P3Dv2.9.3.exe
echo   El tunel efimero se levantara automaticamente y la URL aparecera arriba.
echo =======================================================================
start "" "%~dp0DAOLCDMWoldVirtualP2P3Dv2.9.3.exe" %*
