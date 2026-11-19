@echo off
setlocal
title Wold Virtual 3D - Vista previa C# + Godot DAO

set "HERRAMIENTAS=%~dp0"
set "SRC=%HERRAMIENTAS%..\..\.."
set "PROJECT=%SRC%\MTBGT\WoldVirtualP2P3D"
set "CONSTRUCCION=%HERRAMIENTAS%..\..\..\..\.."
set "DEV=%CONSTRUCCION%\.dev"
set "CS=%DEV%\CS"
set "GODOT=%CS%\runtime\Godot\Godot_v4.7.2-stable_win64.exe"
set "SERVER=%CS%\Publicacion\Servidor\WoldVirtualP2P3D.Servidor.exe"
set "CLOUDFLARED=%CS%\runtime\cloudflared\cloudflared.exe"

if not exist "%PROJECT%\project.godot" (
  echo No se encuentra el proyecto Godot activo: %PROJECT%
  pause
  exit /b 2
)
if not exist "%GODOT%" (
  echo Falta Godot 4.7.2 en .dev\CS\runtime\Godot.
  pause
  exit /b 3
)
if not exist "%SERVER%" (
  echo Falta el servidor modular en .dev\CS\Publicacion\Servidor.
  pause
  exit /b 4
)
if not exist "%CLOUDFLARED%" (
  echo Falta cloudflared en .dev\CS\runtime\cloudflared.
  pause
  exit /b 5
)

set "DOTNET_CLI_HOME=%CS%\.dotnet"
set "NUGET_PACKAGES=%CS%\.nuget\packages"
set "DOTNET_CLI_TELEMETRY_OPTOUT=1"
set "DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1"
set "TEMP=%CS%\tmp"
set "TMP=%TEMP%"
set "APPDATA=%CS%\runtime\roaming"
set "LOCALAPPDATA=%CS%\runtime\local"
set "WVP_DATA_DIR=%CS%\runtime\datos"
set "WVP_IPC_DIR=%CS%\runtime\ipc"
set "WVP_SERVER_EXE=%SERVER%"
set "WVP_LAUNCH_SERVER=1"
set "WVP_MODULAR_DAO=1"
set "WVP_IPC_ONLY=1"
set "WVP_TUNNEL_PROVIDER=cloudflare"
set "WVP_PORT=8765"
set "WVP_GODOT_EXE=%GODOT%"
set "CLOUDFLARED_EXE=%CLOUDFLARED%"

for %%D in ("%DOTNET_CLI_HOME%" "%NUGET_PACKAGES%" "%TEMP%" "%APPDATA%" "%LOCALAPPDATA%" "%WVP_DATA_DIR%" "%WVP_IPC_DIR%" "%CS%\build\HerraMientas\obj" "%CS%\build\HerraMientas\bin") do if not exist "%%~D" mkdir "%%~D"

pushd "%HERRAMIENTAS%"
dotnet run --project "%HERRAMIENTAS%Visor3D.csproj" --no-launch-profile -p:GodotSourcePreview=true -p:SkipGodotAssets=true -p:UseAppHost=false -p:SelfContained=false -p:PublishSingleFile=false -p:NuGetAudit=false -p:RestoreIgnoreFailedSources=true -p:BaseIntermediateOutputPath="%CS%/build/HerraMientas/obj/" -p:BaseOutputPath="%CS%/build/HerraMientas/bin/"
set "CODIGO=%ERRORLEVEL%"
popd
if not "%CODIGO%"=="0" (
  echo.
  echo La vista previa C# no pudo arrancar. Codigo: %CODIGO%
  pause
)
exit /b %CODIGO%
