@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0.python\python.exe"
set "PYTEST_ADDOPTS=-o cache_dir=%~dp0.pytest_cache -c %~dp0pytest.ini"
"%PY%" gestor_entorno.py pytest %*
