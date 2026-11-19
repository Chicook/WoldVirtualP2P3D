$ErrorActionPreference = "Stop"
$csRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$construction = [System.IO.Path]::GetFullPath((Join-Path $csRoot "..\.."))
$publishRoot = Join-Path $csRoot "Publicacion"
$serverExe = Join-Path $publishRoot "Servidor\WoldVirtualP2P3D.Servidor.exe"
$visorExe = Join-Path $publishRoot "WoldVirtualP2P3Dv2.9.3.exe"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = "1"
$env:DOTNET_CLI_HOME = Join-Path $csRoot ".dotnet"
$env:NUGET_PACKAGES = Join-Path $csRoot ".nuget\packages"
$env:TEMP = Join-Path $csRoot "tmp"
$env:TMP = $env:TEMP
$env:LOCALAPPDATA = Join-Path $csRoot "runtime\local"
$env:APPDATA = Join-Path $csRoot "runtime\roaming"
$env:WVP_DATA_DIR = Join-Path $csRoot "runtime\datos"
$env:WVP_IPC_DIR = Join-Path $csRoot "runtime\ipc"
New-Item -ItemType Directory -Force -Path @($env:DOTNET_CLI_HOME,$env:NUGET_PACKAGES,$env:TEMP,$env:LOCALAPPDATA,$env:APPDATA,$env:WVP_DATA_DIR,$env:WVP_IPC_DIR,$publishRoot,(Join-Path $publishRoot "Servidor")) | Out-Null
if(-not(Test-Path $serverExe)){throw "Falta el servidor compilado: $serverExe`nEjecuta .dev\CS\scripts\Compilar_2.9.3.ps1 primero."}
if(-not(Test-Path $visorExe)){throw "Falta el visor exportado: $visorExe`nEjecuta .dev\CS\scripts\Compilar_2.9.3.ps1 primero."}
Start-Process -FilePath $visorExe -WorkingDirectory $publishRoot


