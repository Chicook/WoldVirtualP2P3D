[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path,
    [switch]$Run,
    [switch]$IncludeAllFiles
)

$ErrorActionPreference = "Stop"

function Resolve-ViewerPath {
    param([string]$BasePath)

    $candidates = @(
        (Join-Path $BasePath "Capa3_Visor\CapaVisor3D\bin\Release\net8.0-windows\VisorSingularity.exe"),
        (Join-Path $BasePath "Capa3_Visor\CapaVisor3D\bin\Debug\net8.0-windows\VisorSingularity.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$scriptRepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

if (-not $rootPath.StartsWith($scriptRepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Por seguridad, este script solo puede preparar el visor dentro de su propio directorio extraido: $scriptRepoRoot"
}

$extensions = @(".exe", ".dll", ".ps1", ".cmd", ".html")
$files = Get-ChildItem -LiteralPath $rootPath -Recurse -File -Force

if (-not $IncludeAllFiles) {
    $files = $files | Where-Object { $extensions -contains $_.Extension.ToLowerInvariant() }
}

$count = 0
foreach ($file in $files) {
    if ($PSCmdlet.ShouldProcess($file.FullName, "Unblock-File")) {
        try {
            Unblock-File -LiteralPath $file.FullName -ErrorAction Stop
            $count++
        }
        catch {
            Write-Warning "No se pudo preparar: $($file.FullName) :: $($_.Exception.Message)"
        }
    }
}

Write-Host "Archivos preparados para ejecucion local: $count"

$viewerPath = Resolve-ViewerPath -BasePath $rootPath
if ($viewerPath -eq $null) {
    Write-Warning "No se encontro VisorSingularity.exe en bin\Release ni bin\Debug."
    exit 0
}

Write-Host "Visor localizado: $viewerPath"

if ($Run) {
    $workingDirectory = Split-Path -Parent $viewerPath
    Write-Host "Iniciando visor..."
    Start-Process -FilePath $viewerPath -WorkingDirectory $workingDirectory
}
else {
    Write-Host "Para arrancarlo ahora, ejecuta de nuevo con -Run."
}
