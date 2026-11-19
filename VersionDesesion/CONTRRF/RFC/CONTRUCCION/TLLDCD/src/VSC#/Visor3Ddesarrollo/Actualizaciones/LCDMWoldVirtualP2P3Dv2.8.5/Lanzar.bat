@echo off
REM =========================================================================
REM  Lanzar.bat - Compila y ejecuta Visor3D (WPF .NET 8)
REM =========================================================================
cd /d "%~dp0"
set "DOTNET_CLI_TELEMETRY_OPTOUT=1"
set "DOTNET="
for %%I in (dotnet.exe) do if not defined DOTNET set "DOTNET=%%~$PATH:I"
if not defined DOTNET if exist "%LOCALAPPDATA%\Microsoft\dotnet\dotnet.exe" set "DOTNET=%LOCALAPPDATA%\Microsoft\dotnet\dotnet.exe"
if not defined DOTNET if exist "%ProgramFiles%\dotnet\dotnet.exe" set "DOTNET=%ProgramFiles%\dotnet\dotnet.exe"
if not defined DOTNET if exist "E:\Program Files\dotnet\dotnet.exe" set "DOTNET=E:\Program Files\dotnet\dotnet.exe"
if not defined DOTNET (
    echo [!] No se encuentra dotnet. Instale el SDK .NET 8 o anada dotnet al PATH.
    pause >nul
    exit /b 1
)
echo [*] Iniciando Visor3D... (Argumentos: %*)
"%DOTNET%" run --project Visor3D.csproj -c Debug -- %*
if %ERRORLEVEL% neq 0 (
    echo [!] Error al ejecutar Visor3D. Presione una tecla para salir...
    pause >nul
)
