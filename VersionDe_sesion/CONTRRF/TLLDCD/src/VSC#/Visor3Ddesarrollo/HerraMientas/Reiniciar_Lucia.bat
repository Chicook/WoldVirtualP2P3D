@echo off
setlocal
title Wold Virtual 3D - Reiniciar LucIA (8765)
set "PYW=E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\LC_STM\python\pythonw.exe"
set "SRV=E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"

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
