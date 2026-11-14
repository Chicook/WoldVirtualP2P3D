@echo off
setlocal
set "PY=E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\LC_STM\python\pythonw.exe"
set "SRV=E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
set "LOG=%LOCALAPPDATA%\WoldVirtualP2P3D\logs\lucia_bat.log"
cd /d "%~dp0"
"%PY%" "%SRV%" --modelo qwen2.5:7b --puerto 8765 >> "%LOG%" 2>&1
