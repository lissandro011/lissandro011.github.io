@echo off
rem Prende Licha.bot. Si se cae por un error, lo vuelve a prender solo.
setlocal
cd /d "%~dp0"
title Licha.bot
if exist ".venv\Scripts\python.exe" goto loop
echo Licha.bot todavia no esta instalado.
echo Abri primero el archivo 1-instalar.bat
echo.
pause
exit /b 1

:loop
echo Prendiendo Licha.bot... Para apagarlo, cerra esta ventana.
echo.
".venv\Scripts\python.exe" bot.py
set "CODIGO=%ERRORLEVEL%"
if "%CODIGO%"=="0" goto fin
if "%CODIGO%"=="2" goto vincular
if "%CODIGO%"=="3" goto configuracion
if "%CODIGO%"=="4" goto duplicado
echo.
echo El bot se detuvo por un error, codigo %CODIGO%. Se vuelve a prender en 10 segundos...
timeout /t 10 /nobreak >nul
goto loop

:vincular
echo.
echo Hay que vincular el numero de WhatsApp: el codigo vencio o el bot se desvinculo.
echo Cerra esta ventana y volve a abrir 2-iniciar.bat para pedir un codigo nuevo.
echo.
pause
exit /b 2

:configuracion
echo.
echo Hay un error en la configuracion. Abri 1-instalar.bat para corregirla.
echo.
pause
exit /b 3

:duplicado
echo.
echo Ya hay otra ventana de Licha.bot abierta. Deja una sola.
echo.
pause
exit /b 4

:fin
echo.
echo Licha.bot se apago.
pause
exit /b 0
