# Script de verificación de dependencias para WoldVirtual P2P 3D
# Verifica todos los requisitos necesarios para ejecutar el proyecto
# Fecha: 26 de mayo de 2026
# Autor: DevTraeIA

param(
    [switch]$Detailed = $false,
    [switch]$FixIssues = $false
)

$ErrorActionPreference = "Continue"
$script:AllChecksPassed = $true
$script:IssuesFound = @()

# Colores para output
$ColorSuccess = "Green"
$ColorWarning = "Yellow"
$ColorError = "Red"
$ColorInfo = "Cyan"

function Write-Status {
    param([string]$Message, [bool]$Passed, [string]$FixCommand = "")
    
    $status = if ($Passed) { "[OK]" } else { "[ERROR]" }
    $color = if ($Passed) { $ColorSuccess } else { $ColorError }
    
    Write-Host "$status $Message" -ForegroundColor $color
    
    if (-not $Passed -and $FixCommand -ne "" -and $Detailed) {
        Write-Host "   Solución: $FixCommand" -ForegroundColor $ColorInfo
    }
    
    if (-not $Passed) {
        $script:IssuesFound += $Message
        $script:AllChecksPassed = $false
    }
}

function Test-WindowsOS {
    Write-Host "`n1. VERIFICANDO SISTEMA OPERATIVO" -ForegroundColor $ColorInfo
    
    if (-not $IsWindows) {
        Write-Status "Sistema operativo no es Windows" $false "Este proyecto requiere Windows 10/11"
        return $false
    }
    
    $osInfo = Get-CimInstance -ClassName Win32_OperatingSystem
    $osName = $osInfo.Caption
    $osVersion = $osInfo.Version
    
    Write-Status "Sistema operativo: $osName (v$osVersion)" $true
    
    # Verificar versión mínima (Windows 10)
    $majorVersion = [int]$osVersion.Split('.')[0]
    if ($majorVersion -lt 10) {
        Write-Status "Versión de Windows demasiado antigua" $false "Actualizar a Windows 10 o superior"
        return $false
    }
    
    return $true
}

function Test-DotNetSDK {
    Write-Host "`n2. VERIFICANDO .NET 8 SDK" -ForegroundColor $ColorInfo
    
    # Intentar ejecutar dotnet
    try {
        $dotnetInfo = dotnet --info 2>$null
        if (-not $dotnetInfo) {
            Write-Status ".NET SDK no encontrado" $false "Descargar desde: https://dotnet.microsoft.com/download/dotnet/8.0"
            return $false
        }
        
        # Extraer versión
        $versionLine = $dotnetInfo | Select-String "Version:\s*(\d+\.\d+\.\d+)"
        if ($versionLine) {
            $dotnetVersion = $versionLine.Matches.Groups[1].Value
            Write-Status ".NET SDK instalado: v$dotnetVersion" $true
        } else {
            Write-Status "No se pudo determinar versión de .NET" $false "Reinstalar .NET SDK"
            return $false
        }
        
        # Verificar que sea .NET 8 o superior
        $majorVersion = [int]$dotnetVersion.Split('.')[0]
        if ($majorVersion -lt 8) {
            Write-Status ".NET SDK versión insuficiente (se requiere 8+)" $false "Actualizar a .NET 8 SDK"
            return $false
        }
        
        # Verificar runtime específico
        $runtimeCheck = dotnet --list-runtimes 2>$null | Select-String "Microsoft\.WindowsDesktop\.App"
        if (-not $runtimeCheck) {
            Write-Status "Runtime WindowsDesktop no encontrado" $false "Instalar: dotnet workload install windowsdesktop"
            return $false
        }
        
        Write-Status "Runtime WindowsDesktop disponible" $true
        
    } catch {
        Write-Status "Error al verificar .NET SDK: $($_.Exception.Message)" $false "Revisar instalación de .NET"
        return $false
    }
    
    return $true
}

function Test-ProjectStructure {
    Write-Host "`n3. VERIFICANDO ESTRUCTURA DEL PROYECTO" -ForegroundColor $ColorInfo
    
    $requiredPaths = @(
        @{Path = "Capa3_Visor\CapaVisor3D\VisorSingularity.csproj"; Description = "Proyecto WPF principal"},
        @{Path = "WoldVirtual\project.godot"; Description = "Proyecto Godot"},
        @{Path = "WoldVirtual\servidorinterno\"; Description = "Directorio servidor interno"},
        @{Path = "WoldVirtual\woldvirtual\scene\MTC\N3DWoldVirtualMT.tscn"; Description = "Escena principal 3D"},
        @{Path = "WoldVirtual\Estado_Global\"; Description = "Directorio estado global"},
        @{Path = "www\metamask.html"; Description = "Interfaz web MetaMask"}
    )
    
    $allPathsOk = $true
    
    foreach ($item in $requiredPaths) {
        $exists = Test-Path $item.Path
        Write-Status "$($item.Description): $($item.Path)" $exists
        
        if (-not $exists) {
            $allPathsOk = $false
        }
    }
    
    return $allPathsOk
}

function Test-GodotExecutable {
    Write-Host "`n4. VERIFICANDO GODOT 4.6.2" -ForegroundColor $ColorInfo
    
    $godotPath = "WoldVirtual\servidorinterno\Godot_v4.6.2-stable_mono_win64.exe"
    
    if (-not (Test-Path $godotPath)) {
        Write-Status "Ejecutable de Godot no encontrado" $false "Descargar Godot 4.6.2 Mono para Windows"
        
        # Sugerir URL de descarga
        if ($Detailed) {
            Write-Host "   URL sugerida: https://github.com/godotengine/godot/releases/download/4.6.2-stable/Godot_v4.6.2-stable_mono_win64.zip" -ForegroundColor $ColorInfo
            Write-Host "   Extraer en: WoldVirtual\servidorinterno\" -ForegroundColor $ColorInfo
        }
        
        return $false
    }
    
    # Verificar que sea ejecutable
    try {
        $fileInfo = Get-Item $godotPath
        $fileSizeMB = [math]::Round($fileInfo.Length / 1MB, 2)
        
        Write-Status "Godot encontrado: $fileSizeMB MB" $true
        
        # Verificar versión (aproximadamente)
        $fileVersion = (Get-Item $godotPath).VersionInfo.FileVersion
        if ($fileVersion -like "*4.6.2*") {
            Write-Status "Versión correcta: 4.6.2" $true
        } else {
            Write-Status "Posible versión incorrecta: $fileVersion" $false "Se requiere Godot 4.6.2 exactamente"
            return $false
        }
        
    } catch {
        Write-Status "Error al verificar Godot: $($_.Exception.Message)" $false "Revisar permisos del archivo"
        return $false
    }
    
    return $true
}

function Test-PortsAvailability {
    Write-Host "`n5. VERIFICANDO PUERTOS DISPONIBLES" -ForegroundColor $ColorInfo
    
    $requiredPorts = @(
        @{Port = 8080; Service = "Bridge HTTP MetaMask"},
        @{Port = 8082; Service = "Nodo P2P del visor"},
        @{Port = 50007; Service = "Chat UDP WPF→Godot"},
        @{Port = 50008; Service = "Chat UDP Godot→WPF"}
    )
    
    $allPortsOk = $true
    
    foreach ($portInfo in $requiredPorts) {
        $port = $portInfo.Port
        $service = $portInfo.Service
        
        try {
            # Intentar crear un listener TCP
            $listener = [System.Net.Sockets.TcpListener]$port
            $listener.Start()
            $listener.Stop()
            
            Write-Status "$service (puerto $port): DISPONIBLE" $true
            
        } catch {
            Write-Status "$service (puerto $port): OCUPADO" $false "Liberar puerto o cambiar configuración"
            $allPortsOk = $false
        }
    }
    
    return $allPortsOk
}

function Test-FilePermissions {
    Write-Host "`n6. VERIFICANDO PERMISOS DE ARCHIVOS" -ForegroundColor $ColorInfo
    
    $testPaths = @(
        "Capa3_Visor\CapaVisor3D\bin",
        "WoldVirtual\Estado_Global\peers",
        "."
    )
    
    $allPermissionsOk = $true
    
    foreach ($path in $testPaths) {
        if (Test-Path $path) {
            try {
                # Intentar crear un archivo temporal
                $tempFile = Join-Path $path "test_permission_$(Get-Random).tmp"
                "test" | Out-File -FilePath $tempFile -ErrorAction Stop
                Remove-Item $tempFile -Force -ErrorAction Stop
                
                Write-Status "Escritura en: $path" $true
                
            } catch {
                Write-Status "Sin permisos de escritura en: $path" $false "Ejecutar como administrador o cambiar permisos"
                $allPermissionsOk = $false
            }
        }
    }
    
    return $allPermissionsOk
}

function Test-DiskSpace {
    Write-Host "`n7. VERIFICANDO ESPACIO EN DISCO" -ForegroundColor $ColorInfo
    
    $drive = (Get-Location).Drive.Name + ":"
    $driveInfo = Get-PSDrive -Name $drive
    
    if ($driveInfo) {
        $freeGB = [math]::Round($driveInfo.Free / 1GB, 2)
        $totalGB = [math]::Round($driveInfo.Used / 1GB, 2) + $freeGB
        
        Write-Host "   Unidad $drive : $freeGB GB libres de $totalGB GB" -ForegroundColor $ColorInfo
        
        if ($freeGB -lt 2) {
            Write-Status "Espacio insuficiente (menos de 2 GB)" $false "Liberar espacio en disco"
            return $false
        } else {
            Write-Status "Espacio en disco suficiente" $true
        }
    }
    
    return $true
}

function Show-Summary {
    Write-Host "`n" + "="*60 -ForegroundColor $ColorInfo
    Write-Host "RESUMEN DE VERIFICACIÓN" -ForegroundColor $ColorInfo
    Write-Host "="*60 -ForegroundColor $ColorInfo
    
    if ($script:AllChecksPassed) {
        Write-Host "[OK] TODAS LAS VERIFICACIONES PASARON CORRECTAMENTE" -ForegroundColor $ColorSuccess
        Write-Host "`nEl proyecto está listo para ejecutarse." -ForegroundColor $ColorSuccess
        Write-Host "Puedes ejecutar: .\build-all.ps1" -ForegroundColor $ColorInfo
    } else {
        Write-Host "[ERROR] SE ENCONTRARON PROBLEMAS" -ForegroundColor $ColorError
        Write-Host "`nProblemas encontrados:" -ForegroundColor $ColorWarning
        
        foreach ($issue in $script:IssuesFound) {
            Write-Host "  - $issue" -ForegroundColor $ColorWarning
        }
        
        Write-Host "`nRecomendaciones:" -ForegroundColor $ColorInfo
        Write-Host "1. Corregir los problemas listados arriba" -ForegroundColor $ColorInfo
        Write-Host "2. Ejecutar este script con -Detailed para más información" -ForegroundColor $ColorInfo
        Write-Host "3. Consultar README.md para requisitos específicos" -ForegroundColor $ColorInfo
    }
    
    Write-Host "`n" + "="*60 -ForegroundColor $ColorInfo
}

function Show-QuickStart {
    Write-Host "`nINSTRUCCIONES RÁPIDAS:" -ForegroundColor $ColorSuccess
    
    Write-Host "`n1. COMPILAR PROYECTO:" -ForegroundColor $ColorInfo
    Write-Host "   .\build-all.ps1" -ForegroundColor $ColorInfo
    
    Write-Host "`n2. EJECUTAR VISOR:" -ForegroundColor $ColorInfo
    Write-Host "   dotnet run --project Capa3_Visor\CapaVisor3D\VisorSingularity.csproj" -ForegroundColor $ColorInfo
    Write-Host "   O directamente: Capa3_Visor\CapaVisor3D\bin\Debug\net8.0-windows\VisorSingularity.exe" -ForegroundColor $ColorInfo
    
    Write-Host "`n3. PUERTOS UTILIZADOS:" -ForegroundColor $ColorInfo
    Write-Host "   8080 - Bridge HTTP MetaMask" -ForegroundColor $ColorInfo
    Write-Host "   8082 - Nodo P2P del visor" -ForegroundColor $ColorInfo
    Write-Host "   50007/50008 - Chat UDP" -ForegroundColor $ColorInfo
    
    Write-Host "`n4. SOLUCIÓN DE PROBLEMAS:" -ForegroundColor $ColorInfo
    Write-Host "   Ejecutar: .\check-dependencies.ps1 -Detailed" -ForegroundColor $ColorInfo
}

# --- EJECUCIÓN PRINCIPAL ---
try {
    Write-Host "VERIFICACIÓN DE DEPENDENCIAS - WoldVirtual P2P 3D" -ForegroundColor $ColorSuccess
    Write-Host "Fecha: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor $ColorInfo
    Write-Host "Directorio: $(Get-Location)`n" -ForegroundColor $ColorInfo
    
    # Ejecutar todas las verificaciones
    Test-WindowsOS
    Test-DotNetSDK
    Test-ProjectStructure
    Test-GodotExecutable
    Test-PortsAvailability
    Test-FilePermissions
    Test-DiskSpace
    
    # Mostrar resumen
    Show-Summary
    
    # Mostrar instrucciones rápidas si todo está bien
    if ($script:AllChecksPassed -and -not $Detailed) {
        Show-QuickStart
    }
    
    # Estado de salida
    if ($script:AllChecksPassed) {
        exit 0
    } else {
        exit 1
    }
    
} catch {
    Write-Host "`nERROR NO MANEJADO: $($_.Exception.Message)" -ForegroundColor $ColorError
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor $ColorError
    exit 2
}