@echo off
setlocal
title Wold Virtual 3D - Servidor LucIA (8765)
set "PYW=E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\LC_STM\python\pythonw.exe"
set "SRV=E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"

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
