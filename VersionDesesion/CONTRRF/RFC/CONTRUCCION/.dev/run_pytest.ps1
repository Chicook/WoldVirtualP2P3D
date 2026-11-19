$devDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $devDir "venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    $py = Join-Path $devDir ".python\python.exe"
}
$env:PYTEST_ADDOPTS = "-o cache_dir=$devDir\.pytest_cache -c $devDir\pytest.ini"
& $py (Join-Path $devDir "gestor_entorno.py") pytest $args
