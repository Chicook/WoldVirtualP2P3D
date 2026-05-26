# Script simple de verificación de dependencias
Write-Host "Verificando dependencias para WoldVirtual P2P 3D"
Write-Host "Fecha: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host ""

# Verificar .NET SDK
Write-Host "1. Verificando .NET 8 SDK..."
try {
    $dotnetInfo = dotnet --info 2>$null
    if ($dotnetInfo) {
        Write-Host "   [OK] .NET SDK instalado" -ForegroundColor Green
    } else {
        Write-Host "   [ERROR] .NET SDK no encontrado" -ForegroundColor Red
    }
} catch {
    Write-Host "   [ERROR] Error al verificar .NET SDK" -ForegroundColor Red
}

# Verificar estructura del proyecto
Write-Host "`n2. Verificando estructura del proyecto..."
$requiredFiles = @(
    "Capa3_Visor\CapaVisor3D\VisorSingularity.csproj",
    "WoldVirtual\project.godot",
    "WoldVirtual\servidorinterno\Godot_v4.6.2-stable_mono_win64.exe",
    "WoldVirtual\woldvirtual\scene\MTC\N3DWoldVirtualMT.tscn"
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "   [OK] $file" -ForegroundColor Green
    } else {
        Write-Host "   [ERROR] $file no encontrado" -ForegroundColor Red
    }
}

Write-Host "`nVerificación completada"