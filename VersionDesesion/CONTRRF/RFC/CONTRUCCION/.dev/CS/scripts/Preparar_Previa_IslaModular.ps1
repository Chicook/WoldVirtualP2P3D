$ErrorActionPreference = "Stop"
$csRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$construction = [System.IO.Path]::GetFullPath((Join-Path $csRoot "..\.."))
$projectRoot = Join-Path $construction "TLLDCD\src\MTBGT\WoldVirtualP2P3D"
$godotExe = Join-Path $csRoot "runtime\Godot\Godot_v4.7.2-stable_win64.exe"
$serverExe = Join-Path $csRoot "Publicacion\Servidor\WoldVirtualP2P3D.Servidor.exe"
$cloudflaredExe = Join-Path $csRoot "runtime\cloudflared\cloudflared.exe"
if (-not (Test-Path $godotExe)) {
    $godotExe = Join-Path $construction ".dev\rebuild287\portable292\runtime\Servidor3D\Godot_v4.7.2-stable_win64.exe"
}
if (-not (Test-Path $projectRoot)) { throw "No existe el proyecto Godot de referencia: $projectRoot" }
if (-not (Test-Path $godotExe)) { throw "No se encontró Godot 4.7.2." }
if (-not (Test-Path $serverExe)) { throw "Falta el servidor modular: ejecuta Compilar_2.9.3.ps1 primero." }
if (-not (Test-Path $cloudflaredExe)) { throw "Falta cloudflared; prepara el Quick Tunnel de Cloudflare antes de abrir el visor." }

$env:APPDATA = Join-Path $csRoot "runtime\roaming"
$env:LOCALAPPDATA = Join-Path $csRoot "runtime\local"
$env:TEMP = Join-Path $csRoot "tmp"
$env:TMP = $env:TEMP
$env:WVP_DATA_DIR = Join-Path $csRoot "runtime\datos"
$env:WVP_IPC_DIR = Join-Path $csRoot "runtime\ipc"
$env:WVP_SERVER_EXE = $serverExe
$env:WVP_LAUNCH_SERVER = "1"
$env:WVP_MODULAR_DAO = "1"
$env:WVP_IPC_ONLY = "0"
$env:WVP_TUNNEL_PROVIDER = "cloudflare"
$env:WVP_PORT = "8765"
$env:CLOUDFLARED_EXE = $cloudflaredExe
New-Item -ItemType Directory -Force -Path @($env:APPDATA,$env:LOCALAPPDATA,$env:TEMP,$env:WVP_DATA_DIR,$env:WVP_IPC_DIR) | Out-Null

# Arranca el visor real (Boot + mundo P2P + DAO). La combinación de argumentos
# coloca el avatar de prueba en la DAO y evita que el perfil local redirija a
# otra isla; no se exporta ni compila un ejecutable del visor.
$logDir = Join-Path $csRoot "build\preview"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdout = Join-Path $logDir "godot-preview.out.log"
$stderr = Join-Path $logDir "godot-preview.err.log"
Remove-Item -LiteralPath $stdout,$stderr -Force -ErrorAction SilentlyContinue
$arguments = "--path `"$projectRoot`" --log-file `"$stdout`" -- --dao-lobby --dao-preview"
# ShellExecute entrega el proceso al escritorio interactivo de Windows para que
# sobreviva al cierre del PowerShell que invoca este lanzador.
$shell = New-Object -ComObject Shell.Application
$shell.ShellExecute($godotExe, $arguments, $projectRoot, "open", 1)
Set-Content -LiteralPath (Join-Path $logDir "godot-preview.started") -Value (Get-Date -Format o) -Encoding ascii
