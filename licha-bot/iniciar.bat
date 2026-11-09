@echo off
setlocal EnableExtensions
title Licha Bot
cd /d "%~dp0"
set "PYTHONUTF8=1"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  Licha Bot todavia no esta instalado: primero abri instalar.bat
    echo.
    pause
    exit /b 1
)

:inicio
echo.
echo  Iniciando Licha Bot... Para apagarlo, cerra esta ventana.
echo.
".venv\Scripts\python.exe" main.py
set "CODIGO=%ERRORLEVEL%"

rem 0 = apagado normal, 3 = !reiniciar, 2 = hay que vincular de nuevo, otro = error
if "%CODIGO%"=="0" goto fin
if "%CODIGO%"=="3" goto inicio
if "%CODIGO%"=="2" goto vincular

echo.
echo  El bot se detuvo por un error (codigo %CODIGO%). Vuelvo a intentar en 15 segundos...
echo  El detalle queda en logs\licha-bot.log. Cerra la ventana si queres cancelar.
timeout /t 15 /nobreak >nul
goto inicio

:vincular
echo.
echo  Hay que vincular el numero del bot. Revisa "numero" en config.toml
echo  y volve a abrir iniciar.bat para pedir un codigo nuevo.
echo.
pause

:fin
endlocal
