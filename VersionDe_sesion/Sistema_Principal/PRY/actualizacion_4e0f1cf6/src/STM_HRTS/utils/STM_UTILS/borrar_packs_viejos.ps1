# Borra packs viejos de .git (no usados por HEAD). Ejecutar con Cursor cerrado si falla.
$ErrorActionPreference = 'Continue'
$packDir = 'F:\WoldVirtualP2P3D\.git\objects\pack'
$keepPrefix = 'pack-4342deec480f14ddea627c2bcf9ed0d189148c43'
$targets = @(
  'pack-2a22392ea44a1c52dbcb99a597ab4396a5f8303c.pack',
  'pack-2a22392ea44a1c52dbcb99a597ab4396a5f8303c.idx',
  'pack-a4ff8d9f4427c63efab0731a3101fe0babd6506a.pack',
  'pack-a4ff8d9f4427c63efab0731a3101fe0babd6506a.idx'
)

Write-Host "Keep: $keepPrefix*"
Write-Host "Pack dir: $packDir"
Write-Host 'Before:'
Get-ChildItem $packDir -Force | ForEach-Object { '{0,8:N2} MB  {1}' -f ($_.Length/1MB), $_.Name }

$deadline = (Get-Date).AddMinutes(2)
foreach ($name in $targets) {
  $p = Join-Path $packDir $name
  $ok = $false
  while ((Get-Date) -lt $deadline) {
    try {
      if (-not (Test-Path -LiteralPath $p)) { $ok = $true; break }
      $item = Get-Item -LiteralPath $p -Force
      $item.Attributes = 'Normal'
      Remove-Item -LiteralPath $p -Force -ErrorAction Stop
      if (-not (Test-Path -LiteralPath $p)) { $ok = $true; break }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  if ($ok) { Write-Host "OK deleted $name" } else { Write-Host "FAIL still locked: $name" }
}

Write-Host 'After:'
Get-ChildItem $packDir -Force | ForEach-Object { '{0,8:N2} MB  {1}' -f ($_.Length/1MB), $_.Name }

$gitSize = (Get-ChildItem 'F:\WoldVirtualP2P3D\.git' -Recurse -Force -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum
$workSize = (Get-ChildItem 'F:\WoldVirtualP2P3D' -Recurse -Force -File -EA SilentlyContinue | Where-Object { $_.FullName -notmatch '\\.git\\' } | Measure-Object Length -Sum).Sum
$total = $gitSize + $workSize
Write-Host ("TOTAL_MB={0:N2} bytes={1} UNDER_1GB={2}" -f ($total/1MB), $total, ($total -lt 1GB))
git -C F:\WoldVirtualP2P3D rev-parse HEAD
git -C F:\WoldVirtualP2P3D count-objects -vH
Write-Host 'Listo. Puedes volver a abrir Cursor.'
