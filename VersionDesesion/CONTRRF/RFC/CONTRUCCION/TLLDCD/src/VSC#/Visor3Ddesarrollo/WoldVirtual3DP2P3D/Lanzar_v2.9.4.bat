@echo off
title Wold Virtual 3D v2.9.4
cd /d "%~dp0"
set "DOTNET_ROLL_FORWARD=Major"
set "DOTNET_CLI_TELEMETRY_OPTOUT=1"
set "DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1"

echo =======================================================================
echo   Iniciando DAOLCDMWoldVirtualP2P3Dv2.9.4.exe
echo   - Escena central 3D: res://WoldVirtual3DP2P.tscn
echo   - Tunel efimero publico automatico con URL visible en barra superior
echo   - Servidor modular DAO IPC ultra-rapido (100 ms) activo
echo =======================================================================
start "" "%~dp0DAOLCDMWoldVirtualP2P3Dv2.9.4.exe" %*
