@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0.python\python.exe"
"%PY%" gestor_entorno.py pytest %*
