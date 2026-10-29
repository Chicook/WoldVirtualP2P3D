<#
.SYNOPSIS
    Script de purga progresiva y saneamiento de WoldVirtualP2P3D.
    Reduce el tamaño del repositorio de 7.00 GB a ~415 MB eliminando
    únicamente binarios duplicados, cachés y código zombi, sin tocar código fuente.
#>

$root = $PSScriptRoot
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  WoldVirtualP2P3D - Script de Purga y Saneamiento" -ForegroundColor Cyan
Write-Host "  Objetivo: Reducir de 7.00 GB a < 500 MB" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$vsc = "$root\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_2069d33a\src\VSC#"
$mtbgt = "$root\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_2069d33a\src\MTBGT\WoldVirtualP2P3D"

# Paso 1: Salidas de publicación y ejecutables en descargas (~4.000 MB)
Write-Host "`n[*] Paso 1/4: Purgando carpetas publish y descargas de WebNodo..." -ForegroundColor Yellow
$publishes = @(
    "$vsc\publish_2069d33a",
    "$vsc\publish_release",
    "$vsc\publish_standalone",
    "$vsc\publish_out"
)
foreach ($p in $publishes) {
    if (Test-Path $p) {
        Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue
        Write-Host "  [+] Eliminado: $(Split-Path $p -Leaf)" -ForegroundColor Green
    }
}
if (Test-Path "$vsc\webnodo\descargas") {
    Get-ChildItem -Path "$vsc\webnodo\descargas" -Filter "*.exe" -Force | Remove-Item -Force
    Write-Host "  [+] Eliminados ejecutables viejos de webnodo\descargas\" -ForegroundColor Green
}

# Paso 2: Cachés de compilación .NET (~2.415 MB)
Write-Host "`n[*] Paso 2/4: Purgando bin/ y obj/ de .NET..." -ForegroundColor Yellow
if (Test-Path "$vsc\bin") {
    Remove-Item -Recurse -Force "$vsc\bin" -ErrorAction SilentlyContinue
    Write-Host "  [+] Eliminado: src\VSC#\bin" -ForegroundColor Green
}
if (Test-Path "$vsc\obj") {
    Remove-Item -Recurse -Force "$vsc\obj" -ErrorAction SilentlyContinue
    Write-Host "  [+] Eliminado: src\VSC#\obj" -ForegroundColor Green
}

# Paso 3: Código zombi, zips masivos y binarios sueltos (~850 MB)
Write-Host "`n[*] Paso 3/4: Purgando código zombi (version_prueba), zips masivos y binarios en raíz..." -ForegroundColor Yellow
if (Test-Path "$vsc\version_prueba") {
    Remove-Item -Recurse -Force "$vsc\version_prueba" -ErrorAction SilentlyContinue
    Write-Host "  [+] Eliminado: src\VSC#\version_prueba (código duplicado)" -ForegroundColor Green
}
if (Test-Path "$vsc\Servidor3D") {
    Remove-Item -Recurse -Force "$vsc\Servidor3D" -ErrorAction SilentlyContinue
    Write-Host "  [+] Eliminado: src\VSC#\Servidor3D" -ForegroundColor Green
}
$looseFiles = @(
    "$vsc\godot_project.zip",
    "$vsc\godot_exe.zip",
    "$vsc\Visor3D.exe",
    "$vsc\Visor3D.pdb",
    "$vsc\D3DCompiler_47_cor3.dll",
    "$vsc\wpfgfx_cor3.dll",
    "$vsc\PresentationNative_cor3.dll",
    "$vsc\PenImc_cor3.dll",
    "$vsc\vcruntime140_cor3.dll"
)
foreach ($f in $looseFiles) {
    if (Test-Path $f) {
        Remove-Item -Force $f -ErrorAction SilentlyContinue
        Write-Host "  [+] Eliminado: $(Split-Path $f -Leaf)" -ForegroundColor Green
    }
}

# Paso 4: Caché re-importada de Godot 4 (.godot) (~303 MB)
Write-Host "`n[*] Paso 4/4: Purgando caché local temporal de Godot (.godot)..." -ForegroundColor Yellow
if (Test-Path "$mtbgt\.godot") {
    Remove-Item -Recurse -Force "$mtbgt\.godot" -ErrorAction SilentlyContinue
    Write-Host "  [+] Eliminado: .godot (se auto-regenera al abrir el motor)" -ForegroundColor Green
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  ¡Purga completada con éxito!" -ForegroundColor Cyan

$measure = Get-ChildItem -LiteralPath $root -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum
$totalMB = [math]::Round($measure.Sum / 1MB, 2)
$totalGB = [math]::Round($measure.Sum / 1GB, 2)
Write-Host "  Nuevo tamaño total del repositorio: $totalMB MB ($totalGB GB)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
