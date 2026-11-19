@echo off
setlocal enabledelayedexpansion
title Wold Virtual 3D - Vista Previa DAO y Tuneles Efimeros (v2.9.3)

set "DOTNET_ROLL_FORWARD=Major"
set "DOTNET_CLI_TELEMETRY_OPTOUT=1"
set "DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1"

set "BASE_DIR=%~dp0"
set "CONSTRUCCION=%BASE_DIR%..\..\..\..\.."
set "DEV=%CONSTRUCCION%\.dev"
set "CS=%DEV%\CS"

set "GODOT=%CS%\runtime\Godot\Godot_v4.7.2-stable_win64.exe"
if not exist "%GODOT%" set "GODOT=%DEV%\rebuild287\runtime\Servidor3D\Godot_v4.7.2-stable_win64.exe"

set "SERVER_EXE=%BASE_DIR%Servidor\bin\Debug\net8.0\WoldVirtualP2P3D.Servidor.exe"
if not exist "%SERVER_EXE%" set "SERVER_EXE=%CS%\Publicacion\Servidor\WoldVirtualP2P3D.Servidor.exe"

set "CLOUDFLARED=%CS%\runtime\cloudflared\cloudflared.exe"
set "VISOR_DIR=%BASE_DIR%Visor"

echo =======================================================================
echo   WOLD VIRTUAL 3D - VISTA PREVIA DAO (SEDE Y TUNELES EFIMEROS)
echo =======================================================================
echo.
echo Directorio: %BASE_DIR%
echo Godot:      %GODOT%
echo Servidor:   %SERVER_EXE%
echo.

if not exist "%GODOT%" (
    echo [ERROR] No se encontro Godot 4.7.2 en:
    echo %GODOT%
    pause
    exit /b 1
)

if not exist "%SERVER_EXE%" (
    echo [*] Compilando Servidor Modular...
    set "DOTNET_CLI_TELEMETRY_OPTOUT=1"
    set "DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1"
    set "DOTNET_CLI_HOME=%CS%\.dotnet"
    pushd "%BASE_DIR%Servidor"
    dotnet build WoldVirtual.Servidor.csproj --no-restore
    popd
)

set "WVP_IPC_DIR=%CS%\runtime\ipc"
set "WVP_DATA_DIR=%CS%\runtime\datos"
set "WVP_SERVER_EXE=%SERVER_EXE%"
set "WVP_LAUNCH_SERVER=1"
set "WVP_PORT=8765"
set "CLOUDFLARED_EXE=%CLOUDFLARED%"
set "WVP_TUNNEL_PROVIDER=ssh"

if not exist "%WVP_IPC_DIR%" mkdir "%WVP_IPC_DIR%"
if not exist "%WVP_DATA_DIR%" mkdir "%WVP_DATA_DIR%"

echo 1. Comprobando servidor modular en puerto 8765...
netstat -ano | findstr ":8765" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo    Arrancando servidor modular en segundo plano...
    start "Servidor_Modular_8765" /min "%SERVER_EXE%" --urls http://0.0.0.0:8765
    echo    Esperando a que el servidor levante...
    timeout /t 5 /nobreak >nul
) else (
    echo    Servidor ya activo en puerto 8765.
)

echo 2. Lanzando visor Godot (DAO)...
start "" "%GODOT%" --path "%VISOR_DIR%" "res://escenas/DAO.tscn"

echo.
echo =======================================================================
echo   Vista Previa iniciada correctamente.
echo   En la pantalla veras el boton "CONECTAR A LA DAO"
echo   y el estado del tunel efimero de Lucia en la parte superior.
echo =======================================================================
