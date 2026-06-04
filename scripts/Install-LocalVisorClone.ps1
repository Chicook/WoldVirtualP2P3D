[CmdletBinding()]
param(
    [string]$SourceRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path,
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "WoldVirtual\LocalClone"),
    [switch]$Run,
    [switch]$IncludeRuntimeState
)

$ErrorActionPreference = "Stop"

function Assert-RobocopySuccess {
    param([int]$ExitCode)

    if ($ExitCode -gt 7) {
        throw "Robocopy fallo con codigo $ExitCode"
    }
}

$sourcePath = (Resolve-Path -LiteralPath $SourceRoot).Path
$installPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($InstallRoot)

if ($sourcePath.TrimEnd('\') -ieq $installPath.TrimEnd('\')) {
    throw "El origen y el destino no pueden ser el mismo directorio."
}

New-Item -ItemType Directory -Force -Path $installPath | Out-Null

$excludeDirs = @(
    (Join-Path $sourcePath ".git")
)

$excludeFiles = @()

if (-not $IncludeRuntimeState) {
    $excludeDirs += (Join-Path $sourcePath "WoldVirtual\Estado_Global\peers")
    $excludeFiles += "current_user.json"
}

$robocopyArgs = @(
    $sourcePath,
    $installPath,
    "/E",
    "/R:2",
    "/W:1",
    "/NFL",
    "/NDL",
    "/NP"
)

if ($excludeDirs.Count -gt 0) {
    $robocopyArgs += "/XD"
    $robocopyArgs += $excludeDirs
}

if ($excludeFiles.Count -gt 0) {
    $robocopyArgs += "/XF"
    $robocopyArgs += $excludeFiles
}

Write-Host "Creando clon local del visor..."
Write-Host "Origen : $sourcePath"
Write-Host "Destino: $installPath"

& robocopy.exe @robocopyArgs | Out-Host
Assert-RobocopySuccess -ExitCode $LASTEXITCODE

$instanceInfo = [ordered]@{
    createdAt = (Get-Date).ToString("o")
    source = $sourcePath
    installPath = $installPath
    machineName = $env:COMPUTERNAME
    userName = $env:USERNAME
    includesRuntimeState = [bool]$IncludeRuntimeState
    preservesGodotCache = $true
}

$instanceInfoPath = Join-Path $installPath "local_instance.json"
$instanceInfo | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $instanceInfoPath -Encoding UTF8

$prepareScript = Join-Path $installPath "scripts\Prepare-LocalVisor.ps1"
if (-not (Test-Path -LiteralPath $prepareScript -PathType Leaf)) {
    throw "No se encontro el script de preparacion en el clon local: $prepareScript"
}

Write-Host "Preparando clon como archivos locales..."
& powershell.exe -NoProfile -File $prepareScript -Root $installPath -Run:$Run

Write-Host "Clon local listo."
Write-Host "Manifest: $instanceInfoPath"
