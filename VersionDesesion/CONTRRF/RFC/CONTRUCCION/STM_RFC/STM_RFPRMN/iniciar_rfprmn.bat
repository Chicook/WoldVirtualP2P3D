@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "SCRIPT_DIR=%~dp0"
set "CONTRUCCION_DIR=%SCRIPT_DIR%..\..\"
pushd "%CONTRUCCION_DIR%"
set "CONTRUCCION_DIR=%CD%"
popd

set "DEV_DIR=%CONTRUCCION_DIR%\.dev"
set "VENV_DIR=%DEV_DIR%\venv"
set "PYTHON_DIR=%DEV_DIR%\.python"

set "PY_EXE=%VENV_DIR%\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=%PYTHON_DIR%\python.exe"

set "VIRTUAL_ENV=%VENV_DIR%"
set "PYTHONHOME=%PYTHON_DIR%"
set "WVP_PYTHON=%PY_EXE%"
set "PYTHONPYCACHEPREFIX=%DEV_DIR%\pycache"
set "PYTEST_CACHE_DIR=%DEV_DIR%\.pytest_cache"
set "RUFF_CACHE_DIR=%DEV_DIR%\.ruff_cache"

pushd "%CONTRUCCION_DIR%\.."
set "RFPRMN_RFC_DIR=%CD%"
popd

pushd "%CONTRUCCION_DIR%\..\..\..\SistemaPrincipal\PRY"
set "RFPRMN_PRY_DIR=%CD%"
popd

"%PY_EXE%" "%SCRIPT_DIR%RFPRMN.py" %*
