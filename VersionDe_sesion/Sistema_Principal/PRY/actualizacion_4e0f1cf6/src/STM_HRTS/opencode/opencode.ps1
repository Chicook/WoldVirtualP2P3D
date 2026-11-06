$basedir = Split-Path $MyInvocation.MyCommand.Definition -Parent
$exePath = Join-Path $basedir "opencode.exe"
if (-not (Test-Path $exePath)) {
    $exePath = Join-Path $basedir "node_modules\opencode-ai\bin\opencode.exe"
}

if (Test-Path $exePath) {
    & $exePath @args
} else {
    & opencode @args
}
exit $LASTEXITCODE
