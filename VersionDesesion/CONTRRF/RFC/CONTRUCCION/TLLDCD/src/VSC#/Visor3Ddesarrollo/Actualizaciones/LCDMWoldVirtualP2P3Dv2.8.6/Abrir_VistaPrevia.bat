@echo off
setlocal
title Wold Virtual 3D - Vista previa del visor
REM Arbol activo (..\..\.. desde HerraMientas = TLLDCD\src) y archivo de
REM versiones anteriores, donde vive el Python embebido que no se versiona.
set "SRC=%~dp0..\..\..\.."
if not defined WVP_LEGACY_SRC set "WVP_LEGACY_SRC=%~dp0..\..\..\..\..\..\..\..\..\..\..\..\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"
if not exist "%WVP_LEGACY_SRC%" set "WVP_LEGACY_SRC=%~dp0..\..\..\..\..\..\..\..\..\..\..\..\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"
set "EXE=%~dp0bin\Release\net8.0-windows\win-x64\publish\LCDMWoldVirtualP2P3Dv2.8.6.exe"
if not exist "%EXE%" set "EXE=%~dp0bin\Debug\net8.0-windows\win-x64\LCDMWoldVirtualP2P3Dv2.8.6.exe"
set "PYW=%SRC%\LC_STM\python\pythonw.exe"
if not exist "%PYW%" set "PYW=%WVP_LEGACY_SRC%\LC_STM\python\pythonw.exe"
set "SRV=%SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
if not exist "%SRV%" set "SRV=%WVP_LEGACY_SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"

if not exist "%EXE%" (
  echo No se encuentra la vista previa compilada:
  echo %EXE%
  echo Compila antes con Lanzar.bat o "dotnet build Visor3D.csproj".
  pause
  exit /b 1
)

echo Cerrando servidores de LucIA anteriores...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*servidor_lucia.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
timeout /t 1 /nobreak >nul

echo Arrancando LucIA en 127.0.0.1:8765...
start "LucIA 8765" /min "%PYW%" "%SRV%" --modelo qwen2.5:7b --puerto 8765 --sin-precarga-voz

for /L %%i in (1,1,40) do (
  netstat -ano | findstr ":8765" | findstr "LISTENING" >nul
  if not errorlevel 1 goto listo
  timeout /t 1 /nobreak >nul
)

echo.
echo ERROR: LucIA no abrio el puerto 8765. No se abre el visor.
echo Revisa %%LOCALAPPDATA%%\WoldVirtualP2P3D\logs y ejecuta Reiniciar_Lucia.bat.
pause
exit /b 1

:listo
echo LucIA escuchando. Abriendo el visor preliminar...
start "" "%EXE%"
exit /b 0
