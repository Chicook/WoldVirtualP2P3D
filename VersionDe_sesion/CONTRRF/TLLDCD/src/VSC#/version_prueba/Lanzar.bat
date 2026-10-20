@echo off
title Wold Virtual P2P 3D — v0.2.0
echo.
echo  +------------------------------------------+
echo  ¦   WOLD VIRTUAL P2P 3D — Version 0.2.0   ¦
echo  ¦   Sin usuarios de prueba                 ¦
echo  +------------------------------------------+
echo.

REM Compilar en modo Release si no existe el exe
if not exist "bin\Release\net8.0-windows\win-x64\Visor3D.exe" (
    echo Compilando el visor...
    dotnet build -c Release -r win-x64
    echo.
)

REM Lanzar el visor
echo Iniciando Wold Virtual P2P 3D...
dotnet run --project Visor3D.csproj -c Release
pause
