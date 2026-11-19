@echo off
setlocal
title Wold Virtual 3D - Vista previa del visor
REM Arbol activo (..\..\.. desde HerraMientas = TLLDCD\src) y archivo de
REM versiones anteriores, donde vive el Python embebido que no se versiona.
set "SRC=%~dp0..\..\.."
if not defined WVP_LEGACY_SRC set "WVP_LEGACY_SRC=%~dp0..\..\..\..\..\..\..\..\..\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"
if not exist "%WVP_LEGACY_SRC%" set "WVP_LEGACY_SRC=%~dp0..\..\..\..\..\..\..\..\..\VersionDesesion\SistemaPrincipal\PRY\Archivo\VersionesDeRefuerzo\actualizacion_c5074e3b\src"
set "EXE=%~dp0bin\Debug\net8.0-windows\win-x64\LCDMWoldVirtualP2P3Dv2.8.4.exe"
set "DEV_DIR=%~dp0..\..\..\..\..\.dev"
set "PYW="
if exist "%DEV_DIR%\.python\pythonw.exe" set "PYW=%DEV_DIR%\.python\pythonw.exe"
if not defined PYW if exist "%DEV_DIR%\venv\Scripts\pythonw.exe" set "PYW=%DEV_DIR%\venv\Scripts\pythonw.exe"
if not defined PYW set "PYW=%SRC%\LC_STM\python\pythonw.exe"
if not exist "%PYW%" set "PYW=%WVP_LEGACY_SRC%\LC_STM\python\pythonw.exe"
set "SRV=%SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
if not exist "%SRV%" set "SRV=%WVP_LEGACY_SRC%\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"

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
