@echo off
REM =========================================================================
REM  Lanzar.bat - Ejecuta Visor3D (WPF .NET 8)
REM =========================================================================
cd /d "%~dp0"
set "DOTNET_ROLL_FORWARD=Major"
set "DOTNET_CLI_TELEMETRY_OPTOUT=1"
set "DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1"

set "EXE=%~dp0DAOLCDMWoldVirtualP2P3Dv2.9.3.exe"
if not exist "%EXE%" set "EXE=%~dp0..\WoldVirtual3DP2P3D\DAOLCDMWoldVirtualP2P3Dv2.9.3.exe"
if exist "%EXE%" (
    echo [*] Iniciando DAOLCDMWoldVirtualP2P3Dv2.9.3.exe...
    start "" "%EXE%" %*
    exit /b 0
)

echo [*] Compilando y ejecutando Visor3D...
dotnet run --project Visor3D.csproj -c Debug --no-restore -- %*
if %ERRORLEVEL% neq 0 (
    echo [!] Error al ejecutar Visor3D. Presione una tecla para salir...
    pause >nul
)
