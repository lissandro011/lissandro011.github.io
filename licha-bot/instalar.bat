@echo off
setlocal EnableExtensions
title Licha Bot - Instalacion
cd /d "%~dp0"

echo.
echo  ==================================================
echo     Instalando Licha Bot
echo  ==================================================
echo.

rem --- 1. Buscar Python 3.11 o mas nuevo ------------------------------------
set "PY="
for %%V in (3.13 3.12 3.14 3.11 3.15) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
    )
)
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo  [ERROR] No encontre Python 3.11 o mas nuevo en esta PC.
    echo.
    echo  Instalalo abriendo una ventana de PowerShell y escribiendo:
    echo      winget install -e --id Python.Python.3.13
    echo  o descargalo de https://www.python.org/downloads/windows/
    echo  marcando la opcion "Add python.exe to PATH".
    echo.
    echo  Despues cerra esta ventana y volve a abrir instalar.bat
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%i in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set "PYVER=%%i"
echo  [1/4] Python %PYVER% encontrado.

rem --- 2. Entorno virtual (las librerias del bot quedan dentro de .venv) ----
if not exist ".venv\Scripts\python.exe" (
    echo  [2/4] Creando el entorno virtual...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo  [ERROR] No pude crear el entorno virtual.
        pause
        exit /b 1
    )
) else (
    echo  [2/4] El entorno virtual ya existe.
)

rem --- 3. Dependencias -----------------------------------------------------
echo  [3/4] Instalando las librerias. Puede tardar unos minutos...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo.
    echo  [ERROR] Fallo la instalacion de las librerias. Revisa la conexion a internet
    echo  y volve a abrir instalar.bat. Si sigue fallando, mira el mensaje de arriba.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -c "import neonize, PIL, av" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Las librerias se instalaron pero no cargan. Mensaje:
    ".venv\Scripts\python.exe" -c "import neonize, PIL, av"
    pause
    exit /b 1
)

rem --- 4. Configuracion ----------------------------------------------------
if not exist "config.toml" (
    copy /y "config.ejemplo.toml" "config.toml" >nul
    echo  [4/4] Cree el archivo config.toml.
) else (
    echo  [4/4] config.toml ya existe: no lo toque.
)

echo.
echo  ==================================================
echo     Listo! Licha Bot quedo instalado.
echo  ==================================================
echo.
echo  Ahora:
echo    1. En config.toml completa "numero" con el numero del chip del bot
echo       y "duenos" con tu numero personal. Guarda el archivo.
echo    2. Abri iniciar.bat para prender el bot y vincular el numero.
echo.
set "ABRIR="
set /p "ABRIR=Queres abrir config.toml ahora? (S/N): "
if /i "%ABRIR%"=="S" start "" notepad "config.toml"
echo.
pause
endlocal
