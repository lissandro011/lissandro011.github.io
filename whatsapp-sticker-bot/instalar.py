"""Instalador guiado de Licha.bot (pensado para Windows, también anda en Linux/macOS).

Lo ejecuta 1-instalar.bat con el Python del sistema:

    python instalar.py

1. Crea el entorno virtual (.venv) e instala las librerías.
2. Busca ffmpeg y, en Windows, ofrece instalarlo con winget.
3. Crea el archivo .env y pregunta el número del bot.
4. Revisa que todo esté bien.

Los pasos 2 a 4 corren con el Python del entorno virtual (--fase2), que ya
tiene las librerías del bot. Se puede volver a ejecutar cuantas veces haga falta.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
VENV = BASE / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
ENV_FILE = BASE / ".env"
ENV_EXAMPLE = BASE / ".env.example"
MIN_PYTHON = (3, 10)

PHONE_HELP = """\
   Escribilo con el código de país, sin '+', sin espacios y sin el 0 inicial.
   Argentina: 54 + 9 + código de área sin el 0 + número sin el 15.
     011 15 2345-6789   ->  5491123456789
     0351 15 234-5678   ->  5493512345678"""


def paso(numero: int, texto: str) -> None:
    print(f"\n[{numero}/4] {texto}")


def ok(texto: str) -> None:
    print(f"   [OK] {texto}")


def problema(texto: str) -> None:
    print(f"   [!!] {texto}")


def preguntar(texto: str, default: str = "") -> str:
    try:
        return input(texto).strip()
    except EOFError:  # sin teclado (por ejemplo, en una prueba automática)
        print()
        return default


def preguntar_si(texto: str) -> bool:
    return preguntar(f"{texto} [S/n]: ", "s").lower() in ("", "s", "si", "sí", "y", "yes")


# --------------------------------------------------------------------------- #
# Fase 1: entorno virtual y librerías (Python del sistema, solo biblioteca estándar)
# --------------------------------------------------------------------------- #


def venv_works() -> bool:
    if not VENV_PY.exists():
        return False
    result = subprocess.run([str(VENV_PY), "-c", "import sys"], capture_output=True)
    return result.returncode == 0


def fase1() -> int:
    print("Instalación de Licha.bot")
    paso(1, "Entorno de Python y librerías")
    if sys.version_info < MIN_PYTHON:
        problema(f"Hace falta Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} o más nuevo (tenés {sys.version.split()[0]}).")
        return 1
    ok(f"Python {sys.version.split()[0]}")

    if not venv_works():
        print("   Creando el entorno virtual (.venv)...")
        # clear=True: si la carpeta quedó rota (por ejemplo, copiada de otra PC), se rehace.
        result = subprocess.run([sys.executable, "-m", "venv", "--clear", str(VENV)])
        if result.returncode != 0 or not venv_works():
            problema("No pude crear el entorno virtual.")
            if sys.platform.startswith("linux"):
                print("   En Debian/Ubuntu instalá el paquete python3-venv y probá de nuevo.")
            return 1

    print("   Instalando librerías (puede tardar unos minutos; es normal ver mucho texto)...")
    result = subprocess.run(
        [str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(BASE / "requirements.txt")]
    )
    if result.returncode != 0:
        problema("No se pudieron instalar las librerías. Revisá la conexión a internet y probá de nuevo.")
        return 1
    ok("Librerías instaladas")

    # El resto lo hace el Python del entorno, que ya tiene todo lo del bot.
    return subprocess.run([str(VENV_PY), str(Path(__file__).resolve()), "--fase2"], cwd=BASE).returncode


# --------------------------------------------------------------------------- #
# Fase 2: ffmpeg, número y verificación (Python del entorno virtual)
# --------------------------------------------------------------------------- #


def configurar_ffmpeg() -> None:
    import sticker

    paso(2, "ffmpeg (para convertir videos y GIF)")
    sticker.ensure_ffmpeg_on_path()
    problem = sticker.ffmpeg_problem()
    if problem and shutil.which("ffmpeg") is None and os.name == "nt" and shutil.which("winget"):
        print("   No encontré ffmpeg en esta PC.")
        if preguntar_si("   ¿Lo instalo ahora con winget?"):
            subprocess.run(
                ["winget", "install", "-e", "--id", "Gyan.FFmpeg",
                 "--accept-package-agreements", "--accept-source-agreements"]
            )  # fmt: skip
            sticker.ensure_ffmpeg_on_path()
            problem = sticker.ffmpeg_problem()
    if problem:
        problema(problem)
        print("   Las fotos se van a poder convertir, pero los videos y GIF no.")
        print("   Instalalo y volvé a abrir el instalador (ver GUIA-WINDOWS.md, 'Problemas comunes').")
    else:
        ok("ffmpeg listo")


def validar_numero(texto: str) -> tuple[str | None, str | None]:
    """Devuelve (número normalizado, None) o (None, motivo del error)."""
    from config import ConfigError, normalize_phone

    crudo = re.sub(r"[\s+\-().]", "", texto)
    if crudo.startswith("0"):
        return None, "No empieces con 0: poné primero el código de país (Argentina: 54)."
    try:
        numero = normalize_phone(texto)
    except ConfigError:
        return None, "Ese número no parece válido."
    if numero.startswith("54") and not numero.startswith("549"):
        return None, "En Argentina, después del 54 va un 9 (por ejemplo 5491123456789)."
    return numero, None


def leer_numero_actual(texto_env: str) -> str:
    match = re.search(r"^WA_PHONE_NUMBER=(.*)$", texto_env, re.MULTILINE)
    return match.group(1).strip() if match else ""


def guardar_numero(texto_env: str, numero: str) -> str:
    linea = f"WA_PHONE_NUMBER={numero}"
    if re.search(r"^WA_PHONE_NUMBER=.*$", texto_env, re.MULTILINE):
        return re.sub(r"^WA_PHONE_NUMBER=.*$", linea, texto_env, count=1, flags=re.MULTILINE)
    return texto_env.rstrip("\n") + f"\n{linea}\n"


def configurar_numero() -> None:
    paso(3, "Número de WhatsApp del bot")
    if not ENV_FILE.exists():
        shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
        ok("Creé el archivo de configuración (.env)")
    texto = ENV_FILE.read_text(encoding="utf-8-sig")
    actual = leer_numero_actual(texto)

    if actual:
        print(f"   Número configurado: {actual}")
        pedido = "   Apretá Enter para dejarlo así, o escribí otro número: "
    else:
        print("   ¿Qué número de WhatsApp va a usar el bot?")
        print(PHONE_HELP)
        pedido = "   Número del bot: "

    while True:
        respuesta = preguntar(pedido)
        if not respuesta:
            if not actual:
                problema("No cargaste ningún número. Volvé a abrir el instalador cuando lo tengas.")
            return
        numero, error = validar_numero(respuesta)
        if numero:
            ENV_FILE.write_text(guardar_numero(texto, numero), encoding="utf-8")
            ok(f"Número guardado: {numero}")
            return
        problema(error or "Número inválido.")
        print(PHONE_HELP)
        pedido = "   Probá de nuevo (o Enter para salir): "


def verificar_todo() -> int:
    paso(4, "Revisión final")
    from dotenv import load_dotenv

    load_dotenv(ENV_FILE, override=True)
    try:
        import bot  # también comprueba que neonize y sus librerías carguen bien
        from config import ConfigError, load_config
    except Exception as exc:
        problema(f"No se pudieron cargar las librerías del bot: {exc!r}")
        return 1
    try:
        cfg = load_config()
    except ConfigError as exc:
        problema(f"Configuración inválida: {exc}")
        return 1
    if not bot.verificar(cfg):
        print("\nFaltan cosas: revisá los puntos marcados con [!!] y volvé a abrir el instalador.")
        return 1
    print("\nTodo listo. Ahora abrí 2-iniciar.bat para vincular el número y prender el bot.")
    return 0


def fase2() -> int:
    sys.path.insert(0, str(BASE))
    configurar_ffmpeg()
    configurar_numero()
    return verificar_todo()


if __name__ == "__main__":
    os.chdir(BASE)
    sys.exit(fase2() if "--fase2" in sys.argv[1:] else fase1())
