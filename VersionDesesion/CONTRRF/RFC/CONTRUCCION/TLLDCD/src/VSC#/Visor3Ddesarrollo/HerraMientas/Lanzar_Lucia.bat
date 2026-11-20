@echo off
setlocal
title Wold Virtual 3D - Servidor LucIA (8765)
REM Arbol activo (..\..\.. desde HerraMientas = TLLDCD\src), .dev modular y archivo de versiones
set "DEV_DIR=%~dp0..\..\..\..\..\.dev"
set "PYTHONPYCACHEPREFIX=%DEV_DIR%\pycache"
set "SRC=%~dp0..\..\.."
if not defined WVP_LEGACY_SRC set "WVP_LEGACY_SRC=%~dp0..\..\..\..\..\..\..\..\..\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"
if not exist "%WVP_LEGACY_SRC%" set "WVP_LEGACY_SRC=%~dp0..\..\..\..\..\..\..\..\..\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"
set "PYW="
if exist "%DEV_DIR%\.python\pythonw.exe" set "PYW=%DEV_DIR%\.python\pythonw.exe"
if not defined PYW if exist "%DEV_DIR%\venv\Scripts\pythonw.exe" set "PYW=%DEV_DIR%\venv\Scripts\pythonw.exe"
if not defined PYW if defined WVP_PYTHON if exist "%WVP_PYTHON%" set "PYW=%WVP_PYTHON%"
if not defined PYW set "PYW=%SRC%\LC_STM\python\pythonw.exe"
if not exist "%PYW%" set "PYW=%WVP_LEGACY_SRC%\LC_STM\python\pythonw.exe"

set "SRV=%SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
if not exist "%SRV%" set "SRV=%WVP_LEGACY_SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"

if not exist "%PYW%" (
  echo No se encuentra el Python de LucIA: %PYW%
  pause
  exit /b 1
)
if not exist "%SRV%" (
  echo No se encuentra el servidor de LucIA: %SRV%
  pause
  exit /b 1
)

echo Arrancando el cerebro de LucIA en 127.0.0.1:8765...
"%PYW%" "%SRV%" --modelo qwen2.5:7b --puerto 8765
exit /b %errorlevel%
