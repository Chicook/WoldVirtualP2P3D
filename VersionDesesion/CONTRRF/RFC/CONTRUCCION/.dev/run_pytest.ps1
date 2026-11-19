$devDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $devDir "venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    $py = Join-Path $devDir ".python\python.exe"
}
& $py (Join-Path $devDir "gestor_entorno.py") pytest $args
