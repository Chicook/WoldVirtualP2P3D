@echo off
:: ============================================================
:: ARRANQUE DAEMON IPFS - WoldVirtualP2P3D Celebro 2026
:: Kubo v0.43.1 | nodo local -> red IPFS global
:: ============================================================
set STMIPFS_DIR=%~dp0..
if not defined IPFS_PATH (
    if exist "%STMIPFS_DIR%\.ipfs\config" (
        set "IPFS_PATH=%STMIPFS_DIR%\.ipfs"
    ) else (
        set "IPFS_PATH=%~dp0.ipfs"
    )
)

set "IPFS_EXE="
if exist "%STMIPFS_DIR%\.ipfs\STMIPFSCOMFIG\ipfs.exe" (
    set "IPFS_EXE=%STMIPFS_DIR%\.ipfs\STMIPFSCOMFIG\ipfs.exe"
) else if exist "%~dp0ipfs.exe" (
    set "IPFS_EXE=%~dp0ipfs.exe"
) else (
    set "IPFS_EXE=ipfs"
)

echo.
echo  ================================================
echo   IPFS DAEMON - WoldVirtualP2P3D Celebro 2026
echo   Kubo v0.43.1
echo   IPFS_PATH: %IPFS_PATH%
echo   BINARIO  : %IPFS_EXE%
echo  ================================================
echo.
echo  Arrancando daemon IPFS... (Ctrl+C para detener)
echo  API HTTP disponible en: http://127.0.0.1:5001
echo  Gateway local disponible en: http://127.0.0.1:8080
echo.
"%IPFS_EXE%" daemon --enable-pubsub-experiment
pause
