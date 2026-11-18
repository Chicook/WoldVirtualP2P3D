@echo off
setlocal
title Isla Unica LucIA (DAO) - Visor 3D

set "PROY=%~dp0..\.."

REM 1. Buscar ejecutable de Godot en orden prioritario:
set "GODOT="
if exist "%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.8.4\Servidor3D\Godot_v4.7.2-stable_win64.exe" (
    set "GODOT=%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.8.4\Servidor3D\Godot_v4.7.2-stable_win64.exe"
)
if not defined GODOT if exist "%~dp0..\..\..\..\..\..\.dev\_tmp_bundle\runtime284\Servidor3D\Godot_v4.7.2-stable_win64.exe" (
    set "GODOT=%~dp0..\..\..\..\..\..\.dev\_tmp_bundle\runtime284\Servidor3D\Godot_v4.7.2-stable_win64.exe"
)
if not defined GODOT if exist "%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.8.3\Servidor3D\Godot_v4.7.2-stable_win64.exe" (
    set "GODOT=%LOCALAPPDATA%\WoldVirtualP2P3D\runtime\2.8.3\Servidor3D\Godot_v4.7.2-stable_win64.exe"
)

if not defined GODOT (
    echo [ERROR] No se encontro el ejecutable de Godot.
    echo Asegurate de tener Godot extraido o en tu PATH.
    pause
    exit /b 1
)

cls
echo ==============================================================================
echo                 ISLA UNICA LUCIA (DAO) - VISOR GODOT 3D
echo ==============================================================================
echo  Proyecto: %PROY%
echo  Motor:    %GODOT%
echo ==============================================================================
echo.
echo  Elige que deseas ver:
echo.
echo   1. Camara Libre 3D (Explorar isla, rampas, atrio, oceano y estaciones)
echo   2. Cinematica de Alta y Recorrido de LucIA (OnboardingDAO interactivo)
echo   3. Vista Preliminar DAO Clasica (PreviewDAO)
echo   4. Abrir el proyecto en el Editor de Godot
echo   5. Salir
echo.
echo ==============================================================================
set /p OPCION=Selecciona una opcion (1-5): 

if "%OPCION%"=="1" goto modo_libre
if "%OPCION%"=="2" goto modo_onboarding
if "%OPCION%"=="3" goto modo_preview
if "%OPCION%"=="4" goto modo_editor
if "%OPCION%"=="5" goto fin
goto error_opcion

:modo_libre
echo.
echo Lanzando Visor Interactivo 3D con camara libre...
echo (Controles: WASD para volar, boton derecho raton para mirar, 1-7 teletransporte)
start "" "%GODOT%" --path "%PROY%" "res://lucia3D/IslaUnicaLucIA/PRUEBAS_VISUALES/VisorInteractivoIsla.tscn"
exit /b 0

:modo_onboarding
echo.
echo Lanzando Cinematica Completa de Onboarding y Alta en la DAO...
echo (Despacho LucIA - Salida rampa sur - 4 estaciones - Carrusel - Espejo - Portal)
start "" "%GODOT%" --path "%PROY%" "res://lucia3D/IslaUnicaLucIA/ONBOARDING/OnboardingDAO.tscn"
exit /b 0

:modo_preview
echo.
echo Lanzando Vista Preliminar DAO...
start "" "%GODOT%" --path "%PROY%" "res://lucia3D/IslaUnicaLucIA/PRUEBAS_VISUALES/PreviewDAO.tscn"
exit /b 0

:modo_editor
echo.
echo Abriendo el Editor de Godot en el proyecto...
start "" "%GODOT%" -e --path "%PROY%"
exit /b 0

:error_opcion
echo.
echo Opcion no valida.
pause
exit /b 1

:fin
exit /b 0
