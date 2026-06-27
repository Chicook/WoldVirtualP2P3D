# Script de verificación de compilación y contratos de identidad
$ErrorActionPreference = "Stop"

Write-Host "=== Iniciando Verificación de Compilación ===" -ForegroundColor Cyan

$projectPath = Join-Path $PSScriptRoot "..\Capa3_Visor\CapaVisor3D\VisorSingularity.csproj"
dotnet build $projectPath --configuration Debug

if ($LASTEXITCODE -ne 0) {
    Write-Error "Error de compilación en el visor."
    exit 1
}

Write-Host "✅ Compilación exitosa." -ForegroundColor Green
Write-Host "=== Iniciando Verificación de Contratos y Seguridad ===" -ForegroundColor Cyan

# Comprobar que los archivos de contrato e identidad existen en el código fuente
$filesToCheck = @(
    "..\Capa3_Visor\CapaVisor3D\Services\NodeIdentity.cs",
    "..\Capa3_Visor\CapaVisor3D\Services\NodeIdentityManager.cs",
    "..\Capa3_Visor\CapaVisor3D\p2pipfsCS\PeerStateContract.cs"
)

foreach ($file in $filesToCheck) {
    $path = Join-Path $PSScriptRoot $file
    if (Test-Path $path) {
        Write-Host "  [OK] Encontrado: $(Split-Path $path -Leaf)" -ForegroundColor Green
    } else {
        Write-Error "  [ERROR] Falta archivo crítico: $file"
        exit 1
    }
}

Write-Host "✅ Verificación de archivos completada." -ForegroundColor Green
Write-Host "=== Todos los chequeos pasaron con éxito ===" -ForegroundColor Green
