@echo off
setlocal
set "BASE_DIR=%~dp0"
if exist "%BASE_DIR%opencode.exe" (
    "%BASE_DIR%opencode.exe" %*
) else if exist "%BASE_DIR%node_modules\opencode-ai\bin\opencode.exe" (
    "%BASE_DIR%node_modules\opencode-ai\bin\opencode.exe" %*
) else (
    opencode %*
)
endlocal
