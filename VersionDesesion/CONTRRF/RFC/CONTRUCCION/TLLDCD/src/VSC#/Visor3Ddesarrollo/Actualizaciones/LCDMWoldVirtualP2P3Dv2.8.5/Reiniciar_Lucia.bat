@echo off
setlocal
title Wold Virtual 3D - Reiniciar LucIA (8765)
REM Arbol activo (..\..\..\.. desde esta carpeta = TLLDCD\src) y archivo de
REM versiones anteriores, donde vive el Python embebido que no se versiona.
set "SRC=%~dp0..\..\..\.."
if not defined WVP_LEGACY_SRC set "WVP_LEGACY_SRC=%~dp0..\..\..\..\..\..\..\..\..\..\..\..\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"
if not exist "%WVP_LEGACY_SRC%" set "WVP_LEGACY_SRC=%~dp0..\..\..\..\..\..\..\..\..\..\..\..\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"
set "DEV_DIR=%~dp0..\..\..\..\..\..\..\..\.dev"
set "PYW="
if exist "%DEV_DIR%\.python\pythonw.exe" set "PYW=%DEV_DIR%\.python\pythonw.exe"
if not defined PYW if exist "%DEV_DIR%\venv\Scripts\pythonw.exe" set "PYW=%DEV_DIR%\venv\Scripts\pythonw.exe"
if not defined PYW set "PYW=%SRC%\LC_STM\python\pythonw.exe"
if not exist "%PYW%" set "PYW=%WVP_LEGACY_SRC%\LC_STM\python\pythonw.exe"
if not exist "%PYW%" set "PYW=E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\.python\pythonw.exe"
set "SRV=%SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
if not exist "%SRV%" set "SRV=%WVP_LEGACY_SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"

echo Cerrando servidores de LucIA anteriores...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*servidor_lucia.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo Arrancando LucIA en 127.0.0.1:8765...
start "LucIA 8765" /min "%PYW%" "%SRV%" --modelo qwen2.5:7b --puerto 8765
timeout /t 4 /nobreak >nul

netstat -ano | findstr :8765
if errorlevel 1 (
  echo.
  echo NO se pudo abrir el 8765. Lanzando en modo visible para ver el error...
  "%PYW:\pythonw.exe=\python.exe%" "%SRV%" --modelo qwen2.5:7b --puerto 8765
) else (
  echo.
  echo LucIA escuchando en 8765.
)
pause
