#Requires -Version 5.1
<#
.SYNOPSIS
    Demo local de Wold Virtual 3D: LucIA anfitriona + cuenta por bloque (discusión #86).

.DESCRIPTION
    Arranca el servidor de cuentas (STM_BKCH) con su propio ledger y abre el mundo
    en Godot como anfitrión local. Un comando, sin red externa y sin release.

    Flujo: LucIA te recibe -> creas la cuenta (un bloque = un hash) -> descargas tu
    .zip -> eliges avatar -> entras a tu isla. No hay contraseña ni frase semilla:
    el hash del bloque ES la cuenta.

.PARAMETER Reset
    Deja el demo como primera vez: archiva (no borra) cuenta.json, registro.cfg,
    el avatar y la sesión P2P anteriores, y archiva el ledger del demo.

.PARAMETER Puerto
    Puerto del servidor de cuentas. Por defecto 8545 (el que espera el mundo).

.PARAMETER SinServidor
    Abre solo el mundo (si ya tienes el servidor arrancado en otra consola).

.PARAMETER SoloServidor
    Arranca solo el servidor y se queda en primer plano.

.PARAMETER Editor
    Abre el proyecto en el EDITOR de Godot (para mirar o tocar el mundo), con el
    servidor de cuentas levantado para que F5 funcione. Sin este interruptor se
    abre el juego directamente.

.PARAMETER Godot
    Ruta al ejecutable de Godot 4.7.2 (si no, se busca automáticamente).

.PARAMETER Python
    Ruta al intérprete de Python (si no, se busca automáticamente).

.EXAMPLE
    .\demo_local.ps1 -Reset
    Primera ejecución: todo limpio y el mundo abierto.

.EXAMPLE
    .\demo_local.ps1 -Editor
    Abre el proyecto en el editor de Godot para trabajar sobre él.
#>
[CmdletBinding()]
param(
    [switch]$Reset,
    [int]$Puerto = 8545,
    [switch]$SinServidor,
    [switch]$SoloServidor,
    [switch]$Editor,
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

function Escribir-Titulo {
    Write-Host ''
    Write-Host '==================================================================' -ForegroundColor Cyan
    Write-Host '  WOLD VIRTUAL 3D · DEMO LOCAL · LucIA anfitriona (discusión #86)' -ForegroundColor Cyan
    Write-Host '==================================================================' -ForegroundColor Cyan
}
function Escribir-Paso  ($t) { Write-Host ("  -> " + $t) -ForegroundColor Gray }
function Escribir-Bien  ($t) { Write-Host ("  OK " + $t) -ForegroundColor Green }
function Escribir-Aviso ($t) { Write-Host ("  !  " + $t) -ForegroundColor Yellow }
function Escribir-Fallo ($t) { Write-Host ("  X  " + $t) -ForegroundColor Red }

# --- Búsqueda de intérprete -------------------------------------------------
function Buscar-Python {
    param([string]$Preferido)

    $candidatos = @()
    if ($Preferido)        { $candidatos += $Preferido }
    if ($env:WVP_PYTHON)   { $candidatos += $env:WVP_PYTHON }
    $candidatos += @('python', 'python3', 'py')

    foreach ($c in $candidatos) {
        $exe = $null
        try { $exe = (Get-Command $c -ErrorAction Stop).Source } catch { continue }
        if (-not $exe) { continue }
        try {
            & $exe -c 'import sys' 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return $exe }
        } catch { }
    }

    $rutas = @(
        (Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
        'C:\Python313\python.exe',
        'C:\Python312\python.exe',
        'C:\Python311\python.exe'
    )
    foreach ($r in $rutas) {
        if ($r -and (Test-Path -LiteralPath $r)) { return $r }
    }
    $hallado = Get-ChildItem (Join-Path $env:LOCALAPPDATA 'Programs\Python') -Filter 'python.exe' -Recurse -Depth 1 -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
    return $hallado
}

# --- Búsqueda de Godot ------------------------------------------------------
function Buscar-Godot {
    param([string]$Preferido)

    $nombre = 'Godot_v4.7.2-stable_win64.exe'
    $candidatos = @()
    if ($Preferido)      { $candidatos += $Preferido }
    if ($env:WVP_GODOT)  { $candidatos += $env:WVP_GODOT }

    # Cuatro niveles por encima de src\ : VersionDe_sesion\CONTRRF\TLLDCD\src
    $repo = Split-Path (Split-Path (Split-Path (Split-Path $SRC -Parent) -Parent) -Parent) -Parent
    $candidatos += @(
        # Copia portátil: Godot junto al propio lanzador.
        (Join-Path $SRC ('_godot\' + $nombre)),
        (Join-Path $SRC ('VSC#\Servidor3D\' + $nombre)),
        (Join-Path $repo ('_tmp_tests\godot\' + $nombre)),
        (Join-Path $repo ('_tmp_tests\godot_oficial\' + $nombre))
    )
    try { $enPath = (Get-Command 'godot' -ErrorAction Stop).Source; if ($enPath) { $candidatos += $enPath } } catch { }

    foreach ($r in $candidatos) {
        if ($r -and (Test-Path -LiteralPath $r)) { return $r }
    }
    return $null
}

# --- Comprobación de salud del servidor -------------------------------------
function Esperar-Servidor {
    param([int]$Puerto, [int]$Segundos = 20)
    $url = "http://127.0.0.1:$Puerto/status"
    $limite = (Get-Date).AddSeconds($Segundos)
    while ((Get-Date) -lt $limite) {
        try {
            $r = Invoke-RestMethod -Uri $url -TimeoutSec 2
            if ($null -ne $r) { return $r }
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    return $null
}

# --- Archivado (nunca borrado) de estado del demo ---------------------------
function Archivar-Estado {
    param([string]$Destino, [switch]$SoloSesion)

    New-Item -ItemType Directory -Force -Path $Destino | Out-Null
    if (-not (Test-Path -LiteralPath $USUARIO)) { return }

    $comunes = @(
        'cuenta.json', 'registro.cfg', 'avatar_hash.json', 'avatar.sha256',
        'islas_registro.cfg', 'validacion_conexion.json', 'validacion_resultado.json', 'avatares_variantes.json',
        'abrir_recepcion.flag', 'tunel_solicitud.json', 'reset_flag.txt'
    )
    foreach ($n in $comunes) {
        $o = Join-Path $USUARIO $n
        if (Test-Path -LiteralPath $o) { Move-Item -LiteralPath $o -Destination (Join-Path $Destino $n) -Force }
    }
    Get-ChildItem -LiteralPath $USUARIO -Filter 'cuenta_*.zip' -File -ErrorAction SilentlyContinue | ForEach-Object {
        Move-Item -LiteralPath $_.FullName -Destination (Join-Path $Destino $_.Name) -Force
    }
}

function Archivar-SesionP2P {
    param([string]$Destino)
    $o = Join-Path $USUARIO 'p2p_session.json'
    if (Test-Path -LiteralPath $o) {
        New-Item -ItemType Directory -Force -Path $Destino | Out-Null
        Move-Item -LiteralPath $o -Destination (Join-Path $Destino 'p2p_session.json') -Force
    }
}

# ============================================================================
Escribir-Titulo
New-Item -ItemType Directory -Force -Path $LOGS | Out-Null

if (-not (Test-Path -LiteralPath (Join-Path $PROYECTO 'project.godot'))) {
    Escribir-Fallo "No encuentro el proyecto Godot en $PROYECTO"
    exit 1
}

$pyExe = Buscar-Python -Preferido $Python
$godotExe = Buscar-Godot -Preferido $Godot

# --- Reset del estado del jugador -------------------------------------------
if ($Reset) {
    $backupUsuario = Join-Path $DEMO ("backup_" + $SELLO)
    Escribir-Paso "Dejando el demo como primera vez (archivo en _demo\backup_$SELLO)…"
    # Aviso explícito: si hay cuenta, se dice cuál se aparta y que se puede recuperar.
    $cuentaActual = Join-Path $USUARIO 'cuenta.json'
    if (Test-Path -LiteralPath $cuentaActual) {
        try {
            $j = Get-Content -LiteralPath $cuentaActual -Raw | ConvertFrom-Json
            Escribir-Aviso ("Se aparta la cuenta '" + $j.nick + "' · para volver a usarla, copia cuenta.json del respaldo")
        } catch { }
    }
    Archivar-Estado -Destino $backupUsuario
    Escribir-Bien 'Cuenta, avatar y sesión anteriores archivados'
}
# El demo no usa red: una sesión P2P vieja confundiría el rol (cliente de un host ausente).
Archivar-SesionP2P -Destino (Join-Path $DEMO ("sesion_" + $SELLO))

# --- Servidor de cuentas ----------------------------------------------------
$servidor = $null
if (-not $SinServidor) {
    if (-not $pyExe) {
        Escribir-Fallo 'No encuentro Python. Pásalo con -Python "C:\ruta\python.exe"'
        exit 1
    }
    try { & $pyExe -c 'import numpy' 2>$null | Out-Null } catch { }
    if ($LASTEXITCODE -ne 0) {
        Escribir-Aviso 'Ese Python no tiene numpy; el servidor de bloques lo necesita.'
    }

    $argsServidor = @(
        (Join-Path $SRC 'STM_BKCH\demo_servidor.py'),
        '--puerto', $Puerto,
        '--ledger', (Join-Path $DEMO 'ledger.json'), '--sin-cuota-ubicacion'
    )
    if ($Reset) { $argsServidor += '--reset' }

    if ($SoloServidor) {
        Escribir-Paso "Servidor de cuentas en http://127.0.0.1:$Puerto (Ctrl+C para cerrar)"
        & $pyExe @argsServidor
        exit 0
    }

    # Un servidor viejo en el puerto respondería a /status y el demo hablaría con el
# ledger equivocado: mejor parar con un mensaje claro.
if (Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue) {
    Escribir-Fallo "El puerto $Puerto ya esta ocupado. Cierra el otro servidor y reintenta."
    exit 1
}
$logSrv = Join-Path $LOGS ("servidor_" + $SELLO + ".log")
    $errSrv = Join-Path $LOGS ("servidor_" + $SELLO + ".err")
    Escribir-Paso "Arrancando el servidor de cuentas (puerto $Puerto)…"
    $servidor = Start-Process -FilePath $pyExe -ArgumentList $argsServidor `
        -PassThru -WindowStyle Hidden -RedirectStandardOutput $logSrv -RedirectStandardError $errSrv

    $estado = Esperar-Servidor -Puerto $Puerto
    if ($null -eq $estado) {
        Escribir-Fallo "El servidor no respondió en http://127.0.0.1:$Puerto"
        if (Test-Path -LiteralPath $errSrv) { Get-Content -LiteralPath $errSrv -Tail 15 | ForEach-Object { Write-Host ('     ' + $_) -ForegroundColor DarkGray } }
        if ($servidor -and -not $servidor.HasExited) { Stop-Process -Id $servidor.Id -Force }
        exit 1
    }
    Escribir-Bien ("Servidor de cuentas listo · bloques=" + $estado.total_bloques + ' · cadena=' + $estado.cadena_valida)
}

# --- Mundo ------------------------------------------------------------------
if ($null -eq $godotExe) {
    Escribir-Fallo 'No encuentro Godot 4.7.2. Pásalo con -Godot "C:\ruta\Godot_v4.7.2-stable_win64.exe"'
    if ($servidor -and -not $servidor.HasExited) { Stop-Process -Id $servidor.Id -Force }
    exit 1
}

Write-Host ''
Write-Host '  Guion del demo:' -ForegroundColor White
Write-Host '   1. LucIA te recibe y te propone crear tu cuenta.' -ForegroundColor DarkGray
Write-Host '   2. Escribe un nick de 10 a 15 letras y pulsa "Crear mi cuenta".' -ForegroundColor DarkGray
Write-Host '   3. La cadena mina un bloque: ese hash ES tu cuenta. Descarga tu .zip.' -ForegroundColor DarkGray
Write-Host '   4. Elige avatar, confirma el registro y cruza el portal.' -ForegroundColor DarkGray
Write-Host '   5. Ya estás en tu isla. Cierra y vuelve: la cuenta se reconoce sola.' -ForegroundColor DarkGray
Write-Host ''

Escribir-Paso "Abriendo el proyecto en el EDITOR de Godot…"
$procGodot = $null
if ($Editor) {
    # El ejecutable de Godot tambien es editor: con --editor abre el proyecto,
    # no el Project Manager. El servidor sigue vivo mientras el editor este abierto.
    $procGodot = Start-Process -FilePath $godotExe -ArgumentList @('--editor', '--path', $PROYECTO) -PassThru
} else {
    Escribir-Paso "Abriendo el mundo (servidor local)…"
    $procGodot = Start-Process -FilePath $godotExe -ArgumentList @('--path', $PROYECTO, '--', '--server') -PassThru
}

if ($procGodot) { $procGodot.WaitForExit() }

if ($servidor -and -not $servidor.HasExited) {
    Escribir-Paso 'Cerrando el servidor de cuentas…'
    Stop-Process -Id $servidor.Id -Force -ErrorAction SilentlyContinue
}

Write-Host ''
Escribir-Bien 'Demo cerrado.'
Write-Host ("  Cuenta del jugador : " + $USUARIO) -ForegroundColor DarkGray
Write-Host ("  Ledger del demo    : " + (Join-Path $DEMO 'ledger.json')) -ForegroundColor DarkGray
Write-Host ("  Logs               : " + $LOGS) -ForegroundColor DarkGray
Write-Host ''
