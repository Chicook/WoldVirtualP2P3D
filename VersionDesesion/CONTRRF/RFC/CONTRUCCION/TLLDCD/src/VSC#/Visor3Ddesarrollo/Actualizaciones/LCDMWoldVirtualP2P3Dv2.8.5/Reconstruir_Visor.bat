@echo off
setlocal
title Reconstruir Visor 3D v2.8.5 (carpeta autonoma)
REM Compila esta carpeta tal cual: no depende del arbol de desarrollo ni del gestor .dev.
set "DOTNET="
for %%I in (dotnet.exe) do if not defined DOTNET set "DOTNET=%%~$PATH:I"
if not defined DOTNET if exist "%LOCALAPPDATA%\Microsoft\dotnet\dotnet.exe" set "DOTNET=%LOCALAPPDATA%\Microsoft\dotnet\dotnet.exe"
if not defined DOTNET if exist "%ProgramFiles%\dotnet\dotnet.exe" set "DOTNET=%ProgramFiles%\dotnet\dotnet.exe"
if not defined DOTNET if exist "E:\Program Files\dotnet\dotnet.exe" set "DOTNET=E:\Program Files\dotnet\dotnet.exe"

if not defined DOTNET (
  echo No se encuentra dotnet. Instala el SDK .NET 8 o anade dotnet al PATH.
  pause
  exit /b 1
)

cd /d "%~dp0"
echo [*] Publicando Visor3D v2.8.5 (single-file, win-x64)...
"%DOTNET%" publish Visor3D.csproj -c Release -r win-x64 --self-contained true /p:PublishSingleFile=true %*
if %ERRORLEVEL% neq 0 (
    echo [!] Fallo la compilacion. Presione una tecla para salir...
    pause >nul
)
