# ============================================================================
#  Empaquetado volátil del visor — genera actualizacion_v<Versión>.zip
# ----------------------------------------------------------------------------
#  Produce el .zip que se incrusta como recurso embebido en el .exe:
#     mundo/wvp3d.pck        Mundo Godot compilado (PCK)
#     lucia/                 Modelos y datasets de Lucía (TTS + IA local)
#     config/                cuenta.json + sesion.yaml + version.json
#     manifest.json          SHA-256 + tamaños de cada entrada (verificación)
#
#  Uso:
#     .\empaquetar_actualizacion.ps1
#     .\empaquetar_actualizacion.ps1 -Version 2.8.1 -PckPath ..\..\VSC#\Visor3Ddesarrollo\wvp3d.pck
#     .\empaquetar_actualizacion.ps1 -SkipLucia   (zip solo mundo + config)
# ============================================================================
param(
    [string]$Version   = "2.8.2",
    # Raiz del arbol src (VSC#, STM_HRTS, LC_STM...). Ruta absoluta del proyecto
    # y, si no existe, la relativa a este script (STM_HRTS\empaquetado -> ..\.. = src).
    [string]$SrcRoot   = $(if (Test-Path 'E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src') { 'E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src' } else { (Join-Path $PSScriptRoot '..\..') }),
    [string]$PckPath   = (Join-Path $SrcRoot 'VSC#\Visor3Ddesarrollo\wvp3d.pck'),
    [string]$LuciaRoot = $SrcRoot,
    [string]$OutputZip = (Join-Path $SrcRoot "VSC#\Visor3Ddesarrollo\actualizacion_v$Version.zip"),
    [switch]$SkipLucia
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Resolver-Ruta([string]$p) {
    if ([System.IO.Path]::IsPathRooted($p)) {
        return [System.IO.Path]::GetFullPath($p)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $p))
}

$PckPath   = Resolver-Ruta $PckPath
$LuciaRoot = Resolver-Ruta $LuciaRoot
$OutputZip = Resolver-Ruta $OutputZip

$Staging = Join-Path ([System.IO.Path]::GetTempPath()) ("wvp_empaquetado_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Staging -Force | Out-Null

try {
    # ── 1. Mundo ─────────────────────────────────────────────────────────
    if (Test-Path $PckPath) {
        $mundoDir = Join-Path $Staging "mundo"
        New-Item -ItemType Directory -Path $mundoDir -Force | Out-Null
        Copy-Item $PckPath (Join-Path $mundoDir "wvp3d.pck") -Force
        Write-Host ("[1/5] PCK: " + (Get-Item $PckPath).Length + " bytes -> mundo/wvp3d.pck")
    } else {
        Write-Host "[1/5] PCK: no encontrado en $PckPath (paquete volátil en modo desarrollo/proyecto)"
    }

    # ── 2. Lucía (modelos IA + redes neuronales + blockchain + chat + docs) ─
    if (-not $SkipLucia) {
        $luciaDir = Join-Path $Staging "lucia"
        $mapas = @(
            @{ Origen = "STM_IA\modelosIAlocal";  Destino = "IALOCAL" },
            @{ Origen = "LC_STM\seq2seq";         Destino = "seq2seq" },
            @{ Origen = "LC_STM\red_neuronal";    Destino = "red_neuronal" },
            @{ Origen = "STM_BKCH";               Destino = "STM_BKCH" },
            @{ Origen = "STM_CH";                 Destino = "STM_CH" },
            @{ Origen = "STM_HRTS";               Destino = "STM_HRTS" },
            @{ Origen = "STM_DOC";                Destino = "STM_DOC" }
        )
        foreach ($m in $mapas) {
            $origen = Join-Path $LuciaRoot $m.Origen
            if (-not (Test-Path $origen)) {
                Write-Warning "Carpeta de Lucía no encontrada (se omite): $origen"
                continue
            }
            $destino = Join-Path $luciaDir $m.Destino
            New-Item -ItemType Directory -Path (Split-Path $destino -Parent) -Force | Out-Null
            # Copia hijo a hijo para no atravesar los enlaces al almacen local
            # (_aux, _archivo_ipfs, docs): no deben viajar en el OTA.
            # Solo STM_HRTS aloja enlaces y almacÃ©n local; STM_DOC\docs es contenido real.
            $excluir = if ($m.Origen -eq 'STM_HRTS') { @('_aux', '_archivo_ipfs', 'docs') } else { @() }
            New-Item -ItemType Directory -Path $destino -Force | Out-Null
            foreach ($hijo in (Get-ChildItem -LiteralPath $origen -Force)) {
                if ($excluir -contains $hijo.Name) {
                    Write-Host ("[2/5] excluido del paquete: " + $m.Destino + "/" + $hijo.Name)
                    continue
                }
                Copy-Item -LiteralPath $hijo.FullName -Destination $destino -Recurse -Force
            }
            Write-Host ("[2/5] Lucía: " + $m.Origen + " -> lucia/" + $m.Destino)
        }
    } else {
        Write-Host "[2/5] Lucía: omitida (--SkipLucia)"
    }

    # ── 3. Configuración (plantillas en RAM; nunca se escriben sueltas) ──
    $configDir = Join-Path $Staging "config"
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null

    @'
{
  "cuenta_hash": "",
  "fecha_alta": "",
  "nick": "",
  "red": "WoldVirtualP2P3D",
  "avatar_scene": "res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH2Ch3D.tscn"
}
'@ | Set-Content -Path (Join-Path $configDir "cuenta.json") -Encoding UTF8

    @'
# Configuración de sesión volátil — se monta en RAM y se libera al cerrar.
red: WoldVirtualP2P3D
motor: Godot 4.7.2
modo: volatile
peer_url: ""
host_sesion: ""
invitacion: ""
'@ | Set-Content -Path (Join-Path $configDir "sesion.yaml") -Encoding UTF8

    @{
        version      = $Version
        empaquetado  = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        formato      = "zip-embebido"
        modo         = "volatile"
        motor        = "Godot 4.7.2"
        pck          = "mundo/wvp3d.pck"
    } | ConvertTo-Json | Set-Content -Path (Join-Path $configDir "version.json") -Encoding UTF8
    Write-Host "[3/5] Config: config/cuenta.json + sesion.yaml + version.json"

    # ── 4. Manifiesto (SHA-256 + tamaños) ────────────────────────────────
    $entradas = @()
    Get-ChildItem -Path $Staging -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($Staging.Length).TrimStart('\', '/').Replace('\', '/')
        $hash = (Get-FileHash -Path $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $entradas += [pscustomobject]@{
            ruta      = $rel
            sha256    = $hash
            bytes     = $_.Length
        }
    }
    $manifiesto = [ordered]@{
        version  = $Version
        creado   = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        total_bytes = ($entradas | Measure-Object -Property bytes -Sum).Sum
        archivos = $entradas
    }
    $manifiesto | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $Staging "manifest.json") -Encoding UTF8
    Write-Host ("[4/5] Manifest: " + $entradas.Count + " entradas, " + $manifiesto.total_bytes + " bytes totales")

    # ── 5. Comprimir ─────────────────────────────────────────────────────
    if (Test-Path -LiteralPath $OutputZip) { Remove-Item -LiteralPath $OutputZip -Force }
    [System.IO.Compression.ZipFile]::CreateFromDirectory($Staging, $OutputZip, [System.IO.Compression.CompressionLevel]::Optimal, $false)
    $zipSize = (Get-Item -LiteralPath $OutputZip).Length
    Write-Host ("[5/5] ZIP generado: " + $OutputZip + " (" + $zipSize + " bytes)")
}
finally {
    Remove-Item $Staging -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Siguiente paso: copiar el .zip a VSC# y recompilar con"
Write-Host "  dotnet publish -c Release -r win-x64 --self-contained true"
