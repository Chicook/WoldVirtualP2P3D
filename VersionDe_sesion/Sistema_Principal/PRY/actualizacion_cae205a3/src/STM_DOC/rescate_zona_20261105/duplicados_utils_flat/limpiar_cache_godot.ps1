# Limpia la cache de Godot sin afectar el contenido del proyecto.
# Borra SOLO imports huerfanos de .godot\imported (los que ya no referencia
# ningun .import) + cachés regenerables (shader_cache, editor).
# Los .ctex en uso NO se tocan.
param(
    [string]$ProjectPath = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$proj = (Resolve-Path -LiteralPath $ProjectPath).Path
$godot = Join-Path $proj '.godot'
if (-not (Test-Path -LiteralPath $godot)) {
    Write-Host "[cache] No existe $godot (nada que limpiar)"
    exit 0
}
$imp = Join-Path $godot 'imported'

$referenced = New-Object 'System.Collections.Generic.HashSet[string]'
Get-ChildItem -LiteralPath $proj -Recurse -File -Filter *.import -ErrorAction SilentlyContinue | ForEach-Object {
    $txt = Get-Content -LiteralPath $_.FullName -Raw
    foreach ($m in [regex]::Matches($txt, 'res://\.godot/imported/([^",\]\s]+)')) {
        $fn = $m.Groups[1].Value.Trim()
        [void]$referenced.Add($fn)
        [void]$referenced.Add([IO.Path]::GetFileNameWithoutExtension($fn) + '.md5')
    }
}

$orph = 0; $orphBytes = 0
if (Test-Path -LiteralPath $imp) {
    Get-ChildItem -LiteralPath $imp -File -ErrorAction SilentlyContinue | ForEach-Object {
        if (-not $referenced.Contains($_.Name)) {
            $orph++; $orphBytes += $_.Length
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
        }
    }
}

foreach ($sub in 'shader_cache', 'editor') {
    $p = Join-Path $godot $sub
    if (Test-Path -LiteralPath $p) {
        Get-ChildItem -LiteralPath $p -Force -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

$total = (Get-ChildItem -LiteralPath $proj -Recurse -File -Force -ErrorAction SilentlyContinue |
          Measure-Object Length -Sum).Sum
Write-Host ("[cache] huerfanos borrados: {0} ({1:N1} MB)  |  proyecto: {2:N0} MB" -f $orph, ($orphBytes / 1MB), ($total / 1MB))
