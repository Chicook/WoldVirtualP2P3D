# Script de arranque de RFPRMN para PowerShell
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Argumentos
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $ScriptDir

$ConstruccionDir = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$DevDir = Join-Path $ConstruccionDir ".dev"
$VenvDir = Join-Path $DevDir "venv"
$PythonDir = Join-Path $DevDir ".python"

$PyExe = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $PyExe)) {
    $PyExe = Join-Path $PythonDir "python.exe"
}

$env:VIRTUAL_ENV = $VenvDir
$env:PYTHONHOME = $PythonDir
$env:WVP_PYTHON = $PyExe
$env:PYTHONPYCACHEPREFIX = Join-Path $DevDir "pycache"
$env:PYTEST_CACHE_DIR = Join-Path $DevDir ".pytest_cache"
$env:RUFF_CACHE_DIR = Join-Path $DevDir ".ruff_cache"

$env:RFPRMN_RFC_DIR = (Resolve-Path (Join-Path $ConstruccionDir "..")).Path
$env:RFPRMN_PRY_DIR = (Resolve-Path (Join-Path $ConstruccionDir "..\..\..\SistemaPrincipal\PRY")).Path

& $PyExe (Join-Path $ScriptDir "RFPRMN.py") @Argumentos
