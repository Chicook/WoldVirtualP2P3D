@rem Abre el asistente OpenCode en la consola interactiva.
@echo off
chcp 65001 >nul
set "SCRIPT_DIR=%~dp0"
set "OPENCODE_EXE=%SCRIPT_DIR%..\opencode\opencode.exe"

if exist "%OPENCODE_EXE%" (
    "%OPENCODE_EXE%" %*
) else (
    opencode %*
)
