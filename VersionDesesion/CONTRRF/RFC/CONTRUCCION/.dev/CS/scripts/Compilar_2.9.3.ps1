$ErrorActionPreference = "Stop"
$csRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$construction = [System.IO.Path]::GetFullPath((Join-Path $csRoot "..\.."))
$projectRoot = Join-Path $construction "TLLDCD\src\VSC#\Visor3Ddesarrollo\WoldVirtual3DP2P3D"
$visorSource = Join-Path $projectRoot "Visor"
$serverProject = Join-Path $projectRoot "Servidor\WoldVirtual.Servidor.csproj"
$publishRoot = Join-Path $csRoot "Publicacion"
$serverPublish = Join-Path $publishRoot "Servidor"
$visorExe = Join-Path $publishRoot "WoldVirtualP2P3Dv2.9.3.exe"
$godotExe = Join-Path $csRoot "runtime\Godot\Godot_v4.7.2-stable_win64.exe"
$templateSource = Join-Path $env:USERPROFILE "AppData\Roaming\Godot\export_templates\4.7.2.stable"
$templateRoot = Join-Path $csRoot "runtime\roaming\Godot\export_templates\4.7.2.stable"
$exportProject = Join-Path $csRoot "build\visor-export"

$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = "1"
$env:DOTNET_CLI_HOME = Join-Path $csRoot ".dotnet"
$env:NUGET_PACKAGES = Join-Path $csRoot ".nuget\packages"
$env:TEMP = Join-Path $csRoot "tmp"
$env:TMP = $env:TEMP
$env:APPDATA = Join-Path $csRoot "runtime\roaming"
$env:LOCALAPPDATA = Join-Path $csRoot "runtime\local"

New-Item -ItemType Directory -Force -Path @($csRoot,(Join-Path $csRoot "build"),$publishRoot,$serverPublish,(Join-Path $csRoot "runtime\Godot"),$templateRoot,$env:DOTNET_CLI_HOME,$env:NUGET_PACKAGES,$env:TEMP,$env:APPDATA,$env:LOCALAPPDATA) | Out-Null
if (-not (Test-Path -LiteralPath $godotExe)) {
    $godotSource = Join-Path $construction ".dev\rebuild287\portable292\runtime\Servidor3D"
    if (-not (Test-Path (Join-Path $godotSource "Godot_v4.7.2-stable_win64.exe"))) { $godotSource = Join-Path $construction ".dev\rebuild287\runtime\Servidor3D" }
    if (-not (Test-Path (Join-Path $godotSource "Godot_v4.7.2-stable_win64.exe"))) { throw "No se encontró Godot 4.7.2 en .dev." }
    Get-ChildItem -LiteralPath $godotSource -File | Copy-Item -Destination (Join-Path $csRoot "runtime\Godot") -Force
}
if (-not (Test-Path (Join-Path $templateRoot "windows_release_x86_64.exe"))) {
    if (-not (Test-Path (Join-Path $templateSource "windows_release_x86_64.exe"))) { throw "Falta la plantilla Windows de Godot 4.7.2." }
    foreach ($name in @("windows_release_x86_64.exe","version.txt","icudt_godot.dat")) { $source=Join-Path $templateSource $name; if(Test-Path $source){Copy-Item $source $templateRoot -Force} }
}
$objDir=Join-Path $csRoot "build\servidor\obj"; $binDir=Join-Path $csRoot "build\servidor\bin"
dotnet publish $serverProject -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:BaseIntermediateOutputPath="$objDir\" -p:BaseOutputPath="$binDir\" -o $serverPublish
if($LASTEXITCODE -ne 0){throw "Falló la publicación del servidor (código $LASTEXITCODE)."}
if(Test-Path $exportProject){Remove-Item -LiteralPath $exportProject -Recurse -Force}
Copy-Item -LiteralPath $visorSource -Destination $exportProject -Recurse
Copy-Item -LiteralPath (Join-Path $csRoot "config\export_presets.cfg") -Destination $exportProject -Force
$godotArgs = "--headless --path `"$exportProject`" --export-release `"Windows Desktop`" `"$visorExe`""
$godotLog = Join-Path $csRoot "build\godot-export.out"
$godotErrorLog = Join-Path $csRoot "build\godot-export.err"
$godotProcess = Start-Process -FilePath $godotExe -ArgumentList $godotArgs -Wait -PassThru -NoNewWindow -RedirectStandardOutput $godotLog -RedirectStandardError $godotErrorLog
if ($godotProcess.ExitCode -ne 0) { Get-Content $godotLog; Get-Content $godotErrorLog; throw "Falló la exportación Godot (código $($godotProcess.ExitCode))." }
Write-Host "Publicación lista:" -ForegroundColor Cyan
Get-Item -LiteralPath $visorExe,(Join-Path $serverPublish "WoldVirtualP2P3D.Servidor.exe") | Select-Object FullName,Length


