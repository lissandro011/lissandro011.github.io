@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "CARPETA=%~dp0"
set "ACCESO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Licha Bot.lnk"

rem Crea un acceso directo a iniciar.bat en la carpeta Inicio de Windows (minimizado).
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w = New-Object -ComObject WScript.Shell; $s = $w.CreateShortcut($env:ACCESO); $s.TargetPath = Join-Path $env:CARPETA 'iniciar.bat'; $s.WorkingDirectory = $env:CARPETA; $s.WindowStyle = 7; $s.Description = 'Licha Bot'; $s.Save()"

if exist "%ACCESO%" (
    echo.
    echo  Listo: Licha Bot va a arrancar solo, minimizado, cada vez que inicies sesion en Windows.
    echo  Para sacarlo, abri desactivar_inicio_automatico.bat
) else (
    echo.
    echo  [ERROR] No pude crear el acceso directo en la carpeta Inicio.
)
echo.
pause
endlocal
