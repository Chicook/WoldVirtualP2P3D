@echo off
REM =========================================================================
REM  Lanzar.bat - Compila y ejecuta Visor3D (WPF .NET 8)
REM =========================================================================
cd /d "%~dp0"
echo [*] Iniciando Visor3D... (Argumentos: %*)
dotnet run --project Visor3D.csproj -c Debug -- %*
if %ERRORLEVEL% neq 0 (
    echo [!] Error al ejecutar Visor3D. Presione una tecla para salir...
    pause >nul
)
