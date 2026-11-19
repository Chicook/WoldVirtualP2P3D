# Localiza el árbol activo incluso cuando este lanzador viaja en
# Visor3Ddesarrollo\Actualizaciones\<versión> junto al ejecutable.
$src = $null
$cursor = [System.IO.Path]::GetFullPath($PSScriptRoot)
for ($i = 0; $i -lt 12 -and $cursor; $i++) {
    if (Test-Path (Join-Path $cursor "MTBGT\WoldVirtualP2P3D\project.godot")) {
        $src = $cursor
        break
    }
    $srcCandidate = Join-Path $cursor "src\MTBGT\WoldVirtualP2P3D\project.godot"
    if (Test-Path $srcCandidate) {
        $src = Join-Path $cursor "src"
        break
    }
    $parent = Split-Path $cursor -Parent
    if ($parent -eq $cursor) { break }
    $cursor = $parent
}
if (-not $src) {
    $src = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
}

# El Python privado del taller permanece fuera del .exe; nunca usa el Python del sistema.
$devDir = if ($src) {
    # Cada ruta va en su propia linea: con PowerShell 5.1 una coma final
    # convierte el siguiente Join-Path en parte de ChildPath y rompe el script.
    $candidatosDev = @(
        (Join-Path (Split-Path (Split-Path $src -Parent) -Parent) ".dev")
        (Join-Path (Split-Path $src -Parent) ".dev")
        (Join-Path $PSScriptRoot "..\..\..\..\..\.dev")
    )
    $encontrado = ""
    foreach ($c in $candidatosDev) {
        if (Test-Path $c) { $encontrado = [System.IO.Path]::GetFullPath($c); break }
    }
    $encontrado
} else { "" }

$py = if ($devDir) { Join-Path $devDir ".python\pythonw.exe" } else { "" }
if (-not (Test-Path $py) -and $devDir) { $py = Join-Path $devDir ".python\python.exe" }
if (-not (Test-Path $py) -and $devDir) { $py = Join-Path $devDir "venv\Scripts\pythonw.exe" }
if (-not (Test-Path $py) -and $devDir) { $py = Join-Path $devDir "venv\Scripts\python.exe" }
if (-not (Test-Path $py) -and $env:WVP_PYTHON -and (Test-Path $env:WVP_PYTHON)) { $py = $env:WVP_PYTHON }
if (-not (Test-Path $py) -and $src) { $py = Join-Path $src "LC_STM\python\pythonw.exe" }
if (-not (Test-Path $py) -and $src) { $py = Join-Path $src "LC_STM\python\python.exe" }

$srv = if ($src) { Join-Path $src "MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py" } else { "" }
$logDir = Join-Path $env:LOCALAPPDATA "WoldVirtualP2P3D\logs"
New-Item -ItemType Directory -Force -Path $logDir -ErrorAction SilentlyContinue | Out-Null
$log = Join-Path $logDir "lucia_ps.log"

if ([string]::IsNullOrWhiteSpace($py) -or -not (Test-Path $py)) {
    "No se encontró el Python privado de LucIA (.dev)." | Set-Content -LiteralPath "$log.err"
    exit 2
}
if ([string]::IsNullOrWhiteSpace($srv) -or -not (Test-Path $srv)) {
    "No se encontró servidor_lucia.py en el árbol activo." | Set-Content -LiteralPath "$log.err"
    exit 3
}

# Esta opción válida omite la precarga del modelo y deja activa la voz.
$child = Start-Process -FilePath $py -ArgumentList @("`"$srv`"", "--modelo", "qwen2.5:7b", "--puerto", "8765", "--sin-precalentar", "--sin-precarga-voz") -WorkingDirectory (Split-Path $srv) -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err"
if (-not $child) {
    "No se pudo iniciar el proceso de LucIA." | Set-Content -LiteralPath "$log.err"
    exit 4
}
exit $child.ExitCode
