@echo off
setlocal EnableExtensions
title Licha Bot - volver a la energia normal
cd /d "%~dp0"

rem Deshace activar_no_dormir.bat: vuelve a los valores habituales de Windows.
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
    echo  [ERROR] No pude pedir los permisos. Hace clic derecho en desactivar_no_dormir.bat
    echo          y elegi "Ejecutar como administrador".
    echo.
    pause
)
exit /b

:administrador

set "FALLO="
echo.
echo  === Volver a la energia normal ===
echo.
echo  Al cerrar la tapa: suspender (enchufada y con bateria).
powercfg /setacvalueindex SCHEME_CURRENT %BOTONES% %TAPA% 1 || set "FALLO=1"
powercfg /setdcvalueindex SCHEME_CURRENT %BOTONES% %TAPA% 1 || set "FALLO=1"
echo  Suspender sola: a los 30 minutos enchufada, a los 15 con bateria.
powercfg /change standby-timeout-ac 30 || set "FALLO=1"
powercfg /change standby-timeout-dc 15 || set "FALLO=1"
echo  Hibernar sola: a las 3 horas.
powercfg /change hibernate-timeout-ac 180 || set "FALLO=1"
powercfg /change hibernate-timeout-dc 180 || set "FALLO=1"
powercfg /setactive SCHEME_CURRENT || set "FALLO=1"

echo.
if defined FALLO (
    echo  [ERROR] Windows rechazo alguno de los cambios ^(mira los mensajes de arriba^).
    echo  Lo podes ajustar a mano en Configuracion ^> Sistema ^> Inicio/apagado y bateria.
) else (
    echo  Listo: la notebook vuelve a dormirse cuando cerras la tapa.
    echo  Ojo: con la tapa cerrada el bot deja de andar hasta que la abras.
    echo.
    echo  Estos son los valores habituales de Windows, no los que tenias antes.
    echo  Si usabas otros, cambialos en Configuracion ^> Sistema ^> Inicio/apagado y bateria.
)
echo.
pause
endlocal
