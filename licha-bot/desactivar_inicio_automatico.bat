@echo off
setlocal EnableExtensions
set "ACCESO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Licha Bot.lnk"

if exist "%ACCESO%" (
    del "%ACCESO%"
    echo.
    echo  Listo: Licha Bot ya no arranca solo con Windows.
) else (
    echo.
    echo  El inicio automatico no estaba activado.
)
echo.
pause
endlocal
