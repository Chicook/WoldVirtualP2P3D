# Arbol activo (..\..\.. desde HerraMientas = TLLDCD\src) y archivo de versiones
# anteriores, donde vive el Python embebido que no se versiona.
$src = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
if (-not $env:WVP_LEGACY_SRC) {
    $env:WVP_LEGACY_SRC = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\..\..\..\..\..\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"))
    if (-not (Test-Path $env:WVP_LEGACY_SRC)) {
        $env:WVP_LEGACY_SRC = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\..\..\..\..\..\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"))
    }
}
$devDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\..\.dev"))
$py = Join-Path $devDir ".python\pythonw.exe"
if (-not (Test-Path $py)) { $py = Join-Path $devDir "venv\Scripts\pythonw.exe" }
if (-not (Test-Path $py)) { $py = Join-Path $src "LC_STM\python\pythonw.exe" }
if (-not (Test-Path $py)) { $py = Join-Path $env:WVP_LEGACY_SRC "LC_STM\python\pythonw.exe" }
$srv = Join-Path $src "MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
if (-not (Test-Path $srv)) { $srv = Join-Path $env:WVP_LEGACY_SRC "MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py" }
$log = Join-Path $env:LOCALAPPDATA "WoldVirtualP2P3D\logs\lucia_ps.log"
Start-Process -FilePath $py -ArgumentList @("`"$srv`"", "--modelo", "qwen2.5:7b", "--puerto", "8765", "--sin-precarga-voz") -WorkingDirectory (Split-Path $srv) -WindowStyle Hidden -Wait -RedirectStandardOutput $log -RedirectStandardError "$log.err"
