@echo off
setlocal
title Gestor de Entorno WoldVirtualP2P3D (.dev)
cd /d "%~dp0"
set "PY=%~dp0.python\python.exe"
if not exist "%PY%" set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

rem Bytecode del ecosistema dentro de .dev, nunca __pycache__ en el arbol fuente
set "PYTHONPYCACHEPREFIX=%~dp0pycache"

"%PY%" gestor_entorno.py %*
if "%1"=="" pause
