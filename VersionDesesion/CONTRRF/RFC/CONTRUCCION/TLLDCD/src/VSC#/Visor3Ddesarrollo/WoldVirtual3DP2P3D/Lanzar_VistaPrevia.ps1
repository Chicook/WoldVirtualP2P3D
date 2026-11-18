$ErrorActionPreference = "Stop"
$env:DOTNET_ROLL_FORWARD = "Major"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
$baseDir = $PSScriptRoot
$dev = [System.IO.Path]::GetFullPath((Join-Path $baseDir "..\..\..\..\..\.dev"))
$cs = Join-Path $dev "CS"
$godot = Join-Path $cs "runtime\Godot\Godot_v4.7.2-stable_win64.exe"
if (-not (Test-Path $godot)) {
    $godot = Join-Path $dev "rebuild287\runtime\Servidor3D\Godot_v4.7.2-stable_win64.exe"
}
$serverExe = Join-Path $baseDir "Servidor\bin\Debug\net8.0\WoldVirtualP2P3D.Servidor.exe"
if (-not (Test-Path $serverExe)) {
    $serverExe = Join-Path $cs "Publicacion\Servidor\WoldVirtualP2P3D.Servidor.exe"
}
$visorDir = Join-Path $baseDir "Visor"
$cloudflared = Join-Path $cs "runtime\cloudflared\cloudflared.exe"

$env:WVP_IPC_DIR = Join-Path $cs "runtime\ipc"
$env:WVP_DATA_DIR = Join-Path $cs "runtime\datos"
$env:WVP_SERVER_EXE = $serverExe
$env:WVP_LAUNCH_SERVER = "1"
$env:WVP_PORT = "8765"
$env:CLOUDFLARED_EXE = $cloudflared
$env:WVP_TUNNEL_PROVIDER = "ssh"

New-Item -ItemType Directory -Force -Path @($env:WVP_IPC_DIR, $env:WVP_DATA_DIR) | Out-Null

$isListening = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if (-not $isListening) {
    Write-Host "Iniciando servidor modular (puerto 8765)..." -ForegroundColor Cyan
    Start-Process -FilePath $serverExe -ArgumentList "--urls http://0.0.0.0:8765" -WindowStyle Minimized
    Write-Host "  Esperando a que el servidor levante..." -ForegroundColor DarkCyan
    Start-Sleep -Seconds 5
}

Write-Host "Lanzando visor Godot (DAO)..." -ForegroundColor Green
Start-Process -FilePath $godot -ArgumentList "--path `"$visorDir`" `"res://escenas/DAO.tscn`""
Write-Host "Vista previa de la DAO iniciada. Boton CONECTAR A LA DAO visible en pantalla." -ForegroundColor Cyan
