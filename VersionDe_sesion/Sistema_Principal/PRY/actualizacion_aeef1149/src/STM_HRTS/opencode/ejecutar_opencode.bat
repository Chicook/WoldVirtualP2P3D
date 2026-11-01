@echo off
chcp 65001 >nul
title OpenCode - WoldVirtualP2P3D (STM_HRTS)
echo =======================================================
echo    Iniciando OpenCode (STM_HRTS / WoldVirtualP2P3D)
echo =======================================================
echo.
cd /d "%~dp0"

if exist "opencode.exe" (
    "opencode.exe" %*
) else if exist "node_modules\opencode-ai\bin\opencode.exe" (
    "node_modules\opencode-ai\bin\opencode.exe" %*
) else (
    opencode %*
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo [OpenCode ha finalizado con codigo de salida: %ERRORLEVEL%]
    pause
)
