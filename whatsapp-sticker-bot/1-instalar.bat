@echo off
rem Instalador de Licha.bot: doble clic y seguir las instrucciones.
setlocal
cd /d "%~dp0"
title Instalar Licha.bot

call :buscar_python
if defined PYEXE goto python_ok

echo.
echo No encontre Python 3.10 o mas nuevo en esta PC.
where winget >nul 2>nul
if errorlevel 1 goto python_manual
choice /c SN /m "Queres que lo instale ahora"
if errorlevel 2 goto python_manual
winget install -e --id Python.Python.3.13 --scope user --accept-package-agreements --accept-source-agreements
call :buscar_python
if defined PYEXE goto python_ok

:python_manual
echo.
echo Instala Python desde https://www.python.org/downloads/
echo Durante la instalacion marca la casilla "Add python.exe to PATH".
echo Despues cerra esta ventana y volve a abrir 1-instalar.bat
echo.
pause
exit /b 1

:python_ok
"%PYEXE%" %PYARGS% instalar.py
set "CODIGO=%ERRORLEVEL%"
echo.
pause
exit /b %CODIGO%

rem --- Busca un Python 3.10+ : lanzador py, python del PATH o carpetas habituales.
:buscar_python
set "PYEXE="
set "PYARGS="
call :probar py -3
if defined PYEXE goto :eof
call :probar python
if defined PYEXE goto :eof
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do call :probar "%%~D\python.exe"
goto :eof

:probar
"%~1" %2 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto :eof
set "PYEXE=%~1"
set "PYARGS=%2"
goto :eof
