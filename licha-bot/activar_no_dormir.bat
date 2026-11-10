@echo off
setlocal EnableExtensions
title Licha Bot - que no se duerma
cd /d "%~dp0"

rem Deja la notebook despierta aunque cierres la tapa, para que el bot siga andando.
rem GUIDs de Windows (los mismos en cualquier version e idioma):
rem   BOTONES = "Botones de inicio/apagado y tapa"
rem   TAPA    = "Accion al cerrar la tapa" (0 = no hacer nada, 1 = suspender, 2 = hibernar, 3 = apagar)
set "BOTONES=4f971e89-eebd-4455-a8de-9e59040e7347"
set "TAPA=5ca83367-6e45-459f-a27b-476b1d01c936"

rem fltmc solo funciona con permisos de administrador: sirve para saber si los tenemos.
fltmc >nul 2>&1
if not errorlevel 1 goto administrador

if /i "%~1"=="elevado" (
    echo.
    echo  [ERROR] Windows no me dio permisos de administrador, asi que no puedo
    echo          cambiar la energia. Entra a Configuracion ^> Sistema ^>
    echo          Inicio/apagado y bateria y cambialo a mano.
    echo.
    pause
    exit /b 1
)
echo.
echo  Para cambiar la energia de Windows necesito permisos de administrador.
echo  Decile "Si" a la ventana que va a aparecer.
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList 'elevado' -Verb RunAs" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] No pude pedir los permisos. Hace clic derecho en activar_no_dormir.bat
    echo          y elegi "Ejecutar como administrador".
    echo.
    pause
)
exit /b

:administrador

set "FALLO="
echo.
echo  === Que la notebook no se duerma (Licha Bot) ===
echo.
echo  Enchufada a la corriente:
echo   - al cerrar la tapa, no hace nada
powercfg /setacvalueindex SCHEME_CURRENT %BOTONES% %TAPA% 0 || set "FALLO=1"
echo   - nunca se suspende ni hiberna sola
powercfg /change standby-timeout-ac 0 || set "FALLO=1"
powercfg /change hibernate-timeout-ac 0 || set "FALLO=1"

echo.
choice /c SN /n /m "  Que tampoco se duerma cuando NO esta enchufada? [S/N] "
if errorlevel 2 goto aplicar

set "BATERIA=1"
echo.
echo  Con bateria: igual, no hace nada al cerrar la tapa.
powercfg /setdcvalueindex SCHEME_CURRENT %BOTONES% %TAPA% 0 || set "FALLO=1"
powercfg /change standby-timeout-dc 0 || set "FALLO=1"
powercfg /change hibernate-timeout-dc 0 || set "FALLO=1"

:aplicar
powercfg /setactive SCHEME_CURRENT || set "FALLO=1"

echo.
if defined FALLO (
    echo  [ERROR] Windows rechazo alguno de los cambios ^(mira los mensajes de arriba^).
    echo  Lo podes hacer a mano: Panel de control ^> Opciones de energia ^>
    echo  "Elegir el comportamiento del cierre de la tapa" ^> No hacer nada.
    echo.
    pause
    endlocal
    exit /b 1
)

echo  Listo: ya podes cerrar la tapa y el bot sigue prendido.
echo.
echo  Tene en cuenta:
echo   - La pantalla se apaga igual (eso no molesta al bot).
echo   - Dejala en un lugar ventilado: con la tapa cerrada se calienta mas.
if defined BATERIA echo   - Sin enchufar y con la tapa cerrada, la bateria se va a gastar hasta apagarse.
if not defined BATERIA echo   - Sin enchufar sigue durmiendose al cerrarla ^(asi no se gasta la bateria^).
echo   - Windows Update puede reiniciarla: Configuracion ^> Windows Update ^>
echo     Opciones avanzadas ^> Horas activas.
echo   - Para que el bot arranque solo despues de un reinicio: activar_inicio_automatico.bat
echo.
echo  Para volver a la configuracion normal: desactivar_no_dormir.bat
echo.
pause
endlocal
