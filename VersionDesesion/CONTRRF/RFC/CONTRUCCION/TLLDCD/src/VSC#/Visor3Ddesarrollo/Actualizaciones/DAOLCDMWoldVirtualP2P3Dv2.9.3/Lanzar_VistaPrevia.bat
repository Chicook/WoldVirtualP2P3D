@echo off
setlocal
title Wold Virtual 3D - Vista Previa de LucIA con Servidores Locales

set "SRC=%~dp0..\..\..\..\..\..\..\..\..\VersionDesesion\CONTRRF\RFC\CONTRUCCION\TLLDCD\src"
if not exist "%SRC%" set "SRC=%~dp0..\..\..\.."
if not exist "%SRC%" set "SRC=E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\TLLDCD\src"

set "PY=E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\.python\pythonw.exe"
if not exist "%PY%" set "PY=E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\.python\python.exe"

set "SRV_LUCIA=%SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
set "SRV_BKCH=%SRC%\STM_BKCH\stm_bkch1\servidor_oficial.py"
set "GODOT_EXE=E:\WoldVirtualP2P3D\VersionDesesion\CONTRRF\RFC\CONTRUCCION\.dev\rebuild287\runtime\Servidor3D\Godot_v4.7.2-stable_win64.exe"
set "PROYECTO_GODOT=%SRC%\MTBGT\WoldVirtualP2P3D"
set "ESCENA=res://VistaPreviaRecepcion.tscn"

set "USER_DIR=%APPDATA%\Godot\app_userdata\WoldVirtualP2P3D"
if not exist "%USER_DIR%" mkdir "%USER_DIR%"

echo ========================================================
echo   LEVANTANDO ENTORNO COMPLETO PARA VISTA PREVIA
echo ========================================================

echo 1. Comprobando / Arrancando Servidor Blockchain (Puerto 8545)...
netstat -ano | findstr ":8545" | findstr "LISTENING" >nul
if errorlevel 1 (
  start "Servidor_Blockchain_8545" /min "%PY%" "%SRV_BKCH" --puerto 8545 --sin-cuota-ubicacion
) else (
  echo    Puerto 8545 ya activo.
)

echo 2. Comprobando / Arrancando Servidor Cerebro de LucIA (Puerto 8765)...
netstat -ano | findstr ":8765" | findstr "LISTENING" >nul
if errorlevel 1 (
  start "Servidor_LucIA_8765" /min "%PY%" "%SRV_LUCIA" --modelo "qwen2.5:7b" --puerto 8765 --sin-precalentar --sin-precarga-voz
) else (
  echo    Puerto 8765 ya activo.
)

echo 3. Configurando tunel_lucia_url.json (isla personal de LucIA HOST)...
(
  echo {
  echo   "exito": true,
  echo   "url": "https://magazines-contract-narrow-workforce.trycloudflare.com",
  echo   "mensaje": "T?nel WebNodo activo: https://magazines-contract-narrow-workforce.trycloudflare.com",
  echo   "timestamp": 1700000000
  echo }
) > "%USER_DIR%\tunel_lucia_url.json"

echo 3b. Configurando tunel_dao_url.json (DAO central del metaverso - LucIA HOST)...
(
  echo {
  echo   "exito": true,
  echo   "url": "https://dao-asamblea-test.trycloudflare.com",
  echo   "mensaje": "DAO activa: https://dao-asamblea-test.trycloudflare.com",
  echo   "timestamp": 1700000000
  echo }
) > "%USER_DIR%\tunel_dao_url.json"

echo 4. Esperando sincronizacion de puertos (3 segundos)...
timeout /t 3 /nobreak >nul

echo 5. Lanzando Vista Previa en Godot...
start "" "%GODOT_EXE%" --path "%PROYECTO_GODOT%" "%ESCENA%"

echo.
echo Todo listo. La ventana 3D deberia abrirse conectada a LucIA (8765) y Blockchain (8545).
exit /b 0
