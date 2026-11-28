@echo off
setlocal
title Wold Virtual 3D - Vista previa del visor

REM Detectar la raiz del repo buscando un marcador caracteristico (README.md o VersionDesesion)
set "CURR=%~dp0"
:buscar_raiz
if exist "%CURR%VersionDesesion" (
  set "ROOT_REPO=%CURR:~0,-1%"
  goto raiz_hallada
)
for %%I in ("%CURR%..") do set "PARENT=%%~fI"
if "%PARENT%"=="%CURR%" (
  set "ROOT_REPO=E:\WoldVirtualP2P3D"
  goto raiz_hallada
)
set "CURR=%PARENT%\"
goto buscar_raiz

:raiz_hallada
set "SRC=%ROOT_REPO%\VersionDesesion\CONTRRF\RFC\CONTRUCCION\TLLDCD\src"
set "WVP_LEGACY_SRC=%ROOT_REPO%\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"
set "DEV_DIR=%ROOT_REPO%\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev"
set "EXE=%~dp0bin\Debug\net8.0-windows\win-x64\LCDMWoldVirtualP2P3Dv2.8.4.exe"

set "PYW="
if exist "%DEV_DIR%\.python\pythonw.exe" set "PYW=%DEV_DIR%\.python\pythonw.exe"
if not defined PYW if exist "%DEV_DIR%\venv\Scripts\pythonw.exe" set "PYW=%DEV_DIR%\venv\Scripts\pythonw.exe"
if not defined PYW if exist "%SRC%\LC_STM\python\pythonw.exe" set "PYW=%SRC%\LC_STM\python\pythonw.exe"
if not defined PYW if exist "%WVP_LEGACY_SRC%\LC_STM\python\pythonw.exe" set "PYW=%WVP_LEGACY_SRC%\LC_STM\python\pythonw.exe"

set "SRV="
if exist "%SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py" (
  set "SRV=%SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
) else if exist "%WVP_LEGACY_SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py" (
  set "SRV=%WVP_LEGACY_SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
)

if not exist "%EXE%" (
  echo No se encuentra la vista previa compilada:
  echo %EXE%
  echo Compila antes con "dotnet build Visor3D.csproj".
  pause
  exit /b 1
)

if not exist "%PYW%" (
  echo No se encuentra el interprete de Python:
  echo %PYW%
  pause
  exit /b 1
)

if not exist "%SRV%" (
  echo No se encuentra servidor_lucia.py:
  echo %SRV%
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
