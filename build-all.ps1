# Script de compilación automática para WoldVirtual P2P 3D
# Este script compila el proyecto completo al descomprimir en otra máquina
# Fecha: 26 de mayo de 2026
# Autor: DevTraeIA

param(
    [switch]$CheckOnly = $false,
    [switch]$SkipGodotCheck = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"
$script:StartTime = Get-Date
$script:Success = $true
$script:LogFile = "build-log-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"

# Colores para output
$ColorSuccess = "Green"
$ColorWarning = "Yellow"
$ColorError = "Red"
$ColorInfo = "Cyan"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    
    # Escribir a archivo
    Add-Content -Path $script:LogFile -Value $logEntry
    
    # Mostrar en consola con colores
    switch ($Level) {
        "SUCCESS" { Write-Host $logEntry -ForegroundColor $ColorSuccess }
        "WARNING" { Write-Host $logEntry -ForegroundColor $ColorWarning }
        "ERROR" { Write-Host $logEntry -ForegroundColor $ColorError }
        "INFO" { 
            if ($script:Verbose -or $Level -eq "INFO") {
                Write-Host $logEntry -ForegroundColor $ColorInfo 
            }
        }
        default { Write-Host $logEntry }
    }
}

function Test-Requirements {
    Write-Log "Verificando requisitos del sistema..."
    
    # 1. Verificar sistema operativo
    if (-not $IsWindows) {
        Write-Log "ERROR: Este proyecto requiere Windows" "ERROR"
        return $false
    }
    Write-Log "✓ Sistema operativo: Windows" "SUCCESS"
    
    # 2. Verificar .NET 8 SDK
    $dotnetInfo = dotnet --info 2>$null
    if (-not $dotnetInfo) {
        Write-Log "ERROR: .NET SDK no encontrado" "ERROR"
        return $false
    }
    
    $dotnetVersion = $dotnetInfo | Select-String "Version:\s*(\d+\.\d+\.\d+)"
    if ($dotnetVersion.Matches.Groups[1].Value -lt "8.0") {
        Write-Log "ERROR: Se requiere .NET 8 SDK o superior" "ERROR"
        return $false
    }
    Write-Log "✓ .NET SDK: $($dotnetVersion.Matches.Groups[1].Value)" "SUCCESS"
    
    # 3. Verificar estructura de directorios
    $requiredDirs = @(
        "Capa3_Visor\CapaVisor3D",
        "WoldVirtual",
        "WoldVirtual\servidorinterno",
        "WoldVirtual\woldvirtual",
        "WoldVirtual\Estado_Global"
    )
    
    foreach ($dir in $requiredDirs) {
        if (-not (Test-Path $dir)) {
            Write-Log "ERROR: Directorio faltante: $dir" "ERROR"
            return $false
        }
    }
    Write-Log "✓ Estructura de directorios completa" "SUCCESS"
    
    # 4. Verificar Godot ejecutable (opcional)
    if (-not $SkipGodotCheck) {
        $godotExe = "WoldVirtual\servidorinterno\Godot_v4.6.2-stable_mono_win64.exe"
        if (-not (Test-Path $godotExe)) {
            Write-Log "ADVERTENCIA: Ejecutable de Godot no encontrado: $godotExe" "WARNING"
            Write-Log "El proyecto puede funcionar pero el motor 3D no estará disponible" "WARNING"
        } else {
            Write-Log "✓ Ejecutable de Godot encontrado" "SUCCESS"
        }
    }
    
    # 5. Verificar puertos disponibles
    $requiredPorts = @(8080, 8082, 50007, 50008)
    $busyPorts = @()
    
    foreach ($port in $requiredPorts) {
        try {
            $listener = [System.Net.Sockets.TcpListener]$port
            $listener.Start()
            $listener.Stop()
        } catch {
            $busyPorts += $port
        }
    }
    
    if ($busyPorts.Count -gt 0) {
        Write-Log "ADVERTENCIA: Puertos ocupados: $($busyPorts -join ', ')" "WARNING"
        Write-Log "El proyecto puede requerir liberar estos puertos o cambiar configuración" "WARNING"
    } else {
        Write-Log "✓ Todos los puertos requeridos están disponibles" "SUCCESS"
    }
    
    return $true
}

function Build-WPFProject {
    Write-Log "Compilando proyecto WPF (.NET 8)..."
    
    $projectPath = "Capa3_Visor\CapaVisor3D\VisorSingularity.csproj"
    
    if (-not (Test-Path $projectPath)) {
        Write-Log "ERROR: Archivo de proyecto no encontrado: $projectPath" "ERROR"
        return $false
    }
    
    # Limpiar builds anteriores
    Write-Log "Limpiando builds anteriores..."
    $cleanOutput = dotnet clean $projectPath --configuration Debug 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log "ADVERTENCIA: Error al limpiar proyecto: $cleanOutput" "WARNING"
    }
    
    # Compilar proyecto
    Write-Log "Compilando proyecto..."
    $buildOutput = dotnet build $projectPath --configuration Debug --verbosity minimal 2>&1
    $buildResult = $LASTEXITCODE
    
    if ($buildResult -eq 0) {
        Write-Log "✓ Proyecto WPF compilado exitosamente" "SUCCESS"
        
        # Verificar archivos de salida
        $outputDir = "Capa3_Visor\CapaVisor3D\bin\Debug\net8.0-windows"
        if (Test-Path $outputDir) {
            $exeFile = Get-ChildItem $outputDir -Filter "*.exe" | Select-Object -First 1
            if ($exeFile) {
                Write-Log "✓ Ejecutable generado: $($exeFile.FullName)" "SUCCESS"
                Write-Log "Tamaño: $([math]::Round($exeFile.Length/1MB, 2)) MB" "INFO"
            }
        }
        
        return $true
    } else {
        Write-Log "ERROR: Error al compilar proyecto WPF" "ERROR"
        Write-Log "Salida del compilador:" "ERROR"
        $buildOutput | ForEach-Object { Write-Log $_ "ERROR" }
        return $false
    }
}

function Validate-GodotProject {
    Write-Log "Validando proyecto Godot..."
    
    $godotProject = "WoldVirtual\project.godot"
    if (-not (Test-Path $godotProject)) {
        Write-Log "ERROR: Archivo de proyecto Godot no encontrado" "ERROR"
        return $false
    }
    
    # Verificar archivos esenciales de Godot
    $essentialFiles = @(
        "WoldVirtual\EscenaPrincipal.tscn",
        "WoldVirtual\woldvirtual\scene\MTC\N3DWoldVirtualMT.tscn",
        "WoldVirtual\woldvirtual\gdscrip\WorldManager.gd",
        "WoldVirtual\woldvirtual\gdscrip\NetworkLayer.gd",
        "WoldVirtual\woldvirtual\scene\MTC\RegistroAV.gd"
    )
    
    $missingFiles = @()
    foreach ($file in $essentialFiles) {
        if (-not (Test-Path $file)) {
            $missingFiles += $file
        }
    }
    
    if ($missingFiles.Count -gt 0) {
        Write-Log "ADVERTENCIA: Archivos Godot faltantes: $($missingFiles.Count)" "WARNING"
        foreach ($file in $missingFiles) {
            Write-Log "  - $file" "WARNING"
        }
        Write-Log "El proyecto puede no funcionar correctamente" "WARNING"
    } else {
        Write-Log "✓ Proyecto Godot validado correctamente" "SUCCESS"
    }
    
    return $true
}

function Generate-BuildReport {
    $endTime = Get-Date
    $duration = $endTime - $script:StartTime
    
    Write-Log "=" * 60 "INFO"
    Write-Log "REPORTE DE CONSTRUCCIÓN" "INFO"
    Write-Log "=" * 60 "INFO"
    Write-Log "Fecha: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" "INFO"
    Write-Log "Duración: $($duration.TotalSeconds.ToString('0.00')) segundos" "INFO"
    Write-Log "Estado: $(if ($script:Success) {'ÉXITO' } else {'FALLIDO'})" $(if ($script:Success) {"SUCCESS" } else {"ERROR"})
    Write-Log "Log file: $script:LogFile" "INFO"
    
    # Información del sistema
    Write-Log "-" * 40 "INFO"
    Write-Log "INFORMACIÓN DEL SISTEMA:" "INFO"
    Write-Log "Sistema operativo: $([System.Environment]::OSVersion.VersionString)" "INFO"
    Write-Log "Arquitectura: $([System.Environment]::Is64BitOperatingSystem ? '64-bit' : '32-bit')" "INFO"
    Write-Log "Directorio de trabajo: $(Get-Location)" "INFO"
    
    # Verificar archivos generados
    Write-Log "-" * 40 "INFO"
    Write-Log "ARCHIVOS GENERADOS:" "INFO"
    
    $outputDir = "Capa3_Visor\CapaVisor3D\bin\Debug\net8.0-windows"
    if (Test-Path $outputDir) {
        $exeFiles = Get-ChildItem $outputDir -Filter "*.exe"
        $dllFiles = Get-ChildItem $outputDir -Filter "*.dll"
        
        Write-Log "Ejecutables: $($exeFiles.Count)" "INFO"
        Write-Log "Librerías: $($dllFiles.Count)" "INFO"
        
        if ($exeFiles.Count -gt 0) {
            $mainExe = $exeFiles | Where-Object { $_.Name -like "*Visor*" } | Select-Object -First 1
            if ($mainExe) {
                Write-Log "Ejecutable principal: $($mainExe.Name)" "SUCCESS"
                Write-Log "Ruta: $($mainExe.FullName)" "INFO"
            }
        }
    } else {
        Write-Log "Directorio de salida no encontrado" "WARNING"
    }
    
    # Recomendaciones
    Write-Log "-" * 40 "INFO"
    Write-Log "RECOMENDACIONES:" "INFO"
    
    if ($script:Success) {
        Write-Log "1. Ejecutar el proyecto: dotnet run --project Capa3_Visor\CapaVisor3D\VisorSingularity.csproj" "INFO"
        Write-Log "2. O ejecutar directamente: Capa3_Visor\CapaVisor3D\bin\Debug\net8.0-windows\VisorSingularity.exe" "INFO"
        Write-Log "3. Verificar puertos 8080, 8082, 50007 y 50008 están disponibles" "INFO"
    } else {
        Write-Log "1. Revisar el archivo de log: $script:LogFile" "INFO"
        Write-Log "2. Verificar que .NET 8 SDK esté instalado correctamente" "INFO"
        Write-Log "3. Asegurar estructura completa del proyecto" "INFO"
    }
}

# --- MAIN EXECUTION ---
try {
    Write-Log "Iniciando proceso de construcción de WoldVirtual P2P 3D"
    Write-Log "Directorio actual: $(Get-Location)"
    
    if ($CheckOnly) {
        Write-Log "Modo de verificación solamente" "INFO"
        $requirementsOk = Test-Requirements
        $godotOk = Validate-GodotProject
        
        if ($requirementsOk -and $godotOk) {
            Write-Log "✓ Todas las verificaciones pasaron correctamente" "SUCCESS"
            $script:Success = $true
        } else {
            Write-Log "✗ Algunas verificaciones fallaron" "ERROR"
            $script:Success = $false
        }
    } else {
        # Verificar requisitos primero
        if (-not (Test-Requirements)) {
            Write-Log "ERROR: Requisitos del sistema no cumplidos" "ERROR"
            $script:Success = $false
        } else {
            # Compilar proyecto WPF
            if (-not (Build-WPFProject)) {
                $script:Success = $false
            }
            
            # Validar proyecto Godot
            if (-not (Validate-GodotProject)) {
                # No marcamos como fallido, solo advertencia
                Write-Log "Proyecto Godot tiene problemas pero la construcción continúa" "WARNING"
            }
        }
    }
    
    # Generar reporte
    Generate-BuildReport
    
    # Estado final
    if ($script:Success) {
        Write-Log "¡CONSTRUCCIÓN COMPLETADA EXITOSAMENTE!" "SUCCESS"
        exit 0
    } else {
        Write-Log "CONSTRUCCIÓN FALLIDA" "ERROR"
        exit 1
    }
} catch {
    Write-Log "ERROR NO MANEJADO: $($_.Exception.Message)" "ERROR"
    Write-Log "Stack trace: $($_.ScriptStackTrace)" "ERROR"
    exit 2
}