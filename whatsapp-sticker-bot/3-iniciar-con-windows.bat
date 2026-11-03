@echo off
rem Activa o desactiva que Licha.bot arranque solo al iniciar sesion en Windows.
setlocal
cd /d "%~dp0"
title Licha.bot - inicio automatico
set "OBJETIVO=%~dp02-iniciar.bat"
set "CARPETA=%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command "exit [int](Test-Path (Join-Path ([Environment]::GetFolderPath('Startup')) 'Licha.bot.lnk'))"
if errorlevel 1 goto ya_activado

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Startup')) 'Licha.bot.lnk')); $s.TargetPath = $env:OBJETIVO; $s.WorkingDirectory = $env:CARPETA; $s.WindowStyle = 7; $s.Save()"
if errorlevel 1 goto error
echo.
echo Listo: Licha.bot va a arrancar solo cada vez que inicies sesion en Windows.
echo Su ventana se abre minimizada en la barra de tareas.
echo Para desactivarlo, volve a abrir este archivo.
echo.
pause
exit /b 0

:ya_activado
echo.
echo El inicio automatico de Licha.bot ya esta activado.
choice /c SN /m "Queres desactivarlo"
if errorlevel 2 goto fin
powershell -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item -LiteralPath (Join-Path ([Environment]::GetFolderPath('Startup')) 'Licha.bot.lnk')"
echo Listo: Licha.bot ya no arranca solo con Windows.
:fin
echo.
pause
exit /b 0

:error
echo.
echo No pude crear el acceso directo. Mira la seccion "Problemas comunes" de GUIA-WINDOWS.md
echo.
pause
exit /b 1
