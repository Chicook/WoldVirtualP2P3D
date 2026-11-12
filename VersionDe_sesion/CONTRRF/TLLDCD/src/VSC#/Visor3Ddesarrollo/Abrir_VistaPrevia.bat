@echo off
setlocal
title Wold Virtual 3D - Vista previa del visor
set "EXE=E:\WoldVirtualP2P3D\_tmp_visor_preview\Debug\net8.0-windows\win-x64\DMWoldVirtualP2P3Dv2.8.2.exe"
set "PCK=E:\WoldVirtualP2P3D\_tmp_visor_preview\Debug\net8.0-windows\win-x64\wvp3d.pck"
set "PYW=E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\LC_STM\python\pythonw.exe"
set "SRV=E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"

if not exist "%EXE%" (
  echo No se encuentra la vista previa:
  echo %EXE%
  pause
  exit /b 1
)
if not exist "%PCK%" echo Aviso: falta el PCK junto al .exe.

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
