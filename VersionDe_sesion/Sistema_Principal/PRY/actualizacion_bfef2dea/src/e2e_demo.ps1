#Requires -Version 5.1
<#
.SYNOPSIS
    Prueba E2E del demo local, sin ventana.

.DESCRIPTION
    Arranca el servidor de cuentas con un ledger de pruebas, aparta temporalmente
    la cuenta del jugador, recorre el flujo completo en Godot headless
    (recepción -> alta -> .zip -> carrusel -> registro -> portal -> isla) y
    devuelve la cuenta del jugador a su sitio al terminar.

    Sale con 0 si el flujo llega a la isla; con 1 y el motivo si falla.

.EXAMPLE
    .\e2e_demo.ps1
#>
[CmdletBinding()]
param(
    [int]$Puerto = 8545,
    [string]$Godot,
    [string]$Python
)

$ErrorActionPreference = 'Stop'

$SRC      = $PSScriptRoot
# Dos disposiciones válidas: taller (src\MTBGT\WoldVirtualP2P3D) o demo
# autocontenido (este lanzador vive en la raíz del propio proyecto Godot).
$PROYECTO = if (Test-Path -LiteralPath (Join-Path $SRC 'project.godot')) {
    $SRC
} else {
    Join-Path $SRC 'MTBGT\WoldVirtualP2P3D'
}
$DEMO     = Join-Path $SRC '_demo'
$LOGS     = Join-Path $DEMO 'logs'
$USUARIO  = Join-Path $env:APPDATA 'Godot\app_userdata\WoldVirtualP2P3D'
$SELLO    = Get-Date -Format 'yyyyMMdd_HHmmss'
$RESPALDO = Join-Path $DEMO ("e2e_respaldo_" + $SELLO)

function Escribir-Paso  ($t) { Write-Host ("  -> " + $t) -ForegroundColor Gray }
function Escribir-Bien  ($t) { Write-Host ("  OK " + $t) -ForegroundColor Green }
function Escribir-Fallo ($t) { Write-Host ("  X  " + $t) -ForegroundColor Red }

function Buscar-Python {
    param([string]$Preferido)
    $candidatos = @()
    if ($Preferido)      { $candidatos += $Preferido }
    if ($env:WVP_PYTHON) { $candidatos += $env:WVP_PYTHON }
    $candidatos += @('python', 'python3', 'py')
    foreach ($c in $candidatos) {
        $exe = $null
        try { $exe = (Get-Command $c -ErrorAction Stop).Source } catch { continue }
        if (-not $exe) { continue }
        try { & $exe -c 'import sys' 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { return $exe } } catch { }
    }
    $rutas = @(
        (Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        'C:\Python313\python.exe'
    )
    foreach ($r in $rutas) { if ($r -and (Test-Path -LiteralPath $r)) { return $r } }
    return $null
}

function Buscar-Godot {
    param([string]$Preferido)
    $nombre = 'Godot_v4.7.2-stable_win64.exe'
    $candidatos = @()
    if ($Preferido)     { $candidatos += $Preferido }
    if ($env:WVP_GODOT) { $candidatos += $env:WVP_GODOT }
    $repo = Split-Path (Split-Path (Split-Path (Split-Path $SRC -Parent) -Parent) -Parent) -Parent
    $candidatos += @(
        # Copia portátil: Godot junto al propio lanzador.
        (Join-Path $SRC ('_godot\' + $nombre)),
        (Join-Path $SRC ('VSC#\Servidor3D\' + $nombre)),
        (Join-Path $repo ('_tmp_tests\godot\' + $nombre)),
        (Join-Path $repo ('_tmp_tests\godot_oficial\' + $nombre))
    )
    foreach ($r in $candidatos) { if ($r -and (Test-Path -LiteralPath $r)) { return $r } }
    return $null
}

function Apartar-Cuenta {
    param([string]$Destino)
    New-Item -ItemType Directory -Force -Path $Destino | Out-Null
    if (-not (Test-Path -LiteralPath $USUARIO)) { return }
    foreach ($n in @('cuenta.json','registro.cfg','avatar_hash.json','avatar.sha256','p2p_session.json',
                     'islas_registro.cfg','validacion_conexion.json','abrir_recepcion.flag',
                     'avatares_variantes.json')) {
        $o = Join-Path $USUARIO $n
        if (Test-Path -LiteralPath $o) { Move-Item -LiteralPath $o -Destination (Join-Path $Destino $n) -Force }
    }
    Get-ChildItem -LiteralPath $USUARIO -Filter 'cuenta_*.zip' -File -ErrorAction SilentlyContinue |
        ForEach-Object { Move-Item -LiteralPath $_.FullName -Destination (Join-Path $Destino $_.Name) -Force }
}

function Devolver-Cuenta {
    param([string]$Origen)
    # Fuera lo que haya dejado el E2E…
    foreach ($n in @('cuenta.json','registro.cfg','avatar_hash.json','avatar.sha256','islas_registro.cfg','avatares_variantes.json')) {
        $o = Join-Path $USUARIO $n
        if (Test-Path -LiteralPath $o) { Remove-Item -LiteralPath $o -Force }
    }
    Get-ChildItem -LiteralPath $USUARIO -Filter 'cuenta_*.zip' -File -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
    # …y vuelve lo que había.
    if (Test-Path -LiteralPath $Origen) {
        Get-ChildItem -LiteralPath $Origen -File | ForEach-Object {
            Move-Item -LiteralPath $_.FullName -Destination (Join-Path $USUARIO $_.Name) -Force
        }
    }
}

# ============================================================================
Write-Host ''
Write-Host '  E2E del demo local · LucIA anfitriona (discusión #86)' -ForegroundColor Cyan
Write-Host '  ------------------------------------------------------' -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $LOGS | Out-Null

$pyExe = Buscar-Python -Preferido $Python
$godotExe = Buscar-Godot -Preferido $Godot
if (-not $pyExe)    { Escribir-Fallo 'No encuentro Python (-Python "ruta")'; exit 1 }
if (-not $godotExe) { Escribir-Fallo 'No encuentro Godot (-Godot "ruta")'; exit 1 }

Escribir-Paso 'Apartando la cuenta actual del jugador…'
Apartar-Cuenta -Destino $RESPALDO

$argsServidor = @(
    (Join-Path $SRC 'STM_BKCH\demo_servidor.py'),
    '--puerto', $Puerto,
    '--ledger', (Join-Path $DEMO 'ledger_e2e.json'),
    '--reset',
    '--sin-cuota-ubicacion'
)
# Un servidor viejo en el puerto respondería a /status y el demo hablaría con el
# ledger equivocado: mejor parar con un mensaje claro.
if (Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue) {
    Escribir-Fallo "El puerto $Puerto ya esta ocupado. Cierra el otro servidor y reintenta."
    exit 1
}
$logSrv = Join-Path $LOGS ("e2e_servidor_" + $SELLO + ".log")
$errSrv = Join-Path $LOGS ("e2e_servidor_" + $SELLO + ".err")
Escribir-Paso "Arrancando servidor de pruebas en $Puerto…"
$servidor = Start-Process -FilePath $pyExe -ArgumentList $argsServidor -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $logSrv -RedirectStandardError $errSrv

$listo = $false
for ($i = 0; $i -lt 80 -and -not $listo; $i++) {
    try { $null = Invoke-RestMethod -Uri "http://127.0.0.1:$Puerto/status" -TimeoutSec 2; $listo = $true }
    catch { Start-Sleep -Milliseconds 250 }
}
if (-not $listo) {
    Escribir-Fallo 'El servidor no arrancó'
    if (Test-Path $errSrv) { Get-Content $errSrv -Tail 15 | ForEach-Object { Write-Host ('     ' + $_) -ForegroundColor DarkGray } }
    if ($servidor -and -not $servidor.HasExited) { Stop-Process -Id $servidor.Id -Force }
    Devolver-Cuenta -Origen $RESPALDO
    exit 1
}
Escribir-Bien 'Servidor de pruebas listo'

$logGodot = Join-Path $LOGS ("e2e_godot_" + $SELLO + ".log")
$errGodot = Join-Path $LOGS ("e2e_godot_" + $SELLO + ".err")
Escribir-Paso 'Recorriendo el flujo en Godot (headless)…'

$proc = Start-Process -FilePath $godotExe `
    -ArgumentList @('--headless', '--path', $PROYECTO, '--script', 'res://tools/e2e_demo.gd', '--', '--server') `
    -PassThru -WindowStyle Hidden -RedirectStandardOutput $logGodot -RedirectStandardError $errGodot
$proc.WaitForExit()
$codigo = $proc.ExitCode
# PowerShell 5.1 no siempre rellena ExitCode con Start-Process: si viene vacío,
# se deduce del propio registro del E2E.
if ($null -eq $codigo) {
    $texto = Get-Content -LiteralPath $logGodot -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if ($texto -match '\[E2E\] OK') { $codigo = 0 } else { $codigo = 1 }
}

Get-Content -LiteralPath $logGodot -Encoding UTF8 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host ('   ' + $_) -ForegroundColor DarkGray }

# --- Segunda puerta: las variantes del avatar deben llegar al carrusel -------
Escribir-Paso 'Comprobando el carrusel (catálogo y panel)…'
$logVar = Join-Path $LOGS ("e2e_carrusel_" + $SELLO + ".log")
$errVar = Join-Path $LOGS ("e2e_carrusel_" + $SELLO + ".err")
$procVar = Start-Process -FilePath $godotExe `
    -ArgumentList @('--headless', '--path', $PROYECTO, '--script', 'res://tools/e2e_carrusel.gd') `
    -PassThru -WindowStyle Hidden -RedirectStandardOutput $logVar -RedirectStandardError $errVar
$procVar.WaitForExit()
$codigoVar = $procVar.ExitCode
if ($null -eq $codigoVar) {
    $textoVar = Get-Content -LiteralPath $logVar -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if ($textoVar -match '\[e2e_carrusel\] OK') { $codigoVar = 0 } else { $codigoVar = 1 }
}
Get-Content -LiteralPath $logVar -Encoding UTF8 -ErrorAction SilentlyContinue |
    Where-Object { $_ -match '\[carrusel\]|\[ok\]|\[FALLO\]|e2e_carrusel' } |
    ForEach-Object { Write-Host ('   ' + $_) -ForegroundColor DarkGray }
if ($codigo -eq 0 -and $codigoVar -ne 0) { $codigo = $codigoVar }

if ($servidor -and -not $servidor.HasExited) { Stop-Process -Id $servidor.Id -Force }
Devolver-Cuenta -Origen $RESPALDO

Write-Host ''
if ($codigo -eq 0) {
    Escribir-Bien 'E2E OK · el flujo completo llega a la isla'
} else {
    Escribir-Fallo "E2E FALLÓ (código $codigo)"
    if (Test-Path $errGodot) { Get-Content $errGodot -Tail 12 -Encoding UTF8 | ForEach-Object { Write-Host ('     ' + $_) -ForegroundColor DarkGray } }
}
exit $codigo
