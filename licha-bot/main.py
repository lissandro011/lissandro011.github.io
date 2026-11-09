"""Arranca Licha Bot.

    python main.py

En Windows lo más cómodo es hacer doble clic en iniciar.bat, que además lo
reinicia solo si se cae. Todo se configura en config.toml.
"""

from __future__ import annotations

import sys

if sys.version_info < (3, 11):
    sys.exit("Licha Bot necesita Python 3.11 o más nuevo (tenés %d.%d)." % sys.version_info[:2])

import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

from licha_bot import __version__
from licha_bot.config import Config, ErrorConfig, cargar_config

log = logging.getLogger("licha")


def preparar_consola() -> None:
    # Que un emoji o una tilde nunca rompan el bot por la codificación de la consola.
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    if sys.platform == "win32":
        desactivar_seleccion_rapida()


def desactivar_seleccion_rapida() -> None:
    """Evita que el bot se congele si alguien hace clic en la ventana.

    En la consola clásica de Windows, un clic activa el modo "Seleccionar" y el
    programa queda trabado hasta apretar Esc. Sacamos ese modo (se puede seguir
    copiando texto con clic derecho en la barra de título > Editar > Marcar).
    """
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        entrada = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        modo = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(entrada, ctypes.byref(modo)):
            return  # no es una consola (por ejemplo, salida redirigida)
        seleccion_rapida, banderas_extendidas = 0x0040, 0x0080
        kernel32.SetConsoleMode(entrada, (modo.value | banderas_extendidas) & ~seleccion_rapida)
    except Exception:
        pass


class OcultarAvisosNormales(logging.Filter):
    """Oculta avisos de la conexión que parecen errores pero son normales.

    Por ejemplo, justo después de vincular WhatsApp corta la conexión a propósito
    y la librería reconecta sola: eso deja un "Error sending close to websocket".
    Con nivel DEBUG se muestran igual.
    """

    TEXTOS = ("Error sending close to websocket",)

    def filter(self, registro: logging.LogRecord) -> bool:
        if logging.getLogger().level <= logging.DEBUG:
            return True
        mensaje = registro.getMessage()
        return not any(texto in mensaje for texto in self.TEXTOS)


def configurar_logs(config: Config) -> None:
    formato = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    config.carpeta_logs.mkdir(parents=True, exist_ok=True)
    archivo = RotatingFileHandler(
        config.carpeta_logs / "licha-bot.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    consola = logging.StreamHandler(sys.stdout)
    raiz = logging.getLogger()
    for manejador in list(raiz.handlers):  # neonize configura su propio log al importarse
        raiz.removeHandler(manejador)
    for manejador in (consola, archivo):
        manejador.setFormatter(formato)
        manejador.addFilter(OcultarAvisosNormales())
        raiz.addHandler(manejador)
    raiz.setLevel(config.nivel_log)

    # Nivel de los mensajes de la conexión con WhatsApp (también define lo que manda el núcleo en Go).
    from neonize.utils import log as log_neonize

    log_neonize.setLevel(config.nivel_log_whatsapp)
    for nombre in ("neonize", "whatsmeow", "Whatsmeow"):
        logging.getLogger(nombre).setLevel(config.nivel_log_whatsapp)


def main() -> int:
    preparar_consola()
    try:
        config = cargar_config()
    except ErrorConfig as exc:
        print(f"\nError en la configuración: {exc}\n", file=sys.stderr)
        return 1

    # Se importa acá porque carga la librería de WhatsApp (tarda un poco).
    from licha_bot.bot import LichaBot
    from licha_bot.comandos import REGISTRO, cargar_comandos

    configurar_logs(config)
    log.info("Iniciando %s v%s (Python %s)", config.nombre, __version__, sys.version.split()[0])

    fallidos = cargar_comandos()
    nombres = ", ".join(c.nombre for c in REGISTRO.todos())
    log.info("Comandos cargados (%d): %s", len(REGISTRO.todos()), nombres or "ninguno")
    if fallidos:
        log.warning("Estos archivos de comandos tienen errores y no se cargaron: %s", ", ".join(fallidos))

    bot = LichaBot(config)
    try:
        return asyncio.run(bot.ejecutar())
    except KeyboardInterrupt:
        log.info("Bot detenido.")
        return 0


if __name__ == "__main__":
    codigo = main()
    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    # os._exit en vez de sys.exit: la librería de WhatsApp deja hilos nativos
    # que pueden demorar varios minutos el cierre normal de Python.
    os._exit(codigo)
